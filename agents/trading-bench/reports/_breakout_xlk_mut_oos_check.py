#!/usr/bin/env python3
"""READ-ONLY OOS check on the LIVE mutation child `breakout_xlk__mut_c382b1`.

Main's question: my combo sprint measured the BASE `breakout_xlk` signal
(OOS Sharpe -0.146, 2024-01..2026-06) — but base breakout_xlk is RETIRED from
cron. The live roster member is the mutation child `breakout_xlk__mut_c382b1`,
which adds a regime-conditional hard stop (tight -0.8% in bear / loose -2.3%
in bull). Does the LIVE mutation also show negative recent OOS, or did the
stop fix the fragility?

Method: drive the PRODUCTION backtest engine (runner/backtest.py::backtest)
on the full hourly XLK panel, split IS<=2023-12-31 / OOS>=2024-01-01, 2bps
(CostModel.alpaca_stocks). The engine natively supplies the SPY regime
double-confirm the mutation reads, with walk-forward no-lookahead slicing.
Also run the BASE breakout_xlk through the SAME engine on the SAME panel as
an apples-to-apples reference (so the comparison isn't sprint-vs-engine).

NO writes outside reports/. NO orders. NO spend. READ-only on strategies/runner.
"""
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/home/azureuser/.openclaw/agents/trading-bench/workspace")

from runner import bars_cache
from runner.backtest import backtest, CostModel, bars_per_year

SPLIT = "2024-01-01"  # IS < SPLIT <= OOS
STRATS = ["breakout_xlk__mut_c382b1", "breakout_xlk"]


def _bar_day(b):
    return str(b.get("t", ""))[:10]


def _split_bars(bars):
    is_b = [b for b in bars if _bar_day(b) < SPLIT]
    oos_b = [b for b in bars if _bar_day(b) >= SPLIT]
    return is_b, oos_b


def _stats(res):
    return {
        "sharpe": round(res.sharpe, 4),
        "total_return_pct": round(res.total_return_pct, 4),
        "max_drawdown_pct": round(res.max_drawdown_pct, 4),
        "n_trades": res.n_trades,
        "n_buys": res.n_buys,
        "n_closes": res.n_closes,
        "n_bars": res.n_bars,
        "win_rate": round(res.win_rate, 2),
        "total_costs_usd": round(res.total_costs_usd, 4),
        "final_equity": round(res.final_equity, 2),
    }


def main():
    cost = CostModel.alpaca_stocks()
    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "split": SPLIT,
        "cost": "2bps one-way (CostModel.alpaca_stocks)",
        "engine": "runner/backtest.py::backtest (production, SPY-regime aware, WF no-lookahead)",
        "bars_per_year_1Hour": bars_per_year("1Hour", False),
        "results": {},
    }

    # Pull full hourly XLK panel once (shared by both strategies).
    bars = bars_cache.get_bars("XLK", "1Hour", days=2600)
    if not bars:
        print("NO BARS for XLK 1Hour", file=sys.stderr)
        sys.exit(3)
    panel_first = _bar_day(bars[0])
    panel_last = _bar_day(bars[-1])
    out["panel"] = {"first": panel_first, "last": panel_last, "n_bars": len(bars)}

    is_b, oos_b = _split_bars(bars)
    out["panel"]["n_is_bars"] = len(is_b)
    out["panel"]["n_oos_bars"] = len(oos_b)

    for name in STRATS:
        full = backtest(name, bars, json.loads(open(
            f"strategies/{name}/params.json").read()), cost_model=cost)
        is_r = backtest(name, is_b, json.loads(open(
            f"strategies/{name}/params.json").read()), cost_model=cost)
        oos_r = backtest(name, oos_b, json.loads(open(
            f"strategies/{name}/params.json").read()), cost_model=cost)
        out["results"][name] = {
            "full": _stats(full),
            "is": _stats(is_r),
            "oos": _stats(oos_r),
        }
        print(f"{name}:")
        print(f"  FULL  S {full.sharpe:+.3f}  tot {full.total_return_pct:+.2f}%  n_tr {full.n_trades}")
        print(f"  IS    S {is_r.sharpe:+.3f}  tot {is_r.total_return_pct:+.2f}%  n_tr {is_r.n_trades}")
        print(f"  OOS   S {oos_r.sharpe:+.3f}  tot {oos_r.total_return_pct:+.2f}%  n_tr {oos_r.n_trades}  win {oos_r.win_rate:.1f}%")

    with open("reports/_breakout_xlk_mut_oos_check.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nwrote reports/_breakout_xlk_mut_oos_check.json")


if __name__ == "__main__":
    main()
