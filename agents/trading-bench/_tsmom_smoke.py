import json
import _tsmom_engine as E

CORE4 = ['DBC', 'GLD', 'TLT', 'UUP']
res = E.run_tsmom(CORE4, lookback_m=12, skip_m=1, weighting='ew')
print('out_dates:', len(res['dates']), res['dates'][0] if res['dates'] else None, '->', res['dates'][-1] if res['dates'] else None)
print('net rets:', len(res['net']))
print('n rebalances:', len(res['weights_hist']))
print('mean n_in_trend:', sum(res['n_intrend_hist'])/max(1,len(res['n_intrend_hist'])))
spy = E.spy_buyhold_on_path(res['dates'])
print('--- FULL PERIOD (core4 EW) ---')
sb = E.stats_block(res['net'], res['dates'], 'tsmom_ew_core4')
for k, v in sb.items():
    print(f'  {k}: {v}')
spystats = E.stats_block(spy, res['dates'], 'spy_buyhold_path')
print('--- SPY buy-hold same path ---')
for k, v in spystats.items():
    print(f'  {k}: {v}')
print('corr sleeve-vs-SPY daily:', round(E.corr(res['net'], spy), 4))
print('mean turnover/rebal:', round(sum(res['turnover_events'])/max(1,len(res['turnover_events'])), 4))
