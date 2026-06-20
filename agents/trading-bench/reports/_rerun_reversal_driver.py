"""Notional A/B rerun: short-horizon single-stock reversal (xsec_ss_meanrev_lc20_lowturn).

CONTROLLED A/B: re-run the EXACT prior lead config + neighbors at notional_usd=100
(prior) vs notional_usd=1000 (post-fix). Same params, same universe, same 8 windows,
same active Alpaca cost model (alpaca_stocks 4bps RT). The ONLY change is notional.

Reuses the existing _lowturn_driver.run() (which imports the candidate's decide_xsec
and routes it through walk_forward_xsec with cost model active). FP-continuous Sharpe
is computed exactly as _lowturn_fpsharpe.py (concatenated per-tick equity returns,
sqrt(252)) — the canonical clause-(a) ruler.

NO protected-file edits. Import-only composition.
"""
import sys, math, json
sys.path.insert(0, '.')
from reports._lowturn_driver import run, deployed_ann_return


def fp_sharpe(agg):
    rets = []
    for w in agg.windows:
        ec = w.backtest.equity_curve
        for i in range(1, len(ec)):
            p = ec[i - 1]
            if p > 0:
                rets.append((ec[i] - p) / p)
    if len(rets) < 2:
        return 0.0, len(rets)
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return 0.0, len(rets)
    return (m / sd) * math.sqrt(252.0), len(rets)


# prior lead + the neighbor plateau the prior report jittered (same set)
CFGS = {
    'reb21_k4_lb5_drop3 (LEAD)': {'rebalance_bars': 21, 'top_k': 4, 'lookback_bars': 5, 'safety_max_loss_pct': -25.0, 'min_drop_pct': -3.0},
    'reb21_k3_lb5_drop3':        {'rebalance_bars': 21, 'top_k': 3, 'lookback_bars': 5, 'safety_max_loss_pct': -25.0, 'min_drop_pct': -3.0},
    'reb21_k4_lb6_drop3 (bestA)':{'rebalance_bars': 21, 'top_k': 4, 'lookback_bars': 6, 'safety_max_loss_pct': -25.0, 'min_drop_pct': -3.0},
    'reb21_k4_lb5_drop2.5':      {'rebalance_bars': 21, 'top_k': 4, 'lookback_bars': 5, 'safety_max_loss_pct': -25.0, 'min_drop_pct': -2.5},
    'reb21_k4_lb7_drop3':        {'rebalance_bars': 21, 'top_k': 4, 'lookback_bars': 7, 'safety_max_loss_pct': -25.0, 'min_drop_pct': -3.0},
}


def run_one(label, ov, notional):
    o = dict(ov)
    o['notional_usd'] = float(notional)
    o['max_notional_usd'] = float(notional)
    agg, params = run('xsec_ss_meanrev_lc20_lowturn', o)
    fps, n = fp_sharpe(agg)
    ann = deployed_ann_return(agg, deployed=float(notional))
    return {
        'label': label, 'notional': notional, 'fp_sharpe': round(fps, 3),
        'median_win_sharpe': round(agg.median_sharpe, 3), 'trades': agg.total_trades,
        'nret': n, 'ann_deployed': round(ann, 2),
        'worst_instr_dd': round(agg.worst_instrument_dd_pct, 2),
        'pct_pos': round(agg.pct_positive, 3), 'pct_beat_bh': round(agg.pct_beat_bh_basket, 3),
    }


def main():
    out = {}
    for label, ov in CFGS.items():
        r100 = run_one(label, ov, 100.0)
        r1000 = run_one(label, ov, 1000.0)
        delta = round(r1000['fp_sharpe'] - r100['fp_sharpe'], 3)
        out[label] = {'n100': r100, 'n1000': r1000, 'delta_fp': delta}
        print(f"{label:<28} FP100={r100['fp_sharpe']:+.3f} FP1000={r1000['fp_sharpe']:+.3f} "
              f"d={delta:+.3f} | trd100={r100['trades']} trd1000={r1000['trades']} "
              f"| ann100={r100['ann_deployed']:+.2f}% ann1000={r1000['ann_deployed']:+.2f}% "
              f"| ddinstr {r100['worst_instr_dd']:.1f}/{r1000['worst_instr_dd']:.1f}")
    open('reports/_rerun_reversal_results.json', 'w').write(json.dumps(out, indent=2))
    print("\nwrote reports/_rerun_reversal_results.json")


if __name__ == "__main__":
    main()
