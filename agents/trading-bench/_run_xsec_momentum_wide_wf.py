"""Driver: universe-expansion sensitivity on the PROMOTED 12-1 cross-asset
momentum strategy (xsec_momentum_xa_38d2b2).

EXACT same decide_xsec logic. Vary ONLY the universe + top_k.
Consumer-only: imports runner modules, never mutates them.

Universes (all symbols have Alpaca data from 2020-07-27):
  U6  (promoted baseline): SPY EFA TLT VNQ DBC GLD                       K=2
  U9  : + IWM HYG EEM                                                    K=3
  U12 : + SLV UUP TIP                                                    K=4
Plus K-neighbors for sensitivity.

For each (universe, K):
  - full-period contiguous backtest_xsec (2020-07-27 -> 2026-05-28)
  - walk-forward across 8 NAMED_WINDOWS (+400d warmup) -> Bar A #1, fitness gate
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner import bars_cache
from runner.backtest import CostModel
from runner.backtest_xsec import backtest_xsec
from runner.walk_forward_xsec import walk_forward_xsec, passes_fitness_gate_xsec

# Load decide_xsec from the CANDIDATE dir (not strategies/).
CAND = WORKSPACE / "strategies_candidates" / "xsec_momentum_wide_7c4a1f" / "strategy.py"
spec = importlib.util.spec_from_file_location("_wide_strategy", CAND)
mod = importlib.util.module_from_spec(spec)
sys.modules["_wide_strategy"] = mod
spec.loader.exec_module(mod)
decide_xsec = mod.decide_xsec

U6 = ["SPY", "EFA", "TLT", "VNQ", "DBC", "GLD"]
U9 = U6 + ["IWM", "HYG", "EEM"]
U12 = U9 + ["SLV", "UUP", "TIP"]

# (label, basket, top_k)
CONFIGS = [
    ("U6_K2_promoted", U6, 2),
    ("U9_K3", U9, 3),
    ("U9_K2", U9, 2),
    ("U12_K4", U12, 4),
    ("U12_K3", U12, 3),
    ("U12_K5", U12, 5),
]

FULL_END = datetime(2026, 5, 28, tzinfo=timezone.utc)
FULL_DAYS = 3000  # ~2020-07 -> 2026-05 covers all bars


def base_params(basket, top_k):
    return {
        "basket": list(basket),
        "timeframe": "1Day",
        "max_notional_usd": 100,
        "notional_usd": 100,
        "lookback_bars": 252,
        "skip_bars": 21,
        "top_k": top_k,
        "xsec_basket_size": top_k,
        "use_regime_filter": False,
        "regime_sma_period": 50,
        "safety_max_loss_pct": -50.0,
    }


def run_full_period(basket, params):
    cm = CostModel.alpaca_stocks()
    bars_by = {}
    for sym in basket:
        b = bars_cache.get_bars(sym, "1Day", days=FULL_DAYS, end_dt=FULL_END)
        if b:
            bars_by[sym] = b
    bt = backtest_xsec("wide_full", bars_by, params,
                       decide_xsec_fn=decide_xsec, default_cost_model=cm)
    # per-symbol contribution
    contrib = {}
    for sym, ps in bt.per_symbol.items():
        if ps.n_buys or ps.n_closes or ps.realized_pnl_usd:
            contrib[sym] = {
                "buys": ps.n_buys, "closes": ps.n_closes,
                "realized_pnl": round(ps.realized_pnl_usd, 2),
                "final_mv": round(ps.final_market_value, 2),
            }
    return bt, contrib


def run_wf(basket, params):
    agg = walk_forward_xsec(
        "wide_wf", basket, params=params, decide_xsec_fn=decide_xsec,
        warmup_days=400)
    passed, reason = passes_fitness_gate_xsec(agg)
    return agg, passed, reason


def main():
    out = {"configs": []}
    for label, basket, k in CONFIGS:
        p = base_params(basket, k)
        bt, contrib = run_full_period(basket, p)
        agg, fit_pass, fit_reason = run_wf(basket, p)
        # per-window rows
        rows = [w.to_row() for w in agg.windows]
        entry = {
            "label": label, "N": len(basket), "top_k": k,
            "basket": basket,
            "fp_sharpe": round(bt.sharpe, 3),
            "fp_return_pct": round(bt.total_return_pct * 100, 3),
            "fp_maxdd_pct": round(bt.max_drawdown_pct * 100, 3),
            "fp_maxdd_usd": round(bt.max_drawdown_pct * bt.starting_equity, 2),
            "fp_trades": bt.n_trades,
            "fp_buys": bt.n_buys, "fp_closes": bt.n_closes,
            "fp_clamps": bt.n_basket_clamps,
            "fp_n_ticks": bt.n_ticks,
            "fp_costs": round(bt.total_costs_usd, 3),
            "wf_med_ret": round(agg.median_return_pct, 3),
            "wf_med_sharpe": round(agg.median_sharpe, 3),
            "wf_pos_pct": round(agg.pct_positive * 100, 0),
            "wf_beatbh_pct": round(agg.pct_beat_bh_basket * 100, 0),
            "wf_trades": agg.total_trades,
            "wf_med_bull": agg.median_return_bull,
            "wf_med_chop": agg.median_return_chop,
            "wf_med_bear": agg.median_return_bear,
            "wf_bar_a1_pass": agg.bar_a_bullet1_pass,
            "wf_bar_a1_reason": agg.bar_a_bullet1_reason,
            "fit_pass": fit_pass, "fit_reason": fit_reason,
            "contrib": contrib,
            "windows": rows,
        }
        out["configs"].append(entry)
        print(f"{label:16s} N={len(basket)} K={k} | "
              f"FP Sharpe={bt.sharpe:5.2f} ret={bt.total_return_pct*100:+6.2f}% "
              f"DD={bt.max_drawdown_pct*100:5.2f}% tr={bt.n_trades:3d} | "
              f"WF medRet={agg.median_return_pct:+.2f}% medSh={agg.median_sharpe:+.2f} "
              f"pos={agg.pct_positive*100:.0f}% BarA1={'P' if agg.bar_a_bullet1_pass else 'F'} "
              f"FIT={'P' if fit_pass else 'F'}",
              file=sys.stderr)
    Path("/tmp/xsec_wide_wf.json").write_text(json.dumps(out, indent=2, default=str))
    print("wrote /tmp/xsec_wide_wf.json", file=sys.stderr)


if __name__ == "__main__":
    main()
