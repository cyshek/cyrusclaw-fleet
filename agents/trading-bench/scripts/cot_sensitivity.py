import sys
sys.path.insert(0, '/home/azureuser/.openclaw/agents/trading-bench/workspace')
import importlib.util

spec = importlib.util.spec_from_file_location(
    'backtest_combo',
    '/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/tqqq_cot_combo/backtest_combo.py'
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

IS_END = '2017-12-31'
OOS_START = '2018-01-01'
END = '2026-06-08'
print('scale  OOS_ret   OOS_Sharpe  OOS_maxDD  Full_ret   Full_Sharpe')
print('-' * 62)
for scale in [0.0, 0.25, 0.50, 0.75, 1.0]:
    r = mod.run_combo_backtest(cot_scale_bearish=scale)
    sw_oos = mod.subwindow_stats(r, OOS_START, END, 'OOS')
    sw_full = mod.subwindow_stats(r, r['dates'][0], END, 'Full')
    print(f"{scale:.2f}  {sw_oos['return_pct']:>7.1f}%  {sw_oos['sharpe']:>10.3f}  {sw_oos['max_dd_pct']:>9.1f}%  {sw_full['return_pct']:>8.1f}%  {sw_full['sharpe']:>11.3f}")
