"""Full-period continuous backtest for tsmom_xa_be0d7f.

Single continuous run from ~2021 (warmup) through 2026-05 so we get a
single equity curve -> full-period Sharpe, total return, MaxDD. Needed
for Bar A bullet #3 (Sharpe>=0.5) and #5(a)/(b) (FP Sharpe>=1.0,
MaxDD<=2*MAX_NOTIONAL=$200 absolute).
"""
from __future__ import annotations

import importlib
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

CAND = "tsmom_xa_be0d7f"
cand_dir = WORKSPACE / "strategies_candidates" / CAND
mod = importlib.import_module(f"strategies_candidates.{CAND}.strategy")
params = json.loads((cand_dir / "params.json").read_text())
basket = list(params["basket"])
timeframe = params["timeframe"]

# Full span: earliest window warmup-start (~2021-02) through 2026-05-25.
end_dt = datetime(2026, 5, 25, tzinfo=timezone.utc)
days = int((end_dt - datetime(2021, 1, 1, tzinfo=timezone.utc)).days) + 30

bars_by_sym = {}
for sym in basket:
    bars = bars_cache.get_bars(sym, timeframe, days=days, end_dt=end_dt)
    if bars and len(bars) >= 10:
        bars_by_sym[sym] = bars

cm = CostModel.alpaca_stocks()
bt = backtest_xsec(CAND, bars_by_sym, params, decide_xsec_fn=mod.decide_xsec,
                   default_cost_model=cm)

starting = bt.starting_equity
# Absolute USD drawdown on deployed-notional scale: equity is on $1000 base,
# but exposure is $100 notional. MaxDD in % of equity * starting gives USD
# drawdown of the $1000 book; since only $100 is deployed, scale up by 10
# to express drawdown relative to the $100 notional position (the meaningful
# capital). Report both.
maxdd_pct_equity = bt.max_drawdown_pct * 100
maxdd_usd_book = abs(bt.max_drawdown_pct) * starting  # $ on the $1000 book
# Peak deployed exposure proxy: $100 cap. DD as fraction of book * (book/notional).
maxdd_usd_notional = maxdd_usd_book  # absolute USD loss in book terms

# First/last bar dates
all_t = sorted({str(b["t"]) for bs in bars_by_sym.values() for b in bs})
span0, span1 = all_t[0][:10], all_t[-1][:10]

# BH basket full period (equal-weight, notional $100, $1000 base)
leg_rets = []
for sym, bs in bars_by_sym.items():
    buy = cm.buy_fill_price(float(bs[0]["c"]))
    sell = cm.sell_fill_price(float(bs[-1]["c"]))
    if buy > 0:
        leg_rets.append((sell - buy) / buy)
bh_avg = sum(leg_rets) / len(leg_rets) if leg_rets else 0.0
bh_book_ret_pct = bh_avg * (100.0 / starting) * 100

out = {
    "strategy": CAND,
    "span": [span0, span1],
    "n_ticks": bt.n_ticks,
    "n_trades": bt.n_trades,
    "n_buys": bt.n_buys,
    "n_closes": bt.n_closes,
    "n_basket_clamps": bt.n_basket_clamps,
    "starting_equity": starting,
    "final_equity": bt.final_equity,
    "total_return_pct_book": bt.total_return_pct * 100,
    "total_return_usd": bt.total_return_usd,
    "sharpe_full_period": bt.sharpe,
    "max_drawdown_pct_book": maxdd_pct_equity,
    "max_drawdown_usd_book": maxdd_usd_book,
    "total_costs_usd": bt.total_costs_usd,
    "bh_basket_book_ret_pct": bh_book_ret_pct,
    "per_symbol": {
        s: {"buys": ps.n_buys, "closes": ps.n_closes,
            "realized_pnl_usd": ps.realized_pnl_usd}
        for s, ps in bt.per_symbol.items()
    },
}
print(json.dumps(out, indent=2))
(WORKSPACE / f"_fp_{CAND}.json").write_text(json.dumps(out, indent=2))
