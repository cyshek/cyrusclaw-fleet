"""Hold-the-Dip audit — three-way A/B driver (2026-06-26).

Compares, on the SAME SPY path with the standard CostModel + walk_forward:
  - rsi_oversold_spy            (live parent, dip-buy)
  - rsi_oversold_spy_trendgate  (a) dip-buy gated by daily SMA-200
  - rsi_oversold_spy_momflip    (b) momentum-entry flip (buy strength)

Outputs a JSON datapack to stdout (median Sharpe / median return / %positive /
%beat-BH-SPY / total trades / per-window detail) so the verdict can be written
from real numbers. NO files in strategies/ are modified; this only READS via
walk_forward. Protected runner files are untouched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.walk_forward import (  # noqa: E402
    walk_forward, passes_mutation_gate, passes_fitness_gate,
)

VARIANTS = [
    ("parent_dipbuy", "rsi_oversold_spy"),
    ("a_trendgate", "rsi_oversold_spy_trendgate"),
    ("b_momflip", "rsi_oversold_spy_momflip"),
]

out = {"audit": "hold_the_dip", "variants": {}}
parent_agg = None

for tag, name in VARIANTS:
    agg = walk_forward(name)
    per_window = []
    for w in agg.windows:
        bt = w.backtest
        per_window.append({
            "label": w.label, "regime": w.regime,
            "n_trades": bt.n_trades,
            "return_pct": round(bt.total_return_pct * 100, 3),
            "sharpe": round(bt.sharpe, 3),
            "bh_spy_pct": round(w.bh_spy_return_pct * 100, 3),
            "beats_bh": bool(w.beats_bh_spy),
        })
    summary = {
        "median_return_pct": round(agg.median_return_pct, 3),
        "mean_return_pct": round(agg.mean_return_pct, 3),
        "median_sharpe": round(agg.median_sharpe, 4),
        "pct_positive": round(agg.pct_positive, 3),
        "pct_beat_bh_spy": round(agg.pct_beat_bh_spy, 3),
        "total_trades": agg.total_trades,
        "n_windows_with_data": agg.n_windows_with_data,
        "worst_return_pct": round(min((w["return_pct"] for w in per_window), default=0.0), 3),
        "best_return_pct": round(max((w["return_pct"] for w in per_window), default=0.0), 3),
    }
    if tag == "parent_dipbuy":
        parent_agg = agg
    # Does this variant clear the absolute fitness gate? And (for variants)
    # does it pass the mutation gate vs the parent (beat/not-degrade)?
    gate = {}
    try:
        abs_ok, abs_reason = passes_fitness_gate(agg)
        gate["passes_fitness_gate_absolute"] = bool(abs_ok)
        gate["fitness_reason"] = abs_reason
        if tag == "parent_dipbuy":
            gate["note"] = "parent baseline"
        else:
            ok, reason = passes_mutation_gate(agg, parent_agg)
            gate["passes_mutation_gate_vs_parent"] = bool(ok)
            gate["mutation_reason"] = reason
    except Exception as e:  # pragma: no cover
        gate = {"error": repr(e)}
    out["variants"][tag] = {"strategy": name, "summary": summary,
                            "gate": gate, "per_window": per_window}

print(json.dumps(out, indent=2))
