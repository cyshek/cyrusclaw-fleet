"""THROWAWAY — apples-to-apples ensemble vs baseline under ONE consistent OOS
convention (continuous full-span sim, then slice at 2018-01-01), for BOTH the
binary baseline and the sma_breadth ensemble gate. Resolves the sign conflict.

The earlier two drivers disagreed because they used DIFFERENT OOS conventions:
 - _multihorizon_trend_driver.py : re-sims OOS span cold (start=2018) -> base OOS 0.858
 - _ensemble_trend_driver.py     : re-sims OOS span cold (start=2018) -> base OOS 0.778
   (these differ from each other too -> see note)
 - real engine sliced            : base OOS 0.800
Here we compute BOTH gates the SAME way and slice identically, so the delta is
pure gate effect with zero harness confound.

Reads caches only. No orders, no spend.
"""
import sys, math, bisect
sys.path.insert(0, ".")
sys.path.insert(0, "strategies_candidates/leveraged_long_trend")

from backtest_daily_voltarget import VolTargetParams, TRADING_DAYS
import importlib.util
spec = importlib.util.spec_from_file_location("passdrv", "_ensemble_trend_driver.py")
passdrv = importlib.util.module_from_spec(spec); spec.loader.exec_module(passdrv)

OOS = "2018-01-01"

def fp_sharpe(eq):
    rets = [eq[i]/eq[i-1]-1 for i in range(1,len(eq)) if eq[i-1] > 0]
    n=len(rets)
    if n<2: return 0.0
    m=sum(rets)/n; v=sum((r-m)**2 for r in rets)/(n-1)
    return (m/math.sqrt(v))*math.sqrt(TRADING_DAYS) if v>0 else 0.0

def maxdd(eq):
    peak=eq[0]; mdd=0.0
    for x in eq:
        peak=max(peak,x); mdd=min(mdd, x/peak-1.0)
    return mdd*100

def slice_oos(dates, eq, start):
    i = bisect.bisect_left(dates, start)
    if i<=0: return eq
    base = eq[i-1]
    return [1.0] + [eq[j]/base for j in range(i, len(eq))]

pp = passdrv.base_params()
print("CONVENTION A — re-sim OOS span COLD (start=2018), as both prior drivers did:")
for g in ["baseline_sma200","ens_sma_breadth"]:
    r = passdrv.simulate(passdrv.GATES[g], pp, lag_extra=0, start=OOS)
    print(f"  {g:18s} OOS fpS={r['fp_sharpe']:.3f}  ret={r['total_ret_pct']:7.1f}%  mdd={r['maxdd_pct']:.2f}%")

print("\nCONVENTION B — sim FULL span, then SLICE at 2018 (continuous warmup, real-engine style):")
res = {}
for g in ["baseline_sma200","ens_sma_breadth"]:
    full = passdrv.simulate(passdrv.GATES[g], pp, lag_extra=0)
    oeq = slice_oos(full["dates"], full["equity"], OOS)
    res[g] = (fp_sharpe(oeq), (oeq[-1]/oeq[0]-1)*100, maxdd(oeq))
    print(f"  {g:18s} OOS fpS={res[g][0]:.3f}  ret={res[g][1]:7.1f}%  mdd={res[g][2]:.2f}%")

b = res["baseline_sma200"]; e = res["ens_sma_breadth"]
print(f"\n  CONSISTENT-CONVENTION DELTA (ens - base): dSharpe={e[0]-b[0]:+.3f}  dRet={e[1]-b[1]:+.1f}pp  dMDD={b[2]-e[2]:+.2f}pp (positive=ens shallower DD)")
print("  (If dSharpe sign here disagrees with the +0.027 PASS headline, the PASS was a slicing artifact.)")
