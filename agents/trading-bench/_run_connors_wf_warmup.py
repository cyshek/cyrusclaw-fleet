"""Warmup-extended walk-forward for Connors RSI(2).

The canonical Connors RSI(2) trend filter requires SMA(200) of the
underlying. Our standard walk-forward harness fetches exactly
`window_days` of bars per window (~62 trading days for a 90-day window),
which is insufficient for SMA(200) to warm up — the strategy can never
fire on canonical params under the default harness.

This script fetches `window_days + 220` calendar days of bars per
window (≈ ~155 trading days warmup + 62 trading days trading window)
and runs `backtest()` directly. Equity-curve / return % is reported
over the entire bar slice; in practice the warmup region produces only
HOLD actions so the metric is dominated by the trading region. This is
a fair-shot variant of the standalone gate, intended to answer "does
the strategy work when it actually gets to fire?"

The canonical (no-warmup) variant is also run separately by
_run_connors_wf.py; both results land in the validation report.
"""
from __future__ import annotations

import importlib.util
import json
import statistics
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

from runner import bars_cache  # noqa: E402
from runner.backtest import backtest, CostModel  # noqa: E402
from runner.walk_forward import (  # noqa: E402
    NAMED_WINDOWS,
    _benchmark_spy_return,
    WindowResult,
    WalkForwardAggregate,
    passes_fitness_gate,
)

OUT = WS / "connors_rsi2_wf_warmup_result.json"
WARMUP_DAYS = 220  # ≈ 155 trading days of warmup so SMA(200) computes
CANDIDATES = ["connors_rsi2_spy", "connors_rsi2_qqq"]


def load(name: str):
    d = WS / "strategies_candidates" / name
    spec = importlib.util.spec_from_file_location(f"cand_{name}", d / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((d / "params.json").read_text())
    return mod, params


def walk_forward_with_warmup(name: str, params: dict, decide_fn,
                              warmup_days: int = WARMUP_DAYS) -> WalkForwardAggregate:
    symbol = params.get("symbol", "")
    timeframe = str(params.get("timeframe", "1Day"))
    cost_model = CostModel.for_symbol(symbol)
    notional = float(params.get("notional_usd", 100.0))
    agg = WalkForwardAggregate(strategy=name, n_windows=len(NAMED_WINDOWS))
    returns_pct, sharpes, beats = [], [], []
    for label, end_dt, days, regime in NAMED_WINDOWS:
        full_days = days + warmup_days
        bars = bars_cache.get_bars(symbol, timeframe, days=full_days, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt = backtest(name, bars, params, decide_fn=decide_fn, cost_model=cost_model)
        bh = _benchmark_spy_return(end_dt, days, timeframe,
                                    notional_usd=notional,
                                    starting_cash=bt.starting_equity)
        beats_bh = bt.total_return_pct > bh
        wr = WindowResult(label=label, regime=regime,
                          end_date=end_dt.strftime("%Y-%m-%d"), days=days,
                          backtest=bt, bh_spy_return_pct=bh, beats_bh_spy=beats_bh)
        agg.windows.append(wr)
        returns_pct.append(bt.total_return_pct * 100)
        sharpes.append(bt.sharpe)
        beats.append(beats_bh)
        agg.total_trades += bt.n_trades
    agg.n_windows_with_data = len(agg.windows)
    if returns_pct:
        agg.median_return_pct = statistics.median(returns_pct)
        agg.mean_return_pct = statistics.mean(returns_pct)
        agg.stdev_return_pct = statistics.stdev(returns_pct) if len(returns_pct) >= 2 else 0.0
        agg.pct_positive = sum(1 for r in returns_pct if r > 0) / len(returns_pct)
        agg.pct_beat_bh_spy = sum(1 for b in beats if b) / len(beats)
        agg.median_sharpe = statistics.median(sharpes)
        worst_idx = min(range(len(returns_pct)), key=lambda i: returns_pct[i])
        best_idx = max(range(len(returns_pct)), key=lambda i: returns_pct[i])
        agg.worst_return_pct = returns_pct[worst_idx]
        agg.best_return_pct = returns_pct[best_idx]
        agg.worst_window_label = agg.windows[worst_idx].label
        agg.best_window_label = agg.windows[best_idx].label
    return agg


def main():
    out = {}
    for name in CANDIDATES:
        print(f"== {name} (warmup +{WARMUP_DAYS}d) ==", file=sys.stderr)
        mod, params = load(name)
        agg = walk_forward_with_warmup(name, params, mod.decide)
        gated, reason = passes_fitness_gate(agg)
        windows = []
        for w in agg.windows:
            bt = w.backtest
            windows.append({
                "label": w.label, "regime": w.regime, "end_date": w.end_date,
                "days_traded": w.days, "n_bars_total": bt.n_bars, "n_trades": bt.n_trades,
                "return_pct": bt.total_return_pct * 100, "sharpe": bt.sharpe,
                "max_dd_pct": bt.max_drawdown_pct * 100,
                "bh_spy_pct": w.bh_spy_return_pct * 100, "beats_bh_spy": w.beats_bh_spy,
            })
        out[name] = {
            "symbol": params["symbol"], "warmup_days": WARMUP_DAYS,
            "n_windows": agg.n_windows, "n_windows_with_data": agg.n_windows_with_data,
            "median_return_pct": agg.median_return_pct, "pct_positive": agg.pct_positive,
            "pct_beat_bh_spy": agg.pct_beat_bh_spy, "median_sharpe": agg.median_sharpe,
            "worst": {"label": agg.worst_window_label, "pct": agg.worst_return_pct},
            "best": {"label": agg.best_window_label, "pct": agg.best_return_pct},
            "total_trades": agg.total_trades,
            "fitness_gate_pass": gated, "fitness_gate_reason": reason,
            "windows": windows,
        }
        print(f"  windows={agg.n_windows_with_data}/{agg.n_windows} "
              f"medRet={agg.median_return_pct:+.2f}% pos={agg.pct_positive*100:.0f}% "
              f"beatBH={agg.pct_beat_bh_spy*100:.0f}% medSharpe={agg.median_sharpe:.2f} "
              f"trades={agg.total_trades} "
              f"GATE={'PASS' if gated else 'FAIL'} ({reason})", file=sys.stderr)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
