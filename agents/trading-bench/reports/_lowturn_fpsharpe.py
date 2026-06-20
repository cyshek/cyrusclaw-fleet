"""Full-period (continuous-span) Sharpe for an xsec candidate, matching the
GATE #5(a) definition used in the momentum promotion record (continuous
full-span Sharpe, NOT median-of-windows). We concatenate each window's
per-tick equity returns into one series and annualize with sqrt(252).

This is the HONEST clause-(a) number. Median-of-window Sharpe (what the
walk_forward_xsec aggregate reports) is a different, generally-higher
statistic and is NOT what clause (a) binds on.
"""
import sys, math; sys.path.insert(0,'.')
from reports._lowturn_driver import run

def fp_sharpe(agg):
    rets = []
    for w in agg.windows:
        ec = w.backtest.equity_curve
        for i in range(1, len(ec)):
            p = ec[i-1]
            if p > 0:
                rets.append((ec[i]-p)/p)
    if len(rets) < 2:
        return 0.0, len(rets)
    m = sum(rets)/len(rets)
    var = sum((r-m)**2 for r in rets)/(len(rets)-1)
    sd = math.sqrt(var)
    if sd <= 0:
        return 0.0, len(rets)
    return (m/sd)*math.sqrt(252.0), len(rets)

if __name__ == "__main__":
    cfgs = {
      'reb21_k4_lb5_drop3 (lead)': {'rebalance_bars':21,'top_k':4,'lookback_bars':5,'safety_max_loss_pct':-25.0,'min_drop_pct':-3.0},
      'reb21_k3_lb5_drop3':        {'rebalance_bars':21,'top_k':3,'lookback_bars':5,'safety_max_loss_pct':-25.0,'min_drop_pct':-3.0},
      'reb21_k3_lb5_dropNone':     {'rebalance_bars':21,'top_k':3,'lookback_bars':5,'safety_max_loss_pct':-25.0,'min_drop_pct':None},
      'reb21_k4_lb5_drop2.5':      {'rebalance_bars':21,'top_k':4,'lookback_bars':5,'safety_max_loss_pct':-25.0,'min_drop_pct':-2.5},
      'reb21_k4_lb6_drop3':        {'rebalance_bars':21,'top_k':4,'lookback_bars':6,'safety_max_loss_pct':-25.0,'min_drop_pct':-3.0},
    }
    for label, ov in cfgs.items():
        agg, _ = run('xsec_ss_meanrev_lc20_lowturn', ov)
        fps, n = fp_sharpe(agg)
        print(f"{label:<30} FP-Sharpe(continuous)={fps:+.2f}  medianWinSharpe={agg.median_sharpe:+.2f}  nret={n}  trades={agg.total_trades}")
