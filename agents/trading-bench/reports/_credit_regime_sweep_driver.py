"""One-shot sweep driver for the credit-regime (family A) cross-asset timer.

Runs the NEW harness (runner.sweep.run_sweep) over a lookback x band grid on
the single-symbol credit_regime_spy_hyglqd candidate, plus a HYG-vs-SPY
divergence variant via the credit_num/credit_den knobs. Prints the ranked
markdown table + a per-config vs BH-SPY comparison. Throwaway analysis script
(reports/_*.py convention); imports the public harness API only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest import CostModel
from runner.sweep import SweepSpec, run_sweep
from runner.walk_forward import walk_forward, NAMED_WINDOWS
from runner.fp_sharpe import fp_continuous_sharpe


def _load(cdir_name):
    cdir = WS / "strategies_candidates" / cdir_name
    spec = importlib.util.spec_from_file_location(
        f"cand_{cdir_name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod, params


def bh_spy_full_span():
    """BH-SPY across the SAME concatenated walk-forward span: FP-cont Sharpe +
    total return. Built by running buy_and_hold over each named window and
    concatenating equity returns (same construction the harness uses)."""
    from runner.backtest import backtest
    bh_params = {"symbol": "SPY", "timeframe": "1Day", "notional_usd": 1000.0}

    def bh_decide(ms, ps, p):
        from dataclasses import dataclass
        sym = p.get("symbol", "SPY")
        pos = ps.get(sym)
        hq = float(pos.get("qty", 0)) if pos else 0.0
        class A: pass
        a = A(); a.symbol = sym; a.qty = None; a.reason = ""
        if hq > 0:
            a.action = "hold"; a.notional_usd = 0.0
        else:
            a.action = "buy"; a.notional_usd = 1000.0
        return a

    agg = walk_forward("bh_spy_fullspan", params=bh_params, decide_fn=bh_decide,
                       windows=NAMED_WINDOWS, cost_model=CostModel.alpaca_stocks())
    fps, n = fp_continuous_sharpe(agg.windows, timeframe="1Day", is_crypto=False)
    tot = 0.0
    for w in agg.windows:
        tot += w.backtest.total_return_pct
    return fps, tot * 100.0, agg


def run_family(cdir_name, grid, label):
    mod, base = _load(cdir_name)
    spec = SweepSpec(
        family="single",
        decide_fn=mod.decide,
        base_params=base,
        grid=grid,
        strategy_label=label,
        cost_model=CostModel.alpaca_stocks(),
    )
    report = run_sweep(spec, verbose=True)
    print(report.to_markdown())
    # per-config vs BH-SPY total-return comparison
    print("\n## Per-config total-return (sum of window returns, $1000 scale) vs BH-SPY\n")
    print("| params | FP-cont Sharpe | sum-window-ret% | n-trades |")
    print("|---|---|---|---|")
    for c in report.ranked():
        if c.error:
            continue
        # recompute sum-window-return for this cell
        params = dict(base); params.update(c.params)
        agg = walk_forward(label, params=params, decide_fn=mod.decide,
                           windows=NAMED_WINDOWS, cost_model=CostModel.alpaca_stocks())
        tot = sum(w.backtest.total_return_pct for w in agg.windows) * 100.0
        pstr = " ".join(f"{k}={v}" for k, v in c.params.items()) or "(base)"
        print(f"| {pstr} | {c.fp_cont_sharpe:+.2f} | {tot:+.2f} | {c.round_trip_count} |")
    return report


if __name__ == "__main__":
    print("=" * 70)
    print("BENCHMARK: buy-and-hold SPY across the full walk-forward span")
    bh_fps, bh_tot, bh_agg = bh_spy_full_span()
    print(f"BH-SPY  FP-cont Sharpe={bh_fps:+.3f}  sum-window-ret={bh_tot:+.2f}% "
          f"(scaled to notional/equity)")
    # per-window BH for context
    for w in bh_agg.windows:
        print(f"  {w.label}: ret {w.backtest.total_return_pct*100:+.2f}%  "
              f"sharpe {w.backtest.sharpe:+.2f}")
    print("=" * 70)

    print("\n### FAMILY A1: HYG/LQD credit-spread timer — lookback x band sweep\n")
    grid1 = {
        "signal_lookback": [20, 40, 60, 90, 120, 200],
        "band_pct": [0.0, 0.003, 0.006, 0.01],
    }
    run_family("credit_regime_spy_hyglqd", grid1, "credit_regime_hyglqd")
