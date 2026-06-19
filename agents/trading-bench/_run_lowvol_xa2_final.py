from __future__ import annotations
import sys, importlib.util, json, statistics
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
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
P=json.load(open(WS/"strategies_candidates"/"xsec_lowvol_xa2_440761"/"params.json"))
U=P["basket"]

# Full period
bbs={s:bars_cache.get_bars(s,"1Day",days=3000,end_dt=END) for s in U}
fpr=backtest_xsec("x",bbs,P,decide_xsec_fn=decide,default_cost_model=CM,starting_cash=SC)
peak=-1e18; ddusd=0
for e in fpr.equity_curve:
    peak=max(peak,e); ddusd=max(ddusd,peak-e)
print(f"FULL-PERIOD: Sharpe={fpr.sharpe:.3f} ret={fpr.total_return_pct*100:+.2f}% "
      f"DD%={fpr.max_drawdown_pct*100:.2f} DD$={ddusd:.2f} trades={fpr.n_trades} "
      f"buys={fpr.n_buys} closes={fpr.n_closes} clamps={fpr.n_basket_clamps} costs=${fpr.total_costs_usd:.2f}")
print("  span:", min(b['t'] for s in U for b in bbs[s])[:10], "->", max(b['t'] for s in U for b in bbs[s])[:10])
print("  per-symbol P&L:")
for s,ps in sorted(fpr.per_symbol.items(), key=lambda kv:-kv[1].realized_pnl_usd):
    print(f"    {s:5s} buys={ps.n_buys} closes={ps.n_closes} pnl=${ps.realized_pnl_usd:+.2f} finalqty={ps.final_qty:.3f}")

# Holding frequency
allts=sorted({b["t"] for s in U for b in bbs[s]})
idx={s:{b["t"]:i for i,b in enumerate(bbs[s])} for s in U}
cur={s:-1 for s in U}; last=""; holds=Counter(); months=0
for t in allts:
    for s in U:
        if t in idx[s]: cur[s]=idx[s][t]
    if t[:7]==last: continue
    ranks=sorted([(m._annualized_vol(bbs[s][:cur[s]+1],P["vol_lookback_bars"]),s) for s in U if cur[s]>=0 and m._annualized_vol(bbs[s][:cur[s]+1],P["vol_lookback_bars"])])
    if ranks:
        for v,s in ranks[:P["bottom_k"]]: holds[s]+=1
        months+=1
    last=t[:7]
print(f"  holding-freq over {months} rebalance months:")
for s,c in holds.most_common(): print(f"    {s:5s} {c:3d} ({100*c/months:.1f}%)")

# Walk-forward 8 windows
print("\nWALK-FORWARD 8 windows (warmup +180d):")
rows=[]; per_regime={"bull":[],"chop":[],"bear":[]}
for label,end_dt,days,reg in NAMED_WINDOWS:
    wb={s:bars_cache.get_bars(s,"1Day",days=days+WARM,end_dt=end_dt) for s in U}
    wb={k:v for k,v in wb.items() if v and len(v)>=10}
    bt=backtest_xsec("x",wb,P,decide_xsec_fn=decide,default_cost_model=CM,starting_cash=SC)
    bh=_bh_basket_return(list(wb.keys()),end_dt,days,"1Day",notional_usd=100,starting_cash=SC,cost_model=CM)
    s=bt.total_return_pct; b=bh
    if b<=0: v1=(s>=2*b)
    else: v1=((s-b)>=-1.5*abs(b))
    v2=(s>=b-0.01); cat=(s<=-0.015 and s<b); ok=(v1 or v2) and not cat
    rows.append({"label":label,"reg":reg,"s":s*100,"bh":b*100,"sharpe":bt.sharpe,
                 "dd":bt.max_drawdown_pct*100,"tr":bt.n_trades,"v1":v1,"v2":v2,"cat":cat,"ok":ok})
    per_regime[reg].append(s*100)
    print(f"  {label:20s} {reg:5s} s={s*100:+.2f}% bh={b*100:+.2f}% Sh={bt.sharpe:+.2f} DD={bt.max_drawdown_pct*100:.2f}% tr={bt.n_trades:2d} V1={v1} V2={v2} cat={cat} {'PASS' if ok else 'FAIL'}")
print("  per-regime median:", {k:(round(statistics.median(v),2) if v else None) for k,v in per_regime.items()})

a=fpr.sharpe>=1.0; bb=ddusd<=200; c=all(r["ok"] for r in rows)
print(f"\nBAR A #5: (a)FPSharpe>=1.0={a} ({fpr.sharpe:.2f})  (b)DD<=$200={bb} (${ddusd:.2f})  (c)all-windows={c}  => {'PASS' if (a and bb and c) else 'FAIL'}")
json.dump({"fp":{"sharpe":fpr.sharpe,"ret":fpr.total_return_pct*100,"dd_usd":ddusd,"dd_pct":fpr.max_drawdown_pct*100,"trades":fpr.n_trades,"costs":fpr.total_costs_usd},
           "rows":rows,"per_regime":{k:(statistics.median(v) if v else None) for k,v in per_regime.items()},
           "holds":dict(holds),"months":months,
           "persym":{s:{"buys":ps.n_buys,"closes":ps.n_closes,"pnl":ps.realized_pnl_usd} for s,ps in fpr.per_symbol.items()}},
          open("/tmp/lv2_final.json","w"),indent=2,default=str)
print("wrote /tmp/lv2_final.json")
