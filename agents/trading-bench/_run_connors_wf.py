"""Run walk-forward on the two Connors RSI(2) candidates and dump JSON.

Quarantined candidates are loaded via importlib.util (mirrors
runner/reeval_candidates.py) so they need not live under strategies/.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

from runner.walk_forward import walk_forward, passes_fitness_gate  # noqa: E402

OUT = WS / "connors_rsi2_wf_result.json"
CANDIDATES = ["connors_rsi2_spy", "connors_rsi2_qqq"]


def load(name: str):
    d = WS / "strategies_candidates" / name
    spec = importlib.util.spec_from_file_location(f"cand_{name}", d / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((d / "params.json").read_text())
    return mod, params


def main():
    out = {}
    for name in CANDIDATES:
        print(f"== {name} ==", file=sys.stderr)
        mod, params = load(name)
        agg = walk_forward(name, params=params, decide_fn=mod.decide)
        gated, reason = passes_fitness_gate(agg)
        windows = []
        for w in agg.windows:
            bt = w.backtest
            windows.append({
                "label": w.label,
                "regime": w.regime,
                "end_date": w.end_date,
                "days": w.days,
                "n_bars": bt.n_bars,
                "n_trades": bt.n_trades,
                "return_pct": bt.total_return_pct * 100,
                "sharpe": bt.sharpe,
                "max_dd_pct": bt.max_drawdown_pct * 100,
                "bh_spy_pct": w.bh_spy_return_pct * 100,
                "beats_bh_spy": w.beats_bh_spy,
            })
        out[name] = {
            "symbol": params["symbol"],
            "n_windows": agg.n_windows,
            "n_windows_with_data": agg.n_windows_with_data,
            "median_return_pct": agg.median_return_pct,
            "pct_positive": agg.pct_positive,
            "pct_beat_bh_spy": agg.pct_beat_bh_spy,
            "median_sharpe": agg.median_sharpe,
            "worst": {"label": agg.worst_window_label, "pct": agg.worst_return_pct},
            "best": {"label": agg.best_window_label, "pct": agg.best_return_pct},
            "total_trades": agg.total_trades,
            "fitness_gate_pass": gated,
            "fitness_gate_reason": reason,
            "windows": windows,
        }
        print(f"  windows={agg.n_windows_with_data}/{agg.n_windows} "
              f"medRet={agg.median_return_pct:+.2f}% "
              f"pos={agg.pct_positive*100:.0f}% "
              f"beatBH={agg.pct_beat_bh_spy*100:.0f}% "
              f"medSharpe={agg.median_sharpe:.2f} "
              f"trades={agg.total_trades} "
              f"GATE={'PASS' if gated else 'FAIL'} ({reason})",
              file=sys.stderr)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
