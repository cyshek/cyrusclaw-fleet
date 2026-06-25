import math
import _xstrat_corr as X
import _tsmom_engine as E

LIVE = ["breakout_xlk__mut_c382b1","sma_crossover_qqq_regime","sma_crossover_qqq_rth",
        "rsi_oversold_spy","volume_breakout_qqq","macd_momentum_iwm",
        "tqqq_cot_combo","allocator_blend"]

series, meta, spy_ret = X.build_all_series()

# common window across the 8 live
sets = [set(series[n].keys()) for n in LIVE]
common = sorted(set.intersection(*sets))
print("common window:", common[0], "..", common[-1], "n=", len(common))

def ann_vol(rets):
    n=len(rets)
    if n<2: return 0.0
    m=sum(rets)/n
    var=sum((r-m)**2 for r in rets)/(n-1)
    return math.sqrt(var)*math.sqrt(252)

print("\nper-sleeve ANNUALIZED VOL on common window (THE load-bearing claim):")
for n in LIVE:
    col=[series[n][d] for d in common]
    print(f"  {n:30s} ann_vol={ann_vol(col)*100:8.3f}%   mean_daily={sum(col)/len(col)*1e4:+7.2f}bps")

# core4 sleeve vol for reference
out=E.run_tsmom(["DBC","GLD","TLT","UUP"], lookback_m=12, skip_m=1, weighting="ew", start="2008-05-01")
print(f"\n  core4_tsmom               ann_vol={ann_vol(out['net_rets'])*100:8.3f}%")
