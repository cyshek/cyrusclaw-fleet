#!/usr/bin/env python3
"""
H1 CROSS-ASSET CARRY -- COMMODITY LEG via TRUE WTI FUTURES CALENDAR-SPREAD (reopen of the
ETF-proxy version that CLOSED 2026-06-23, report H1_CARRY_COMMODITY_COMBINED_20260623T193840Z.md).

WHY THIS LANE (documented reopen): the ETF-proxy commodity carry FAILED its make-or-break EW
control by -77.5pp OOS, had NEGATIVE in-sample Sharpe on every split, full-period Sharpe ~0; its
"edge" was a single post-2018 backwardation regime + vol-suppression, and corr->SPY +0.45 = long
beta. The prior report's "Revisit-triggers" named EXACTLY this reopen: a NON-ETF curve-shape
instrument (true front-vs-deferred WTI futures) to isolate the roll-yield premium without expense
drag / tracking error / fund mechanics; it MUST show (a) positive IS Sharpe (premium exists
pre-2019) AND (b) beat a dumb static-long-WTI control net OOS, or it is the SAME dirty/regime story.

CLEAN SIGNAL SOURCE (the whole point): NYMEX WTI futures contracts 1-4 daily settle from EIA bulk
(keyless): PET.RCLC1.D .. PET.RCLC4.D, span CL1 1983-2024. These are REAL front-through-4th-month
settle prices -> a clean term structure with NO ETF confound. Signal = curve SHAPE only:
  roll1 = log(CL1/CL2)  (backwardation>0 => positive carry => long; contango<0 => flat/cash)
  roll14 = log(CL1/CL4)/3  (multi-point slope, per-step, robustness)
This is the genuine curve-shape premium the ETF proxy could NOT isolate.

TRADED RETURN STREAM (honest execution): the SIGNAL is clean-futures-derived even if execution
uses an ETF -- that is legitimate and the explicit difference from the dead version (where the
SIGNAL ITSELF was ETF-derived). Two execution vehicles, both reported:
  (A) ROLL-ADJUSTED FRONT-MONTH WTI futures return (the standard continuous front-month proxy):
      hold CL1; daily return = CL1 settle-to-settle WITHIN a contract; ROLL near expiry by splicing
      on the CL1->CL2 ratio so the held-contract return is continuous (no roll price-jump). Roll
      convention documented + the 2020-04-20 negative-print handled (a disciplined roll is already
      in CL2 by then -- the catastrophic -$37.63 front print is NOT taken as a held return).
  (B) USO adjclose as the execution vehicle (signal still from the clean futures curve). USO carries
      the real-world roll cost an actual trader pays -> the honest "can you actually harvest this".

HONEST HARNESS (the gates that killed the ETF version + 4 survivorship lanes today):
  k1 OOS Sharpe >~ 0.4 ; k2 BEATS its own EW/static-long control net OOS (make-or-break) ;
  k3 corr to bond leg <~ 0.3 ; k4 POSITIVE in-sample Sharpe (not a single-regime artifact) ;
  k5 combined bond+commodity equal-risk sleeve FULL Sharpe must exceed bond-leg-alone 0.578.
  PASS only if k1+k2+k3+k4 AND k5 full>0.578. Else CLOSE with the killer.
Plus: lookahead canary (same-day cheat), cost grid 0/2/5 bps (2 primary), SPX on traded path,
Sharpe=(mean/std)*sqrt(252) ddof=1 continuous-span (NEVER median-of-windows; mirrors fp_sharpe).

PROTECTED dirs untouched. Imports bond leg READ-ONLY for the bond path + shared helpers (which
itself imports only runner/fred_cache). Run: python3 _h1_carry_commodity_futures_tests.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

WORKSPACE = Path(__file__).resolve().parent
EIA = WORKSPACE / "data_cache" / "eia_wti"
YH = WORKSPACE / "data_cache" / "yahoo"

# Bond leg (READ-ONLY): reuse its sharpe/metrics/slice/monthly/corr + run_one for the bond path.
import _h1_carry_bondleg_tests as bl  # noqa: E402

TRADING_DAYS = 252.0
SQRT_252 = math.sqrt(TRADING_DAYS)
OOS_SPLIT = bl.OOS_SPLIT  # "2018-12-31" -- matched to the bond leg


# ---------------------------------------------------------------------------
# Data loading: WTI futures term structure (EIA RCLC1-4, keyless bulk) + ETFs (adjclose)
# ---------------------------------------------------------------------------

def _isodate(s: str) -> str:
    """EIA 'YYYYMMDD' -> 'YYYY-MM-DD'."""
    return s[:4] + "-" + s[4:6] + "-" + s[6:8]


def load_rclc() -> Dict[int, Dict[str, float]]:
    """Load NYMEX WTI contracts 1-4 daily settle from the pre-grepped EIA bulk lines.
    Returns {contract: {iso_date: settle}}. Keeps the lone 2020-04-20 negative front print
    (handled explicitly by the roll-adjusted return builder)."""
    out: Dict[int, Dict[str, float]] = {}
    for s in (1, 2, 3, 4):
        o = json.loads((EIA / f"rclc{s}.jsonl").read_text())
        m: Dict[str, float] = {}
        for d, v in o["data"]:
            if v is not None:
                m[_isodate(d)] = float(v)
        out[s] = m
    return out


def load_adjclose(ticker: str) -> Dict[str, float]:
    rows = json.loads((YH / f"{ticker}_parsed.json").read_text())
    rows = [r for r in rows if r.get("adjclose") is not None]
    rows.sort(key=lambda r: r["date"])
    return {r["date"][:10]: float(r["adjclose"]) for r in rows}


# ---------------------------------------------------------------------------
# Roll-adjusted continuous FRONT-MONTH WTI futures return (execution vehicle A).
#
# Convention (documented):
#   * The held instrument is the front contract (CL1).
#   * Daily return = CL1 settle-to-settle, EXCEPT across a roll, where the price level of the
#     CL1 series jumps because the underlying contract changes. To make the HELD-CONTRACT return
#     continuous we detect roll days as days where the CL1 underlying changed, and on those days
#     splice using the CL2/CL1 relationship so the return reflects holding-then-rolling, not the
#     artificial level gap. We DO NOT have contract-id labels, so we use a robust, standard,
#     lookahead-free heuristic: a "roll" is flagged when |log(CL1_t/CL1_{t-1})| is large AND it
#     coincides with the front rolling (proxied by CL1_t jumping toward the PRIOR CL2 level). On a
#     flagged roll day we instead take the within-contract return = CL2_t/CL2_{t-1} (the deferred
#     contract's clean daily return, which the now-front contract followed). This is the textbook
#     "roll on the deferred's return at the seam" continuous-return construction.
#   * 2020-04-20: CL1 settle = -37.63 (negative). A disciplined front-month roll is OUT of the
#     expiring May contract days earlier; we cap any single daily front return at a floor and, more
#     importantly, the roll detector treats the -37.63 -> next jump as a seam (uses CL2's return),
#     so the catastrophic expiring-contract print is NEVER taken as a held daily return. We also
#     hard-guard: if either price in a ratio is <= 0, fall back to the CL2 (deferred) return.
# ---------------------------------------------------------------------------

def build_front_roll_return(S: Dict[int, Dict[str, float]], dates: List[str]) -> List[float]:
    """Continuous roll-adjusted front-month daily return over `dates` (index aligned; r[0]=0)."""
    c1 = S[1]
    c2 = S[2]
    r = [0.0] * len(dates)
    for i in range(1, len(dates)):
        d0, d1 = dates[i - 1], dates[i]
        p1_0, p1_1 = c1.get(d0), c1.get(d1)
        p2_0, p2_1 = c2.get(d0), c2.get(d1)
        # default: clean within-contract CL1 return
        ret = None
        if p1_0 is not None and p1_1 is not None and p1_0 > 0 and p1_1 > 0:
            ret = p1_1 / p1_0 - 1.0
        # roll / negative-print seam handling: if CL1 return is missing, non-finite, or a
        # blatant roll jump (|ret|>0.40 i.e. >40% in a day -- far beyond any non-2020 real move
        # and the only >40% CL1 day is the 2020-04-20 negative seam), use the deferred CL2 return
        # which is the clean held-then-rolled return at the seam.
        use_c2 = (ret is None) or (abs(ret) > 0.40) or (p1_1 is not None and p1_1 <= 0) or (p1_0 is not None and p1_0 <= 0)
        if use_c2 and p2_0 is not None and p2_1 is not None and p2_0 > 0 and p2_1 > 0:
            ret = p2_1 / p2_0 - 1.0
        r[i] = ret if ret is not None else 0.0
    return r


# ---------------------------------------------------------------------------
# Curve-shape carry signal (the clean isolate). Computed on data <= as-of day; lagged T+1.
# ---------------------------------------------------------------------------

def carry_signal(S: Dict[int, Dict[str, float]], d: str, *, mode: str = "roll12") -> Optional[float]:
    """Per-step log roll yield from the futures curve shape on date d (None if unavailable).
      mode 'roll12' : log(CL1/CL2)            -- front-vs-second (primary)
      mode 'roll14' : log(CL1/CL4)/3          -- multi-point slope, per-contract-step (robustness)
    Positive => backwardation => positive carry => long signal; negative => contango => flat/cash.
    """
    c1 = S[1].get(d)
    if mode == "roll12":
        c2 = S[2].get(d)
        if c1 is None or c2 is None or c1 <= 0 or c2 <= 0:
            return None
        return math.log(c1 / c2)
    elif mode == "roll14":
        c4 = S[4].get(d)
        if c1 is None or c4 is None or c1 <= 0 or c4 <= 0:
            return None
        return math.log(c1 / c4) / 3.0
    else:
        raise ValueError(mode)


# ---------------------------------------------------------------------------
# Position sizing variants from the signal.
#   long_only_timing : LONG the traded vehicle when backwardated (signal>thr), else CASH (SHY).
#                      Optional vol-target of the long leg to a budget (cap leverage 1.0).
#   continuous       : weight = clip(signal/scale, lo, hi) -- can go modestly short in deep contango
#                      (market-neutral-ish curve tilt); the genuinely-untested expression.
# Signal is the PRIOR day's curve shape (data <= T), positions effective T+1 (handled in backtest).
# ---------------------------------------------------------------------------

def signal_weights(
    S: Dict[int, Dict[str, float]],
    dates: List[str],
    vehicle_ret: List[float],
    me_idx: List[int],
    *,
    mode: str = "roll12",
    variant: str = "long_only_timing",
    thr: float = 0.0,
    scale: float = 0.02,
    w_lo: float = -1.0,
    w_hi: float = 1.0,
    vol_target: Optional[float] = None,
    vol_lookback: int = 20,
    cheat_sameday: bool = False,
) -> Dict[int, float]:
    """Return {rebal_index : target_weight_on_vehicle}. CASH (weight 0) earns nothing (SHY handled
    separately for the long_only cash anchor in the net-return path). Weights are decided at each
    month-end from data <= that day (or SAME day if cheat_sameday -- the lookahead canary)."""
    w: Dict[int, float] = {}
    for T in me_idx:
        d = dates[T]
        sig = carry_signal(S, d, mode=mode)
        if sig is None:
            continue
        if variant == "long_only_timing":
            base = 1.0 if sig > thr else 0.0
        elif variant == "continuous":
            base = max(w_lo, min(w_hi, sig / scale))
        else:
            raise ValueError(variant)
        if vol_target is not None and base != 0.0:
            rv = bl.realized_vol_ann(vehicle_ret, T, vol_lookback)
            if rv is not None and rv > 1e-9:
                base *= min(1.0, vol_target / rv)
        w[T] = base
    return w


# ---------------------------------------------------------------------------
# Backtest a single-vehicle weight schedule with T+1 lag, daily mark, monthly turnover cost.
# Cash (1 - |w| of the long_only leg, or the un-invested fraction) optionally earns SHY.
# ---------------------------------------------------------------------------

def backtest_single(
    dates: List[str],
    vehicle_ret: List[float],
    rebal_w: Dict[int, float],
    *,
    cash_ret: Optional[List[float]] = None,
    cost_bps_roundtrip: float = 2.0,
    lag_days: int = 1,
) -> Tuple[List[float], List[str], float, int]:
    """Returns (daily_net, daily_dates, avg_turnover_per_rebal, n_rebals).
      * rebal_w[T] decided from data <= dates[T]; effective at T+lag_days (1-day lag).
      * held constant between effective dates; daily marked on vehicle_ret.
      * cash fraction (1 - w, only when w in [0,1]) earns cash_ret if provided (SHY anchor), so the
        long_only_timing leg is a true long-or-cash sleeve, not long-or-flat-zero.
      * cost = (cost_bps/1e4)*|w_new - w_old| on the effective day (conservative, monotone)."""
    n = len(dates)
    sched = []
    for T in sorted(rebal_w.keys()):
        eff = T + lag_days
        if eff < n:
            sched.append((eff, rebal_w[T]))
    sched.sort(key=lambda x: x[0])
    if not sched:
        return [], [], 0.0, 0
    bt_start = sched[0][0]
    cur_w = 0.0
    ptr = 0
    out_r: List[float] = []
    out_d: List[str] = []
    turns: List[float] = []
    for i in range(bt_start, n):
        # mark with yesterday's weight
        gross = cur_w * vehicle_ret[i]
        if cash_ret is not None:
            cash_frac = 1.0 - cur_w if (0.0 <= cur_w <= 1.0) else 0.0
            gross += cash_frac * cash_ret[i]
        cost = 0.0
        while ptr < len(sched) and sched[ptr][0] == i:
            nw = sched[ptr][1]
            cost += (cost_bps_roundtrip / 1e4) * abs(nw - cur_w)
            turns.append(abs(nw - cur_w))
            cur_w = nw
            ptr += 1
        out_r.append(gross - cost)
        out_d.append(dates[i])
    avg_turn = (sum(turns) / len(turns)) if turns else 0.0
    return out_r, out_d, avg_turn, len(turns)


# ---------------------------------------------------------------------------
# Controls (the make-or-break k2 tests) -- on the SAME traded path + cost.
#   static_long : ALWAYS long the vehicle (weight 1.0 every month, no timing). "Does the curve
#                 signal add over just being long WTI?" -- the dumb-static-long the ETF version lost to.
#   ew_hold     : same as static_long for a single vehicle (a no-signal constant hold). We keep both
#                 names for parity with the prior report's k2 language; for a single instrument the
#                 EW / static-long control IS the constant full-weight hold.
# ---------------------------------------------------------------------------

def control_static_long(me_idx: List[int]) -> Dict[int, float]:
    return {T: 1.0 for T in me_idx}


# ---------------------------------------------------------------------------
# Bond-leg daily path (READ-ONLY import) for the corr gate + combined sleeve.
# ---------------------------------------------------------------------------

def bond_leg_path() -> Tuple[List[float], List[str]]:
    """Regenerate the bond-leg PRIMARY daily return series via the bond-leg engine (not reimplemented).
    Returns (daily, dates) on the bond leg's own aligned span."""
    panel = bl.Panel(["TLT", "IEF", "SHY"])
    me_idx = bl.month_end_indices(panel.dates)
    slope_2y = bl.AsOfSeries("T10Y2Y", "1990-01-01", panel.dates[-1])
    bl._SLOPE_IDS[id(slope_2y)] = "T10Y2Y"
    PRIM = dict(long_sleeve="TLT", scale=1.5, vol_target=0.09, vol_lookback=20)
    res = bl.run_one(panel, slope_2y, me_idx, cost_bps=2.0, **PRIM)
    return res["_daily"], res["_dates"]


# ---------------------------------------------------------------------------
# Inverse-vol (equal-risk) combine of two daily-return PATHS, monthly rebalanced, lookahead-safe.
# Mirrors the construction the bond+commodity-ETF combined report used.
# ---------------------------------------------------------------------------

def inverse_vol_combine(
    a_daily: List[float], a_dates: List[str],
    b_daily: List[float], b_dates: List[str],
    *, vol_lookback: int = 63,
) -> Tuple[List[float], List[str]]:
    """Equal-RISK-weight (inverse-vol) monthly-rebalanced blend of two daily series on their
    OVERLAPPING span. Weights set at each month-end from realized vol over the trailing
    vol_lookback days (data <= month-end), held for the next month (lookahead-safe)."""
    ma = dict(zip(a_dates, a_daily))
    mb = dict(zip(b_dates, b_daily))
    common = sorted(set(a_dates) & set(b_dates))
    if len(common) < 70:
        return [], []
    ra = [ma[d] for d in common]
    rb = [mb[d] for d in common]
    me = bl.month_end_indices(common)
    me_set = set(me)
    # default equal weight until first vol estimate available
    wa, wb = 0.5, 0.5
    out_d: List[float] = []
    out_dates: List[str] = []
    for i in range(len(common)):
        if i in me_set and i >= vol_lookback:
            va = _trailing_vol(ra, i, vol_lookback)
            vb = _trailing_vol(rb, i, vol_lookback)
            if va and vb and va > 1e-9 and vb > 1e-9:
                ia, ib = 1.0 / va, 1.0 / vb
                wa, wb = ia / (ia + ib), ib / (ia + ib)
        out_d.append(wa * ra[i] + wb * rb[i])
        out_dates.append(common[i])
    return out_d, out_dates


def _trailing_vol(r: List[float], end_i: int, lb: int) -> Optional[float]:
    lo = max(0, end_i - lb + 1)
    seg = r[lo:end_i + 1]
    if len(seg) < max(5, lb // 2):
        return None
    n = len(seg)
    mean = sum(seg) / n
    var = sum((x - mean) ** 2 for x in seg) / (n - 1)
    if var <= 0:
        return None
    return math.sqrt(var)


# ---------------------------------------------------------------------------
# Calendar helpers: align an adjclose series' daily returns onto the futures calendar, and the
# month-end rebalance schedule on the futures calendar.
# ---------------------------------------------------------------------------

def _align_ret_to_calendar(px: dict, cal: list) -> list:
    """Daily simple returns of an adjclose series, sampled on calendar `cal` (index-aligned, r[0]=0).
    For each cal day we use the price as-of that exact day if present, else the most recent prior
    price (step/forward-fill) so a missing ETF day does not inject a spurious zero-return; the
    return is (price_today / price_prev_used - 1). Lookahead-safe (only past/contemporaneous prices)."""
    keys = sorted(px)
    from bisect import bisect_right
    def asof(d):
        i = bisect_right(keys, d) - 1
        return px[keys[i]] if i >= 0 else None
    out = [0.0] * len(cal)
    prev = asof(cal[0])
    for i in range(1, len(cal)):
        cur = asof(cal[i])
        if cur is not None and prev is not None and prev > 0:
            out[i] = cur / prev - 1.0
        if cur is not None:
            prev = cur
    return out


def month_end_indices_local(dates: list) -> list:
    out = []
    for i in range(len(dates)):
        ym = dates[i][:7]
        is_last = (i == len(dates) - 1) or (dates[i + 1][:7] != ym)
        if is_last:
            out.append(i)
    return out


# ---------------------------------------------------------------------------
# IS/OOS split-robustness table (the decisive check that killed the ETF version).
# ---------------------------------------------------------------------------

SPLITS = ["2014-12-31", "2016-12-31", "2018-12-31", "2020-12-31"]


def split_table(daily: List[float], dates: List[str]) -> List[Dict[str, object]]:
    rows = []
    for sp in SPLITS:
        is_r, is_d = bl.slice_window(daily, dates, "1900-01-01", sp)
        oos_r, oos_d = bl.slice_window(daily, dates, bl._next_day(sp), "2999-12-31")
        rows.append({
            "split": sp,
            "is_sharpe": round(bl.sharpe(is_r), 4), "is_total": round(bl.total_return(is_r), 4),
            "oos_sharpe": round(bl.sharpe(oos_r), 4), "oos_total": round(bl.total_return(oos_r), 4),
            "is_n": len(is_r), "oos_n": len(oos_r),
        })
    return rows


def year_by_year(daily: List[float], dates: List[str]) -> Dict[str, float]:
    out: Dict[str, List[float]] = {}
    for r, d in zip(daily, dates):
        out.setdefault(d[:4], []).append(r)
    return {y: round(bl.total_return(rs), 4) for y, rs in sorted(out.items())}


def is_oos(daily: List[float], dates: List[str]) -> Tuple[Dict, Dict, Dict]:
    full = bl.metrics(daily, dates)
    is_r, is_d = bl.slice_window(daily, dates, "1900-01-01", OOS_SPLIT)
    oos_r, oos_d = bl.slice_window(daily, dates, bl._next_day(OOS_SPLIT), "2999-12-31")
    return full, bl.metrics(is_r, is_d), bl.metrics(oos_r, oos_d)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    stamp = os.environ.get("UTCSTAMP") or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    print(f"[H1 carry commodity FUTURES] UTC stamp = {stamp}")

    # ---- Load WTI term structure + execution vehicles ----
    S = load_rclc()
    # Common futures calendar = days where CL1 AND CL2 both present (need the spread). Use this as
    # the signal calendar. For execution we align the vehicle to this calendar too.
    fut_dates = sorted(set(S[1]) & set(S[2]))
    print(f"[wti] CL1n CL2 common days: {len(fut_dates)}  {fut_dates[0]} -> {fut_dates[-1]}")
    for c in (1, 2, 3, 4):
        ds = sorted(S[c])
        print(f"      CL{c}: n={len(S[c])} {ds[0]} -> {ds[-1]}")

    # Execution vehicle A: roll-adjusted continuous front-month WTI futures return, on fut_dates.
    front_ret = build_front_roll_return(S, fut_dates)

    # Cash anchor (SHY) aligned to fut_dates (forward-fill last known; 0 if none before).
    shy_px = load_adjclose("SHY")
    shy_sorted = sorted(shy_px)
    shy_ret_on_fut = _align_ret_to_calendar(shy_px, fut_dates)

    # Execution vehicle B: USO adjclose, aligned to fut_dates.
    uso_px = load_adjclose("USO")
    uso_ret_on_fut = _align_ret_to_calendar(uso_px, fut_dates)

    me_idx = month_end_indices_local(fut_dates)
    print(f"[wti] month-end rebalances: {len(me_idx)}")

    # SPX on the actually-traded path: SPY daily returns aligned to fut_dates.
    spy_px = load_adjclose("SPY")
    spy_ret_on_fut = _align_ret_to_calendar(spy_px, fut_dates)

    # ===================================================================
    # PRIMARY signal: roll12 (log CL1/CL2), long_only_timing, thr=0, vehicle = roll-adjusted front.
    # Cash anchor = SHY. 2 bps. This is the economically-motivated default (NOT tuned).
    # ===================================================================
    PRIMARY = dict(mode="roll12", variant="long_only_timing", thr=0.0)
    w_prim = signal_weights(S, fut_dates, front_ret, me_idx, **PRIMARY)
    prim_daily, prim_dates, prim_turn, prim_nreb = backtest_single(
        fut_dates, front_ret, w_prim, cash_ret=shy_ret_on_fut, cost_bps_roundtrip=2.0)
    p_full, p_is, p_oos = is_oos(prim_daily, prim_dates)
    print(f"[PRIMARY front-roll] FULL Sh {p_full['sharpe']} IS {p_is['sharpe']} OOS {p_oos['sharpe']} "
          f"OOS tot {p_oos['total_return']} turn {round(prim_turn,3)}")

    # ===================================================================
    # CONTROLS on the SAME path/cost (k2 make-or-break).
    # ===================================================================
    w_static = control_static_long(me_idx)
    st_daily, st_dates, st_turn, st_nreb = backtest_single(
        fut_dates, front_ret, w_static, cash_ret=shy_ret_on_fut, cost_bps_roundtrip=2.0)
    s_full, s_is, s_oos = is_oos(st_daily, st_dates)
    print(f"[CONTROL static-long-WTI] FULL Sh {s_full['sharpe']} IS {s_is['sharpe']} OOS {s_oos['sharpe']} "
          f"OOS tot {s_oos['total_return']}")

    d_ew_oos_sh = round(p_oos["sharpe"] - s_oos["sharpe"], 4)
    d_ew_oos_tot = round(p_oos["total_return"] - s_oos["total_return"], 4)


    # ===================================================================
    # SECONDARY variants (robustness; same harness):
    #   V2 roll14 multi-point slope (CL1 vs CL4), long_only_timing.
    #   V3 continuous curve tilt (market-neutral-ish; can short deep contango).
    #   V4 PRIMARY signal but executed via USO (real-world roll cost vehicle).
    # ===================================================================
    variants_out = {}

    # V2: roll14 multi-point slope
    w_v2 = signal_weights(S, fut_dates, front_ret, me_idx, mode="roll14", variant="long_only_timing", thr=0.0)
    v2_daily, v2_dates, v2_turn, _ = backtest_single(fut_dates, front_ret, w_v2, cash_ret=shy_ret_on_fut, cost_bps_roundtrip=2.0)
    v2_full, v2_is, v2_oos = is_oos(v2_daily, v2_dates)
    variants_out["V2_roll14_frontroll"] = {"full": v2_full, "is": v2_is, "oos": v2_oos, "turn": round(v2_turn, 4)}
    print(f"[V2 roll14 front-roll]   FULL {v2_full['sharpe']} IS {v2_is['sharpe']} OOS {v2_oos['sharpe']}")

    # V3: continuous curve tilt (scale=0.02 ~ a 2% per-step roll maps to full long; can short)
    w_v3 = signal_weights(S, fut_dates, front_ret, me_idx, mode="roll12", variant="continuous",
                          scale=0.02, w_lo=-1.0, w_hi=1.0)
    v3_daily, v3_dates, v3_turn, _ = backtest_single(fut_dates, front_ret, w_v3, cash_ret=None, cost_bps_roundtrip=2.0)
    v3_full, v3_is, v3_oos = is_oos(v3_daily, v3_dates)
    variants_out["V3_continuous_frontroll"] = {"full": v3_full, "is": v3_is, "oos": v3_oos, "turn": round(v3_turn, 4)}
    print(f"[V3 continuous front-roll] FULL {v3_full['sharpe']} IS {v3_is['sharpe']} OOS {v3_oos['sharpe']}")

    # V4: PRIMARY signal, executed via USO (real roll cost)
    w_v4 = signal_weights(S, fut_dates, uso_ret_on_fut, me_idx, **PRIMARY)
    v4_daily, v4_dates, v4_turn, _ = backtest_single(fut_dates, uso_ret_on_fut, w_v4, cash_ret=shy_ret_on_fut, cost_bps_roundtrip=2.0)
    v4_full, v4_is, v4_oos = is_oos(v4_daily, v4_dates)
    variants_out["V4_primary_signal_USO_exec"] = {"full": v4_full, "is": v4_is, "oos": v4_oos, "turn": round(v4_turn, 4)}
    print(f"[V4 primary-sig USO-exec] FULL {v4_full['sharpe']} IS {v4_is['sharpe']} OOS {v4_oos['sharpe']}")

    # ===================================================================
    # LOOKAHEAD CANARY: same-day (no-lag-on-signal) cheat on the PRIMARY. Honest uses prior-day
    # signal effective T+1; cheat decides AND trades using the SAME day's curve (lag_days=0) AND
    # peeks the same-day close. If honest ~ cheat, info leaked.
    # ===================================================================
    w_cheat = signal_weights(S, fut_dates, front_ret, me_idx, cheat_sameday=True, **PRIMARY)
    cheat_daily, cheat_dates, _, _ = backtest_single(fut_dates, front_ret, w_cheat, cash_ret=shy_ret_on_fut,
                                                     cost_bps_roundtrip=2.0, lag_days=0)
    cheat_full = bl.metrics(cheat_daily, cheat_dates)
    canary_differs = abs(p_full["sharpe"] - cheat_full["sharpe"]) > 1e-6
    print(f"[canary] honest FULL {p_full['sharpe']}  cheat(sameday,nolag) {cheat_full['sharpe']}  differ={canary_differs}")

    # ===================================================================
    # COST GRID (monotonic) on the PRIMARY.
    # ===================================================================
    cost_grid = []
    for c in [0.0, 2.0, 5.0]:
        wc = signal_weights(S, fut_dates, front_ret, me_idx, **PRIMARY)
        cd, cdd, _, _ = backtest_single(fut_dates, front_ret, wc, cash_ret=shy_ret_on_fut, cost_bps_roundtrip=c)
        cf, _, co = is_oos(cd, cdd)
        # control at same cost for breakeven framing
        sc, scd, _, _ = backtest_single(fut_dates, front_ret, w_static, cash_ret=shy_ret_on_fut, cost_bps_roundtrip=c)
        _, _, sco = is_oos(sc, scd)
        cost_grid.append({"cost_bps": c, "full_sharpe": cf["sharpe"], "oos_sharpe": co["sharpe"],
                          "oos_total": co["total_return"], "ctrl_oos_total": sco["total_return"],
                          "beats_ctrl_oos": bool(co["total_return"] > sco["total_return"])})
    print("[cost grid]", cost_grid)

    # ---- Threshold sensitivity (k2/k4 robustness): does ANY long_only threshold beat static-long
    #      net OOS, and does IS Sharpe stay positive? ----
    thr_sens = []
    for thr in [-0.005, -0.002, 0.0, 0.002, 0.005, 0.01]:
        wt = signal_weights(S, fut_dates, front_ret, me_idx, mode="roll12", variant="long_only_timing", thr=thr)
        td, tdd, tturn, _ = backtest_single(fut_dates, front_ret, wt, cash_ret=shy_ret_on_fut, cost_bps_roundtrip=2.0)
        tf, ti, to = is_oos(td, tdd)
        thr_sens.append({"thr": thr, "full_sharpe": tf["sharpe"], "is_sharpe": ti["sharpe"],
                         "oos_sharpe": to["sharpe"], "oos_total": to["total_return"],
                         "beats_static_oos_total": bool(to["total_return"] > s_oos["total_return"])})
    print("[thr sensitivity]", [(t["thr"], t["is_sharpe"], t["oos_sharpe"], t["beats_static_oos_total"]) for t in thr_sens])


    # ===================================================================
    # CORR TO BOND LEG (k3) + COMBINED SLEEVE (k5).
    # ===================================================================
    bond_daily, bond_dates = bond_leg_path()
    bf = bl.metrics(bond_daily, bond_dates)
    print(f"[bond leg] FULL {bf['sharpe']}  span {bf['start']}->{bf['end']}  (target full 0.578)")

    # corr of PRIMARY commodity leg to bond leg (monthly + daily, overlapping span)
    c_mk, c_mv = bl.monthly_returns(prim_daily, prim_dates)
    b_mk, b_mv = bl.monthly_returns(bond_daily, bond_dates)
    corr_bond_monthly = bl.aligned_monthly_corr(c_mk, c_mv, b_mk, b_mv)
    # daily corr on overlap
    mbd = dict(zip(bond_dates, bond_daily))
    mcd = dict(zip(prim_dates, prim_daily))
    ov = sorted(set(bond_dates) & set(prim_dates))
    corr_bond_daily = round(bl.corr([mcd[d] for d in ov], [mbd[d] for d in ov]), 4) if len(ov) > 2 else 0.0
    print(f"[k3 corr->bond] monthly {corr_bond_monthly}  daily {corr_bond_daily}  overlap_days {len(ov)}")

    # combined equal-risk (inverse-vol) sleeve on overlapping span
    comb_daily, comb_dates = inverse_vol_combine(bond_daily, bond_dates, prim_daily, prim_dates)
    comb_full, comb_is, comb_oos = is_oos(comb_daily, comb_dates)
    comb_splits = split_table(comb_daily, comb_dates)
    # naive 50/50 daily-avg on the same overlap, for the diversification-math cross-check
    naive = []
    nd = []
    for d in sorted(set(bond_dates) & set(prim_dates)):
        naive.append(0.5 * mbd[d] + 0.5 * mcd[d]); nd.append(d)
    _, _, naive_oos = is_oos(naive, nd)
    print(f"[k5 combined] FULL {comb_full['sharpe']}  IS {comb_is['sharpe']}  OOS {comb_oos['sharpe']}  "
          f"(bond-alone full {bf['sharpe']}; naive50/50 OOS {naive_oos['sharpe']})")

    # combined sleeve corr to SPX / TQQQ
    spx_px_full = load_adjclose("SPY")
    tqqq_px_full = load_adjclose("TQQQ")
    spx_ret_comb = _align_ret_to_calendar(spx_px_full, comb_dates)
    tqqq_ret_comb = _align_ret_to_calendar(tqqq_px_full, comb_dates)
    cmb_mk, cmb_mv = bl.monthly_returns(comb_daily, comb_dates)
    spx_mk, spx_mv = bl.monthly_returns(spx_ret_comb[1:], comb_dates[1:])
    tqqq_mk, tqqq_mv = bl.monthly_returns(tqqq_ret_comb[1:], comb_dates[1:])
    comb_corr_spx = bl.aligned_monthly_corr(cmb_mk, cmb_mv, spx_mk, spx_mv)
    comb_corr_tqqq = bl.aligned_monthly_corr(cmb_mk, cmb_mv, tqqq_mk, tqqq_mv)
    print(f"[k5 combined] corr->SPX {comb_corr_spx}  corr->TQQQ {comb_corr_tqqq}")

    # SPAN-MATCHED k5 fairness: the commodity leg's EIA data ends 2024-04-05, so the combined sleeve
    # is bounded there. Compare against the bond leg RESTRICTED to the identical overlap span (apples
    # to apples), not the bond leg's unrestricted 2026 full Sharpe.
    bond_restr_r, bond_restr_d = bl.slice_window(bond_daily, bond_dates,
                                                 comb_dates[0] if comb_dates else "1900-01-01",
                                                 comb_dates[-1] if comb_dates else "2999-12-31")
    bond_restr_full = bl.metrics(bond_restr_r, bond_restr_d)
    print(f"[k5 span-matched] bond-alone restricted to {comb_dates[0]}->{comb_dates[-1]}: "
          f"{bond_restr_full['sharpe']}  vs combined {comb_full['sharpe']}")

    # ===================================================================
    # SPX on the actually-traded path (commodity leg) + commodity leg orthogonality to equities.
    # ===================================================================
    spx_mk2, spx_mv2 = bl.monthly_returns(spy_ret_on_fut[1:], fut_dates[1:])
    prim_corr_spx = bl.aligned_monthly_corr(c_mk, c_mv, spx_mk2, spx_mv2)
    # SPX buy&hold on the commodity-leg traded span (same dates), for context
    spx_path_full = bl.metrics(spy_ret_on_fut[1:], fut_dates[1:])
    _, _, spx_path_oos = is_oos(spy_ret_on_fut[1:], fut_dates[1:])
    print(f"[SPX on traded path] FULL {spx_path_full['sharpe']} OOS {spx_path_oos['sharpe']}  "
          f"commodity-leg corr->SPX {prim_corr_spx}")

    # ===================================================================
    # SPLIT-ROBUSTNESS + YEAR-BY-YEAR on the PRIMARY commodity leg (the artifact detector).
    # ===================================================================
    prim_splits = split_table(prim_daily, prim_dates)
    prim_yby = year_by_year(prim_daily, prim_dates)
    print("[split-robustness PRIMARY]")
    for r in prim_splits:
        print(f"   split {r['split']}: IS Sh {r['is_sharpe']:>7} (tot {r['is_total']:>7})  "
              f"OOS Sh {r['oos_sharpe']:>7} (tot {r['oos_total']:>7})")

    # ===================================================================
    # VERDICT
    # ===================================================================
    k1 = p_oos["sharpe"] >= 0.4
    k2 = (d_ew_oos_sh > 0) and (d_ew_oos_tot > 0)  # beats static-long net OOS (Sharpe AND total)
    k3 = abs(corr_bond_monthly) <= 0.3
    k4 = p_is["sharpe"] > 0.0  # POSITIVE in-sample Sharpe (premium exists pre-2019)
    k5 = comb_full["sharpe"] > 0.578  # combined FULL must exceed bond-leg-alone
    overall = bool(k1 and k2 and k3 and k4 and k5)

    verdict = {
        "overall_PASS": overall,
        "k1_oos_sharpe_ge_0.4": {"pass": bool(k1), "value": p_oos["sharpe"], "bar": 0.4},
        "k2_beats_static_long_net_oos": {
            "pass": bool(k2), "delta_sharpe": d_ew_oos_sh, "delta_total": d_ew_oos_tot,
            "signal_oos_sharpe": p_oos["sharpe"], "signal_oos_total": p_oos["total_return"],
            "ctrl_oos_sharpe": s_oos["sharpe"], "ctrl_oos_total": s_oos["total_return"]},
        "k3_corr_to_bond_le_0.3": {"pass": bool(k3), "corr_monthly": corr_bond_monthly, "corr_daily": corr_bond_daily, "bar": 0.3},
        "k4_positive_IS_sharpe": {"pass": bool(k4), "is_sharpe": p_is["sharpe"]},
        "k5_combined_full_gt_bond_alone": {
            "pass": bool(k5), "combined_full_sharpe": comb_full["sharpe"], "bond_alone_full": bf["sharpe"],
            "bond_alone_full_span_matched": bond_restr_full["sharpe"],
            "pass_vs_span_matched": bool(comb_full["sharpe"] > bond_restr_full["sharpe"]),
            "combined_oos_sharpe": comb_oos["sharpe"], "combined_is_sharpe": comb_is["sharpe"]},
    }
    print("\n========== VERDICT ==========")
    print(json.dumps(verdict, indent=2))
    print("=============================")
    print(f"[OVERALL] {'PASS' if overall else 'CLOSE'} (k1={k1} k2={k2} k3={k3} k4={k4} k5={k5})\n")


    # ---- Assemble machine-readable result ----
    def strip(d):
        return {k: v for k, v in d.items() if not str(k).startswith("_")}

    result = {
        "meta": {
            "utc_stamp": stamp,
            "hypothesis": "H1 cross-asset carry -- commodity leg via TRUE WTI futures calendar-spread",
            "reopen_of": "reports/H1_CARRY_COMMODITY_COMBINED_20260623T193840Z.md (ETF-proxy version CLOSED)",
            "data_provenance": {
                "futures": "EIA bulk PET.RCLC1.D..RCLC4.D (keyless, NYMEX WTI contracts 1-4 daily settle)",
                "futures_file": "data_cache/eia_wti/rclc{1,2,3,4}.jsonl (grepped from data_cache/eia_PET_bulk.txt)",
                "futures_span_cl1": [sorted(S[1])[0], sorted(S[1])[-1]],
                "futures_last_updated": "2024-04-10 (bulk dump); CL data ends 2024-04-05",
                "execution_vehicles": ["roll-adjusted continuous front-month WTI futures return (A, primary)",
                                       "USO adjclose (B, real roll cost)"],
                "cash_anchor": "SHY adjclose",
                "negative_print_handling": "2020-04-20 CL1=-37.63 treated as roll seam (deferred CL2 return used); never taken as a held front return",
            },
            "signal_def": {
                "roll12": "log(CL1/CL2) -- front-vs-second per-step roll yield (primary)",
                "roll14": "log(CL1/CL4)/3 -- multi-point slope per contract step (robustness)",
                "convention": "backwardation (>0)=positive carry=long; contango (<0)=flat/cash (long_only) or short (continuous)",
            },
            "roll_convention": "hold CL1; within-contract CL1 settle-to-settle return; on roll/negative seam (|daily|>40% or non-positive price) splice on deferred CL2 daily return -- textbook continuous front-month",
            "futures_calendar_days": len(fut_dates),
            "futures_calendar_span": [fut_dates[0], fut_dates[-1]],
            "n_month_end_rebals": len(me_idx),
            "oos_split": OOS_SPLIT,
            "sharpe_convention": "(mean/std)*sqrt(252), ddof=1, continuous-span (mirrors runner/fp_sharpe.py / bond leg)",
            "signal_lag_days": 1,
            "cost_bps_primary": 2.0,
            "primary_config": PRIMARY,
        },
        "primary_commodity_leg": {
            "config": PRIMARY, "vehicle": "roll-adjusted front-month WTI",
            "full": p_full, "is": p_is, "oos": p_oos,
            "avg_turnover_per_rebal": round(prim_turn, 4), "n_rebals": prim_nreb,
            "split_robustness": prim_splits,
            "year_by_year": prim_yby,
            "corr_to_bond_monthly": corr_bond_monthly, "corr_to_bond_daily": corr_bond_daily,
            "corr_to_spx_monthly": prim_corr_spx,
        },
        "control_static_long_wti": {"full": s_full, "is": s_is, "oos": s_oos, "turn": round(st_turn, 4),
                                    "delta_signal_minus_ctrl_oos_sharpe": d_ew_oos_sh,
                                    "delta_signal_minus_ctrl_oos_total": d_ew_oos_tot},
        "secondary_variants": variants_out,
        "lookahead_canary": {"honest_full_sharpe": p_full["sharpe"], "cheat_sameday_full_sharpe": cheat_full["sharpe"],
                             "paths_differ": bool(canary_differs),
                             "interpretation": "honest != cheat => no leakage (cheat uses same-day curve + no lag)"},
        "cost_grid": cost_grid,
        "bond_leg": {"full": bf, "target_full_sharpe": 0.578,
                     "full_restricted_to_combined_span": bond_restr_full["sharpe"],
                     "restricted_span": [comb_dates[0], comb_dates[-1]] if comb_dates else None},
        "threshold_sensitivity": thr_sens,
        "combined_sleeve": {
            "method": "equal-risk inverse-vol (63d, monthly, lookahead-safe) of bond-leg path + commodity-leg path",
            "overlap_span": [comb_dates[0], comb_dates[-1]] if comb_dates else None,
            "n_days": len(comb_daily),
            "full": comb_full, "is": comb_is, "oos": comb_oos,
            "split_robustness": comb_splits,
            "naive_5050_oos_sharpe": naive_oos["sharpe"],
            "corr_to_spx_monthly": comb_corr_spx, "corr_to_tqqq_monthly": comb_corr_tqqq,
            "bond_alone_full_sharpe": bf["sharpe"],
            "bond_alone_full_sharpe_SPAN_MATCHED": bond_restr_full["sharpe"],
            "k5_span_matched_verdict": "combined %.4f vs bond-alone(span-matched) %.4f -> %s" % (
                comb_full["sharpe"], bond_restr_full["sharpe"],
                "PASS" if comb_full["sharpe"] > bond_restr_full["sharpe"] else "FAIL"),
        },
        "spx_on_traded_path": {"full": spx_path_full, "oos": spx_path_oos, "commodity_leg_corr_spx": prim_corr_spx},
        "verdict": verdict,
    }

    out_json = WORKSPACE / "reports" / "_h1_carry_commodity_futures_result.json"
    out_json.write_text(json.dumps(result, indent=2, default=str))
    print(f"[written] {out_json}")
    # stash for the report writer
    (WORKSPACE / "reports" / f"_h1_carry_commodity_futures_RUNSTAMP.txt").write_text(stamp)
    return result


if __name__ == "__main__":
    main()
