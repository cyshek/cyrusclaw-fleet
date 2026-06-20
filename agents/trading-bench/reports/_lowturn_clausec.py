"""Evaluate GATE Bar A #5 fast-track clause (c) per-window for a candidate agg.

Clause (c): for EVERY window, pass EITHER
  V1 (multiplicative): strat_ret >= 2*BH when BH<=0, OR gap >= -1.5*|BH| when BH>0
  V2 (absolute gap):   strat_ret >= BH - 1.0pp
AND no catastrophe window: NOT (strat_ret <= -1.5% AND strat_ret < BH).
All in PERCENT.
"""
import sys; sys.path.insert(0,'.')
from reports._lowturn_driver import run

def clause_c(agg):
    fails=[]; cat=[]
    for w in agg.windows:
        s = w.backtest.total_return_pct*100.0
        bh = w.bh_basket_return_pct*100.0
        if bh <= 0:
            v1 = s >= 2*bh  # both negative; 2*bh is more negative, easy-ish
        else:
            v1 = (s - bh) >= -1.5*abs(bh)
        v2 = s >= bh - 1.0
        if not (v1 or v2):
            fails.append(f"{w.label}: s={s:+.2f} bh={bh:+.2f} V1={v1} V2={v2}")
        if s <= -1.5 and s < bh:
            cat.append(f"{w.label}: CATASTROPHE s={s:+.2f}<=-1.5 AND s<bh={bh:+.2f}")
    ok = (not fails) and (not cat)
    return ok, fails, cat

if __name__ == "__main__":
    ov = {'rebalance_bars':21,'top_k':4,'lookback_bars':5,'safety_max_loss_pct':-25.0,'min_drop_pct':-3.0}
    agg, params = run('xsec_ss_meanrev_lc20_lowturn', ov)
    ok, fails, cat = clause_c(agg)
    print("CLAUSE (c) reb21_k4_drop3:", "PASS" if ok else "FAIL")
    for f in fails: print("  V-fail:", f)
    for c in cat: print("  ", c)
    # also the k3 variant
    ov3 = dict(ov); ov3['top_k']=3
    agg3, _ = run('xsec_ss_meanrev_lc20_lowturn', ov3)
    ok3, f3, c3 = clause_c(agg3)
    print("CLAUSE (c) reb21_k3_drop3:", "PASS" if ok3 else "FAIL")
    for f in f3: print("  V-fail:", f)
    for c in c3: print("  ", c)
