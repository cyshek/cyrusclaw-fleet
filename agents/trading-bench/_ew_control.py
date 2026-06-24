# DECISIVE survivorship test: equal-weight ALL 104 universe names (no factor tilt),
# monthly rebal, 2bps, vs SPY and vs the factor strategy. If EW-104 ~ matches the
# factor strat, the "edge" is the survivorship-biased UNIVERSE, not the factor.
import _fundamentals_pit_tests as F
import json

univ = json.load(open('data_cache/edgar_fundamentals/universe.json'))
keys = list(univ["ticker_cik"].keys())
adj_px, adj_dates, raw_close, raw_dates = F._load_prices(keys)
spy_px = F.load_px("SPY"); spy_dates = sorted(spy_px.keys())
START="2010-06-01"
cal = [d for d in spy_dates if d >= START]
mo = set(F.month_starts(cal))

# EW-104: hold all names with price, equal weight, rebalance monthly (turnover ~ entry/exit only)
ew = [0.0]
held = []
for i in range(len(cal)):
    d = cal[i]
    if i in mo:
        held = [t for t in keys if d in adj_px.get(t, {})]
    if i==0: continue
    if held:
        rs=[]
        for t in held:
            p0=adj_px[t].get(cal[i-1]); p1=adj_px[t].get(d)
            if p0 and p1 and p0>0: rs.append(p1/p0-1)
        ew.append(sum(rs)/len(rs) if rs else 0.0)
    else:
        ew.append(0.0)

def block(rets, dts, st, en):
    sd=[];sr=[]
    for dd,rr in zip(dts,rets):
        if st<=dd<en: sd.append(dd);sr.append(rr)
    if len(sr)<20: return {}
    return F.stat_block(sd,sr)

spy_ret=[0.0]
for i in range(1,len(cal)):
    p0=spy_px.get(cal[i-1]);p1=spy_px.get(cal[i])
    spy_ret.append(p1/p0-1 if (p0 and p1 and p0>0) else 0.0)

print("EW-104 universe (NO factor tilt) vs SPY -- the survivorship control:")
for lbl,st,en in [("FULL","2000-01-01","2099-01-01"),("IS pre2019","2000-01-01","2019-01-01"),("OOS 2019+","2019-01-01","2099-01-01")]:
    e=block(ew,cal,st,en); s=block(spy_ret,cal,st,en)
    print(f"  {lbl:12s} EW104: Sh {e.get('sharpe')} ret {e.get('total_return_pct')}% mDD {e.get('maxdd_pct')}% | SPY: Sh {s.get('sharpe')} ret {s.get('total_return_pct')}%")
