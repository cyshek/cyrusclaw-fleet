import sys, json
d = json.load(open(sys.argv[1]))
print('=== HOLD-THE-DIP AUDIT - three-way (trendgate = SMA-100d daily, testable) ===')
for tag, v in d['variants'].items():
    s = v['summary']
    g = v['gate']
    print()
    print(f"{tag} [{v['strategy']}]")
    print(f"  medSharpe={s['median_sharpe']:.4f}  medRet={s['median_return_pct']:+.3f}%  meanRet={s['mean_return_pct']:+.3f}%  pos={s['pct_positive']:.0%}  beatBH={s['pct_beat_bh_spy']:.0%}  trades={s['total_trades']}  worst={s['worst_return_pct']:+.2f}%  best={s['best_return_pct']:+.2f}%")
    print(f"  abs_gate={g.get('passes_fitness_gate_absolute')}  ({g.get('fitness_reason')})")
    if 'passes_mutation_gate_vs_parent' in g:
        print(f"  vs_parent={g['passes_mutation_gate_vs_parent']}  ({g.get('mutation_reason')})")
