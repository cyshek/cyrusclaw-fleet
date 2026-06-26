"""Diagnostic: is the slower-cadence raw-return 'win' a genuine cadence edge or a
drift-up-the-winner (de-facto leverage-up) CONFOUND?

For each cadence we recompute the blend but ALSO track the realized EFFECTIVE
(drifted) sleeve weights every day, and report:
  - avg effective w_tqqq over the whole path (the real average exposure)
  - the static MONTHLY baseline's avg effective w_tqqq
If a 'winning' cadence simply runs a higher avg TQQQ exposure, its extra return
is the SAME leverage-up the blend's weight dial already offers (70/30 etc), not a
free cadence edge -- exactly the confound the regime report flagged.

We ALSO build, for direct comparison, FIXED-weight monthly blends at the avg
effective w_tqqq each winner realizes, to show the winner sits ON the existing
return-vs-DD dial (same return for same DD), not above it.
"""
from __future__ import annotations

import json
import sys
from typing import Callable, Dict, List

sys.path.insert(0, ".")
sys.path.insert(0, "tests")

import _cadence_sweep as cs
from strategies_candidates.leveraged_long_trend.backtest_daily import _stats_from_equity


def blend_track_weights(dates: List[str], sleeves: List[List[float]],
                        should_rebalance: Callable, blend_cost_bps: float = cs.BLEND_COST_BPS,
                        lookback: int = cs.VOL_LOOKBACK_DAYS) -> Dict:
    """Same as cs.blend_with_cadence but also records the daily EFFECTIVE w_tqqq
    (the drifted weight actually held that day)."""
    n = len(dates)
    ns = len(sleeves)
    w0 = cs.invvol_target(sleeves, 0, lookback)
    bucket = [w0[k] for k in range(ns)]
    eff_w_tqqq: List[float] = []
    n_rebal = 0
    for i in range(1, n):
        tot = sum(bucket)
        cur_w = [b / tot for b in bucket] if tot > 0 else [0.0] * ns
        tgt = cs.invvol_target(sleeves, i, lookback)
        if should_rebalance(i, cur_w, tgt):
            turn = sum(abs(tgt[k] - cur_w[k]) for k in range(ns))
            if turn > 1e-9:
                cost = (blend_cost_bps / 10000.0) * turn
                n_rebal += 1
                tot_after = tot * (1.0 - cost)
                bucket = [tgt[k] * tot_after for k in range(ns)]
        # effective weight held over day i (after any rebalance, before drift)
        tot2 = sum(bucket)
        eff_w_tqqq.append(bucket[0] / tot2 if tot2 > 0 else 0.0)
        for k in range(ns):
            bucket[k] *= (1.0 + sleeves[k][i])
    return {"avg_eff_w_tqqq": sum(eff_w_tqqq) / len(eff_w_tqqq) if eff_w_tqqq else 0.0,
            "max_eff_w_tqqq": max(eff_w_tqqq) if eff_w_tqqq else 0.0,
            "min_eff_w_tqqq": min(eff_w_tqqq) if eff_w_tqqq else 0.0,
            "n_rebal": n_rebal}


def fixed_monthly_blend(dates, sleeves, w_tqqq_fixed, moset):
    """Fixed-weight (w_tqqq_fixed / 1-w) monthly-rebalanced blend for comparison."""
    def tgt_fn(i):
        return [w_tqqq_fixed, 1.0 - w_tqqq_fixed]
    import _allocator_blend_tests as ab
    return ab.blend_portfolio(dates, sleeves, tgt_fn,
                              blend_cost_bps=cs.BLEND_COST_BPS,
                              vol_lookback_days=cs.VOL_LOOKBACK_DAYS)


def main() -> None:
    S = cs.load_sleeves()
    dates = S["common_dates"]
    sleeves = [S["tqqq_r"], S["rot_r"]]
    moset = cs.month_open_set(dates)
    qset = cs.quarter_open_set(dates)
    wset = cs.week_open_set(dates, anchor_dow=0)

    cadences = {
        "monthly_baseline": cs.month_open_set(dates),
    }

    def cal(trigset):
        def fn(i, cur_w, tgt_w):
            return i in trigset
        return fn

    def drift_max(tau):
        def fn(i, cur_w, tgt_w):
            return max(abs(cur_w[k] - tgt_w[k]) for k in range(len(cur_w))) > tau
        return fn

    def drift_l1(tau):
        def fn(i, cur_w, tgt_w):
            return sum(abs(cur_w[k] - tgt_w[k]) for k in range(len(cur_w))) > tau
        return fn

    triggers = {
        "monthly_baseline": cal(moset),
        "weekly": cal(wset),
        "quarterly": cal(qset),
        "drift_maxleg_0.10": drift_max(0.10),
        "drift_maxleg_0.20": drift_max(0.20),
        "drift_maxleg_0.25": drift_max(0.25),
        "drift_l1_0.15": drift_l1(0.15),
        "drift_l1_0.25": drift_l1(0.25),
    }

    print(">>> realized effective w_tqqq per cadence (the confound check) ...")
    rows = {}
    for name, trig in triggers.items():
        tw = blend_track_weights(dates, sleeves, trig)
        b = cs.blend_with_cadence(dates, sleeves, trig)
        rows[name] = {"avg_eff_w_tqqq": tw["avg_eff_w_tqqq"],
                      "min_eff_w_tqqq": tw["min_eff_w_tqqq"],
                      "max_eff_w_tqqq": tw["max_eff_w_tqqq"],
                      "net_totret_pct": b["stats"]["total_return_pct"],
                      "sharpe": b["stats"]["sharpe"],
                      "maxdd_pct": b["stats"]["max_drawdown_pct"]}
        print("   %-20s avg_eff_w_tqqq %.3f [%.3f..%.3f] | net %.1f%% Sh %.3f maxDD %.1f%%" % (
            name, tw["avg_eff_w_tqqq"], tw["min_eff_w_tqqq"], tw["max_eff_w_tqqq"],
            b["stats"]["total_return_pct"], b["stats"]["sharpe"], b["stats"]["max_drawdown_pct"]))

    base_avg = rows["monthly_baseline"]["avg_eff_w_tqqq"]
    print("")
    print(">>> CONTROL: fixed-weight MONTHLY blend at the SAME avg w_tqqq each winner runs")
    print("    (if the winner's (return,maxDD) ~ the fixed blend at its avg w_tqqq, it's the dial, not an edge)")
    control = {}
    for name in ("quarterly", "drift_maxleg_0.20", "drift_maxleg_0.25", "drift_l1_0.25"):
        w = rows[name]["avg_eff_w_tqqq"]
        fb = fixed_monthly_blend(dates, sleeves, w, moset)
        control[name] = {"matched_w_tqqq": w,
                         "fixed_monthly_totret_pct": fb["stats"]["total_return_pct"],
                         "fixed_monthly_sharpe": fb["stats"]["sharpe"],
                         "fixed_monthly_maxdd_pct": fb["stats"]["max_drawdown_pct"],
                         "cadence_totret_pct": rows[name]["net_totret_pct"],
                         "cadence_sharpe": rows[name]["sharpe"],
                         "cadence_maxdd_pct": rows[name]["maxdd_pct"]}
        print("   %-20s w=%.3f | FIXED-monthly: %.1f%% Sh %.3f DD %.1f%%  vs  CADENCE: %.1f%% Sh %.3f DD %.1f%%" % (
            name, w, fb["stats"]["total_return_pct"], fb["stats"]["sharpe"],
            fb["stats"]["max_drawdown_pct"], rows[name]["net_totret_pct"],
            rows[name]["sharpe"], rows[name]["maxdd_pct"]))

    out = {"avg_eff_weights": rows, "baseline_avg_eff_w_tqqq": base_avg,
           "fixed_weight_control": control}
    with open("reports/_cadence_confound_diag.json", "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("wrote reports/_cadence_confound_diag.json")


if __name__ == "__main__":
    main()
