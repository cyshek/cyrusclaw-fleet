import sys, bisect
sys.path.insert(0, '.')
from strategies_candidates._archive.tqqq_cot_combo.backtest_combo import (
    run_combo_backtest, COT_SCALE_BEARISH)

res = run_combo_backtest(target_ann_vol=0.40, vol_window=20, w_max=1.0)
pl = [p for p in res['pos_log'] if '2022-01-01' <= p['date'] <= '2022-12-31']

# The 18 in-market days (w_vt > 0) — show what COT did on each, and the sleeve
# return that day, to quantify whether the COT cut helped or hurt on in-market days.
print("=== THE IN-MARKET DAYS IN 2022 (vol-target wanted exposure, w_vt>0) ===")
print(f"{'date':12} {'trend':5} {'rvol':6} {'w_vt':6} {'cot':4} {'w_combo':7} {'sleeveRet%':10}")
inmkt = [p for p in pl if p['w_vt'] > 0.0]
sum_vt_pnl = 0.0
sum_combo_pnl = 0.0
for p in inmkt:
    cot = 'BEAR' if p['cot_scale'] == COT_SCALE_BEARISH else 'bull'
    sr = p['sleeve_ret'] * 100
    # daily contribution to book = w * sleeve_ret (ignoring tiny cash term for in-market days)
    vt_c = p['w_vt'] * p['sleeve_ret']
    combo_c = p['w_combo'] * p['sleeve_ret']
    sum_vt_pnl += vt_c
    sum_combo_pnl += combo_c
    rv = p['rvol'] if p['rvol'] is not None else float('nan')
    print(f"{p['date']:12} {str(p['trend_up'])[0]:5} {rv*100:5.1f}% {p['w_vt']:.3f}  {cot:4} {p['w_combo']:.3f}  {sr:+9.2f}")

print(f"\nIn-market days: {len(inmkt)}")
print(f"Sum of daily (w*sleeveRet) on in-market days: vt={sum_vt_pnl*100:+.2f}%  combo={sum_combo_pnl*100:+.2f}%")
print(f"  -> COT effect on in-market days: {(sum_combo_pnl-sum_vt_pnl)*100:+.2f}% (positive = COT helped)")

# How many of the 18 in-market days were COT-bearish (cut to 0.5)?
bear_inmkt = [p for p in inmkt if p['cot_scale'] == COT_SCALE_BEARISH]
print(f"  of which COT-bearish (exposure cut x0.5): {len(bear_inmkt)}")
# On those bearish-cut days, what was the avg sleeve return? (if negative, the cut helped)
if bear_inmkt:
    avg_sr_bear = sum(p['sleeve_ret'] for p in bear_inmkt)/len(bear_inmkt)*100
    print(f"  avg TQQQ sleeve return on the COT-cut days: {avg_sr_bear:+.2f}% "
          f"({'cut helped (down days)' if avg_sr_bear<0 else 'cut hurt (up days)'})")

# When was the gate UP in 2022 (the only window COT can act)?
up_days = [p['date'] for p in pl if p['trend_up']]
if up_days:
    print(f"\nGate-UP window in 2022: {up_days[0]} .. {up_days[-1]} ({len(up_days)} days)")
    # contiguous blocks
    blocks=[]; s=up_days[0]; prev=up_days[0]
    allpl=[p['date'] for p in pl]
    for d in up_days[1:]:
        i_prev=allpl.index(prev); i_d=allpl.index(d)
        if i_d==i_prev+1: prev=d
        else: blocks.append((s,prev)); s=d; prev=d
    blocks.append((s,prev))
    print("Contiguous gate-UP blocks:", blocks)
