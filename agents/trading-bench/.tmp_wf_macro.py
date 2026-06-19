"""Ad-hoc walk-forward eval for the macro_regime_long CANDIDATE (not on the
strategies.* path). Loads the candidate module + params directly and runs the
REAL runner/walk_forward.walk_forward() + passes_fitness_gate().
"""
import sys, json, importlib.util
from pathlib import Path

from runner.walk_forward import walk_forward, passes_fitness_gate

WS = Path(".").resolve()
cand_dir = WS / "strategies_candidates" / "macro_regime_long"
spec = importlib.util.spec_from_file_location("cand_macro_regime_long", cand_dir / "strategy.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["cand_macro_regime_long"] = mod
spec.loader.exec_module(mod)
params = json.loads((cand_dir / "params.json").read_text())
print("params:", params)

agg = walk_forward("macro_regime_long", params=params, decide_fn=mod.decide)
passed, reason = passes_fitness_gate(agg)
gate = "PASS" if passed else "FAIL"
print()
print(f"windows_with_data : {agg.n_windows_with_data}/{agg.n_windows}")
print(f"median_return_pct : {agg.median_return_pct:+.3f}%")
print(f"median_sharpe     : {agg.median_sharpe:.3f}")
print(f"pct_positive      : {agg.pct_positive*100:.0f}%")
print(f"pct_beat_bh_spy   : {agg.pct_beat_bh_spy*100:.0f}%")
print(f"total_trades      : {agg.total_trades}")
print(f"worst window      : {agg.worst_window_label} {agg.worst_return_pct:+.2f}%")
print(f"best window       : {agg.best_window_label} {agg.best_return_pct:+.2f}%")
print(f"GATE              : {gate} ({reason})")
print()
print("Per-window:")
for w in agg.windows:
    bt = w.backtest
    print(f"  {w.label:24s} {w.regime:5s} bars={bt.n_bars:4d} trades={bt.n_trades:3d} "
          f"ret={bt.total_return_pct*100:+7.2f}% sharpe={bt.sharpe:+6.2f} "
          f"bhSPY={w.bh_spy_return_pct*100:+6.2f}% beats={w.beats_bh_spy}")
