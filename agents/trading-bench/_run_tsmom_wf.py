"""Warmup-extended walk-forward for tsmom_spy_2951d463.

The strategy needs trend_lookback_days (252 trading days) + vol_lookback_days
(63 trading days) of warmup before it can fire. The standard walk_forward
harness fetches only `window_days` (60-90) per window, so we extend with
~400 calendar days of warmup (~280 trading days, safely > 252) so the
strategy's signal can actually compute inside each regime window.

Equity-curve / return % is reported over the FULL bar slice; during the
warmup region the strategy returns 'hold' so the trading metric is dominated
by the labeled regime window. This is the same pattern used by
_run_connors_wf_warmup.py for the Connors RSI(2) port.

Also runs a single long-period full backtest (2018→2026 if data permits)
for full-period stats.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from datetime import datetime, timezone
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

WARMUP_DAYS = 400
CANDIDATE = "tsmom_spy_2951d463"


def load(name: str):
    d = WS / "strategies_candidates" / name
    spec = importlib.util.spec_from_file_location(f"cand_{name}", d / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((d / "params.json").read_text())
    return mod, params


def walk_forward_with_warmup(name, params, decide_fn, warmup_days=WARMUP_DAYS):
    symbol = params.get("symbol", "")
    timeframe = str(params.get("timeframe", "1Day"))
    cost_model = CostModel.for_symbol(symbol)
    notional = float(params.get("notional_usd", 100.0))
    agg = WalkForwardAggregate(strategy=name, n_windows=len(NAMED_WINDOWS))
    rets, sharpes, beats = [], [], []
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
        rets.append(bt.total_return_pct * 100)
        sharpes.append(bt.sharpe)
        beats.append(beats_bh)
        agg.total_trades += bt.n_trades
    agg.n_windows_with_data = len(agg.windows)
    if rets:
        agg.median_return_pct = statistics.median(rets)
        agg.mean_return_pct = statistics.mean(rets)
        agg.stdev_return_pct = statistics.stdev(rets) if len(rets) >= 2 else 0.0
        agg.pct_positive = sum(1 for r in rets if r > 0) / len(rets)
        agg.pct_beat_bh_spy = sum(1 for b in beats if b) / len(beats)
        agg.median_sharpe = statistics.median(sharpes)
        wi = min(range(len(rets)), key=lambda i: rets[i])
        bi = max(range(len(rets)), key=lambda i: rets[i])
        agg.worst_return_pct = rets[wi]
        agg.best_return_pct = rets[bi]
        agg.worst_window_label = agg.windows[wi].label
        agg.best_window_label = agg.windows[bi].label
    return agg


def full_period_backtest(name, params, decide_fn, days=1800,
                          end_dt=None):
    """Run a single long backtest spanning ~5 years for full-period stats."""
    symbol = params.get("symbol", "")
    timeframe = str(params.get("timeframe", "1Day"))
    cost_model = CostModel.for_symbol(symbol)
    if end_dt is None:
        now = datetime.now(timezone.utc)
        end_dt = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    bars = bars_cache.get_bars(symbol, timeframe, days=days, end_dt=end_dt)
    bt = backtest(name, bars, params, decide_fn=decide_fn, cost_model=cost_model)
    return bt, bars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default="/tmp/tsmom_wf.md")
    ap.add_argument("--json", default="/tmp/tsmom_wf.json")
    args = ap.parse_args()

    print(f"== {CANDIDATE} (warmup +{WARMUP_DAYS}d) ==", file=sys.stderr)
    mod, params = load(CANDIDATE)

    agg = walk_forward_with_warmup(CANDIDATE, params, mod.decide)
    gated, reason = passes_fitness_gate(agg)

    # Full-period backtest
    print(f"-- full-period backtest (1800d) --", file=sys.stderr)
    fp_bt, fp_bars = full_period_backtest(CANDIDATE, params, mod.decide, days=1800)

    # Build JSON
    windows = []
    for w in agg.windows:
        bt = w.backtest
        windows.append({
            "label": w.label, "regime": w.regime, "end_date": w.end_date,
            "days_traded": w.days, "n_bars_total": bt.n_bars,
            "n_trades": bt.n_trades, "n_buys": bt.n_buys, "n_closes": bt.n_closes,
            "return_pct": bt.total_return_pct * 100,
            "sharpe": bt.sharpe,
            "max_dd_pct": bt.max_drawdown_pct * 100,
            "win_rate_pct": bt.win_rate * 100,
            "bh_spy_pct": w.bh_spy_return_pct * 100,
            "beats_bh_spy": w.beats_bh_spy,
        })
    out = {
        "candidate": CANDIDATE,
        "warmup_calendar_days": WARMUP_DAYS,
        "n_windows": agg.n_windows,
        "n_windows_with_data": agg.n_windows_with_data,
        "median_return_pct": agg.median_return_pct,
        "mean_return_pct": agg.mean_return_pct,
        "stdev_return_pct": agg.stdev_return_pct,
        "pct_positive": agg.pct_positive,
        "pct_beat_bh_spy": agg.pct_beat_bh_spy,
        "median_sharpe": agg.median_sharpe,
        "worst": {"label": agg.worst_window_label, "pct": agg.worst_return_pct},
        "best": {"label": agg.best_window_label, "pct": agg.best_return_pct},
        "total_trades": agg.total_trades,
        "fitness_gate_pass": gated,
        "fitness_gate_reason": reason,
        "windows": windows,
        "full_period": {
            "n_bars": fp_bt.n_bars,
            "n_trades": fp_bt.n_trades,
            "n_buys": fp_bt.n_buys,
            "n_closes": fp_bt.n_closes,
            "total_return_pct": fp_bt.total_return_pct * 100,
            "sharpe": fp_bt.sharpe,
            "max_dd_pct": fp_bt.max_drawdown_pct * 100,
            "win_rate_pct": fp_bt.win_rate * 100,
            "avg_trade_pnl_usd": fp_bt.avg_trade_pnl_usd,
            "total_costs_usd": fp_bt.total_costs_usd,
            "first_bar_t": (fp_bars[0].get("t") if fp_bars else None),
            "last_bar_t": (fp_bars[-1].get("t") if fp_bars else None),
        },
    }
    Path(args.json).write_text(json.dumps(out, indent=2))
    print(f"wrote {args.json}", file=sys.stderr)

    # Build MD
    lines = [f"# Walk-Forward Report: {CANDIDATE}",
             "",
             f"Warmup (extra calendar days fetched per window): **{WARMUP_DAYS}**",
             "",
             "## Per-window results",
             "",
             "| Window | Regime | Bars | Trades | Return % | Sharpe | MaxDD % | Win % | BH-SPY % | Beats BH? |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for w in windows:
        lines.append(
            f"| {w['label']} | {w['regime']} | {w['n_bars_total']} | {w['n_trades']} | "
            f"{w['return_pct']:+.2f} | {w['sharpe']:.2f} | {w['max_dd_pct']:.2f} | "
            f"{w['win_rate_pct']:.0f} | {w['bh_spy_pct']:+.2f} | "
            f"{'✅' if w['beats_bh_spy'] else '❌'} |"
        )
    lines += [
        "",
        f"**Aggregate:** median ret {agg.median_return_pct:+.2f}% · "
        f"{agg.pct_positive * 100:.0f}% windows positive · "
        f"{agg.pct_beat_bh_spy * 100:.0f}% beat BH-SPY · "
        f"median Sharpe {agg.median_sharpe:.2f} · "
        f"worst {agg.worst_return_pct:+.2f}% ({agg.worst_window_label}) · "
        f"best {agg.best_return_pct:+.2f}% ({agg.best_window_label}) · "
        f"total trades {agg.total_trades}",
        f"**Fitness gate:** {'🟢 PASS' if gated else '🔴 FAIL'} — {reason}",
        "",
        "## Full-period backtest (~1800 calendar days)",
        "",
        f"- Window: {out['full_period']['first_bar_t']} → {out['full_period']['last_bar_t']}",
        f"- Bars: {out['full_period']['n_bars']} · Trades: {out['full_period']['n_trades']} "
        f"(buys {out['full_period']['n_buys']} / closes {out['full_period']['n_closes']})",
        f"- Total return: {out['full_period']['total_return_pct']:+.2f}%",
        f"- Sharpe (annualized): {out['full_period']['sharpe']:.2f}",
        f"- Max drawdown: {out['full_period']['max_dd_pct']:.2f}%",
        f"- Win rate: {out['full_period']['win_rate_pct']:.0f}%",
        f"- Avg $/trade: ${out['full_period']['avg_trade_pnl_usd']:+.2f}",
        f"- Total costs paid: ${out['full_period']['total_costs_usd']:.2f}",
    ]
    Path(args.md).write_text("\n".join(lines))
    print(f"wrote {args.md}", file=sys.stderr)

    print(f"  windows={agg.n_windows_with_data}/{agg.n_windows} "
          f"medRet={agg.median_return_pct:+.2f}% pos={agg.pct_positive*100:.0f}% "
          f"beatBH={agg.pct_beat_bh_spy*100:.0f}% medSharpe={agg.median_sharpe:.2f} "
          f"trades={agg.total_trades} "
          f"GATE={'PASS' if gated else 'FAIL'} ({reason})", file=sys.stderr)


if __name__ == "__main__":
    main()
