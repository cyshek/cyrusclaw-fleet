"""Robustness: does 'adding a 3rd sleeve dilutes raw return below SPX' survive
across inv-vol lookbacks? And quantify the dilution mechanism."""
import sys, math
sys.path.insert(0, ".")
from _allocator_blend_tests import (
    build_sleeves, blend_portfolio, stats_from_returns, slice_equity_stats,
    annualized_vol, equity_to_daily_returns,
)
from _third_sleeve_tests import (
    real_etf_sleeve, synthetic_trend_sleeve, credit_macro_sleeve,
    invvol_wfn_factory,
)
from runner import daily_bars_cache as dbc

S = build_sleeves()

def spx_bh_ret(start, end):
    bars = dbc.get_daily("^GSPC")
    rows = [b for b in bars if start <= b["date"] <= end]
    return (rows[-1]["adjclose"]/rows[0]["adjclose"]-1.0)*100

def run(third_map, lookbacks=(21,42,63,126)):
    tq=dict(zip(S["common_dates"],S["tqqq_r"])); ro=dict(zip(S["common_dates"],S["rot_r"]))
    shared=[d for d in S["common_dates"] if d in third_map]
    tqqq_r=[tq[d] for d in shared]; rot_r=[ro[d] for d in shared]; third_r=[third_map[d] for d in shared]
    spx_ret = spx_bh_ret(shared[0], shared[-1])
    rows=[]
    for lb in lookbacks:
        b2=blend_portfolio(shared,[tqqq_r,rot_r],invvol_wfn_factory([tqqq_r,rot_r],lb),blend_cost_bps=2.0)
        b3=blend_portfolio(shared,[tqqq_r,rot_r,third_r],invvol_wfn_factory([tqqq_r,rot_r,third_r],lb),blend_cost_bps=2.0)
        s2=b2["stats"]; s3=b3["stats"]
        # OOS sharpe
        o2=slice_equity_stats(b2["dates"],b2["equity"],"2019-01-01","2099")["sharpe"]
        o3=slice_equity_stats(b3["dates"],b3["equity"],"2019-01-01","2099")["sharpe"]
        rows.append((lb,s2["sharpe"],s2["total_return_pct"],s2["max_drawdown_pct"],o2,
                        s3["sharpe"],s3["total_return_pct"],s3["max_drawdown_pct"],o3))
    return spx_ret, rows

for name, tm in [("DBMF", real_etf_sleeve("DBMF")),
                 ("KMLM", real_etf_sleeve("KMLM")),
                 ("SYN_TREND", synthetic_trend_sleeve(["DBC","GLD","TLT","UUP"],start="2005-01-01")),
                 ("CREDIT", credit_macro_sleeve("SPY","IEF","BAA10Y",start="2005-01-01"))]:
    spx, rows = run(tm)
    print("\n=== %s (SPX B&H raw ret on window = %.0f%%) ===" % (name, spx))
    print("  lb |   2-sleeve: Sh   ret%   mdd   OOS  |   3-sleeve: Sh   ret%   mdd   OOS  | 3s>SPX-raw? 3s-Sh>2s?")
    for r in rows:
        lb,s2,t2,m2,o2,s3,t3,m3,o3=r
        print("  %3d| %5.3f %6.0f %6.1f %5.3f | %5.3f %6.0f %6.1f %5.3f | %s  %s" % (
            lb,s2,t2,m2,o2, s3,t3,m3,o3,
            "YES" if t3>spx else "NO ", "yes" if s3>s2 else "no"))
