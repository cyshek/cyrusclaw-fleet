#!/usr/bin/env python3
"""FINAL ROBUSTNESS: the raw spread has a structural ~-0.19 offset (sector-vs-stock
correlation-object mismatch). Maybe the TRADEABLE signal is the spread RELATIVE to
its own recent history (z-score / detrended), which strips the constant offset and
isolates 'unusually wide/narrow corr premium right now'. Re-test monotonicity on:
  (a) spread z-score over trailing 252d
  (b) spread minus its trailing-252d mean (level-detrended)
If BOTH horizons stay non-monotone even after detrending -> clean RED. If detrended
version becomes monotone+sensible -> the offset was the only problem -> AMBER/retest.
"""
import csv, math, statistics as st, bisect
from runner import daily_bars_cache as dbc
from collections import defaultdict

BASKET = ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB"]

def load_adj(sym):
    out={}
    for b in dbc.get_daily(sym):
        a=b.get("adjclose")
        if a is None: continue
        out[b["date"]]=float(a)
    return out

spy=load_adj("SPY")
sectors={s:load_adj(s) for s in BASKET}
cor={}
for r in list(csv.reader(open("data_cache/cboe/COR1M_History.csv")))[1:]:
    if len(r)<5 or not r[4]: continue
    mm,dd,yy=r[0].split("/")
    cor[f"{yy}-{int(mm):02d}-{int(dd):02d}"]=float(r[4])/100.0

common=set(spy)&set(cor)
for s in BASKET: common&=set(sectors[s])
days=sorted(common)
spx=[spy[d] for d in days]

def log_rets(series):
    r=[None]
    for i in range(1,len(days)):
        r.append(math.log(series[days[i]]/series[days[i-1]]))
    return r
sec_rets={s:log_rets(sectors[s]) for s in BASKET}
PAIRS=[(i,j) for i in range(len(BASKET)) for j in range(i+1,len(BASKET))]

def pearson(a,b):
    n=len(a)
    if n<3: return float('nan')
    ma=sum(a)/n; mb=sum(b)/n
    num=sum((a[k]-ma)*(b[k]-mb) for k in range(n))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((x-mb)**2 for x in b))
    return num/(da*db) if da*db else float('nan')

def avg_pairwise(end,win):
    lo=end-win+1
    if lo<1: return None
    cs=[]
    for (i,j) in PAIRS:
        c=pearson(sec_rets[BASKET[i]][lo:end+1],sec_rets[BASKET[j]][lo:end+1])
        if not math.isnan(c): cs.append(c)
    return sum(cs)/len(cs) if cs else None

# build raw spread (21d realized)
idxs=[]; spread=[]
for k in range(len(days)):
    rc=avg_pairwise(k,21)
    if rc is None: continue
    idxs.append(k); spread.append(cor[days[k]]-rc)

# detrended variants over trailing 252 of the spread series itself
LB=252
z=[None]*len(spread)        # z-score
dm=[None]*len(spread)       # demeaned
for n in range(len(spread)):
    if n<LB: continue
    w=spread[n-LB:n]
    mu=sum(w)/len(w); sd=st.pstdev(w)
    dm[n]=spread[n]-mu
    z[n]=(spread[n]-mu)/sd if sd>0 else 0.0

def sort_table(signal, label):
    print(f"\n--- {label} ---")
    for H in (5,21):
        pairs=[]
        for n,k in enumerate(idxs):
            if signal[n] is None: continue
            if k+H>=len(days): continue
            pairs.append((signal[n], math.log(spx[k+H]/spx[k])))
        if not pairs:
            print(f"  fwd{H}d: no data"); continue
        sv=sorted(p[0] for p in pairs)
        def pct(x): return bisect.bisect_left(sv,x)/len(sv)
        bk={b:[] for b in range(5)}
        for s,f in pairs:
            bk[min(4,int(pct(s)*5))].append(f)
        means=[sum(bk[b])/len(bk[b]) for b in range(5)]
        anns=[m*(252/H)*100 for m in means]
        up=all(means[b]<=means[b+1] for b in range(4))
        dn=all(means[b]>=means[b+1] for b in range(4))
        v="MONO-UP" if up else "MONO-DOWN" if dn else "NON-MONOTONE"
        print(f"  fwd{H}d ann by quintile: "+" | ".join(f"{a:+.1f}%" for a in anns)+f"   -> {v}")

sort_table(spread,"RAW spread (already shown: non-monotone)")
sort_table(dm,"DEMEANED spread (trailing-252 mean removed)")
sort_table(z,"Z-SCORE spread (trailing-252)")
