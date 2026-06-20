"""Param-jitter robustness check around the best-FP-Sharpe momentum variant
(6-1 monthly K5, FP-cont Sharpe +0.21, ann +8.9%/yr). Jitter ONE knob at a
time (lookback +-, K +-1, cadence +-) to confirm there is no hidden plateau
that reaches FP-cont Sharpe >= 1.0. A real edge is a plateau; this is a
basin near zero."""
import sys
from pathlib import Path
WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))
from reports._ss_momentum_driver import run, fp_continuous_sharpe, deployed_ann_return

CENTER = {"lookback_bars": 126, "skip_bars": 21, "rebalance_months": 1, "top_k": 5}
JITTERS = {
    "center 6-1 mo K5":        dict(CENTER),
    "lookback 105 (5-1)":      {**CENTER, "lookback_bars": 105},
    "lookback 147 (7-1)":      {**CENTER, "lookback_bars": 147},
    "K=4":                     {**CENTER, "top_k": 4},
    "K=6":                     {**CENTER, "top_k": 6},
    "skip 10":                 {**CENTER, "skip_bars": 10},
    "skip 42":                 {**CENTER, "skip_bars": 42},
    "quarterly (reb_months 3)":{**CENTER, "rebalance_months": 3},
}
print(f"{'jitter':<28}{'FPcont':>8}{'medWin':>8}{'ann%':>8}{'trd':>6}  >=1.0?")
for label, ov in JITTERS.items():
    agg, params = run(ov)
    fps, _ = fp_continuous_sharpe(agg)
    ann = deployed_ann_return(agg, float(params.get("notional_usd", 1000.0)))
    print(f"{label:<28}{fps:>8.2f}{agg.median_sharpe:>8.2f}{ann:>8.1f}"
          f"{agg.total_trades:>6}   {'YES' if fps>=1.0 else 'no'}")
