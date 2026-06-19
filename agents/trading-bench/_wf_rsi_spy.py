"""One-shot walk-forward runner for strategies_candidates/rsi_mean_revert_spy.

Loads the candidate strategy directly (bypassing strategies/ loader) and
runs it through the full named-window walk-forward + fitness gate.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE))

from runner.walk_forward import (
    NAMED_WINDOWS, walk_forward, passes_fitness_gate, format_per_strategy_md,
)
from runner.backtest import CostModel

CAND_DIR = WORKSPACE / "strategies_candidates" / "rsi_mean_revert_spy"

# Load candidate module by file path.
spec = importlib.util.spec_from_file_location(
    "rsi_mean_revert_spy_strategy", CAND_DIR / "strategy.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

params = json.loads((CAND_DIR / "params.json").read_text())

print(f"Loaded candidate: symbol={params['symbol']} timeframe={params['timeframe']}")
print(f"Params: rsi_period={params['rsi_period']} buy_below={params['buy_below']} exit_above={params['exit_above']}")
print(f"Cost model: CostModel.alpaca_stocks() => {CostModel.alpaca_stocks()}")
print()

agg = walk_forward(
    strategy_name="rsi_mean_revert_spy",
    params=params,
    windows=NAMED_WINDOWS,
    cost_model=CostModel.alpaca_stocks(),
    decide_fn=mod.decide,
)

print(format_per_strategy_md(agg))

passed, reason = passes_fitness_gate(agg)
print()
print(f"FITNESS GATE: {'PASS' if passed else 'FAIL'}")
print(f"Reason: {reason}")
print()
print(f"Median return: {agg.median_return_pct:+.3f}%")
print(f"% windows positive: {agg.pct_positive*100:.0f}%")
print(f"% beat BH-SPY: {agg.pct_beat_bh_spy*100:.0f}%")
print(f"Median Sharpe: {agg.median_sharpe:.2f}")
print(f"Total trades: {agg.total_trades}")

# Write per-window JSON for the report.
out = {
    "strategy": "rsi_mean_revert_spy",
    "params": params,
    "windows": [w.to_row() for w in agg.windows],
    "n_windows_with_data": agg.n_windows_with_data,
    "median_return_pct": agg.median_return_pct,
    "pct_positive": agg.pct_positive,
    "pct_beat_bh_spy": agg.pct_beat_bh_spy,
    "median_sharpe": agg.median_sharpe,
    "worst": {"label": agg.worst_window_label, "pct": agg.worst_return_pct},
    "best": {"label": agg.best_window_label, "pct": agg.best_return_pct},
    "total_trades": agg.total_trades,
    "fitness_gate_passed": passed,
    "fitness_gate_reason": reason,
}
out_path = CAND_DIR / "walk_forward_result.json"
out_path.write_text(json.dumps(out, indent=2))
print(f"\nWrote: {out_path}")
