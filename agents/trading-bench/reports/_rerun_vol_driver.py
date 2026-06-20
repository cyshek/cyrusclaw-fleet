"""Notional A/B rerun: Vol-regime SPY proportional inverse-vol sleeve.

CONTROLLED A/B: re-run the candidate vol_regime_spy_prop (single-name {SPY}
fractional-deployment sleeve via PUBLIC backtest_xsec) over the SAME 8
NAMED_WINDOWS + active Alpaca cost model — at notional 100 vs 1000. ONLY the
notional/starting-cash scale changes; params (vol_source, lookbacks, target_vol,
exposure_mode, resize_band) are the candidate's locked values. Also re-runs the
prior-best REALIZED-prop cell (lb10/tv0.15, the +0.544 lead) at both notionals.

Mirrors reports/_vol_r3_driver.py composition exactly (backtest_xsec on {SPY} +
fp_continuous_sharpe over NAMED_WINDOWS), parameterized on notional. Import-only;
no protected edits.
"""
import sys, math, json, importlib.util
from pathlib import Path
WS = Path('/home/azureuser/.openclaw/agents/trading-bench/workspace')
sys.path.insert(0, str(WS))

from runner.backtest_xsec import backtest_xsec
from runner.backtest import CostModel
from runner.walk_forward import NAMED_WINDOWS
from runner.fp_sharpe import fp_continuous_sharpe
from runner import bars_cache

WARMUP = 120
CDIR = WS / 'strategies_candidates' / 'vol_regime_spy_prop'


def load():
    spec = importlib.util.spec_from_file_location('cand_vrp', str(CDIR / 'strategy.py'))
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((CDIR / 'params.json').read_text())
    return mod.decide_xsec, params


class _W:
    def __init__(self, bt): self.backtest = bt


def run_panel(decide, params, notional):
    start_cash = float(notional)
    p = dict(params); p['notional_usd'] = float(notional); p['max_notional_usd'] = float(notional)
    cm = CostModel.alpaca_stocks()
    assert cm.spread_bps == 2.0 and cm.fee_bps == 0.0, 'cost model not active'
    bts = []; total_trades = 0; worst = 0.0
    for label, end_dt, days, regime in NAMED_WINDOWS:
        bars = bars_cache.get_bars('SPY', '1Day', days=days + WARMUP, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt = backtest_xsec('vrp', {'SPY': bars}, p, decide_xsec_fn=decide,
                           starting_cash=start_cash, default_cost_model=cm)
        bts.append(bt); total_trades += bt.n_trades
        worst = min(worst, bt.worst_instrument_dd_pct)
    fps, n = fp_continuous_sharpe([_W(b) for b in bts], timeframe='1Day', is_crypto=False)
    pnl = sum(b.total_return_usd for b in bts)
    return {'notional': notional, 'fp_sharpe': round(fps, 3), 'nret': n,
            'trades': total_trades, 'worst_instr_dd': round(worst, 3),
            'pnl_usd': round(pnl, 3), 'ret_on_dep_pct': round(pnl / notional * 100, 3)}


def main():
    decide, base = load()
    out = {}
    # locked candidate config (vixy_ratio prop)
    for tag, override in {
        'locked_vixy_ratio_prop': {},
        'realized_prop_lb10_tv0.15 (prior best +0.544)': {
            'vol_source': 'realized', 'exposure_mode': 'proportional',
            'vol_lookback': 10, 'target_vol': 0.15, 'resize_band': 0.15},
    }.items():
        p = dict(base); p.update(override)
        r100 = run_panel(decide, p, 100.0)
        r1000 = run_panel(decide, p, 1000.0)
        d = round(r1000['fp_sharpe'] - r100['fp_sharpe'], 3)
        out[tag] = {'n100': r100, 'n1000': r1000, 'delta_fp': d}
        print(f"{tag:<46} FP100={r100['fp_sharpe']:+.3f} FP1000={r1000['fp_sharpe']:+.3f} d={d:+.3f} "
              f"| trd {r100['trades']}/{r1000['trades']} | retDep {r100['ret_on_dep_pct']:+.2f}/{r1000['ret_on_dep_pct']:+.2f}%")
    open('reports/_rerun_vol_results.json', 'w').write(json.dumps(out, indent=2))
    print('wrote reports/_rerun_vol_results.json')


if __name__ == '__main__':
    main()
