"""Pre-declared sensitivity grid for tsmom_xa_be0d7f. NOT a promotion
basis (the promoted config is the canonical 252/21). Reported for honesty
so the reader knows whether the 0.98 FP Sharpe near-miss is a knife-edge
artifact of one parameter choice or robust to perturbation."""
import importlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

W = Path(__file__).resolve().parent
if str(W) not in sys.path: sys.path.insert(0, str(W))
from runner import bars_cache
from runner.backtest import CostModel
from runner.backtest_xsec import backtest_xsec

CAND = "tsmom_xa_be0d7f"
mod = importlib.import_module(f"strategies_candidates.{CAND}.strategy")
base = json.loads((W/"strategies_candidates"/CAND/"params.json").read_text())
basket = list(base["basket"]); tf = base["timeframe"]
end_dt = datetime(2026,5,25,tzinfo=timezone.utc)
days = (end_dt - datetime(2021,1,1,tzinfo=timezone.utc)).days + 30
bbs = {}
for s in basket:
    b = bars_cache.get_bars(s, tf, days=days, end_dt=end_dt)
    if b and len(b)>=10: bbs[s]=b
cm = CostModel.alpaca_stocks()

grid = [(252,21),(252,0),(189,21),(126,21),(252,42)]
print(f"{'lookback/skip':16s} {'FP Sharpe':>10s} {'ret%':>8s} {'MaxDD%':>8s} {'trades':>7s}")
for lb,sk in grid:
    p = dict(base); p["lookback_bars"]=lb; p["skip_bars"]=sk
    bt = backtest_xsec(CAND, bbs, p, decide_xsec_fn=mod.decide_xsec, default_cost_model=cm)
    print(f"{str(lb)+'/'+str(sk):16s} {bt.sharpe:>10.3f} {bt.total_return_pct*100:>8.2f} {bt.max_drawdown_pct*100:>8.2f} {bt.n_trades:>7d}")
