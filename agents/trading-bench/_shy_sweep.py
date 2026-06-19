from __future__ import annotations
import sys, importlib.util, json
from datetime import datetime, timezone
from pathlib import Path
WS=Path(__file__).resolve().parent; sys.path.insert(0,str(WS))
from runner import bars_cache
from runner.backtest import CostModel
from runner.backtest_xsec import backtest_xsec
from runner.walk_forward import NAMED_WINDOWS
from runner.walk_forward_xsec import _bh_basket_return
STRAT=WS/"strategies_candidates"/"xsec_lowvol_xa2_440761"/"strategy.py"
spec=importlib.util.spec_from_file_location("lv2s",STRAT); m=importlib.util.module_from_spec(spec)
sys.modules["lv2s"]=m; spec.loader.exec_module(m)
decide=m.decide_xsec
CM=CostModel.alpaca_stocks(); END=datetime(2026,5,29,tzinfo=timezone.utc); SC=1000.0; WARM=180
U=["SPY","EFA","SHY","VNQ","DBC","GLD"]

def fp(basket,p):
    bbs={s:bars_cache.get_bars(s,"1Day",days=3000,end_dt=END) for s in basket}
    r=backtest_xsec("x",bbs,p,decide_xsec_fn=decide,default_cost_model=CM,starting_cash=SC)
    peak=-1e18; dd=0
    for e in r.equity_curve:
        peak=max(peak,e); dd=max(dd,peak-e)
    return r.sharpe, r.total_return_pct*100, dd, r.n_trades

def q3chop(basket,p):
    # just the 2022-Q3 chop window
    label,end_dt,days,reg=[w for w in NAMED_WINDOWS if w[0]=="2022-Q3 chop"][0]
    bbs={s:bars_cache.get_bars(s,"1Day",days=days+WARM,end_dt=end_dt) for s in basket}
    bbs={k:v for k,v in bbs.items() if v and len(v)>=10}
    bt=backtest_xsec("x",bbs,p,decide_xsec_fn=decide,default_cost_model=CM,starting_cash=SC)
    bh=_bh_basket_return(list(bbs.keys()),end_dt,days,"1Day",notional_usd=100,starting_cash=SC,cost_model=CM)
    return bt.total_return_pct*100, bh*100

def mk(k,lb,wm,reg=False):
    return {"basket":U,"timeframe":"1Day","max_notional_usd":100,"notional_usd":100,
            "vol_lookback_bars":lb,"bottom_k":k,"weight_mode":wm,"use_regime_filter":reg,
            "regime_sma_period":50,"xsec_basket_size":k,"safety_max_loss_pct":-50.0}

print("SHY-for-TLT universe sweep (FP sharpe / Q3-chop window):")
for lb in [42,60,63,90,126]:
    for k in [2,3,4]:
        for wm in ["equal"]:
            p=mk(k,lb,wm)
            s,ret,dd,tr=fp(U,p)
            q,bh=q3chop(U,p)
            cat = (q<=-1.5 and q<bh)
            flag = "<<<" if (s>=1.0 and not cat and dd<=200) else ""
            print(f"  K={k} N={lb:3d} {wm:6s}: FPSharpe={s:+.2f} ret={ret:+.2f}% DD=${dd:.1f} tr={tr:3d} | Q3chop s={q:+.2f}% bh={bh:+.2f}% cat={cat} {flag}")
