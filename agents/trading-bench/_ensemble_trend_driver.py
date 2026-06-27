"""Multi-timeframe TREND-SIGNAL ENSEMBLE on the TQQQ vol-target sleeve.

Replaces the SINGLE SMA-200 binary risk-on gate with a 3-horizon EW ENSEMBLE
breadth scaler g in [0,1], multiplied into the SAME vol-target sizing. Honest
harness, matching the BACKLOG spec exactly:

  - D+1 lag (decision from data <= D; held over D+1). Same convention + the
    engine's no-lookahead slicing helpers, reused verbatim.
  - 2 bps/side cost on ABS change in weight (engine convention).
  - IS/OOS split @ 2018-01-01 (feasible: daily TQQQ data from 2010).
  - FP-continuous Sharpe (daily, sqrt(252)) = the gate metric. Baseline
    single-window SMA-200 vol-target = ~0.856-0.859.
  - MANDATORY 1-day-lag robustness canary (gate evaluated on data <= D-1).
  - HONESTY CONSTRAINT: EW across horizons, NO per-horizon weight optimization.
    g = (# horizons agreeing trend-up) / n_horizons. Nothing fitted.

Ensemble flavors (both EW, zero fitted knobs):
  (a) SMA breadth      : g = (#{price > SMA_w} for w in {50,100,200}) / 3
  (b) TSMOM-sign breadth: g = (#{price > price[-h]} for h in {63,126,252}) / 3
                          (~3 / 6 / 12 trading months)

Baseline = the live engine's single SMA-200 binary gate (g in {0,1}).

Promote ONLY if an ensemble beats the single-window baseline OOS net of cost
AND the Sharpe-gain survives the 1-day-lag canary.
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")
sys.path.insert(0, "strategies_candidates/leveraged_long_trend")

import backtest_daily as bd
from backtest_daily_voltarget import (VolTargetParams, realized_ann_vol,
                                      target_weight, _clamp,
                                      _stats_from_equity, TRADING_DAYS)

TARGET_VOL = 0.25
VOL_WINDOW = 20
W_MAX = 1.0
COST_BPS = 2.0
OOS_START = "2018-01-01"

SMA_WINDOWS = [50, 100, 200]
TSMOM_HORIZONS = [63, 126, 252]  # ~3/6/12 trading months


def _sma(values: List[float], n: int) -> Optional[float]:
    if len(values) < n or n <= 0:
        return None
    return sum(values[-n:]) / n


def sma_breadth(under_closes: List[float]) -> float:
    """Fraction of {50,100,200}d SMAs the last price is above. EW, no weights."""
    if not under_closes:
        return 0.0
    last = under_closes[-1]
    agree = 0
    for w in SMA_WINDOWS:
        s = _sma(under_closes, w)
        if s is not None and last > s:
            agree += 1
    return agree / len(SMA_WINDOWS)


def tsmom_breadth(under_closes: List[float]) -> float:
    """Fraction of {63,126,252}-day TSMOM horizons that are positive. EW."""
    if not under_closes:
        return 0.0
    last = under_closes[-1]
    agree = 0
    for h in TSMOM_HORIZONS:
        if len(under_closes) > h and last > under_closes[-1 - h]:
            agree += 1
    return agree / len(TSMOM_HORIZONS)


def sma200_binary(under_closes: List[float]) -> float:
    """Baseline single-window gate as a [0,1] scaler (in {0,1})."""
    s = _sma(under_closes, 200)
    if s is None:
        return 0.0
    return 1.0 if under_closes[-1] > s else 0.0


GATES = {
    "baseline_sma200": sma200_binary,
    "ens_sma_breadth": sma_breadth,
    "ens_tsmom_breadth": tsmom_breadth,
}


def fp_sharpe_from_equity(equity: List[float]) -> float:
    rets = []
    for i in range(1, len(equity)):
        if equity[i - 1] > 0:
            rets.append(equity[i] / equity[i - 1] - 1.0)
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(TRADING_DAYS)


def simulate(gate_fn, p: VolTargetParams, lag_extra: int = 0,
             start: Optional[str] = None, end: Optional[str] = None) -> Dict:
    """Run the vol-target engine with `gate_fn` producing the continuous risk-on
    scaler g in [0,1]. Sleeve weight = g * voltarget_weight. `lag_extra` shifts
    the decision day back an ADDITIONAL `lag_extra` trading days (the canary).
    """
    sleeve_bars = bd.dbc.get_daily(p.sleeve)
    under_bars = bd.dbc.get_daily(p.underlying)
    bench_bars = bd.dbc.get_daily(p.benchmark)
    sleeve_by = {b["date"]: b for b in sleeve_bars}

    s0 = start or sleeve_bars[0]["date"]
    e0 = end or sleeve_bars[-1]["date"]
    cal = [b["date"] for b in sleeve_bars if s0 <= b["date"] <= e0]

    under_dates = [b["date"] for b in under_bars]
    under_close = [b["adjclose"] for b in under_bars]

    def under_closes_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(under_dates, d_iso)
        return under_close[:idx]

    sleeve_dates = [b["date"] for b in sleeve_bars]
    sleeve_close = [b["adjclose"] for b in sleeve_bars]
    sret_end_dates: List[str] = []
    sret_vals: List[float] = []
    for k in range(1, len(sleeve_close)):
        if sleeve_close[k - 1] > 0:
            sret_end_dates.append(sleeve_dates[k])
            sret_vals.append(sleeve_close[k] / sleeve_close[k - 1] - 1.0)

    def sleeve_rets_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(sret_end_dates, d_iso)
        return sret_vals[:idx]

    # For the canary we need to step the DECISION date back lag_extra trading
    # days within the sleeve calendar.
    full_cal = sleeve_dates

    def lagged_decision_date(d_prev: str) -> str:
        if lag_extra <= 0:
            return d_prev
        idx = bisect.bisect_right(full_cal, d_prev) - 1
        j = max(0, idx - lag_extra)
        return full_cal[j]

    equity = [1.0]
    strat_dates = [cal[0]]
    weights: List[float] = []
    in_market: List[bool] = []
    prev_w = 0.0
    n_rebal = 0
    for i in range(1, len(cal)):
        d_prev = cal[i - 1]
        d = cal[i]
        dec = lagged_decision_date(d_prev)

        uc = under_closes_through(dec)
        g = gate_fn(uc)  # continuous risk-on scaler [0,1]
        # VIX gate (same as engine): if risk-off, force g=0
        if p.vix_gate and g > 0 and bd._vix_risk_off(dec, p.vix_ratio_thr):
            g = 0.0

        rv = realized_ann_vol(sleeve_rets_through(dec), p.vol_window) \
            if p.target_ann_vol is not None else None
        # vol-target weight assuming trend "up" (we apply breadth as a multiplier)
        vt = target_weight(True, rv, p.target_ann_vol, p.w_max)
        w = g * vt

        b_now = sleeve_by.get(d)
        b_prev = sleeve_by.get(d_prev)
        sleeve_ret = (b_now["adjclose"] / b_prev["adjclose"] - 1.0) \
            if (b_now and b_prev and b_prev["adjclose"] > 0) else 0.0
        cash_ret = bd._tbill_daily_rate(dec) if p.use_tbill_cash else 0.0
        blended = w * sleeve_ret + (1.0 - w) * cash_ret

        dw = abs(w - prev_w)
        cost = (p.switch_cost_bps / 10000.0) * dw
        if dw > 1e-9:
            n_rebal += 1
        equity.append(equity[-1] * (1.0 + blended) * (1.0 - cost))
        strat_dates.append(d)
        weights.append(w)
        in_market.append(w > 0.0)
        prev_w = w

    stats = _stats_from_equity(strat_dates, equity, in_market, n_rebal)
    return {
        "dates": strat_dates, "equity": equity, "weights": weights,
        "fp_sharpe": fp_sharpe_from_equity(equity),
        "total_ret_pct": (equity[-1] / equity[0] - 1.0) * 100.0,
        "maxdd_pct": stats.max_drawdown_pct,
        "avg_weight": sum(weights) / len(weights) if weights else 0.0,
        "n_rebal": n_rebal,
        "n_days": len(strat_dates),
    }


def base_params() -> VolTargetParams:
    return VolTargetParams(
        sleeve="TQQQ", underlying="QQQ", benchmark="^GSPC",
        gate_mode="sma200", sma_window=200, vix_gate=True, vix_ratio_thr=1.0,
        switch_cost_bps=COST_BPS, use_tbill_cash=True,
        target_ann_vol=TARGET_VOL, vol_window=VOL_WINDOW, w_max=W_MAX,
    )


def main():
    p = base_params()
    results = {}
    for gname, gfn in GATES.items():
        full = simulate(gfn, p, lag_extra=0)
        is_ = simulate(gfn, p, lag_extra=0, end="2017-12-31")
        oos = simulate(gfn, p, lag_extra=0, start=OOS_START)
        canary_full = simulate(gfn, p, lag_extra=1)
        canary_oos = simulate(gfn, p, lag_extra=1, start=OOS_START)
        results[gname] = {
            "full": full, "is": is_, "oos": oos,
            "canary_full": canary_full, "canary_oos": canary_oos,
        }
        print(f"\n=== {gname} ===")
        print(f"  FULL : fpS={full['fp_sharpe']:.3f} ret={full['total_ret_pct']:8.1f}% "
              f"maxDD={full['maxdd_pct']:.2f}% avgW={full['avg_weight']:.3f} rebal={full['n_rebal']}")
        print(f"  IS   : fpS={is_['fp_sharpe']:.3f} ret={is_['total_ret_pct']:8.1f}% maxDD={is_['maxdd_pct']:.2f}%")
        print(f"  OOS  : fpS={oos['fp_sharpe']:.3f} ret={oos['total_ret_pct']:8.1f}% maxDD={oos['maxdd_pct']:.2f}% avgW={oos['avg_weight']:.3f}")
        print(f"  canary FULL fpS={canary_full['fp_sharpe']:.3f}  canary OOS fpS={canary_oos['fp_sharpe']:.3f}")

    base = results["baseline_sma200"]
    print("\n\n===== VERDICT vs baseline_sma200 =====")
    print(f"baseline: full fpS={base['full']['fp_sharpe']:.3f} OOS fpS={base['oos']['fp_sharpe']:.3f} OOS maxDD={base['oos']['maxdd_pct']:.2f}%")
    for gname in ["ens_sma_breadth", "ens_tsmom_breadth"]:
        r = results[gname]
        d_full = r["full"]["fp_sharpe"] - base["full"]["fp_sharpe"]
        d_oos = r["oos"]["fp_sharpe"] - base["oos"]["fp_sharpe"]
        canary_drop = r["oos"]["fp_sharpe"] - r["canary_oos"]["fp_sharpe"]
        dd_improve = base["oos"]["maxdd_pct"] - r["oos"]["maxdd_pct"]  # +ve = ensemble shallower DD (maxdd is negative)
        beats_oos = d_oos > 0
        canary_robust = abs(canary_drop) <= 0.10 and (r["oos"]["fp_sharpe"] >= 0) == (r["canary_oos"]["fp_sharpe"] >= 0)
        passed = beats_oos and canary_robust
        print(f"\n{gname}: {'PASS' if passed else 'REJECT'}")
        print(f"  d_full_fpS={d_full:+.3f}  d_OOS_fpS={d_oos:+.3f}  OOS_canary_drop={canary_drop:+.3f}  OOS_DD_change={dd_improve:+.2f}pp")
        print(f"  cond_beats_oos={beats_oos}  cond_canary_robust={canary_robust}")

    json.dump(results, open("_ensemble_results.json", "w"), indent=2, default=str)
    print("\nwrote _ensemble_results.json")


if __name__ == "__main__":
    main()
