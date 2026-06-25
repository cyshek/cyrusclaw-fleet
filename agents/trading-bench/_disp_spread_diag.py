#!/usr/bin/env python3
"""DIAGNOSTIC: why is realized avg-pairwise-corr (0.565) HIGHER than CBOE implied
COR1M (0.375)? Textbook correlation risk premium has implied >= realized (you pay a
premium for correlation insurance). A persistently NEGATIVE spread suggests the two
series measure DIFFERENT correlation objects -> the gate's spread may be an
apples-to-oranges artifact. Check:
 (a) what CBOE COR1M actually measures (large-cap index-implied corr, top ~50 SPX
     names weighted) vs my equal-ish 9-sector realized basket.
 (b) per-year implied vs realized to see if spread sign is stable or flips.
 (c) does a 9-sector IMPLIED proxy even exist? No — so we only have the index
     implied. Quantify the level gap and its time variation.
"""
import csv, math, statistics as st
from runner import daily_bars_cache as dbc

BASKET = ["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB"]

def load_adj(sym):
    out = {}
    for b in dbc.get_daily(sym):
        a = b.get("adjclose")
        if a is None:
            continue
        out[b["date"]] = float(a)
    return out

sectors = {s: load_adj(s) for s in BASKET}
cor = {}
for r in list(csv.reader(open("data_cache/cboe/COR1M_History.csv")))[1:]:
    if len(r) < 5 or not r[4]:
        continue
    mm, dd, yy = r[0].split("/")
    cor[f"{yy}-{int(mm):02d}-{int(dd):02d}"] = float(r[4]) / 100.0

common = set(cor)
for s in BASKET:
    common &= set(sectors[s])
days = sorted(common)

def log_rets(series):
    r = [None]
    for i in range(1, len(days)):
        r.append(math.log(series[days[i]]/series[days[i-1]]))
    return r

sec_rets = {s: log_rets(sectors[s]) for s in BASKET}
PAIRS = [(i, j) for i in range(len(BASKET)) for j in range(i+1, len(BASKET))]

def pearson(a, b):
    n = len(a)
    if n < 3: return float('nan')
    ma=sum(a)/n; mb=sum(b)/n
    num=sum((a[k]-ma)*(b[k]-mb) for k in range(n))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((x-mb)**2 for x in b))
    return num/(da*db) if da*db else float('nan')

def avg_pairwise(end, win):
    lo = end - win + 1
    if lo < 1: return None
    cs=[]
    for (i,j) in PAIRS:
        c=pearson(sec_rets[BASKET[i]][lo:end+1], sec_rets[BASKET[j]][lo:end+1])
        if not math.isnan(c): cs.append(c)
    return sum(cs)/len(cs) if cs else None

# per-year implied vs realized(21d)
from collections import defaultdict
yr_imp=defaultdict(list); yr_real=defaultdict(list)
for k in range(len(days)):
    rc=avg_pairwise(k,21)
    if rc is None: continue
    y=days[k][:4]
    yr_imp[y].append(cor[days[k]])
    yr_real[y].append(rc)
print("year   implied  realized  spread(imp-real)")
for y in sorted(yr_imp):
    im=sum(yr_imp[y])/len(yr_imp[y]); rl=sum(yr_real[y])/len(yr_real[y])
    print(f"{y}   {im:.3f}    {rl:.3f}    {im-rl:+.3f}")

# Also: does 63d-realized (smoother, closer to a 'typical' corr) change the gap?
all_imp=[]; all_r21=[]; all_r63=[]
for k in range(len(days)):
    r21=avg_pairwise(k,21); r63=avg_pairwise(k,63)
    if r21 is None or r63 is None: continue
    all_imp.append(cor[days[k]]); all_r21.append(r21); all_r63.append(r63)
print(f"\nfull-sample means: implied={sum(all_imp)/len(all_imp):.3f}  "
      f"real21={sum(all_r21)/len(all_r21):.3f}  real63={sum(all_r63)/len(all_r63):.3f}")
print("NOTE: CBOE COR1M = implied corr of the ~50 largest SPX names (cap-weighted,")
print("option-implied). My realized basket = 9 SPDR sectors. Sector indices are")
print("themselves diversified => cross-SECTOR realized corr runs HIGHER than the")
print("cross-STOCK implied corr CBOE quotes. This LEVEL mismatch is structural, not")
print("a risk premium -> differencing them is partly apples-to-oranges.")
