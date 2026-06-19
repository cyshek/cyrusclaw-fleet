"""Driver: walk-forward for candidate tsmom_xa_be0d7f.

Loads decide_xsec + params from strategies_candidates/ (the shared
walk_forward_xsec loader only reads strategies/, so we inject explicitly),
runs across the 8 NAMED_WINDOWS with +400d warmup (matches the lookback
needs of the 252+21 12-1 signal and the promoted winner's driver), and
emits MD + JSON.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.walk_forward_xsec import walk_forward_xsec, format_xsec_md, passes_fitness_gate_xsec

CAND = "tsmom_xa_be0d7f"
cand_dir = WORKSPACE / "strategies_candidates" / CAND

mod = importlib.import_module(f"strategies_candidates.{CAND}.strategy")
params = json.loads((cand_dir / "params.json").read_text())
basket = list(params["basket"])

WARMUP = 400

agg = walk_forward_xsec(
    CAND, basket, params=params, decide_xsec_fn=mod.decide_xsec,
    warmup_days=WARMUP)

md = format_xsec_md(agg)
(WORKSPACE / f"_wf_{CAND}.md").write_text(md)
print(md)

passed, reason = passes_fitness_gate_xsec(agg)
payload = {
    "strategy": agg.strategy,
    "basket": agg.basket,
    "warmup_days": WARMUP,
    "n_windows_with_data": agg.n_windows_with_data,
    "median_return_pct": agg.median_return_pct,
    "mean_return_pct": agg.mean_return_pct,
    "stdev_return_pct": agg.stdev_return_pct,
    "pct_positive": agg.pct_positive,
    "pct_beat_bh_basket": agg.pct_beat_bh_basket,
    "median_sharpe": agg.median_sharpe,
    "median_return_bull": agg.median_return_bull,
    "median_return_chop": agg.median_return_chop,
    "median_return_bear": agg.median_return_bear,
    "worst": {"label": agg.worst_window_label, "pct": agg.worst_return_pct},
    "best": {"label": agg.best_window_label, "pct": agg.best_return_pct},
    "total_trades": agg.total_trades,
    "fitness_gate": list(passes_fitness_gate_xsec(agg)),
    "bar_a_bullet1_pass": agg.bar_a_bullet1_pass,
    "bar_a_bullet1_reason": agg.bar_a_bullet1_reason,
    "bar_a_b_used_count": agg.bar_a_b_used_count,
    "windows": [w.to_row() for w in agg.windows],
}
(WORKSPACE / f"_wf_{CAND}.json").write_text(json.dumps(payload, indent=2))
print("\n[driver] wrote _wf_%s.md / .json" % CAND, file=sys.stderr)
