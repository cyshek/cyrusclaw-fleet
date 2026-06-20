"""Notional A/B rerun: Dollar lead-lag (UUP->SPY) long/flat overlay.

CONTROLLED A/B: re-run the EXACT prior construction (candidate
dollar_leadlag_spy_6df4f1, SMA-63, monthly rebalance, long/flat) over the SAME
full real Alpaca daily span, SAME active Alpaca cost model — at notional_usd=100
(prior) vs notional_usd=1000 (post-fix). ONLY notional changes.

Composes the PUBLIC runner.backtest.backtest + the candidate's decide() +
canonical runner.fp_sharpe.fp_continuous_sharpe. Import-only; no protected edits.
"""
import sys, math, json, importlib.util
from pathlib import Path
WS = Path('/home/azureuser/.openclaw/agents/trading-bench/workspace')
sys.path.insert(0, str(WS))

from runner.backtest import backtest, CostModel
from runner.fp_sharpe import fp_continuous_sharpe
from runner import bars_cache

CDIR = WS / 'strategies_candidates' / 'dollar_leadlag_spy_6df4f1'


def load():
    spec = importlib.util.spec_from_file_location('cand_dll', str(CDIR / 'strategy.py'))
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((CDIR / 'params.json').read_text())
    return mod.decide, params


class _W:
    def __init__(self, bt): self.backtest = bt


def run_one(decide, base, spy_bars, uup_series, notional):
    p = dict(base)
    p['notional_usd'] = float(notional)
    p['_uup_series'] = uup_series
    cm = CostModel.alpaca_stocks()
    assert cm.spread_bps == 2.0 and cm.fee_bps == 0.0, 'cost model not active'
    bt = backtest('dollar_leadlag', spy_bars, p, starting_cash=1000.0,
                  decide_fn=decide, cost_model=cm)
    fps, n = fp_continuous_sharpe([_W(bt)], timeframe='1Day', is_crypto=False)
    # ann return on deployed notional
    pnl = bt.total_return_usd
    years = len(spy_bars) / 252.0
    ron = pnl / float(notional)
    try:
        ann = ((1.0 + ron) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0
    except (ValueError, OverflowError):
        ann = ron / years * 100.0
    return {
        'notional': notional, 'fp_sharpe': round(fps, 3), 'nret': n,
        'trades': bt.n_trades, 'total_return_pct': round(bt.total_return_pct * 100, 3),
        'total_cost_usd': round(getattr(bt, 'total_costs_usd', float('nan')), 4)
            if hasattr(bt, 'total_costs_usd') else None,
        'ann_deployed': round(ann, 3), 'pnl_usd': round(pnl, 4),
    }


def main():
    decide, base = load()
    # full real daily span (data floor 2020-07-27 .. latest) — same as prior report
    spy_bars = bars_cache.get_bars('SPY', '1Day', days=3000)
    uup_bars = bars_cache.get_bars('UUP', '1Day', days=3000)
    uup_series = [((b.get('t') or '')[:10], float(b['c'])) for b in (uup_bars or [])]
    uup_series.sort(key=lambda x: x[0])
    print(f"SPY bars={len(spy_bars)} span {spy_bars[0]['t'][:10]}..{spy_bars[-1]['t'][:10]} | UUP bars={len(uup_series)}")
    r100 = run_one(decide, base, spy_bars, uup_series, 100.0)
    r1000 = run_one(decide, base, spy_bars, uup_series, 1000.0)
    delta = round(r1000['fp_sharpe'] - r100['fp_sharpe'], 3)
    # sensitivity sweep at $1000 to confirm plateau ceiling unchanged
    sens = {}
    for sma in [21, 42, 63, 84, 126]:
        b = dict(base); b['signal_sma_period'] = sma
        rr = run_one(decide, b, spy_bars, uup_series, 1000.0)
        sens[sma] = rr
    out = {'n100': r100, 'n1000': r1000, 'delta_fp': delta, 'sens1000': sens}
    print(f"FP100={r100['fp_sharpe']:+.3f} FP1000={r1000['fp_sharpe']:+.3f} d={delta:+.3f} "
          f"| trd {r100['trades']}/{r1000['trades']} | cost ${r100['total_cost_usd']}/{r1000['total_cost_usd']} "
          f"| ann {r100['ann_deployed']:+.2f}/{r1000['ann_deployed']:+.2f}%")
    print("SMA sweep @ $1000:")
    for sma, rr in sens.items():
        print(f"  SMA{sma:<4} FP={rr['fp_sharpe']:+.3f} trd={rr['trades']} ann={rr['ann_deployed']:+.2f}%")
    open('reports/_rerun_dollar_results.json', 'w').write(json.dumps(out, indent=2))
    print("wrote reports/_rerun_dollar_results.json")


if __name__ == '__main__':
    main()
