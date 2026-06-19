"""Diagnostics for macro_regime_long:
 (1) what the macro regime actually IS at each named-window end date (and across
     the window) — to show whether the signal even flips within 90 days;
 (2) a CONTINUOUS long backtest over the full 2022->2026 period on QQQ 1Day bars
     with the macro gate, vs buy-and-hold QQQ and buy-and-hold SPY on the SAME
     path (the real mission: beat-SPX-raw on the path actually traded).
No lookahead: macro is resolved via macro_cache (lagged) at each bar's date.
"""
import sys, json, importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path

from runner import macro_cache, bars_cache
from runner.backtest import backtest, CostModel

WS = Path(".").resolve()
cand_dir = WS / "strategies_candidates" / "macro_regime_long"
spec = importlib.util.spec_from_file_location("cand_macro_regime_long", cand_dir / "strategy.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["cand_macro_regime_long"] = mod
spec.loader.exec_module(mod)
params = json.loads((cand_dir / "params.json").read_text())

print("=== (1) Macro regime sampled monthly 2022-01 -> 2026-06 (PIT, lagged) ===")
print(" date        liq_slope($M)   curve(10y2y)  risk_on")
d = datetime(2022, 1, 1, tzinfo=timezone.utc)
end = datetime(2026, 6, 1, tzinfo=timezone.utc)
flips = 0
prev = None
while d <= end:
    ds = d.strftime("%Y-%m-%d")
    ls = macro_cache.liq_slope_asof(ds, 13, 9)
    cv = macro_cache.curve_spread_asof(ds, 0)
    if ls is None or cv is None:
        ron = None
    else:
        ron = (ls >= 0.0) and (cv > -0.5)
    if prev is not None and ron is not None and ron != prev:
        flips += 1
    prev = ron if ron is not None else prev
    ls_s = f"{ls:>13,.0f}" if ls is not None else "         None"
    cv_s = f"{cv:>+7.2f}" if cv is not None else "   None"
    print(f" {ds}  {ls_s}   {cv_s}      {ron}")
    # step ~1 month
    d = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
print(f"\n  regime flips over the 4.4y monthly grid: {flips}")

print("\n=== (2) CONTINUOUS daily backtest 2022-01-03 -> 2026-06-05 on QQQ 1Day ===")
end_dt = datetime(2026, 6, 6, tzinfo=timezone.utc)
days = (end_dt - datetime(2022, 1, 1, tzinfo=timezone.utc)).days + 5
# daily params (same gate, daily cadence so the slow signal has room to act)
dparams = dict(params)
dparams["timeframe"] = "1Day"

qqq = bars_cache.get_bars("QQQ", "1Day", days=days, end_dt=end_dt)
spy = bars_cache.get_bars("SPY", "1Day", days=days, end_dt=end_dt)
print(f"  QQQ daily bars: {len(qqq) if qqq else 0}  SPY daily bars: {len(spy) if spy else 0}")
if qqq:
    print(f"  span: {qqq[0]['t'][:10]} -> {qqq[-1]['t'][:10]}")

cm = CostModel.alpaca_stocks()
bt = backtest("macro_regime_long_daily", qqq, dparams, decide_fn=mod.decide, cost_model=cm)

# Raw buy-and-hold on the SAME path, fee-modeled, FULL notional (apples-to-apples
# "did the macro overlay beat just holding"). We compare PRICE returns (exposure
# normalized): strategy deploys 100/1000 = 0.1x, so to compare the overlay's
# market-timing skill we report BOTH the bench-scaled equity return AND the
# implied full-exposure return.
def bh_price_ret(bars):
    if not bars or len(bars) < 2:
        return 0.0
    return (cm.sell_fill_price(float(bars[-1]['c'])) - cm.buy_fill_price(float(bars[0]['c']))) / cm.buy_fill_price(float(bars[0]['c']))

qqq_bh = bh_price_ret(qqq)
spy_bh = bh_price_ret(spy)

# Strategy equity return is on 1000 cash w/ 100 notional -> 0.1x exposure.
# Implied full-exposure return = equity_return / 0.1 (only valid because it's
# single-name long/flat; this is the time-in-market-adjusted comparison).
strat_eq_ret = bt.total_return_pct
implied_full = strat_eq_ret * (1000.0 / dparams["notional_usd"])

print(f"\n  macro overlay (bench-scale, $100 notional / $1000 eq):")
print(f"    total_return_pct (equity) : {strat_eq_ret*100:+.2f}%")
print(f"    implied FULL-exposure ret  : {implied_full*100:+.2f}%   (= equity_ret / 0.1)")
print(f"    sharpe                     : {bt.sharpe:.2f}")
print(f"    max_drawdown_pct           : {bt.max_drawdown_pct*100:.2f}%")
print(f"    n_trades                   : {bt.n_trades}  (buys={bt.n_buys} closes={bt.n_closes})")
print(f"    final_position_qty         : {bt.final_position_qty:.4f}")
print(f"\n  RAW buy-and-hold over SAME path (full-exposure price return, fee-modeled):")
print(f"    QQQ B&H : {qqq_bh*100:+.2f}%")
print(f"    SPY B&H : {spy_bh*100:+.2f}%")
print(f"\n  => beat-SPX-raw (full-exposure overlay vs SPY B&H)? "
      f"{implied_full > spy_bh}   ({implied_full*100:+.2f}% vs {spy_bh*100:+.2f}%)")
print(f"  => beat-QQQ-raw (full-exposure overlay vs QQQ B&H)? "
      f"{implied_full > qqq_bh}   ({implied_full*100:+.2f}% vs {qqq_bh*100:+.2f}%)")

# time in market
days_long = sum(1 for q in bt.equity_curve)  # not exact; report trades instead
print(f"\n  (time-in-market proxy: {bt.n_buys} entries, {bt.n_closes} exits over {len(qqq)} daily bars)")
