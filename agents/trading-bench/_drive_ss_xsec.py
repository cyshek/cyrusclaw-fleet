"""Throwaway driver: walk-forward a SINGLE-STOCK xsec candidate from
strategies_candidates/ on the corrected ruler. Not a runner file."""
import sys, json, importlib
sys.path.insert(0, '.')
from pathlib import Path
from runner.walk_forward_xsec import (
    walk_forward_xsec, passes_fitness_gate_xsec, passes_bar_a_5b,
    format_xsec_md, BAR_A_5B_MAX_INSTRUMENT_DD_PCT)
from runner.backtest import CostModel

CAND = Path('strategies_candidates')

def load(name):
    params = json.loads((CAND / name / 'params.json').read_text())
    mod = importlib.import_module(f'strategies_candidates.{name}.strategy')
    return mod.decide_xsec, params

def ann_return_on_deployed(agg, params):
    """Approx full-span annualized return on DEPLOYED notional (clause f).
    Sum window dollar PnL across all windows / deployed notional, annualized
    by total trading days across windows."""
    notional = float(params.get('notional_usd', 100.0))
    total_pnl = 0.0
    total_days = 0
    for w in agg.windows:
        bt = w.backtest
        total_pnl += bt.total_return_usd          # dollar pnl on $1000 book == pnl in $
        total_days += bt.n_ticks
    if total_days <= 0:
        return 0.0
    years = total_days / 252.0
    # return on deployed notional, annualized (simple)
    tot_ret_on_deployed = total_pnl / notional
    return (tot_ret_on_deployed / years) * 100.0 if years > 0 else 0.0

def run(name, warmup):
    decide, params = load(name)
    basket = list(params.get('basket') or [])
    cm = CostModel.alpaca_stocks()
    print(f"\n{'='*70}\n{name}  basket N={len(basket)} warmup={warmup}d cost=spread{cm.spread_bps}bp fee{cm.fee_bps}bp", file=sys.stderr)
    agg = walk_forward_xsec(name, basket, params=params, decide_xsec_fn=decide,
                            warmup_days=warmup, cost_model=cm)
    fit_pass, fit_reason = passes_fitness_gate_xsec(agg)
    dd_pass, dd_reason = passes_bar_a_5b(agg)
    annret = ann_return_on_deployed(agg, params)
    out = {
        'name': name, 'n_windows': agg.n_windows_with_data,
        'median_return_pct': agg.median_return_pct,
        'median_sharpe': agg.median_sharpe,
        'pct_positive': agg.pct_positive,
        'pct_beat_bh': agg.pct_beat_bh_basket,
        'worst_instrument_dd_pct': agg.worst_instrument_dd_pct,
        'total_trades': agg.total_trades,
        'bar_a_bullet1_pass': agg.bar_a_bullet1_pass,
        'bar_a_bullet1_reason': agg.bar_a_bullet1_reason,
        'fitness_pass': fit_pass, 'fitness_reason': fit_reason,
        'dd5b_pass': dd_pass, 'dd5b_reason': dd_reason,
        'ann_return_on_deployed_pct': annret,
        'windows': [w.to_row() for w in agg.windows],
    }
    Path(f'/tmp/wf_{name}.json').write_text(json.dumps(out, indent=2, default=str))
    Path(f'/tmp/wf_{name}.md').write_text(format_xsec_md(agg))
    print(format_xsec_md(agg))
    print(f"  -> medSharpe={agg.median_sharpe:.3f} medRet={agg.median_return_pct:+.2f}% "
          f"pos={agg.pct_positive*100:.0f}% beatBH={agg.pct_beat_bh_basket*100:.0f}% "
          f"worstInstDD={agg.worst_instrument_dd_pct:.2f}% trades={agg.total_trades} "
          f"annRetDeployed={annret:.2f}%/yr", file=sys.stderr)
    print(f"  -> BarA#1={'PASS' if agg.bar_a_bullet1_pass else 'FAIL'} "
          f"FIT={'PASS' if fit_pass else 'FAIL'} #5b={'PASS' if dd_pass else 'FAIL'}", file=sys.stderr)
    return out

if __name__ == '__main__':
    name = sys.argv[1]
    warmup = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    run(name, warmup)
