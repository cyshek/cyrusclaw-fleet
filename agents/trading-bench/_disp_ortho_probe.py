#!/usr/bin/env python3
"""ORTHOGONALITY PROBE: is CBOE implied correlation (COR3M) a genuine orthogonal
signal, or just inverse-SPY in disguise? This is the crux for the dispersion lane.

Tests:
 1. corr(daily ΔCOR3M, daily SPY return) — if strongly negative, COR just spikes
    when SPY falls = lagging beta proxy, NOT orthogonal.
 2. corr(COR3M LEVEL, forward N-day SPY return) — does the LEVEL/percentile carry
    predictive info about forward equity returns (a tradeable regime signal)?
 3. The signal we'd actually trade: COR3M percentile as a risk-on/off gate. Does
    'low implied correlation = risk-on (stay long), high = risk-off (de-risk)'
    or the reverse separate forward SPY returns? Report mean fwd return by
    COR3M-percentile bucket.
NO trading, NO config. Pure measurement -> prints, parent synthesizes.
"""
import json, csv, math, statistics as st
from datetime import datetime

# SPY adjclose
d = json.load(open("/tmp/spy.json"))["chart"]["result"][0]
ts = d["timestamp"]; adj = d["indicators"]["adjclose"][0]["adjclose"]
spy = {}
for t, a in zip(ts, adj):
    if a is None: continue
    day = datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
    spy[day] = a

# COR3M close, parse MM/DD/YYYY -> YYYY-MM-DD
cor = {}
for r in list(csv.reader(open("data_cache/cboe/COR3M_History.csv")))[1:]:
    if len(r) < 5 or not r[4]: continue
    mm, dd, yy = r[0].split("/")
    cor[f"{yy}-{int(mm):02d}-{int(dd):02d}"] = float(r[4])

days = sorted(set(spy) & set(cor))
print(f"common days SPY∩COR3M: {len(days)} ({days[0]} → {days[-1]})")

# build aligned series
spx = [spy[d] for d in days]
c = [cor[d] for d in days]
spy_ret = [math.log(spx[i]/spx[i-1]) for i in range(1, len(spx))]
dcor = [c[i]-c[i-1] for i in range(1, len(c))]

def corr(a, b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((a[i]-ma)*(b[i]-mb) for i in range(n))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((x-mb)**2 for x in b))
    return num/(da*db) if da*db else float('nan')

# TEST 1: contemporaneous ΔCOR vs SPY return
print(f"\n[1] corr(ΔCOR3M, SPY_ret) contemporaneous = {corr(dcor, spy_ret):+.3f}")
print("    (strongly negative => COR is just inverse-SPY = NOT orthogonal as a CHANGE series)")

# TEST 2: COR LEVEL vs forward SPY return (5d, 21d)
for H in (5, 21):
    lv=[]; fwd=[]
    for i in range(len(days)-H):
        lv.append(c[i])
        fwd.append(math.log(spx[i+H]/spx[i]))
    print(f"[2] corr(COR3M level, fwd {H}d SPY ret) = {corr(lv, fwd):+.3f}")

# TEST 3: forward 21d SPY return by COR3M percentile bucket (the tradeable regime read)
H=21
pairs=[(c[i], math.log(spx[i+H]/spx[i])) for i in range(len(days)-H)]
levels=sorted(p[0] for p in pairs)
def pct(x):
    # percentile rank of x within levels
    import bisect
    return bisect.bisect_left(levels, x)/len(levels)
buckets={0:[],1:[],2:[],3:[],4:[]}
for lvl, f in pairs:
    b=min(4, int(pct(lvl)*5))
    buckets[b].append(f)
print(f"\n[3] forward {H}d SPY log-return by COR3M-LEVEL quintile (annualized %):")
labels=["Q1 (lowest corr)","Q2","Q3","Q4","Q5 (highest corr)"]
for b in range(5):
    v=buckets[b]
    ann=(sum(v)/len(v))*(252/H)*100
    print(f"    {labels[b]:22s} n={len(v):4d}  mean fwd21d ann = {ann:+6.1f}%")
print("    (monotone HIGH-corr->LOW-fwd-return would = a tradeable risk-off regime signal;")
print("     flat across buckets = no predictive edge in the level)")

# TEST 4: also test COR3M vs realized corr proxy? quick: is implied corr mean-reverting (tradeable)
m=sum(c)/len(c)
hi=sum(1 for x in c if x>m+st.pstdev(c))
print(f"\n[4] COR3M mean={m:.1f} sd={st.pstdev(c):.1f}; lag-1 autocorr {corr(c[1:],c[:-1]):.3f} (slow=low turnover, good)")
