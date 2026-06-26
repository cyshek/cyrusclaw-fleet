"""COT-percentile threshold WALK-FORWARD sweep on the TQQQ vol-target sleeve.

BACKLOG item (OPEN 2026-06-21): the COT lev_net speculator-percentile overlay was
a marginal DD-shaper at FIRST-GUESS 20/80 thresholds (full Sharpe 0.875 vs base
0.864, maxDD -31.7%). This does the PROPER sweep the report flagged as needed.

WHAT THIS SWEEPS (reusing the EXACT lookahead-safe machinery from
_sigimprove_tests.py -- same engine, same COT release-lagged percentile fn):
  * entry/exit percentile thresholds: 10/90, 15/85, 20/80, 25/75, 30/70
  * field interpretation: lev_net (speculator) vs deal_net (dealer/"commercial")
  * overlay shape: caution-only (1.0/0.5) vs boost (1.25/0.5) -- and on the
    winning field, a magnitude sub-sweep (boost in {1.0,1.25,1.5}, caution in
    {0.5,0.75}) and a percentile-window robustness pass (26/52/78 wk).

THE GATE: FP-cont (full-period CONTINUOUS-SPAN) Sharpe >= 1.0. In this engine the
continuous single-path sim's full Sharpe (_stats_from_equity.sharpe: per-tick
returns over the WHOLE concatenated equity curve, x sqrt(252)) IS the FP-cont
Sharpe -- same convention as runner/fp_sharpe.sharpe_from_returns. Baseline = 0.864.

WALK-FORWARD STABILITY: for the gate we report the full continuous Sharpe; for
robustness (the "walk-forward" spirit on a single-symbol overlay engine) we ALSO
report IS(<=2018)/OOS(2019->) Sharpe AND a rolling 3-yr-window Sharpe series, so a
knife-edge / overfit threshold is visible (stable IS~OOS + tight rolling band =
real; one window carrying it = mirage).

NO-LOOKAHEAD: inherited from _sigimprove_tests -- COT via release-lagged
percentile (Tuesday snapshot invisible until Friday release), multiplier for held
day D+1 computed from decision day D only.

Run: python3 _cot_percentile_wf_sweep.py
Writes: reports/_cot_percentile_wf_sweep.json
"""
from __future__ import annotations

import bisect
import json
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import VolTargetParams
from strategies_candidates.leveraged_long_trend.backtest_daily import TRADING_DAYS
import _sigimprove_tests as S

BASE_P = dict(target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
              vix_gate=False, switch_cost_bps=2.0)
GATE = 1.0
OOS_START = "2019-01-01"
IS_END = "2018-12-31"


def _fp_sharpe_from_equity(dates: List[str], equity: List[float],
                           start: Optional[str] = None,
                           end: Optional[str] = None) -> Tuple[float, int]:
    """FP-continuous Sharpe over [start,end] of one equity path, sample-stdev x
    sqrt(252) (the fp_sharpe convention). Rebases inside the slice."""
    lo = bisect.bisect_left(dates, start) if start else 0
    hi = bisect.bisect_right(dates, end) if end else len(dates)
    eq = equity[lo:hi]
    if len(eq) < 3:
        return 0.0, len(eq)
    rets = [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq)) if eq[i - 1] > 0]
    n = len(rets)
    if n < 2:
        return 0.0, n
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    if var <= 0:
        return 0.0, n
    return (mean / var ** 0.5) * (TRADING_DAYS ** 0.5), n


def _win_rate(dates: List[str], equity: List[float]) -> float:
    rets = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity)) if equity[i - 1] > 0]
    moves = [r for r in rets if abs(r) > 1e-12]
    if not moves:
        return 0.0
    return 100.0 * sum(1 for r in moves if r > 0) / len(moves)


def _rolling_window_sharpes(dates: List[str], equity: List[float],
                            win_years: float = 3.0,
                            step_years: float = 1.0) -> List[Dict]:
    """Rolling FP-cont Sharpe over win_years windows stepped by step_years --
    the walk-forward stability view. Returns list of {start,end,sharpe,n}."""
    win = int(win_years * TRADING_DAYS)
    step = int(step_years * TRADING_DAYS)
    out: List[Dict] = []
    i = 0
    n = len(equity)
    while i + win <= n:
        seg = equity[i:i + win]
        seg_d = dates[i:i + win]
        rets = [seg[k] / seg[k - 1] - 1.0 for k in range(1, len(seg)) if seg[k - 1] > 0]
        m = len(rets)
        if m >= 2:
            mean = sum(rets) / m
            var = sum((r - mean) ** 2 for r in rets) / (m - 1)
            sh = (mean / var ** 0.5) * (TRADING_DAYS ** 0.5) if var > 0 else 0.0
            out.append({"start": seg_d[0], "end": seg_d[-1], "sharpe": round(sh, 3), "n": m})
        i += step
    return out


def _overlay_active_days(fn, dates: List[str]) -> Dict[str, int]:
    """Count how many decision days the overlay multiplier != 1.0 (so we know it
    isn't a near-no-op). dates = the decision days (d_prev) of the sim."""
    low = high = neutral = 0
    for d in dates:
        m = fn(d)
        if m > 1.0 + 1e-9:
            high += 1
        elif m < 1.0 - 1e-9:
            low += 1
        else:
            neutral += 1
    return {"boost_days": high, "caution_days": low, "neutral_days": neutral}


def eval_cell(field: str, low_thr: float, high_thr: float,
              long_mult: float, caution_mult: float,
              pct_window: int = 52) -> Dict:
    fn = S.build_cot_percentile_fn(pct_window=pct_window, low_thr=low_thr,
                                   high_thr=high_thr, long_mult=long_mult,
                                   caution_mult=caution_mult, field=field)
    r = S.run_voltarget_with_multiplier(VolTargetParams(**BASE_P), multiplier_fn=fn)
    ds = r["strategy"]["dates"]
    eq = r["strategy"]["equity"]
    st = r["strategy"]["stats"]

    fp_full, n_full = _fp_sharpe_from_equity(ds, eq)
    fp_oos, n_oos = _fp_sharpe_from_equity(ds, eq, OOS_START, "2099-12-31")
    fp_is, n_is = _fp_sharpe_from_equity(ds, eq, "2010-01-01", IS_END)
    # decision days = all but the last sim date (d_prev loop)
    active = _overlay_active_days(fn, ds[:-1])

    # OOS / full maxDD via the report_block slices (population-var Sharpe there is
    # only used for the engine's own stats; we use our fp_* for the gate).
    rb = S.report_block(r, "cell")

    return {
        "fp_full_sharpe": round(fp_full, 4),       # THE GATE METRIC
        "fp_oos_sharpe": round(fp_oos, 4),
        "fp_is_sharpe": round(fp_is, 4),
        "is_oos_gap": round(fp_is - fp_oos, 4),
        "engine_full_sharpe_popvar": round(st["sharpe"], 4),  # cross-check
        "full_cagr_pct": round(rb["full"]["cagr_pct"], 2),
        "full_maxdd_pct": round(rb["full"]["maxdd_pct"], 2),
        "full_vol_pct": round(rb["full"]["vol_pct"], 2),
        "oos_maxdd_pct": round(rb["oos_2019_today"]["maxdd_pct"], 2),
        "win_rate_pct": round(_win_rate(ds, eq), 2),
        "avg_weight": round(st["avg_weight"], 4),
        "n_rebalances": st["n_rebalances"],
        "n_days": n_full,
        "overlay_active": active,
        "rolling_3y": _rolling_window_sharpes(ds, eq),
        "passes_gate": fp_full >= GATE,
    }


def main():
    out: Dict = {"gate": GATE, "baseline": {}, "threshold_sweep": {},
                 "magnitude_subsweep": {}, "window_robustness": {}}

    # ---- BASELINE (multiplier = none) ----
    base = S.run_voltarget_with_multiplier(VolTargetParams(**BASE_P), multiplier_fn=None)
    bds, beq = base["strategy"]["dates"], base["strategy"]["equity"]
    fp_b, _ = _fp_sharpe_from_equity(bds, beq)
    fp_b_oos, _ = _fp_sharpe_from_equity(bds, beq, OOS_START, "2099-12-31")
    fp_b_is, _ = _fp_sharpe_from_equity(bds, beq, "2010-01-01", IS_END)
    rbb = S.report_block(base, "baseline")
    out["baseline"] = {
        "fp_full_sharpe": round(fp_b, 4), "fp_oos_sharpe": round(fp_b_oos, 4),
        "fp_is_sharpe": round(fp_b_is, 4),
        "full_cagr_pct": round(rbb["full"]["cagr_pct"], 2),
        "full_maxdd_pct": round(rbb["full"]["maxdd_pct"], 2),
        "win_rate_pct": round(_win_rate(bds, beq), 2),
        "rolling_3y": _rolling_window_sharpes(bds, beq),
        "passes_gate": fp_b >= GATE,
    }
    print(">>> BASELINE fp_full_sharpe %.4f (gate %.2f)  maxDD %.1f%%  win%% %.1f"
          % (fp_b, GATE, rbb["full"]["maxdd_pct"], out["baseline"]["win_rate_pct"]), flush=True)

    # ---- MAIN THRESHOLD SWEEP: 5 thresholds x 2 fields x 2 shapes ----
    thresholds = [(0.10, 0.90), (0.15, 0.85), (0.20, 0.80), (0.25, 0.75), (0.30, 0.70)]
    fields = ["lev_net", "deal_net"]
    shapes = {"caution(1.0/0.5)": (1.0, 0.5), "boost(1.25/0.5)": (1.25, 0.5)}

    for field in fields:
        for sname, (lm, cm) in shapes.items():
            for (lo, hi) in thresholds:
                key = "%s|%s|%02d-%02d" % (field, sname, int(lo * 100), int(hi * 100))
                cell = eval_cell(field, lo, hi, lm, cm, pct_window=52)
                out["threshold_sweep"][key] = cell
                print("   %-34s fpFull %.4f %s | OOS %.4f | maxDD %.1f%% | win%% %.1f | active(b/c) %d/%d"
                      % (key, cell["fp_full_sharpe"], "PASS" if cell["passes_gate"] else "    ",
                         cell["fp_oos_sharpe"], cell["full_maxdd_pct"], cell["win_rate_pct"],
                         cell["overlay_active"]["boost_days"], cell["overlay_active"]["caution_days"]),
                      flush=True)

    # ---- MAGNITUDE SUB-SWEEP on lev_net at the best-looking thresholds ----
    # (lev_net is the validated working field; sweep boost/caution strength.)
    print(">>> MAGNITUDE sub-sweep (lev_net, 20/80) ...", flush=True)
    for lm in [1.0, 1.25, 1.5]:
        for cm in [0.5, 0.75]:
            key = "lev_net|20-80|boost%.2f|caut%.2f" % (lm, cm)
            cell = eval_cell("lev_net", 0.20, 0.80, lm, cm, pct_window=52)
            out["magnitude_subsweep"][key] = cell
            print("   %-36s fpFull %.4f %s | OOS %.4f | maxDD %.1f%%"
                  % (key, cell["fp_full_sharpe"], "PASS" if cell["passes_gate"] else "    ",
                     cell["fp_oos_sharpe"], cell["full_maxdd_pct"]), flush=True)

    # ---- PERCENTILE-WINDOW robustness on the validated config ----
    print(">>> WINDOW robustness (lev_net, 20/80, boost 1.25/0.5) ...", flush=True)
    for w in [26, 52, 78]:
        key = "lev_net|20-80|boost1.25/0.5|win%dw" % w
        cell = eval_cell("lev_net", 0.20, 0.80, 1.25, 0.5, pct_window=w)
        out["window_robustness"][key] = cell
        print("   %-40s fpFull %.4f %s | OOS %.4f | maxDD %.1f%%"
              % (key, cell["fp_full_sharpe"], "PASS" if cell["passes_gate"] else "    ",
                 cell["fp_oos_sharpe"], cell["full_maxdd_pct"]), flush=True)

    # ---- best cell across the full sweep ----
    allcells = {**out["threshold_sweep"], **out["magnitude_subsweep"], **out["window_robustness"]}
    best_key = max(allcells, key=lambda k: allcells[k]["fp_full_sharpe"])
    out["best_cell"] = {"key": best_key, **allcells[best_key]}
    any_pass = [k for k, c in allcells.items() if c["passes_gate"]]
    out["passing_cells"] = any_pass
    print("")
    print(">>> BEST: %s  fpFull %.4f (baseline %.4f, gate %.2f)"
          % (best_key, allcells[best_key]["fp_full_sharpe"], fp_b, GATE))
    print(">>> CELLS PASSING GATE (>=1.0): %s" % (any_pass if any_pass else "NONE"))

    with open("reports/_cot_percentile_wf_sweep.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("wrote reports/_cot_percentile_wf_sweep.json")
    return out


if __name__ == "__main__":
    main()
