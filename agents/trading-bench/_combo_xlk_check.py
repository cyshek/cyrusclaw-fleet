import _combo_fusion_lib as L
from runner.fp_sharpe import equity_curve_returns, sharpe_from_returns
from runner.backtest import bars_per_year, CostModel, backtest

def fp_s(c):
    return sharpe_from_returns(equity_curve_returns(c), bars_per_year("1Hour", False))
def tim(c):
    if len(c)<2: return 0.0
    return sum(1 for i in range(1,len(c)) if c[i]!=c[i-1])/(len(c)-1)

iwm = L.load_full_1h("IWM"); st = L.build_iwm_macd_states(iwm)
xlk = L.load_full_1h("XLK")
mod,_ = L.load_strategy_module_and_params("breakout_xlk"); solo=mod.decide
_,params = L.load_strategy_module_and_params("breakout_xlk")
def run(fn, state, s=None,e=None):
    b=L.slice_by_date(xlk,s,e); L.reset_lookup(state)
    return backtest("breakout_xlk",b,params,starting_cash=1000.0,decide_fn=fn,cost_model=CostModel.alpaca_stocks())

dl,ds=L.make_aligned_lookup(st,0)
sres=run(solo,ds)
ol,os_=L.make_aligned_lookup(st,0); orfn,_=L.make_or_fusion("breakout_xlk",ol)
ores=run(orfn,os_)
def xlk_bh(s=None,e=None):
    b=L.slice_by_date(xlk,s,e)
    if len(b)<2: return [1000.0]
    sh=1000.0/float(b[0]["c"]); return [sh*float(x["c"]) for x in b]
print("XLK OR-fusion check (full span)")
print(f"  solo fpS={fp_s(sres.equity_curve):+.3f} tim={tim(sres.equity_curve):.3f} tr={sres.n_trades}")
print(f"  OR   fpS={fp_s(ores.equity_curve):+.3f} tim={tim(ores.equity_curve):.3f} tr={ores.n_trades}")
print(f"  XLK BH fpS={fp_s(xlk_bh()):+.3f} (pure beta)")
for lbl,s,e in [("IS",None,L.IS_END),("OOS",L.OOS_START,None)]:
    L.reset_lookup(ds); sr=run(solo,ds,s,e)
    ol2,os2=L.make_aligned_lookup(st,0); orf2,_=L.make_or_fusion("breakout_xlk",ol2); orr=run(orf2,os2,s,e)
    print(f"  {lbl}: solo {fp_s(sr.equity_curve):+.3f}(tr{sr.n_trades}) OR {fp_s(orr.equity_curve):+.3f}(tr{orr.n_trades}) XLK-BH {fp_s(xlk_bh(s,e)):+.3f}")
