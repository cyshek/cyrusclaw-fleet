"""Breakeven-cost + zero-cost sanity for the headline FX basket configs.
Confirms whether ANY config has a real gross edge that cost is killing, and
finds the breakeven one-way spread. Throwaway.
"""
from __future__ import annotations
import json
from runner.fx_strategies import run_basket, fx_cost_model, sharpe, total_return, tsmom_signal
from runner.fx_bars_cache import FX_MAJORS

FX7 = list(FX_MAJORS) + ["NZDUSD=X"]

def gross_net(lb, skip, short):
    sig = lambda c: tsmom_signal(c, lookback=lb, skip=skip, allow_short=short)
    res0 = run_basket(FX7, sig, cost=fx_cost_model(spread_bps=0.0))   # zero cost
    res1 = run_basket(FX7, sig, cost=fx_cost_model(spread_bps=1.0))   # 1bp
    return {
        "gross_sharpe": round(sharpe(res0.rets), 4),
        "gross_total_ret": round(total_return(res0.rets), 4),
        "net1bp_sharpe": round(sharpe(res1.rets), 4),
        "net1bp_total_ret": round(total_return(res1.rets), 4),
        "avg_turnover": round(sum(res1.turnover)/len(res1.turnover), 4),
    }

def breakeven_bps(lb, skip, short):
    """Smallest one-way spread (bps) that drives total return <= 0 (gross>0 only)."""
    sig = lambda c: tsmom_signal(c, lookback=lb, skip=skip, allow_short=short)
    g = run_basket(FX7, sig, cost=fx_cost_model(spread_bps=0.0))
    if total_return(g.rets) <= 0:
        return None  # no gross edge to erode
    lo, hi = 0.0, 50.0
    for _ in range(40):
        mid = (lo+hi)/2
        r = run_basket(FX7, sig, cost=fx_cost_model(spread_bps=mid))
        if total_return(r.rets) > 0:
            lo = mid
        else:
            hi = mid
    return round((lo+hi)/2, 3)

out = {}
for lb, skip, short, lab in [(63,0,True,"3mo_LS"),(126,0,True,"6mo_LS"),
                             (252,0,True,"12mo_LS"),(252,21,True,"12-1_LS"),
                             (252,0,False,"12mo_LF")]:
    g = gross_net(lb, skip, short)
    g["breakeven_oneway_bps"] = breakeven_bps(lb, skip, short)
    out[lab] = g

print(json.dumps(out, indent=2))
