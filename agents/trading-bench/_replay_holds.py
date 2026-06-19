from __future__ import annotations
import sys, importlib.util, statistics
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))
from runner import bars_cache
STRAT = WS/"strategies_candidates"/"xsec_lowvol_xa2_440761"/"strategy.py"
spec=importlib.util.spec_from_file_location("lv2s",STRAT); m=importlib.util.module_from_spec(spec)
sys.modules["lv2s"]=m; spec.loader.exec_module(m)

END=datetime(2026,5,29,tzinfo=timezone.utc)
def replay(basket, lb, k):
    bbs={s:bars_cache.get_bars(s,"1Day",days=3000,end_dt=END) for s in basket}
    # build monthly rebalance selection by replaying vol rank at month boundaries
    # use union clock
    allts=sorted({b["t"] for s in basket for b in bbs[s]})
    idx={s:{b["t"]:i for i,b in enumerate(bbs[s])} for s in basket}
    cur={s:-1 for s in basket}
    last_month=""; holds=Counter(); months=0
    for t in allts:
        for s in basket:
            if t in idx[s]: cur[s]=idx[s][t]
        mk=t[:7]
        if mk==last_month: continue
        # rank
        ranks=[]
        for s in basket:
            if cur[s]<0: continue
            bars=bbs[s][:cur[s]+1]
            v=m._annualized_vol(bars,lb)
            if v: ranks.append((v,s))
        ranks.sort()
        if not ranks: 
            last_month=mk; continue
        for v,s in ranks[:k]:
            holds[s]+=1
        months+=1
        last_month=mk
    print(f"basket={basket} lb={lb} k={k} months={months}")
    for s,c in holds.most_common():
        print(f"  {s:5s} {c:3d} {100*c/months:5.1f}%")

print("=== EXPANDED K=3 N=63 ===")
replay(["SPY","EFA","TLT","IEF","SHY","LQD","USMV","VNQ","DBC","GLD"],63,3)
print("=== WAVE4 K=3 N=60 ===")
replay(["SPY","EFA","TLT","VNQ","DBC","GLD"],60,3)
