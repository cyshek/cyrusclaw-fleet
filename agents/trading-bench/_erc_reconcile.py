#!/usr/bin/env python3
"""Reconcile the two 'effective bets' metrics on the 8-strategy submatrix so the
report is honest: (A) eigenvalue participation ratio of the CORRELATION matrix
(the audit's metric — measures structural redundancy, weight-independent), vs
(B) risk-contribution HHI of a WEIGHTED book (depends on weights).

Also report the capital-weighted equity-beta share before/after, which is the
number that actually matters operationally (how much of the book is one factor).
"""
import json, math
from pathlib import Path

WS = Path(__file__).resolve().parent
M = json.load(open(WS / "reports/_interstrategy_corr_matrix.json"))
E = json.load(open(WS / "reports/_erc_weights.json"))
labels_all = M["labels"]; R_all = M["corr_full"]
LIVE = E["live"]

def idx_of(name):
    if name in labels_all: return labels_all.index(name)
    for i,lb in enumerate(labels_all):
        if name in lb or lb in name: return i
    raise KeyError(name)
idxs = [idx_of(n) for n in LIVE]
n = len(LIVE)
R = [[R_all[idxs[a]][idxs[b]] for b in range(n)] for a in range(n)]

# --- (A) eigenvalue participation ratio of the 8x8 correlation matrix ---
# power-iteration-free: use numpy if available, else Jacobi. Try numpy.
try:
    import numpy as np
    eig = np.linalg.eigvalsh(np.array(R))
    eig = [float(x) for x in eig]
except Exception:
    # Jacobi eigenvalue for small symmetric matrix
    import copy
    A = [row[:] for row in R]; m=n
    for _ in range(100):
        # find largest off-diag
        p,q,mx=0,1,0
        for i in range(m):
            for j in range(i+1,m):
                if abs(A[i][j])>mx: mx=abs(A[i][j]); p,q=i,j
        if mx<1e-12: break
        app,aqq,apq=A[p][p],A[q][q],A[p][q]
        phi=0.5*math.atan2(2*apq, aqq-app) if (aqq-app)!=0 else math.pi/4
        c,s=math.cos(phi),math.sin(phi)
        for k in range(m):
            akp,akq=A[k][p],A[k][q]
            A[k][p]=c*akp - s*akq; A[k][q]=s*akp + c*akq
        for k in range(m):
            apk,aqk=A[p][k],A[q][k]
            A[p][k]=c*apk - s*aqk; A[q][k]=s*apk + c*aqk
    eig=[A[i][i] for i in range(m)]

eig=[max(x,0.0) for x in eig]
se=sum(eig); se2=sum(x*x for x in eig)
part_ratio = (se*se)/se2   # participation ratio = (sum λ)^2 / sum λ^2
top_eig = max(eig)
print("=== (A) eigenvalue structure of the 8x8 CORRELATION matrix ===")
print("eigenvalues:", [round(x,3) for x in sorted(eig, reverse=True)])
print(f"participation ratio (eff independent bets, weight-free) = {part_ratio:.2f} of {n}")
print(f"top eigenvalue = {top_eig:.2f} ({100*top_eig/se:.0f}% of variance)")

# --- (B) capital-weighted equity-beta exposure share ---
# Define the equity-trend cluster (high mutual corr, ~the long-beta factor):
EQUITY_CLUSTER = {"breakout_xlk__mut_c382b1","sma_crossover_qqq_regime",
                  "sma_crossover_qqq_rth","volume_breakout_qqq",
                  "tqqq_cot_combo","allocator_blend"}
DIVERSIFIERS = {"rsi_oversold_spy","macd_momentum_iwm"}

def beta_share(capmap):
    tot=sum(capmap.values())
    eq=sum(v for k,v in capmap.items() if k in EQUITY_CLUSTER)
    dv=sum(v for k,v in capmap.items() if k in DIVERSIFIERS)
    return eq/tot, dv/tot

flat_cap={k:100.0 for k in LIVE}
# current ACTUAL cap (tqqq runs $1000 base, rest $100) — the real status quo
actual_cap={k:100.0 for k in LIVE}; actual_cap["tqqq_cot_combo"]=1000.0
erc_cap=E["capital_usd"]

for name,cm in [("flat $100 each",flat_cap),("ACTUAL (tqqq=$1000)",actual_cap),("ERC",erc_cap)]:
    eq,dv=beta_share(cm)
    print(f"\n--- {name}: total=${sum(cm.values()):.0f} ---")
    print(f"    equity-beta cluster capital share = {eq*100:.1f}%")
    print(f"    diversifier (rsi+macd) capital share = {dv*100:.1f}%")

# Also: leverage-weighted equity *exposure* (notional×leverage) which is the true
# economic beta. For ACTUAL, tqqq=$1000×~0.95w×3lev dominates.
def beta_exposure(capmap):
    # event eq strategies: cap×1; tqqq: cap×0.95w×3; allocator: cap×~0.5(tqqq leg)×... approx cap×1.3 but only ~40% in tqqq
    exp={}
    for k,v in capmap.items():
        if k=="tqqq_cot_combo": exp[k]=v*0.95*3.0
        elif k=="allocator_blend": exp[k]=v*1.3
        elif k in DIVERSIFIERS: exp[k]=v*1.0
        else: exp[k]=v*1.0
    tot=sum(exp.values())
    eq=sum(x for k,x in exp.items() if k in EQUITY_CLUSTER)
    return eq/tot, tot

print("\n=== (C) leverage-adjusted ECONOMIC equity-beta exposure ===")
for name,cm in [("ACTUAL (tqqq=$1000)",actual_cap),("ERC",erc_cap)]:
    eqshare,tot=beta_exposure(cm)
    print(f"  {name}: total economic exposure ${tot:.0f}, equity-beta share {eqshare*100:.1f}%")
