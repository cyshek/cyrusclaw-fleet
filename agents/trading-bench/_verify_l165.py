import json

fu = json.load(open('_regime_l165_followup.json'))
for k in ['tqqq_only', 'alloc_only', 'tqqq_alloc', 'levered_pair_plus_trend', 'all8']:
    v = fu.get(k, {})
    print(f'=== GATE SCENARIO: {k} ===')
    for sub in ['full', 'is_', 'oos']:
        m = v.get(sub, {})
        if not m:\n            continue\n        sh = m.get('sharpe', float('nan'))\n        so = m.get('sortino', float('nan'))\n        cg = m.get('cagr_pct', float('nan'))\n        md = m.get('maxdd_pct', float('nan'))
        print(f'  {sub}: Sharpe={sh:.4f}  Sortino={so:.4f}  CAGR={cg:.2f}%  maxDD={md:.2f}%')
    print()

print('=== BEAR MEAN CONTRIB BPS ===')
bc = fu.get('bear_mean_contrib_bps', {})
total = sum(bc.values())
for s, v in sorted(bc.items(), key=lambda x: x[1]):
    pct = v / total * 100 if total else 0
    print(f'  {s[:34]:34s}  {v:+.4f} bps  ({pct:.1f}%)')
print(f'  TOTAL: {total:+.4f} bps')
