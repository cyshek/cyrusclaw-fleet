"""Robustness stress on the ens_sma_breadth winner (the only gate-passing
ensemble). Skeptical-of-own-output checks:

  1. HORIZON-SET robustness: does the OOS Sharpe-bump + DD-reduction survive
     nearby SMA window triples (not just {50,100,200})? If only the exact
     triple works = overfit knife-edge.
  2. SUB-WINDOW stability: per-year OOS FP-Sharpe + maxDD, baseline vs ensemble.
     Is the DD win broad or one-event?
  3. A 2-horizon and 4-horizon variant (is "3" special, or is gradeated
     breadth monotonically helpful?).
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List

sys.path.insert(0, ".")
sys.path.insert(0, "strategies_candidates/leveraged_long_trend")

import _ensemble_trend_driver as E


def make_sma_breadth(windows: List[int]):
    def g(under_closes):
        if not under_closes:
            return 0.0
        last = under_closes[-1]
        agree = 0
        for w in windows:
            s = E._sma(under_closes, w)
            if s is not None and last > s:
                agree += 1
        return agree / len(windows)
    return g


def main():
    p = E.base_params()
    base_oos = E.simulate(E.sma200_binary, p, start=E.OOS_START)
    print(f"baseline_sma200 OOS: fpS={base_oos['fp_sharpe']:.3f} maxDD={base_oos['maxdd_pct']:.2f}%")

    print("\n[1] HORIZON-SET robustness (OOS 2018-2026):")
    triples = [
        [50, 100, 200], [40, 100, 200], [60, 120, 200], [50, 100, 150],
        [50, 125, 250], [30, 90, 180], [75, 150, 250], [20, 100, 200],
    ]
    horizon_rows = []
    for tr in triples:
        oos = E.simulate(make_sma_breadth(tr), p, start=E.OOS_START)
        cano = E.simulate(make_sma_breadth(tr), p, start=E.OOS_START, lag_extra=1)
        d = oos["fp_sharpe"] - base_oos["fp_sharpe"]
        ddc = base_oos["maxdd_pct"] - oos["maxdd_pct"]
        beats = d > 0 and abs(oos["fp_sharpe"] - cano["fp_sharpe"]) <= 0.10
        horizon_rows.append({"triple": tr, "oos_fpS": oos["fp_sharpe"],
                             "d": d, "ddc": ddc, "canary_robust_beat": beats})
        print(f"  {str(tr):20s} OOS fpS={oos['fp_sharpe']:.3f} d={d:+.3f} "
              f"DD={oos['maxdd_pct']:.2f}% (Δ{ddc:+.2f}pp) canary={cano['fp_sharpe']:.3f} "
              f"{'BEAT' if beats else '----'}")
    n_beat = sum(1 for r in horizon_rows if r["canary_robust_beat"])
    print(f"  --> {n_beat}/{len(triples)} horizon-triples are canary-robust OOS beats")

    print("\n[2] PER-YEAR OOS stability (baseline vs {50,100,200} ensemble):")
    ens = make_sma_breadth([50, 100, 200])
    for yr in range(2018, 2027):
        s = f"{yr}-01-01"; e = f"{yr}-12-31"
        b = E.simulate(E.sma200_binary, p, start=s, end=e)
        x = E.simulate(ens, p, start=s, end=e)
        print(f"  {yr}: base fpS={b['fp_sharpe']:+.2f} DD={b['maxdd_pct']:6.2f}%  |  "
              f"ens fpS={x['fp_sharpe']:+.2f} DD={x['maxdd_pct']:6.2f}%  |  ret base={b['total_ret_pct']:+6.1f}% ens={x['total_ret_pct']:+6.1f}%")

    print("\n[3] N-horizon graduation (OOS):")
    for windows in [[100, 200], [50, 100, 200], [50, 100, 150, 200], [50, 100, 150, 200, 250]]:
        oos = E.simulate(make_sma_breadth(windows), p, start=E.OOS_START)
        d = oos["fp_sharpe"] - base_oos["fp_sharpe"]
        print(f"  {len(windows)}-horizon {str(windows):26s} OOS fpS={oos['fp_sharpe']:.3f} d={d:+.3f} DD={oos['maxdd_pct']:.2f}%")

    json.dump({"horizon_rows": horizon_rows}, open("_ensemble_robustness.json", "w"),
              indent=2, default=str)
    print("\nwrote _ensemble_robustness.json")


if __name__ == "__main__":
    main()
