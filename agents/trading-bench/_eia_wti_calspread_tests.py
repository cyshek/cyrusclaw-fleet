#!/usr/bin/env python3
"""
EIA WTI FUTURES CALENDAR-SPREAD CARRY LEG — the clean, NON-ETF curve-shape instrument.

================================================================================
WHY THIS EXISTS (and why the prior version is DEAD)
================================================================================
The H1 commodity-carry COMMODITY LEG was CLOSED 2026-06-23 (report
reports/H1_CARRY_COMMODITY_COMBINED_20260623T193840Z.md). It used front-vs-deferred
*ETF* spreads (USO/USL/DBC/GSG) as the curve-shape proxy and died on the make-or-break
no-signal control: it LOST to a dumb EW hold of the very same ETFs by -77.5pp OOS (k2 FAIL)
and had a NEGATIVE in-sample Sharpe on every split (IS -0.44, full ~-0.01). The diagnosis:
the ETF spread conflates genuine roll-yield with expense-ratio drag / tracking error / fund
mechanics, and what edge remained was post-2018 long-commodity-beta, not a curve-shape premium.

The close report's explicit reopen trigger (§ "Revisit-triggers", line 221):
  "A non-ETF curve-shape instrument. ... A true futures-calendar-spread (front vs deferred WTI
   futures ...) would isolate the curve-shape premium cleanly. If that data became free/available,
   the carry signal could be re-tested without the dirty-proxy confound."
AND (line 222): "Any reopening must show a POSITIVE IS Sharpe (not just OOS)."

This file IS that reopen. The signal is derived from REAL NYMEX contract settlements (EIA RCLC1..4,
$/bbl), and the traded return is the FRONT-CONTRACT price change — a clean roll-timing /
calendar-spread construct, ZERO fund mechanics. The prior ETF logic is NOT reused.

================================================================================
DATA (EIA Cushing WTI Future Contracts 1-4, daily, $/bbl)
================================================================================
data_cache/eia_wti/RCLC{1..4}d.xls. Parse: pd.ExcelFile(f).parse('Data 1', skiprows=2)
-> col0=Date, col1=price. Inner-join all 4 -> 9,857 days 1985-01-02 -> 2024-04-05.
EIA STOPPED publishing NYMEX futures after 2024-04-05 -> the leg CANNOT be tested past then on
free data (honest OOS-truncation caveat; OOS = 2019-01-01 .. 2024-04-05).

CRITICAL DATA GOTCHA: 2020-04-20 CL1 settled NEGATIVE (-$37.63, the famous WTI-negative day).
A daily simple return computed across that print is meaningless (and slope=(CL1-CL4)/CL4=-2.32
that day is garbage). The signal RANKS ON PRIOR-MONTH-END (Apr-2020 month-end is 2020-04-30,
CL1=18.84 -> clean), so the negative day never enters the signal. But it WOULD poison the traded
daily return series, so the front-contract return is MASKED to 0 across the negative-print roll
window 2020-04-17..2020-04-21 (4 trading days) for ALL strategies AND ALL controls identically
(so no strategy gets an unfair edge from the mask). Documented + reported.

================================================================================
THE SIGNAL (calendar-spread carry — isolate curve shape, zero fund mechanics)
================================================================================
At each MONTH-END T (signal uses settlements with date <= dates[T], PIT-safe):
  slope_T = (CL1_T - CL4_T) / CL4_T          # front-to-back roll yield; >0 = backwardation
Backwardation (slope>0) = positive roll yield = go LONG crude exposure; contango (slope<0) = flat.
The traded RETURN is the FRONT-CONTRACT (CL1) daily simple return. Weights effective at T+1
(1-trading-day lag, non-negotiable), held constant intramonth, marked daily.

THREE mappings (all <=3 free params; primary chosen a priori, NOT tuned to the answer):
  - LONG/FLAT (primary): w = 1 if slope>thr else 0,   then vol-target the leg.
  - LONG/SHORT:          w = +1 if slope>thr else -1,  then vol-target the leg.
  - SCALED:              w = clip(slope/scale, lo, hi), then vol-target the leg.
PRIMARY = LONG/FLAT, thr=0, vol_target=12%/yr on 20d realized vol of CL1, cap leverage 1.0x.
(12% budget vs the bond leg's 9%: crude is ~5x more volatile than duration; 12% keeps the leg's
realized vol in a diversifier-sleeve range without forcing it to ~0 exposure. It is ONE param,
fixed before seeing results; a vol-target sensitivity sweep is reported.)

================================================================================
MANDATORY HONESTY HARNESS (this is what killed the ETF version)
================================================================================
1. EW / no-signal control (MAKE-OR-BREAK): static-always-long CL1 (vol-targeted, no timing) AND
   naive buy-&-hold CL1. The signal MUST beat the no-signal control OOS net of cost on BOTH total
   return AND Sharpe. If timing doesn't beat dumb static-long, it's beta not carry -> CLOSE.
2. POSITIVE IS Sharpe REQUIRED (hard gate per main + the reopen trigger). The ETF version had
   negative IS Sharpe on every split -> auto-fail. Reported on every split.
3. corr-to-bond-leg <=0.30 (abs): import _h1_carry_bondleg_tests, call bl.run_one(...) primary
   config to get the bond-leg daily net series; align monthly via bl.monthly_returns +
   bl.aligned_monthly_corr. Bond-leg ref: OOS Sharpe 0.4338, corr_spy -0.20, corr_tqqq -0.14.
4. Lookahead canary: a deliberate SAME-DAY (D0, no lag) cheat variant; honest D+1 version must
   NOT match the cheat. Both reported.
5. Cost grid: net at 2bps min (per round-trip on turnover); also 5bps + breakeven cost. Turnover
   reported.
6. IS/OOS split: OOS = post-2018 (OOS_SPLIT 2018-12-31, imported from the bond leg). OOS ends
   2024-04-05 (truncation). Also report a post-GFC (2009+) cut for context.
7. Reuse bond-leg primitives (metrics/sharpe/max_drawdown/monthly_returns/aligned_monthly_corr/
   total_return/cagr/ann_vol/corr/OOS_SPLIT) so numbers are comparable to the decimal.

VERDICT k1..k5 (mirror bond-leg verdict shape):
  k1: OOS Sharpe > 0.4 (reopen bar main set: "~0.4 Sharpe")
  k2: beats no-signal static-long control OOS (total + Sharpe) — MAKE OR BREAK
  k3: IS Sharpe POSITIVE on all/most splits
  k4: corr-to-bond-leg <=0.30
  k5 (go/no-go): ONLY if k1-k4 pass -> does adding this as a 3rd inverse-vol sleeve LIFT the
      allocator frontier vs the live 2-sleeve (TQQQ-voltarget + sector-rotation)? Else k5=N/A, CLOSE.

SELF-CONTAINED. Imports: pandas (xls parse), and _h1_carry_bondleg_tests (pure primitives +
bond-leg path for the corr gate; it imports only runner/fred_cache). The allocator-frontier
section (k5) lazily imports _allocator_blend_tests ONLY if k1-k4 pass (read-only path repro).
PROTECTED dirs (runner/*.py beyond fred_cache, strategies*/, cron, *.db, broker/clock/allocator)
are NOT written. Run: python3 _eia_wti_calspread_tests.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

WORKSPACE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE))

# Reuse the bond-leg engine's PURE primitives so numbers match to the decimal, AND its run_one
# to get the bond-leg daily net path for the corr-to-bond gate. (It imports only runner/fred_cache.)
import _h1_carry_bondleg_tests as bl  # noqa: E402

sharpe = bl.sharpe
metrics = bl.metrics
total_return = bl.total_return
cagr = bl.cagr
ann_vol = bl.ann_vol
max_drawdown = bl.max_drawdown
corr = bl.corr
monthly_returns = bl.monthly_returns
aligned_monthly_corr = bl.aligned_monthly_corr
OOS_SPLIT = bl.OOS_SPLIT  # "2018-12-31"
TRADING_DAYS = bl.TRADING_DAYS
SQRT_252 = bl.SQRT_252

EIA_DIR = WORKSPACE / "data_cache" / "eia_wti"

# The negative-print roll window: front-contract daily return is MASKED to 0 here (for the
# signal AND every control identically). 2020-04-20 is the -$37.63 print; we blank the days
# bracketing it so neither the crash-in nor the bounce-out enters any traded series.
NEG_PRINT_MASK = {"2020-04-17", "2020-04-20", "2020-04-21"}


# ---------------------------------------------------------------------------
# Data loading (real NYMEX settlements)
# ---------------------------------------------------------------------------

def load_contracts() -> pd.DataFrame:
    """Inner-join RCLC1..4 daily $/bbl on common calendar -> DataFrame[CL1..CL4], date index."""
    series = {}
    for n in (1, 2, 3, 4):
        f = EIA_DIR / f"RCLC{n}d.xls"
        df = pd.ExcelFile(f).parse("Data 1", skiprows=2)
        df.columns = ["Date", "px"]
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["px"] = pd.to_numeric(df["px"], errors="coerce")
        df = df.dropna().set_index("Date").sort_index()
        series[f"CL{n}"] = df["px"]
    panel = pd.DataFrame(series).dropna()
    panel = panel[["CL1", "CL2", "CL3", "CL4"]]
    return panel


class Panel:
    """Daily aligned WTI futures panel + front-contract masked daily returns + month-end schedule."""

    def __init__(self):
        df = load_contracts()
        self.dates: List[str] = [d.strftime("%Y-%m-%d") for d in df.index]
        self.idx: Dict[str, int] = {d: i for i, d in enumerate(self.dates)}
        self.CL1 = df["CL1"].tolist()
        self.CL2 = df["CL2"].tolist()
        self.CL3 = df["CL3"].tolist()
        self.CL4 = df["CL4"].tolist()
        # Front-contract daily simple return, MASKED across the negative-print window.
        n = len(self.dates)
        r = [0.0] * n
        for i in range(1, n):
            p0, p1 = self.CL1[i - 1], self.CL1[i]
            d = self.dates[i]
            if d in NEG_PRINT_MASK or self.dates[i - 1] in NEG_PRINT_MASK:
                r[i] = 0.0  # blank the crash-in and bounce-out; no strategy earns/loses here
            elif p0 > 0 and p1 > 0:
                r[i] = p1 / p0 - 1.0
            else:
                r[i] = 0.0  # any other non-positive print (none exist beyond the masked day) -> flat
        self.front_ret = r
        # Month-end indices (last trading day of each calendar month)
        self.me_idx: List[int] = []
        for i in range(n):
            ym = self.dates[i][:7]
            if i == n - 1 or self.dates[i + 1][:7] != ym:
                self.me_idx.append(i)

    def __len__(self):
        return len(self.dates)

    def slope_at(self, i: int) -> float:
        """(CL1 - CL4)/CL4 at index i (front-to-back roll yield)."""
        c4 = self.CL4[i]
        if c4 == 0:
            return 0.0
        return (self.CL1[i] - c4) / c4

    def realized_vol_front(self, end_i: int, lookback: int = 20) -> Optional[float]:
        """Annualized realized vol of the (masked) front-contract return over (end_i-lb, end_i]."""
        lo = max(1, end_i - lookback + 1)
        seg = self.front_ret[lo:end_i + 1]
        if len(seg) < max(5, lookback // 2):
            return None
        m = sum(seg) / len(seg)
        var = sum((x - m) ** 2 for x in seg) / (len(seg) - 1)
        if var <= 0:
            return None
        return math.sqrt(var) * SQRT_252


# ---------------------------------------------------------------------------
# Signal -> month-end target weight on the FRONT contract
# ---------------------------------------------------------------------------

def build_weights(
    panel: Panel,
    *,
    mapping: str = "long_flat",     # long_flat | long_short | scaled
    thr: float = 0.0,               # slope threshold (backwardation cutoff)
    scale: float = 0.05,            # for "scaled": slope that maps to full weight
    vol_target: float = 0.12,       # annual vol budget for the leg
    vol_lookback: int = 20,
    cheat_d0: bool = False,         # canary handled in backtest (lag=0); kept for symmetry
) -> Dict[int, float]:
    """Return {month_end_index: front-contract target weight} (pre-lag)."""
    weights: Dict[int, float] = {}
    for T in panel.me_idx:
        s = panel.slope_at(T)
        if mapping == "long_flat":
            raw = 1.0 if s > thr else 0.0
        elif mapping == "long_short":
            raw = 1.0 if s > thr else -1.0
        elif mapping == "scaled":
            raw = max(-1.0, min(1.0, (s - thr) / scale))
        else:
            raise ValueError(mapping)
        # vol-target the leg toward the budget (cap leverage at 1.0x -> never lever)
        rv = panel.realized_vol_front(T, vol_lookback)
        if rv is None or rv <= 1e-9:
            scaler = 1.0
        else:
            scaler = min(1.0, vol_target / rv)
        weights[T] = raw * scaler
    return weights


def static_long_weights(panel: Panel, *, vol_target: float = 0.12, vol_lookback: int = 20) -> Dict[int, float]:
    """No-signal control: ALWAYS long front contract, vol-targeted (same sizing, no timing)."""
    out: Dict[int, float] = {}
    for T in panel.me_idx:
        rv = panel.realized_vol_front(T, vol_lookback)
        scaler = 1.0 if (rv is None or rv <= 1e-9) else min(1.0, vol_target / rv)
        out[T] = 1.0 * scaler
    return out


def buyhold_weights(panel: Panel) -> Dict[int, float]:
    """Naive buy-&-hold: full long front contract, no vol target, no timing."""
    return {T: 1.0 for T in panel.me_idx}


# ---------------------------------------------------------------------------
# Backtest: apply month-end weights to the FRONT-contract return with 1-day lag + turnover cost
# ---------------------------------------------------------------------------

def backtest(
    panel: Panel,
    rebal_w: Dict[int, float],
    *,
    cost_bps_roundtrip: float = 2.0,
    lag_days: int = 1,
) -> Tuple[List[float], List[str], float, int]:
    """Returns (daily_net, daily_dates, avg_turnover_per_rebal, n_rebals).

    Anti-lookahead: rebal_w[T] computed from data<=dates[T]; effective at T+lag_days; held
    constant; marked on the (masked) front-contract daily return. Cost = (bps/1e4)*|dw| on the
    trade day. lag_days=0 is the D0 lookahead-canary cheat (trades on the signal bar itself).
    """
    dates = panel.dates
    n = len(dates)
    me_sorted = sorted(rebal_w.keys())
    sched: List[Tuple[int, float]] = []
    for T in me_sorted:
        eff = T + lag_days
        if eff < n:
            sched.append((eff, rebal_w[T]))
    sched.sort(key=lambda x: x[0])
    if not sched:
        return [], [], 0.0, 0
    bt_start = sched[0][0]

    cur_w = 0.0
    ptr = 0
    daily_net: List[float] = []
    daily_dates: List[str] = []
    turnovers: List[float] = []
    for i in range(bt_start, n):
        gross = cur_w * panel.front_ret[i]
        cost = 0.0
        while ptr < len(sched) and sched[ptr][0] == i:
            new_w = sched[ptr][1]
            dw = abs(new_w - cur_w)
            cost += (cost_bps_roundtrip / 1e4) * dw
            turnovers.append(dw)
            cur_w = new_w
            ptr += 1
        daily_net.append(gross - cost)
        daily_dates.append(dates[i])
    avg_turn = (sum(turnovers) / len(turnovers)) if turnovers else 0.0
    return daily_net, daily_dates, avg_turn, len(turnovers)


# ---------------------------------------------------------------------------
# Window slicing (mirror bond leg)
# ---------------------------------------------------------------------------

def slice_window(daily: List[float], dd: List[str], lo: str, hi: str) -> Tuple[List[float], List[str]]:
    r, d = [], []
    for x, dt in zip(daily, dd):
        if lo <= dt <= hi:
            r.append(x); d.append(dt)
    return r, d


def _next_day(d: str) -> str:
    y, m, dd = map(int, d.split("-"))
    return date.fromordinal(date(y, m, dd).toordinal() + 1).isoformat()


def run_config(
    panel: Panel,
    *,
    mapping: str,
    thr: float,
    scale: float,
    vol_target: float,
    vol_lookback: int,
    cost_bps: float,
) -> Dict[str, object]:
    w = build_weights(panel, mapping=mapping, thr=thr, scale=scale,
                      vol_target=vol_target, vol_lookback=vol_lookback)
    daily, dd, turn, nreb = backtest(panel, w, cost_bps_roundtrip=cost_bps, lag_days=1)
    is_r, is_d = slice_window(daily, dd, "1900-01-01", OOS_SPLIT)
    oos_r, oos_d = slice_window(daily, dd, _next_day(OOS_SPLIT), "2999-12-31")
    return {
        "config": {"mapping": mapping, "thr": thr, "scale": scale, "vol_target": vol_target,
                   "vol_lookback": vol_lookback, "cost_bps": cost_bps},
        "full": metrics(daily, dd),
        "is": metrics(is_r, is_d),
        "oos": metrics(oos_r, oos_d),
        "avg_turnover_per_rebal": round(turn, 4),
        "n_rebals": nreb,
        "_daily": daily, "_dates": dd,
    }


def strip_series(d: Dict[str, object]) -> Dict[str, object]:
    return {k: v for k, v in d.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Bond-leg daily path (for the corr-to-bond gate) — primary config from the bond-leg engine
# ---------------------------------------------------------------------------

def bond_leg_path() -> Tuple[List[float], List[str], Dict[str, object]]:
    """Run the bond leg's PRIMARY config (TLT, scale=1.5, vol_target=0.09, vol_lookback=20, 2bps)
    and return (daily_net, daily_dates, headline_metrics). Mirrors _h1_carry_bondleg_tests.main()."""
    panel_b = bl.Panel(["TLT", "IEF", "SHY"])
    me_b = bl.month_end_indices(panel_b.dates)
    end_d = panel_b.dates[-1]
    slope_2y = bl.AsOfSeries("T10Y2Y", "1990-01-01", end_d)
    bl._SLOPE_IDS[id(slope_2y)] = "T10Y2Y"
    PRIM = dict(long_sleeve="TLT", scale=1.5, vol_target=0.09, vol_lookback=20)
    res = bl.run_one(panel_b, slope_2y, me_b, cost_bps=2.0, **PRIM)
    return res["_daily"], res["_dates"], {
        "oos_sharpe": res["oos"]["sharpe"], "oos_total": res["oos"]["total_return"],
        "full_sharpe": res["full"]["sharpe"], "is_sharpe": res["is"]["sharpe"],
    }


# ---------------------------------------------------------------------------
# Stress windows (crude-specific) — report signal vs static-long vs buy-hold total return
# ---------------------------------------------------------------------------

STRESS = {
    "2008_GFC_oilcrash":   ("2008-07-01", "2009-03-31"),   # $147 -> $34 collapse then contango
    "2014_15_oilbust":     ("2014-07-01", "2015-12-31"),   # shale glut, deep contango
    "2020_covid_negative": ("2020-02-01", "2020-06-30"),   # negative-print + super-contango
    "2021_22_backwardation": ("2021-01-01", "2022-06-30"), # post-covid demand, backwardation
}


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    stamp = os.environ.get("UTCSTAMP") or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    print(f"[EIA WTI cal-spread carry] UTC stamp = {stamp}")

    panel = Panel()
    print(f"[panel] {len(panel)} aligned NYMEX days {panel.dates[0]} -> {panel.dates[-1]}  "
          f"({len(panel.me_idx)} month-end rebalances)")
    last = len(panel) - 1
    print(f"[panel] last-row term structure CL1..CL4 = "
          f"{panel.CL1[last]:.2f} {panel.CL2[last]:.2f} {panel.CL3[last]:.2f} {panel.CL4[last]:.2f} "
          f"(slope={panel.slope_at(last):+.4f})")
    frac_back = sum(1 for T in panel.me_idx if panel.slope_at(T) > 0) / len(panel.me_idx)
    print(f"[panel] frac month-ends backwardated (slope>0): {frac_back:.3f}")

    # ===================================================================
    # PRIMARY config (chosen a priori): LONG/FLAT, thr=0, 12% vol target, 20d vol, 2 bps.
    # ===================================================================
    PRIM = dict(mapping="long_flat", thr=0.0, scale=0.05, vol_target=0.12, vol_lookback=20)
    primary = run_config(panel, cost_bps=2.0, **PRIM)
    print(f"[primary long/flat] FULL Sh {primary['full']['sharpe']}  IS Sh {primary['is']['sharpe']}  "
          f"OOS Sh {primary['oos']['sharpe']}  OOS tot {primary['oos']['total_return']}  "
          f"turn {primary['avg_turnover_per_rebal']}")

    # ---- Controls on the SAME path/cost ----
    stat_w = static_long_weights(panel, vol_target=0.12, vol_lookback=20)
    stat_daily, stat_dd, stat_turn, stat_nreb = backtest(panel, stat_w, cost_bps_roundtrip=2.0, lag_days=1)
    stat_full = metrics(stat_daily, stat_dd)
    stat_is_r, stat_is_d = slice_window(stat_daily, stat_dd, "1900-01-01", OOS_SPLIT)
    stat_oos_r, stat_oos_d = slice_window(stat_daily, stat_dd, _next_day(OOS_SPLIT), "2999-12-31")
    stat_is = metrics(stat_is_r, stat_is_d); stat_oos = metrics(stat_oos_r, stat_oos_d)

    bh_w = buyhold_weights(panel)
    bh_daily, bh_dd, bh_turn, bh_nreb = backtest(panel, bh_w, cost_bps_roundtrip=2.0, lag_days=1)
    bh_full = metrics(bh_daily, bh_dd)
    bh_oos_r, bh_oos_d = slice_window(bh_daily, bh_dd, _next_day(OOS_SPLIT), "2999-12-31")
    bh_oos = metrics(bh_oos_r, bh_oos_d)

    print(f"[control STATIC-LONG] FULL {stat_full['sharpe']}  IS {stat_is['sharpe']}  "
          f"OOS {stat_oos['sharpe']}  OOS tot {stat_oos['total_return']}")
    print(f"[control BUY-HOLD]    FULL {bh_full['sharpe']}  OOS {bh_oos['sharpe']}  OOS tot {bh_oos['total_return']}")

    sig_oos = primary["oos"]; sig_is = primary["is"]
    delta_static_oos_sh = round(sig_oos["sharpe"] - stat_oos["sharpe"], 4)
    delta_static_oos_tot = round(sig_oos["total_return"] - stat_oos["total_return"], 4)
    delta_bh_oos_sh = round(sig_oos["sharpe"] - bh_oos["sharpe"], 4)
    delta_bh_oos_tot = round(sig_oos["total_return"] - bh_oos["total_return"], 4)

    # ---- Lookahead canary: honest (lag=1) vs D0 cheat (lag=0) ----
    cheat_w = build_weights(panel, **PRIM)
    cheat_daily, cheat_dd, _, _ = backtest(panel, cheat_w, cost_bps_roundtrip=2.0, lag_days=0)
    cheat_full = metrics(cheat_daily, cheat_dd)
    honest_sh = primary["full"]["sharpe"]; cheat_sh = cheat_full["sharpe"]
    canary_differs = abs(honest_sh - cheat_sh) > 1e-6
    print(f"[canary] honest(D+1) FULL Sh {honest_sh}  cheat(D0) {cheat_sh}  differ={canary_differs}")

    # ---- Cost grid (monotonic): 0/1/2/5 bps + breakeven vs static-long OOS ----
    cost_grid = []
    for c in (0.0, 1.0, 2.0, 5.0):
        r = run_config(panel, cost_bps=c, **PRIM)
        cost_grid.append({"cost_bps": c, "full_sharpe": r["full"]["sharpe"],
                          "is_sharpe": r["is"]["sharpe"], "oos_sharpe": r["oos"]["sharpe"],
                          "oos_total": r["oos"]["total_return"]})
    # breakeven: bisect the cost (bps) at which OOS total return -> 0
    def oos_total_at(c: float) -> float:
        return run_config(panel, cost_bps=c, **PRIM)["oos"]["total_return"]
    lo, hi = 0.0, 200.0
    be = None
    if oos_total_at(lo) > 0:
        for _ in range(40):
            mid = (lo + hi) / 2
            if oos_total_at(mid) > 0:
                lo = mid
            else:
                hi = mid
        be = round((lo + hi) / 2, 2)
    print(f"[cost grid] {cost_grid}  breakeven_bps={be}")

    # ---- Robustness sweep (report FULL + OOS spread; knife-edge = fail) ----
    sweep = []
    for mapping in ("long_flat", "long_short", "scaled"):
        for thr in (-0.005, 0.0, 0.005):
            for vt in (0.10, 0.12, 0.15):
                r = run_config(panel, mapping=mapping, thr=thr, scale=0.05,
                               vol_target=vt, vol_lookback=20, cost_bps=2.0)
                sweep.append({
                    "mapping": mapping, "thr": thr, "vol_target": vt,
                    "full_sharpe": r["full"]["sharpe"], "is_sharpe": r["is"]["sharpe"],
                    "oos_sharpe": r["oos"]["sharpe"], "oos_total": r["oos"]["total_return"],
                    "full_maxdd": r["full"]["max_drawdown"], "turn": r["avg_turnover_per_rebal"],
                })
    oos_sharpes = [s["oos_sharpe"] for s in sweep]
    is_sharpes = [s["is_sharpe"] for s in sweep]
    sweep_stats = {
        "n": len(sweep),
        "oos_sharpe_min": round(min(oos_sharpes), 4), "oos_sharpe_max": round(max(oos_sharpes), 4),
        "oos_sharpe_median": round(sorted(oos_sharpes)[len(oos_sharpes) // 2], 4),
        "is_sharpe_min": round(min(is_sharpes), 4), "is_sharpe_max": round(max(is_sharpes), 4),
        "is_sharpe_median": round(sorted(is_sharpes)[len(is_sharpes) // 2], 4),
        "n_oos_above_0.4": sum(1 for x in oos_sharpes if x > 0.4),
        "frac_oos_above_0.4": round(sum(1 for x in oos_sharpes if x > 0.4) / len(oos_sharpes), 3),
        "n_is_positive": sum(1 for x in is_sharpes if x > 0),
        "frac_is_positive": round(sum(1 for x in is_sharpes if x > 0) / len(is_sharpes), 3),
    }
    print("[sweep stats]", sweep_stats)

    # ---- Post-GFC (2009+) context cut on the primary ----
    pg_r, pg_d = slice_window(primary["_daily"], primary["_dates"], "2009-01-01", "2999-12-31")
    postgfc = metrics(pg_r, pg_d)

    # ---- Stress windows: signal vs static-long vs buy-hold (total return) ----
    stress_table = {}
    for name, (lo_w, hi_w) in STRESS.items():
        s_r, _ = slice_window(primary["_daily"], primary["_dates"], lo_w, hi_w)
        t_r, _ = slice_window(stat_daily, stat_dd, lo_w, hi_w)
        b_r, _ = slice_window(bh_daily, bh_dd, lo_w, hi_w)
        stress_table[name] = {
            "window": [lo_w, hi_w], "n_days": len(s_r),
            "signal_total": round(total_return(s_r), 4), "signal_sharpe": round(sharpe(s_r), 4),
            "static_total": round(total_return(t_r), 4), "buyhold_total": round(total_return(b_r), 4),
        }
    print("[stress]", json.dumps(stress_table))

    # ---- corr-to-bond-leg (k4) ----
    bond_daily, bond_dd, bond_head = bond_leg_path()
    sig_mk, sig_mv = monthly_returns(primary["_daily"], primary["_dates"])
    bond_mk, bond_mv = monthly_returns(bond_daily, bond_dd)
    corr_bond = aligned_monthly_corr(sig_mk, sig_mv, bond_mk, bond_mv)
    print(f"[corr-to-bond] {corr_bond}  (bond leg OOS Sh {bond_head['oos_sharpe']}, "
          f"full Sh {bond_head['full_sharpe']})")

    # ===================================================================
    # VERDICT k1..k5
    # ===================================================================
    k1 = sig_oos["sharpe"] > 0.4
    k2 = (delta_static_oos_sh > 0 and delta_static_oos_tot > 0)
    # k3: IS Sharpe POSITIVE on primary AND on a majority of swept configs
    k3 = (sig_is["sharpe"] > 0) and (sweep_stats["frac_is_positive"] >= 0.5)
    k4 = abs(corr_bond) <= 0.30
    k1to4 = bool(k1 and k2 and k3 and k4)

    # k5: ONLY if k1-k4 pass -> allocator-frontier lift (lazy import). Else N/A.
    k5_block: Dict[str, object]
    if k1to4:
        try:
            k5_block = allocator_frontier_check(primary["_daily"], primary["_dates"], bond_daily, bond_dd)
        except Exception as e:  # pragma: no cover
            k5_block = {"pass": False, "error": f"allocator check failed: {e}", "na": False}
    else:
        k5_block = {"pass": False, "na": True,
                    "note": "k1-k4 did not all pass -> allocator-frontier check NOT run; CLOSE."}

    verdict = {
        "overall": "GO" if (k1to4 and k5_block.get("pass")) else "CLOSE",
        "k1_oos_sharpe_gt_0.4": {"pass": bool(k1), "oos_sharpe": sig_oos["sharpe"], "bar": 0.4},
        "k2_beats_static_long_oos": {
            "pass": bool(k2), "delta_sharpe": delta_static_oos_sh, "delta_total": delta_static_oos_tot,
            "signal_oos_sharpe": sig_oos["sharpe"], "static_oos_sharpe": stat_oos["sharpe"],
            "signal_oos_total": sig_oos["total_return"], "static_oos_total": stat_oos["total_return"],
            "vs_buyhold_delta_sharpe": delta_bh_oos_sh, "vs_buyhold_delta_total": delta_bh_oos_tot,
            "note": "MAKE-OR-BREAK: timing must beat dumb static-long (and buy-hold) OOS net",
        },
        "k3_is_sharpe_positive": {
            "pass": bool(k3), "primary_is_sharpe": sig_is["sharpe"],
            "frac_swept_is_positive": sweep_stats["frac_is_positive"],
            "is_sharpe_median_sweep": sweep_stats["is_sharpe_median"],
            "note": "HARD GATE — the ETF version FAILED this (IS -0.44 on every split)",
        },
        "k4_corr_to_bond_le_0.3": {"pass": bool(k4), "value": corr_bond, "bar": 0.30},
        "k5_allocator_frontier_lift": k5_block,
    }
    print("\n========== VERDICT ==========")
    print(json.dumps(verdict, indent=2))
    print("=============================\n")

    # ---- Assemble machine-readable result (mirror bond-leg result.json) ----
    result = {
        "meta": {
            "utc_stamp": stamp,
            "hypothesis": "EIA WTI futures CALENDAR-SPREAD carry leg (true curve-shape, non-ETF)",
            "reopen_trigger_source": "reports/H1_CARRY_COMMODITY_COMBINED_20260623T193840Z.md (§Revisit-triggers, lines 221-222)",
            "instruments": ["RCLC1", "RCLC2", "RCLC3", "RCLC4 (EIA Cushing WTI future contracts, $/bbl)"],
            "traded_return": "FRONT-contract (CL1) daily simple return, calendar-spread/roll-timing",
            "signal": "slope = (CL1-CL4)/CL4 at month-end; long/flat on backwardation; 1-day lag",
            "panel_span": [panel.dates[0], panel.dates[-1]],
            "n_aligned_days": len(panel),
            "n_month_end_rebals": len(panel.me_idx),
            "frac_month_ends_backwardated": round(frac_back, 4),
            "oos_split": OOS_SPLIT,
            "oos_truncation": "EIA stopped publishing NYMEX futures after 2024-04-05; OOS = 2019-01-01..2024-04-05; leg CANNOT be tested past Apr-2024 on free data",
            "negative_print_handling": f"2020-04-20 CL1=-37.63; front-ret masked to 0 across {sorted(NEG_PRINT_MASK)} for signal AND all controls identically",
            "sharpe_convention": "(mean/std)*sqrt(252), ddof=1, continuous-span (reuses _h1_carry_bondleg_tests.sharpe)",
            "signal_lag_days": 1,
            "vol_target_pct": 0.12,
            "primary_config": primary["config"],
        },
        "series_stats": {
            "primary_signal": strip_series(primary),
            "primary_postgfc_2009plus": postgfc,
            "control_static_long": {"full": stat_full, "is": stat_is, "oos": stat_oos,
                                    "avg_turnover_per_rebal": round(stat_turn, 4), "n_rebals": stat_nreb},
            "control_buyhold": {"full": bh_full, "oos": bh_oos,
                                "avg_turnover_per_rebal": round(bh_turn, 4), "n_rebals": bh_nreb},
        },
        "cost_analysis": {"grid": cost_grid, "breakeven_bps_oos": be,
                          "note": "monthly rebal on the front-contract timing weight; turnover is the cost driver"},
        "lookahead_canary": {
            "honest_d1_full_sharpe": honest_sh, "cheat_d0_full_sharpe": cheat_sh,
            "paths_differ": bool(canary_differs),
            "interpretation": "honest(D+1) != cheat(D0) => no same-day leakage",
        },
        "controls": {
            "static_long": {"oos_sharpe": stat_oos["sharpe"], "oos_total": stat_oos["total_return"],
                            "delta_signal_minus_static_oos_sharpe": delta_static_oos_sh,
                            "delta_signal_minus_static_oos_total": delta_static_oos_tot},
            "buyhold": {"oos_sharpe": bh_oos["sharpe"], "oos_total": bh_oos["total_return"],
                        "delta_signal_minus_buyhold_oos_sharpe": delta_bh_oos_sh,
                        "delta_signal_minus_buyhold_oos_total": delta_bh_oos_tot},
        },
        "robustness_sweep": {"stats": sweep_stats, "grid": sweep},
        "stress_windows": stress_table,
        "corr_to_bond_leg": {"value": corr_bond, "bar": 0.30,
                             "bond_leg_oos_sharpe": bond_head["oos_sharpe"],
                             "bond_leg_full_sharpe": bond_head["full_sharpe"]},
        "verdict": verdict,
    }

    out_json = WORKSPACE / "reports" / "_eia_wti_calspread_result.json"
    out_json.write_text(json.dumps(result, indent=2))
    print(f"[written] {out_json}")
    print(f"[OVERALL] {verdict['overall']}  (k1={k1} k2={k2} k3={k3} k4={k4} "
          f"k5={k5_block.get('pass') if not k5_block.get('na') else 'N/A'})")
    return result


# ---------------------------------------------------------------------------
# k5: allocator-frontier lift (only invoked if k1-k4 pass). Lazy, read-only.
# ---------------------------------------------------------------------------

def _inv_vol_blend(paths: List[Tuple[List[float], List[str]]], lookback: int = 63) -> Tuple[List[float], List[str]]:
    """Inverse-vol monthly-rebalanced blend of N daily return paths on their common calendar."""
    # align on intersection of dates
    common = None
    maps = []
    for daily, dd in paths:
        m = dict(zip(dd, daily))
        maps.append(m)
        s = set(dd)
        common = s if common is None else (common & s)
    dates = sorted(common)
    n = len(dates)
    # per-path daily series on the common calendar
    series = [[m[d] for d in dates] for m in maps]
    # month-end indices on the common calendar
    me = [i for i in range(n) if i == n - 1 or dates[i + 1][:7] != dates[i][:7]]
    me_set = set(me)
    # inverse-vol weights set at each month-end from trailing `lookback` daily vol, held forward
    w = [1.0 / len(series)] * len(series)
    out = [0.0] * n
    for i in range(n):
        if i in me_set and i >= lookback:
            inv = []
            for s in series:
                seg = s[i - lookback + 1:i + 1]
                mu = sum(seg) / len(seg)
                var = sum((x - mu) ** 2 for x in seg) / (len(seg) - 1) if len(seg) > 1 else 0.0
                vol = math.sqrt(var) if var > 0 else 0.0
                inv.append(1.0 / vol if vol > 1e-12 else 0.0)
            tot = sum(inv)
            if tot > 0:
                w = [x / tot for x in inv]
        out[i] = sum(w[j] * series[j][i] for j in range(len(series)))
    return out, dates


def allocator_frontier_check(
    comm_daily: List[float], comm_dd: List[str],
    bond_daily: List[float], bond_dd: List[str],
) -> Dict[str, object]:
    """k5: does adding the comm cal-spread leg as a 3rd inverse-vol sleeve LIFT the frontier vs
    the LIVE 2-sleeve allocator (TQQQ vol-target + sector rotation)?

    Reproduces the live 2-sleeve inv-vol blend EXACTLY via _allocator_blend_tests (read-only),
    then builds a 3-sleeve inv-vol blend on the common calendar and compares full + OOS Sharpe and
    max-DD. Lift = 3-sleeve full Sharpe > 2-sleeve full Sharpe AND OOS Sharpe not worse AND max-DD
    not materially worse. The comm leg's daily series is mapped onto the allocator calendar (days
    with no WTI observation -> 0 return for that sleeve, i.e. flat/cash that day)."""
    import _allocator_blend_tests as ab  # noqa

    S = ab.build_sleeves()
    dates = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]

    # Map the comm cal-spread daily net returns onto the allocator calendar (missing day -> 0.0).
    comm_map = dict(zip(comm_dd, comm_daily))
    comm_r_aligned = [comm_map.get(d, 0.0) for d in dates]
    comm_coverage = round(sum(1 for d in dates if d in comm_map) / len(dates), 3)

    # ---- 2-sleeve LIVE baseline: inv-vol 63d (matches _allocator_blend_tests.invvol_wfn) ----
    sleeves2 = [tqqq_r, rot_r]

    def invvol2(idx):
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - 63)
        v0 = ab.annualized_vol(sleeves2[0][lo:idx])
        v1 = ab.annualized_vol(sleeves2[1][lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv = [1.0 / v0, 1.0 / v1]
        s = sum(iv)
        return [x / s for x in iv]

    b2 = ab.blend_portfolio(dates, sleeves2, invvol2, blend_cost_bps=2.0)
    rep2 = ab.report_blend(b2, "live_2sleeve_invvol", dates,
                           ab.stats_from_returns(dates, S["spx_r"])["equity"])

    # ---- 3-sleeve: TQQQ + rot + comm cal-spread, inv-vol 63d ----
    sleeves3 = [tqqq_r, rot_r, comm_r_aligned]

    def invvol3(idx):
        if idx < 2:
            return [1 / 3, 1 / 3, 1 / 3]
        lo = max(0, idx - 63)
        vs = [ab.annualized_vol(s[lo:idx]) for s in sleeves3]
        if any(v <= 0 for v in vs):
            return [1 / 3, 1 / 3, 1 / 3]
        iv = [1.0 / v for v in vs]
        s = sum(iv)
        return [x / s for x in iv]

    b3 = ab.blend_portfolio(dates, sleeves3, invvol3, blend_cost_bps=2.0)
    rep3 = ab.report_blend(b3, "with_comm_3sleeve_invvol", dates,
                           ab.stats_from_returns(dates, S["spx_r"])["equity"])

    sh2 = rep2["full"]["sharpe"]; sh3 = rep3["full"]["sharpe"]
    oos2 = (rep2["oos_2019_today"] or {}).get("sharpe")
    oos3 = (rep3["oos_2019_today"] or {}).get("sharpe")
    dd2 = rep2["full"]["maxdd_pct"]; dd3 = rep3["full"]["maxdd_pct"]

    full_lift = sh3 > sh2
    oos_ok = (oos3 is not None and oos2 is not None and oos3 >= oos2 - 1e-9)
    dd_ok = dd3 >= dd2 - 2.0  # max-DD (pct, negative) not materially worse (>2pp deterioration fails)
    passed = bool(full_lift and oos_ok and dd_ok)

    return {
        "pass": passed, "na": False,
        "comm_coverage_on_allocator_calendar": comm_coverage,
        "two_sleeve_full_sharpe": sh2, "three_sleeve_full_sharpe": sh3,
        "delta_full_sharpe": round(sh3 - sh2, 4),
        "two_sleeve_oos_sharpe": oos2, "three_sleeve_oos_sharpe": oos3,
        "two_sleeve_full_maxdd_pct": dd2, "three_sleeve_full_maxdd_pct": dd3,
        "full_sharpe_lift": bool(full_lift), "oos_not_worse": bool(oos_ok),
        "maxdd_not_materially_worse": bool(dd_ok),
        "note": "3rd inverse-vol sleeve must LIFT full Sharpe, not hurt OOS Sharpe, not blow out max-DD",
    }


if __name__ == "__main__":
    main()
