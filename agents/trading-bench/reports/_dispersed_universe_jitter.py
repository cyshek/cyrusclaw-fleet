"""Param-jitter robustness for the dispersed-universe momentum test.

Jitters ONE knob at a time around the strongest cell (12-1 monthly K10
decile, the best FP-cont Sharpe at +0.16) to confirm the reject is a flat
basin near zero, NOT a knife-edge tuning miss. Also includes a UNIVERSE
stress: drop the highest-idio-vol bucket (semis+biotech) to test whether the
catastrophic -86% instrument DDs (and any apparent edge) depend on the
dispersion tail. Real edge is a PLATEAU; a hindsight-fragile result collapses
under universe perturbation.
"""
from __future__ import annotations
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from _dispersed_universe_driver import (  # type: ignore
    run, fp_continuous_sharpe, deployed_ann_return, UNIVERSE,
)
from runner.walk_forward_xsec import passes_bar_a_5b

# Center cell: 12-1 monthly K10 decile.
CENTER = {"lookback_bars": 252, "skip_bars": 21, "rebalance_months": 1, "top_k": 10}

JITTERS = {
    "center (12-1 mo K10)":   {},
    "lookback 210 (~10-1)":   {"lookback_bars": 210},
    "lookback 294 (~14-1)":   {"lookback_bars": 294},
    "K=7 (tighter decile)":   {"top_k": 7},
    "K=14 (looser)":          {"top_k": 14},
    "skip 10":                {"skip_bars": 10},
    "skip 42":                {"skip_bars": 42},
    "quarterly (reb_m=3)":    {"rebalance_months": 3},
}

# Universe subset stress: drop the high-idio-vol tail (semis+biotech+TSLA/MRNA).
HIGH_IDIO = {"NVDA", "AMD", "AVGO", "QCOM", "MU", "INTC", "TXN", "AMAT", "LRCX",
             "GILD", "BIIB", "AMGN", "REGN", "VRTX", "MRNA", "TSLA"}
UNIVERSE_NO_TAIL = [s for s in UNIVERSE if s not in HIGH_IDIO]


def one(label, override, universe=None):
    ov = dict(CENTER)
    ov.update(override)
    agg, params = run(ov, universe=universe)
    fps, _ = fp_continuous_sharpe(agg)
    dd_pass, _ = passes_bar_a_5b(agg)
    ann = deployed_ann_return(agg, float(params.get("notional_usd", 1000.0)))
    print(f"{label:<30}{fps:>8.2f}{agg.median_sharpe:>9.2f}{ann:>8.1f}"
          f"{agg.total_trades:>6}{agg.worst_instrument_dd_pct:>9.2f}"
          f"{'  >=1.0!' if fps >= 1.0 else ''}")
    return fps


if __name__ == "__main__":
    print(f"{'jitter (1 knob from 12-1 mo K10)':<30}{'FPcont':>8}{'medWin':>9}{'ann%':>8}{'trd':>6}{'instrDD':>9}")
    best = -9.0
    for label, ov in JITTERS.items():
        best = max(best, one(label, ov))
    print(f"\n--- UNIVERSE STRESS: drop high-idio-vol tail (semis+biotech+TSLA/MRNA), N={len(UNIVERSE_NO_TAIL)} ---")
    print(f"{'universe subset':<30}{'FPcont':>8}{'medWin':>9}{'ann%':>8}{'trd':>6}{'instrDD':>9}")
    one("12-1 mo K10, no-idio-tail", {}, universe=UNIVERSE_NO_TAIL)
    print(f"\nBEST FP-cont Sharpe across all jitter cells: {best:+.2f} "
          f"({'PLATEAU/basin near 0 — robust reject' if best < 1.0 else 'NEEDS REVIEW'})")
