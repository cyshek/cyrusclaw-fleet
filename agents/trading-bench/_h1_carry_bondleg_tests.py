#!/usr/bin/env python3
"""
H1 CROSS-ASSET CARRY — BOND-CURVE-CARRY LEG (feasibility / kill-test, NOT a promotion).

Hypothesis (from reports/LITERATURE_HYPOTHESES_20260623T185057Z.md §2 H1 + §5 sketch):
  Hold a slow, monthly duration tilt toward long-duration Treasuries (TLT / IEF) SCALED by
  curve steepness (T10Y2Y / T10Y3M). Steeper curve => more roll-down => bigger long-duration
  tilt; flat/inverted => sit in SHY (cash-like). Vol-target the leg to a modest annual budget.
  This is the "carry / roll-down" premium — non-directional, anti-momentum, the leg we never trade.

This is a DIVERSIFIER-SLEEVE feasibility study. Bar is modest (OOS Sharpe > 0.5), and the WHOLE
point is the controls: it must beat (a) a no-signal EW hold of the same instruments AND (b) a
static always-long-duration vol-targeted hold (does the TIMING add over just being long duration?),
net of cost, out-of-sample — or the "carry timing" is a mirage / duration beta in disguise.

MANDATORY measurement hygiene (banked from BAB + FUNDAMENTALS-PIT closes, and MEMORY.md):
  - adjclose ONLY (TLT/IEF distribute+split heavily; raw close is garbage).
  - 1-day signal lag: signal computed on data STRICTLY <= month-end, then TRADED forward with a
    1-trading-day lag. Non-negotiable.
  - Full continuous-span Sharpe = (mean/std)*sqrt(252), sample std ddof=1 — NEVER median-of-windows.
    (Mirrors runner/fp_sharpe.py sharpe_from_returns exactly.)
  - Monotonic cost grid 0/1/2/5 bps round-trip + breakeven.
  - Real OOS walk-forward (IS<=2018 / OOS 2019+) + stress windows (2008/2020/2022) reported separately.
  - No-signal EW control + static-duration control = the decisive cheap kills.
  - Lookahead canary: a deliberately-cheating variant that peeks ~1mo-FORWARD curve slope; honest
    path Sharpe MUST differ from cheat path (identical => leakage).

SELF-CONTAINED: imports nothing from runner/ EXCEPT fred_cache (per task). PROTECTED dirs untouched.
Run: python3 _h1_carry_bondleg_tests.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from bisect import bisect_right
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

WORKSPACE = Path(__file__).resolve().parent
YH = WORKSPACE / "data_cache" / "yahoo"
sys.path.insert(0, str(WORKSPACE / "runner"))
import fred_cache as fc  # noqa: E402  (ONLY runner import allowed)

TRADING_DAYS = 252.0
SQRT_252 = math.sqrt(TRADING_DAYS)

# ---------------------------------------------------------------------------
# Data loading (adjclose only)
# ---------------------------------------------------------------------------

def load_adjclose(ticker: str) -> Tuple[List[str], List[float]]:
    """Return (dates[], adjclose[]) oldest-first for a cached Yahoo parsed JSON."""
    rows = json.loads((YH / f"{ticker}_parsed.json").read_text())
    rows = [r for r in rows if r.get("adjclose") is not None]
    rows.sort(key=lambda r: r["date"])
    dates = [r["date"][:10] for r in rows]
    px = [float(r["adjclose"]) for r in rows]
    return dates, px


def load_fred(series_id: str, start: str, end: str) -> Tuple[List[str], List[float]]:
    """[(date,value)] -> (dates[], values[]) oldest-first, missing dropped."""
    vv = fc.get_values(series_id, start, end, vintage="latest", drop_missing=True)
    vv.sort(key=lambda t: t[0])
    return [d[:10] for d, _ in vv], [float(v) for _, v in vv]


# ---------------------------------------------------------------------------
# Aligned daily panel on a common calendar (intersection of all price series)
# ---------------------------------------------------------------------------

class Panel:
    """Daily aligned panel of adjclose for a set of tickers + as-of FRED lookups."""

    def __init__(self, tickers: Sequence[str]):
        per: Dict[str, Dict[str, float]] = {}
        common: Optional[set] = None
        for t in tickers:
            d, p = load_adjclose(t)
            m = dict(zip(d, p))
            per[t] = m
            s = set(d)
            common = s if common is None else (common & s)
        self.tickers = list(tickers)
        self.dates = sorted(common)  # type: ignore[arg-type]
        self.px: Dict[str, List[float]] = {t: [per[t][dt] for dt in self.dates] for t in tickers}
        self.idx: Dict[str, int] = {dt: i for i, dt in enumerate(self.dates)}
        # daily simple returns per ticker (index i = return from i-1 -> i; ret[0]=0)
        self.ret: Dict[str, List[float]] = {}
        for t in tickers:
            p = self.px[t]
            r = [0.0]
            for i in range(1, len(p)):
                r.append(p[i] / p[i - 1] - 1.0 if p[i - 1] else 0.0)
            self.ret[t] = r

    def __len__(self):
        return len(self.dates)


class AsOfSeries:
    """A daily FRED series queried PIT: latest observation with date <= as-of."""

    def __init__(self, series_id: str, start: str, end: str):
        self.dates, self.values = load_fred(series_id, start, end)

    def asof(self, d: str) -> Optional[float]:
        i = bisect_right(self.dates, d) - 1  # last obs with date <= d
        return self.values[i] if i >= 0 else None

    def future(self, d: str, days_ahead_dates: List[str], k_idx: int) -> Optional[float]:
        """For the lookahead canary ONLY: value as-of a date ~1mo forward."""
        if k_idx >= len(days_ahead_dates):
            k_idx = len(days_ahead_dates) - 1
        return self.asof(days_ahead_dates[k_idx])


# ---------------------------------------------------------------------------
# Month-end rebalance schedule (last trading day of each calendar month)
# ---------------------------------------------------------------------------

def month_end_indices(dates: List[str]) -> List[int]:
    """Indices of the last trading day in each (year, month)."""
    out: List[int] = []
    for i in range(len(dates)):
        ym = dates[i][:7]
        is_last = (i == len(dates) - 1) or (dates[i + 1][:7] != ym)
        if is_last:
            out.append(i)
    return out


# ---------------------------------------------------------------------------
# Sharpe / metrics (mirror runner/fp_sharpe.py exactly)
# ---------------------------------------------------------------------------

def sharpe(returns: Sequence[float], bpy: float = TRADING_DAYS) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(bpy)


def cagr(returns: Sequence[float]) -> float:
    if not returns:
        return 0.0
    eq = 1.0
    for r in returns:
        eq *= (1.0 + r)
    yrs = len(returns) / TRADING_DAYS
    if yrs <= 0 or eq <= 0:
        return 0.0
    return eq ** (1.0 / yrs) - 1.0


def total_return(returns: Sequence[float]) -> float:
    eq = 1.0
    for r in returns:
        eq *= (1.0 + r)
    return eq - 1.0


def max_drawdown(returns: Sequence[float]) -> float:
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        eq *= (1.0 + r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)
    return mdd


def ann_vol(returns: Sequence[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return math.sqrt(var) * SQRT_252


def realized_vol_ann(daily_rets: List[float], end_i: int, lookback: int) -> Optional[float]:
    """Annualized realized vol of a daily return series over (end_i-lookback, end_i], data<=end_i."""
    lo = max(1, end_i - lookback + 1)
    seg = daily_rets[lo:end_i + 1]
    if len(seg) < max(5, lookback // 2):
        return None
    n = len(seg)
    mean = sum(seg) / n
    var = sum((r - mean) ** 2 for r in seg) / (n - 1)
    if var <= 0:
        return None
    return math.sqrt(var) * SQRT_252


def corr(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a = a[:n]; b = b[:n]
    ma = sum(a) / n; mb = sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


# ---------------------------------------------------------------------------
# THE STRATEGY: monthly duration tilt scaled by curve steepness, vol-targeted, 1-day lag.
# ---------------------------------------------------------------------------

def build_target_weights(
    panel: Panel,
    slope: AsOfSeries,
    me_idx: List[int],
    *,
    long_sleeve: str = "TLT",            # "TLT" or "TLTIEF" (50/50)
    scale: float = 1.5,                  # steepness (pct pts) that maps to full duration weight
    vol_target: float = 0.09,            # annual vol budget for the LEG
    vol_lookback: int = 20,
    cheat_forward: bool = False,         # lookahead canary: peek ~1mo-fwd slope
    cheat_months_fwd: int = 1,
) -> Dict[int, Dict[str, float]]:
    """Return {rebalance_month_end_index : {ticker: weight}}.

    Weight logic at each month-end T (signal uses data with date <= dates[T]):
      steep = slope.asof(dates[T])  (clip negative -> 0)
      w_dur = clip(steep / scale, 0, 1)              # duration weight (long-duration sleeve)
      remainder (1 - w_dur) -> SHY (cash-like short-duration anchor)
      Then vol-target the WHOLE leg: scale gross by (vol_target / realized_vol_of_leg),
        cap leverage at 1.0 (no leverage — diversifier sleeve).
    The dict is keyed by the month-end index; the BACKTEST applies a 1-trading-day lag
    (positions effective at T+1) so nothing is traded on the signal bar itself.
    """
    dates = panel.dates
    weights: Dict[int, Dict[str, float]] = {}

    if long_sleeve == "TLT":
        dur_legs = {"TLT": 1.0}
    elif long_sleeve == "TLTIEF":
        dur_legs = {"TLT": 0.5, "IEF": 0.5}
    else:
        raise ValueError(long_sleeve)

    for T in me_idx:
        d = dates[T]
        if cheat_forward:
            # peek at the slope ~cheat_months_fwd month-ends into the FUTURE (leakage on purpose)
            pos = me_idx.index(T)
            fwd_pos = min(pos + cheat_months_fwd, len(me_idx) - 1)
            steep = slope.asof(dates[me_idx[fwd_pos]])
        else:
            steep = slope.asof(d)
        if steep is None:
            continue
        steep_pos = max(0.0, steep)  # inverted/flat -> 0 duration tilt
        w_dur = min(1.0, steep_pos / scale)

        # raw (pre-vol-target) leg weights
        raw: Dict[str, float] = {}
        for leg, frac in dur_legs.items():
            raw[leg] = w_dur * frac
        raw["SHY"] = max(0.0, 1.0 - w_dur)

        # realized vol of the RAW leg (data <= T), then scale toward vol_target
        leg_daily = _portfolio_daily_returns(panel, raw)
        rv = realized_vol_ann(leg_daily, T, vol_lookback)
        if rv is None or rv <= 1e-9:
            scaler = 1.0
        else:
            scaler = min(1.0, vol_target / rv)  # cap at 1.0 -> never lever

        weights[T] = {t: w * scaler for t, w in raw.items()}
    return weights


def _portfolio_daily_returns(panel: Panel, static_w: Dict[str, float]) -> List[float]:
    """Daily returns of a FIXED-weight portfolio over the whole panel (for vol estimation)."""
    n = len(panel.dates)
    out = [0.0] * n
    for i in range(n):
        s = 0.0
        for t, w in static_w.items():
            s += w * panel.ret[t][i]
        out[i] = s
    return out


# ---------------------------------------------------------------------------
# Backtest: apply target weights with 1-day lag, daily mark, monthly turnover cost.
# ---------------------------------------------------------------------------

def backtest_weights(
    panel: Panel,
    rebal_weights: Dict[int, Dict[str, float]],
    *,
    cost_bps_roundtrip: float = 2.0,
    lag_days: int = 1,
    start_i: int = 0,
) -> Tuple[List[float], List[str], float, int]:
    """
    Returns (daily_net_returns, daily_dates, avg_turnover_per_rebal, n_rebals).

    Mechanics (anti-lookahead):
      - rebal_weights[T] is computed from data <= dates[T] (signal/month-end).
      - Those weights become EFFECTIVE at T+lag_days (trade with a 1-day lag).
      - Between effective dates, weights are held constant (daily marked on adjclose returns).
      - Cost = cost_bps * sum(|w_new - w_old|) charged on the effective (trade) day.
        cost_bps here is round-trip per unit traded notional: we use
        (cost_bps/1e4) * turnover where turnover = 0.5*sum|dw|*2 = sum|dw| (one-way notional moved
        on each side); to stay conservative+monotone we charge (cost_bps/1e4)*sum|dw|.
    """
    dates = panel.dates
    n = len(dates)
    tickers = panel.tickers

    # Build the schedule of (effective_index, weights), lagged.
    me_sorted = sorted(rebal_weights.keys())
    sched: List[Tuple[int, Dict[str, float]]] = []
    for T in me_sorted:
        eff = T + lag_days
        if eff >= n:
            continue
        sched.append((eff, rebal_weights[T]))
    sched.sort(key=lambda x: x[0])

    # Walk daily from the first effective date.
    if not sched:
        return [], [], 0.0, 0
    first_eff = sched[0][0]
    bt_start = max(start_i, first_eff)

    cur_w: Dict[str, float] = {t: 0.0 for t in tickers}
    sched_ptr = 0
    daily_net: List[float] = []
    daily_dates: List[str] = []
    turnovers: List[float] = []

    for i in range(bt_start, n):
        # (1) mark today's PnL using YESTERDAY's held weights (positions set on prior days)
        gross = 0.0
        for t, w in cur_w.items():
            if w != 0.0:
                gross += w * panel.ret[t][i]
        cost_today = 0.0

        # (2) if today is an effective rebalance date, trade to the new weights AT today's close
        #     (cost charged today; new weights earn starting tomorrow). This is conservative:
        #     we do not let the freshly-traded weights capture today's already-realized return.
        while sched_ptr < len(sched) and sched[sched_ptr][0] == i:
            new_w_raw = sched[sched_ptr][1]
            new_w = {t: float(new_w_raw.get(t, 0.0)) for t in tickers}
            dw = sum(abs(new_w[t] - cur_w.get(t, 0.0)) for t in tickers)
            cost_today += (cost_bps_roundtrip / 1e4) * dw
            turnovers.append(dw)
            cur_w = new_w
            sched_ptr += 1

        daily_net.append(gross - cost_today)
        daily_dates.append(dates[i])

    avg_turn = (sum(turnovers) / len(turnovers)) if turnovers else 0.0
    return daily_net, daily_dates, avg_turn, len(turnovers)


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def control_ew(panel: Panel, me_idx: List[int], legs: Sequence[str]) -> Dict[int, Dict[str, float]]:
    """No-signal control: fixed equal-weight hold of the SAME instruments, rebalanced monthly."""
    w = {t: 1.0 / len(legs) for t in legs}
    return {T: dict(w) for T in me_idx}


def control_static_duration(
    panel: Panel, me_idx: List[int], *, long_sleeve: str = "TLT",
    vol_target: float = 0.09, vol_lookback: int = 20,
) -> Dict[int, Dict[str, float]]:
    """Static always-long-duration, vol-targeted (NO steepness timing). Does timing add over this?"""
    if long_sleeve == "TLT":
        dur_legs = {"TLT": 1.0}
    elif long_sleeve == "TLTIEF":
        dur_legs = {"TLT": 0.5, "IEF": 0.5}
    else:
        raise ValueError(long_sleeve)
    out: Dict[int, Dict[str, float]] = {}
    for T in me_idx:
        leg_daily = _portfolio_daily_returns(panel, dur_legs)
        rv = realized_vol_ann(leg_daily, T, vol_lookback)
        scaler = 1.0 if (rv is None or rv <= 1e-9) else min(1.0, vol_target / rv)
        # remainder in SHY so it's risk-comparable cash-anchored, same as the signal leg structure
        w = {t: f * scaler for t, f in dur_legs.items()}
        w["SHY"] = max(0.0, 1.0 - scaler)
        out[T] = w
    return out


# ---------------------------------------------------------------------------
# Metric bundle + window slicing
# ---------------------------------------------------------------------------

def metrics(daily_net: List[float], daily_dates: List[str]) -> Dict[str, float]:
    return {
        "sharpe": round(sharpe(daily_net), 4),
        "cagr": round(cagr(daily_net), 4),
        "total_return": round(total_return(daily_net), 4),
        "max_drawdown": round(max_drawdown(daily_net), 4),
        "ann_vol": round(ann_vol(daily_net), 4),
        "n_days": len(daily_net),
        "start": daily_dates[0] if daily_dates else None,
        "end": daily_dates[-1] if daily_dates else None,
    }


def slice_window(daily_net: List[float], daily_dates: List[str], lo: str, hi: str) -> Tuple[List[float], List[str]]:
    r, d = [], []
    for x, dt in zip(daily_net, daily_dates):
        if lo <= dt <= hi:
            r.append(x); d.append(dt)
    return r, d


def monthly_returns(daily_net: List[float], daily_dates: List[str]) -> Tuple[List[str], List[float]]:
    """Compound daily -> monthly returns keyed by YYYY-MM (for orthogonality corr)."""
    out_keys: List[str] = []
    out_vals: List[float] = []
    cur_ym = None
    eq = 1.0
    for r, d in zip(daily_net, daily_dates):
        ym = d[:7]
        if cur_ym is None:
            cur_ym = ym
        if ym != cur_ym:
            out_keys.append(cur_ym); out_vals.append(eq - 1.0)
            eq = 1.0; cur_ym = ym
        eq *= (1.0 + r)
    if cur_ym is not None:
        out_keys.append(cur_ym); out_vals.append(eq - 1.0)
    return out_keys, out_vals


def aligned_monthly_corr(
    a_keys: List[str], a_vals: List[float], b_keys: List[str], b_vals: List[float]
) -> float:
    bm = dict(zip(b_keys, b_vals))
    xa, xb = [], []
    for k, v in zip(a_keys, a_vals):
        if k in bm:
            xa.append(v); xb.append(bm[k])
    return round(corr(xa, xb), 4)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

OOS_SPLIT = "2018-12-31"  # IS <= 2018, OOS 2019+
STRESS = {
    "2008_GFC": ("2008-01-01", "2009-06-30"),
    "2020_covid": ("2020-02-01", "2020-06-30"),
    "2022_rateshock": ("2022-01-01", "2022-12-31"),
    "2013_tapertantrum": ("2013-05-01", "2013-09-30"),
}


def run_one(
    panel: Panel,
    slope: AsOfSeries,
    me_idx: List[int],
    *,
    long_sleeve: str,
    scale: float,
    vol_target: float,
    vol_lookback: int,
    cost_bps: float,
) -> Dict[str, object]:
    """Build signal weights, backtest, return full+IS+OOS metric bundle + turnover/rebals."""
    w = build_target_weights(
        panel, slope, me_idx,
        long_sleeve=long_sleeve, scale=scale, vol_target=vol_target, vol_lookback=vol_lookback,
    )
    daily, dd, turn, nreb = backtest_weights(panel, w, cost_bps_roundtrip=cost_bps)
    full = metrics(daily, dd)
    is_r, is_d = slice_window(daily, dd, "1900-01-01", OOS_SPLIT)
    oos_r, oos_d = slice_window(daily, dd, _next_day(OOS_SPLIT), "2999-12-31")
    return {
        "config": {
            "long_sleeve": long_sleeve, "scale": scale, "vol_target": vol_target,
            "vol_lookback": vol_lookback, "cost_bps": cost_bps, "slope_series": slope_id_of(slope),
        },
        "full": full,
        "is": metrics(is_r, is_d),
        "oos": metrics(oos_r, oos_d),
        "avg_turnover_per_rebal": round(turn, 4),
        "n_rebals": nreb,
        "_daily": daily, "_dates": dd,  # retained for downstream corr/stress; stripped before JSON
    }


def _next_day(d: str) -> str:
    y, m, dd = map(int, d.split("-"))
    dt = date(y, m, dd)
    nxt = dt.toordinal() + 1
    return date.fromordinal(nxt).isoformat()


_SLOPE_IDS: Dict[int, str] = {}
def slope_id_of(s: AsOfSeries) -> str:
    return _SLOPE_IDS.get(id(s), "?")


def strip_series(d: Dict[str, object]) -> Dict[str, object]:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def main() -> None:
    stamp = os.environ.get("UTCSTAMP") or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    print(f"[H1 carry bond-leg] UTC stamp = {stamp}")

    # ---- Load aligned panel (TLT/IEF/SHY) + SPY/TQQQ for orthogonality ----
    panel = Panel(["TLT", "IEF", "SHY"])
    print(f"[panel] {len(panel)} aligned days {panel.dates[0]} -> {panel.dates[-1]}")
    me_idx = month_end_indices(panel.dates)
    print(f"[panel] {len(me_idx)} month-end rebalances")

    start_d = panel.dates[0]
    end_d = panel.dates[-1]
    slope_2y = AsOfSeries("T10Y2Y", "1990-01-01", end_d)
    slope_3m = AsOfSeries("T10Y3M", "1990-01-01", end_d)
    _SLOPE_IDS[id(slope_2y)] = "T10Y2Y"
    _SLOPE_IDS[id(slope_3m)] = "T10Y3M"
    print(f"[fred] T10Y2Y {len(slope_2y.dates)} obs, T10Y3M {len(slope_3m.dates)} obs")

    # SPY / TQQQ monthly returns for orthogonality (aligned to the bond-leg traded path).
    spy_panel = Panel(["SPY"])
    tqqq_panel = Panel(["TQQQ"])
    spy_daily = spy_panel.ret["SPY"]
    spy_dates = spy_panel.dates
    spy_mk, spy_mv = monthly_returns(spy_daily[1:], spy_dates[1:])
    tqqq_mk, tqqq_mv = monthly_returns(tqqq_panel.ret["TQQQ"][1:], tqqq_panel.dates[1:])

    # ===================================================================
    # PRIMARY config (economically-motivated default, NOT tuned):
    #   T10Y2Y steepness, TLT-only long-duration sleeve, scale=1.5pp -> full tilt,
    #   9% annual vol target, 20d realized vol, 2 bps round-trip.
    # ===================================================================
    PRIM = dict(long_sleeve="TLT", scale=1.5, vol_target=0.09, vol_lookback=20)
    primary = run_one(panel, slope_2y, me_idx, cost_bps=2.0, **PRIM)
    print(f"[primary] FULL Sharpe {primary['full']['sharpe']}  OOS Sharpe {primary['oos']['sharpe']}  "
          f"OOS tot {primary['oos']['total_return']}  turn {primary['avg_turnover_per_rebal']}")

    # ---- Controls on the SAME path/cost ----
    ew_w = control_ew(panel, me_idx, ["TLT", "IEF", "SHY"])
    ew_daily, ew_dd, ew_turn, ew_nreb = backtest_weights(panel, ew_w, cost_bps_roundtrip=2.0)
    ew_full = metrics(ew_daily, ew_dd)
    ew_oos_r, ew_oos_d = slice_window(ew_daily, ew_dd, _next_day(OOS_SPLIT), "2999-12-31")
    ew_oos = metrics(ew_oos_r, ew_oos_d)

    stat_w = control_static_duration(panel, me_idx, long_sleeve="TLT", vol_target=0.09, vol_lookback=20)
    stat_daily, stat_dd, stat_turn, stat_nreb = backtest_weights(panel, stat_w, cost_bps_roundtrip=2.0)
    stat_full = metrics(stat_daily, stat_dd)
    stat_oos_r, stat_oos_d = slice_window(stat_daily, stat_dd, _next_day(OOS_SPLIT), "2999-12-31")
    stat_oos = metrics(stat_oos_r, stat_oos_d)

    print(f"[control EW]     FULL {ew_full['sharpe']}  OOS {ew_oos['sharpe']}  OOS tot {ew_oos['total_return']}")
    print(f"[control STATIC] FULL {stat_full['sharpe']}  OOS {stat_oos['sharpe']}  OOS tot {stat_oos['total_return']}")

    sig_oos = primary["oos"]
    delta_ew_oos = round(sig_oos["sharpe"] - ew_oos["sharpe"], 4)
    delta_static_oos = round(sig_oos["sharpe"] - stat_oos["sharpe"], 4)
    delta_ew_oos_tot = round(sig_oos["total_return"] - ew_oos["total_return"], 4)
    delta_static_oos_tot = round(sig_oos["total_return"] - stat_oos["total_return"], 4)

    # ---- Lookahead canary: honest vs forward-peeking slope ----
    cheat_w = build_target_weights(panel, slope_2y, me_idx, cheat_forward=True, cheat_months_fwd=1, **PRIM)
    cheat_daily, cheat_dd, _, _ = backtest_weights(panel, cheat_w, cost_bps_roundtrip=2.0)
    cheat_full = metrics(cheat_daily, cheat_dd)
    honest_sh = primary["full"]["sharpe"]
    cheat_sh = cheat_full["sharpe"]
    canary_differs = abs(honest_sh - cheat_sh) > 1e-6
    print(f"[canary] honest FULL Sharpe {honest_sh}  cheat(+1mo) {cheat_sh}  differ={canary_differs}")

    # ---- Cost grid (monotonic) on the primary signal ----
    cost_grid = []
    for c in [0.0, 1.0, 2.0, 5.0]:
        r = run_one(panel, slope_2y, me_idx, cost_bps=c, **PRIM)
        cost_grid.append({"cost_bps": c, "full_sharpe": r["full"]["sharpe"],
                          "oos_sharpe": r["oos"]["sharpe"], "full_total": r["full"]["total_return"]})
    # breakeven: vs EW control on OOS total return (does signal still add at higher cost?)
    print("[cost grid]", cost_grid)

    # ---- Robustness sweep (report FULL spread; knife-edge = fail) ----
    sweep = []
    for sl in ["T10Y2Y", "T10Y3M"]:
        slope = slope_2y if sl == "T10Y2Y" else slope_3m
        for long_sleeve in ["TLT", "TLTIEF"]:
            for scale in [1.0, 1.5, 2.0]:
                for vt in [0.08, 0.10]:
                    r = run_one(panel, slope, me_idx, long_sleeve=long_sleeve, scale=scale,
                                vol_target=vt, vol_lookback=20, cost_bps=2.0)
                    sweep.append({
                        "slope": sl, "long_sleeve": long_sleeve, "scale": scale, "vol_target": vt,
                        "full_sharpe": r["full"]["sharpe"], "oos_sharpe": r["oos"]["sharpe"],
                        "oos_total": r["oos"]["total_return"], "full_maxdd": r["full"]["max_drawdown"],
                        "turn": r["avg_turnover_per_rebal"],
                    })
    oos_sharpes = [s["oos_sharpe"] for s in sweep]
    sweep_stats = {
        "n": len(sweep),
        "oos_sharpe_min": round(min(oos_sharpes), 4),
        "oos_sharpe_max": round(max(oos_sharpes), 4),
        "oos_sharpe_median": round(sorted(oos_sharpes)[len(oos_sharpes) // 2], 4),
        "n_oos_above_0.5": sum(1 for x in oos_sharpes if x > 0.5),
        "frac_oos_above_0.5": round(sum(1 for x in oos_sharpes if x > 0.5) / len(oos_sharpes), 3),
    }
    print("[sweep stats]", sweep_stats)

    # ---- Stress windows (primary signal vs EW vs static), total return ----
    stress_table = {}
    for name, (lo, hi) in STRESS.items():
        s_r, s_d = slice_window(primary["_daily"], primary["_dates"], lo, hi)
        e_r, _ = slice_window(ew_daily, ew_dd, lo, hi)
        t_r, _ = slice_window(stat_daily, stat_dd, lo, hi)
        stress_table[name] = {
            "window": [lo, hi],
            "n_days": len(s_r),
            "signal_total": round(total_return(s_r), 4),
            "signal_sharpe": round(sharpe(s_r), 4),
            "ew_total": round(total_return(e_r), 4),
            "static_total": round(total_return(t_r), 4),
        }
    print("[stress]", json.dumps(stress_table, indent=0))

    # ---- Orthogonality: corr of signal-leg MONTHLY returns to SPY & TQQQ ----
    sig_mk, sig_mv = monthly_returns(primary["_daily"], primary["_dates"])
    corr_spy = aligned_monthly_corr(sig_mk, sig_mv, spy_mk, spy_mv)
    corr_tqqq = aligned_monthly_corr(sig_mk, sig_mv, tqqq_mk, tqqq_mv)
    # also corr of EW + static controls to SPY for context
    ew_mk, ew_mv = monthly_returns(ew_daily, ew_dd)
    stat_mk, stat_mv = monthly_returns(stat_daily, stat_dd)
    ew_corr_spy = aligned_monthly_corr(ew_mk, ew_mv, spy_mk, spy_mv)
    stat_corr_spy = aligned_monthly_corr(stat_mk, stat_mv, spy_mk, spy_mv)
    print(f"[orthogonality] signal corr->SPY {corr_spy}  corr->TQQQ {corr_tqqq}  "
          f"(EW corr->SPY {ew_corr_spy}, static corr->SPY {stat_corr_spy})")

    # ===================================================================
    # VERDICT
    # ===================================================================
    c1 = sig_oos["sharpe"] > 0.5
    c2 = delta_ew_oos > 0 and delta_ew_oos_tot > 0
    c3 = delta_static_oos > 0 and delta_static_oos_tot > 0
    c4 = (abs(corr_tqqq) < 0.5 and abs(corr_spy) < 0.5) and (sig_oos["total_return"] > 0 and sig_oos["sharpe"] > 0)
    overall_pass = bool(c1 and c2 and c3 and c4)

    verdict = {
        "overall_PASS": overall_pass,
        "c1_oos_sharpe_gt_0.5": {"pass": bool(c1), "oos_sharpe": sig_oos["sharpe"], "bar": 0.5},
        "c2_beats_EW_control_oos": {
            "pass": bool(c2), "delta_sharpe": delta_ew_oos, "delta_total": delta_ew_oos_tot,
            "signal_oos_sharpe": sig_oos["sharpe"], "ew_oos_sharpe": ew_oos["sharpe"],
        },
        "c3_beats_static_duration_oos": {
            "pass": bool(c3), "delta_sharpe": delta_static_oos, "delta_total": delta_static_oos_tot,
            "signal_oos_sharpe": sig_oos["sharpe"], "static_oos_sharpe": stat_oos["sharpe"],
        },
        "c4_low_book_corr_and_positive": {
            "pass": bool(c4), "corr_spy": corr_spy, "corr_tqqq": corr_tqqq,
            "oos_total": sig_oos["total_return"], "oos_sharpe": sig_oos["sharpe"],
        },
    }
    print("\n========== VERDICT ==========")
    print(json.dumps(verdict, indent=2))
    print("=============================\n")

    # ---- Assemble machine-readable result ----
    result = {
        "meta": {
            "utc_stamp": stamp,
            "hypothesis": "H1 cross-asset carry — bond-curve-carry leg",
            "source_spec": "reports/LITERATURE_HYPOTHESES_20260623T185057Z.md (§2 H1 + §5)",
            "instruments": ["TLT", "IEF", "SHY"],
            "slope_series": ["T10Y2Y", "T10Y3M"],
            "panel_span": [panel.dates[0], panel.dates[-1]],
            "n_aligned_days": len(panel),
            "n_month_end_rebals": len(me_idx),
            "oos_split": OOS_SPLIT,
            "sharpe_convention": "(mean/std)*sqrt(252), ddof=1, continuous-span (mirrors runner/fp_sharpe.py)",
            "signal_lag_days": 1,
            "adjclose_only": True,
            "primary_config": primary["config"],
        },
        "series_stats": {
            "primary_signal": strip_series(primary),
            "control_ew": {"full": ew_full, "oos": ew_oos, "avg_turnover_per_rebal": round(ew_turn, 4),
                           "n_rebals": ew_nreb, "corr_spy": ew_corr_spy},
            "control_static_duration": {"full": stat_full, "oos": stat_oos,
                                        "avg_turnover_per_rebal": round(stat_turn, 4),
                                        "n_rebals": stat_nreb, "corr_spy": stat_corr_spy},
        },
        "cost_analysis": {"grid": cost_grid,
                          "note": "monthly rebal on liquid bond ETFs; cost not expected to be the killer"},
        "lookahead_canary": {
            "honest_full_sharpe": honest_sh, "cheat_forward_full_sharpe": cheat_sh,
            "paths_differ": bool(canary_differs),
            "interpretation": "honest != cheat => no leakage (cheat peeks +1mo-forward slope)",
        },
        "controls": {
            "ew": {"oos_sharpe": ew_oos["sharpe"], "oos_total": ew_oos["total_return"],
                   "delta_signal_minus_ew_oos_sharpe": delta_ew_oos,
                   "delta_signal_minus_ew_oos_total": delta_ew_oos_tot},
            "static_duration": {"oos_sharpe": stat_oos["sharpe"], "oos_total": stat_oos["total_return"],
                                "delta_signal_minus_static_oos_sharpe": delta_static_oos,
                                "delta_signal_minus_static_oos_total": delta_static_oos_tot},
        },
        "robustness_sweep": {"stats": sweep_stats, "grid": sweep},
        "orthogonality": {"corr_spy": corr_spy, "corr_tqqq": corr_tqqq,
                          "ew_corr_spy": ew_corr_spy, "static_corr_spy": stat_corr_spy},
        "stress_windows": stress_table,
        "verdict": verdict,
    }

    out_json = WORKSPACE / "reports" / "_h1_carry_bondleg_result.json"
    out_json.write_text(json.dumps(result, indent=2))
    print(f"[written] {out_json}")
    print(f"[OVERALL] {'PASS' if overall_pass else 'CLOSE'}  "
          f"(c1={c1} c2={c2} c3={c3} c4={c4})")


if __name__ == "__main__":
    main()
