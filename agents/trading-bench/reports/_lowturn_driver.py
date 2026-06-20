"""Driver: run a candidate xsec strategy from strategies_candidates/ through
the full 8-window walk_forward_xsec harness (corrected ruler). Reports
Sharpe, worst_instrument_dd_pct, ann-return-on-deployed, round-trip count,
BH-basket deltas, and all three front-door gates.

Loads decide_xsec by importing the candidate module directly and passing
decide_xsec_fn + params into walk_forward_xsec (the harness supports this
override path — NO protected-file edits). Cost model: alpaca_stocks (4bps RT).
"""
from __future__ import annotations
import importlib.util
import json
import math
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest import CostModel
from runner.walk_forward_xsec import (
    walk_forward_xsec, passes_bar_a_5b, passes_fitness_gate_xsec,
)

UNIVERSE = ["AAPL","MSFT","JNJ","XOM","JPM","PG","KO","WMT","CVX","HD",
            "MRK","PEP","CSCO","VZ","DIS","MCD","NKE","UNH","BA","CAT"]


def load_candidate(name: str):
    cdir = WS / "strategies_candidates" / name
    spec = importlib.util.spec_from_file_location(
        f"cand_{name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


def deployed_ann_return(agg, deployed=100.0, start_equity=1000.0):
    """Annualized return on DEPLOYED notional over the full WF span.

    Sum window total_return_usd across all windows / deployed, annualized
    by total trading days across windows. Matches report methodology:
    return is expressed on the $100 deployed cap, not bench equity.
    """
    total_pnl = 0.0
    total_days = 0
    for w in agg.windows:
        bt = w.backtest
        # total_return_usd is on $1000 bench equity; pnl in USD is direct.
        total_pnl += bt.total_return_usd
        total_days += w.days
    if total_days <= 0:
        return 0.0
    # return-on-deployed over the span
    ret_on_deployed = total_pnl / deployed
    years = total_days / 252.0
    if years <= 0:
        return 0.0
    # annualize (compound)
    try:
        return ((1.0 + ret_on_deployed) ** (1.0 / years) - 1.0) * 100.0
    except (ValueError, OverflowError):
        return ret_on_deployed / years * 100.0


def run(name: str, params_override: dict | None = None):
    decide, params = load_candidate(name)
    if params_override:
        params = dict(params)
        params.update(params_override)
    cm = CostModel.alpaca_stocks()
    assert cm.spread_bps == 2.0 and cm.fee_bps == 0.0, "cost model not active!"
    agg = walk_forward_xsec(
        name, UNIVERSE, params=params, decide_xsec_fn=decide,
        warmup_days=40, cost_model=cm)
    return agg, params


def report(name, agg, params):
    fit_pass, fit_reason = passes_fitness_gate_xsec(agg)
    dd_pass, dd_reason = passes_bar_a_5b(agg)
    ann = deployed_ann_return(agg)
    print(f"\n===== {name} =====")
    print(f"params: lookback={params.get('lookback_bars')} "
          f"rebalance={params.get('rebalance_bars')} top_k={params.get('top_k')} "
          f"min_drop={params.get('min_drop_pct','-')}")
    print(f"{'window':<22}{'reg':<6}{'trd':>5}{'ret%':>8}{'shrp':>7}"
          f"{'instrDD':>9}{'bh%':>8}{'beatBH':>7}{'A#1':>5}")
    for w in agg.windows:
        r = w.to_row()
        print(f"{r['label']:<22}{r['regime']:<6}{r['n_trades']:>5}"
              f"{r['return_pct']:>8.2f}{r['sharpe']:>7.2f}"
              f"{w.backtest.worst_instrument_dd_pct*100:>9.2f}"
              f"{r['bh_basket_pct']:>8.2f}{('Y' if r['beats_bh_basket'] else 'n'):>7}"
              f"{('Y' if r['bar_a_pass'] else 'n'):>5}")
    print(f"--- AGG: medRet={agg.median_return_pct:+.2f}% "
          f"pos={agg.pct_positive*100:.0f}% beatBH={agg.pct_beat_bh_basket*100:.0f}% "
          f"medSharpe={agg.median_sharpe:.2f} trades={agg.total_trades} "
          f"worstInstrDD={agg.worst_instrument_dd_pct:.2f}% annDeployed={ann:+.2f}%/yr")
    print(f"    Fitness: {'PASS' if fit_pass else 'FAIL'} | "
          f"BarA#1: {'PASS' if agg.bar_a_bullet1_pass else 'FAIL'} ({agg.bar_a_bullet1_reason[:60]}) | "
          f"#5b-DD: {'PASS' if dd_pass else 'FAIL'} | "
          f"clause(f)≥8%/yr: {'PASS' if ann >= 8.0 else 'FAIL'} | "
          f"Sharpe≥1.0: {'PASS' if agg.median_sharpe >= 1.0 else 'FAIL'}")
    return {"name": name, "ann_deployed": ann, "trades": agg.total_trades,
            "med_sharpe": agg.median_sharpe, "worst_instr_dd": agg.worst_instrument_dd_pct,
            "fit": fit_pass, "barA1": agg.bar_a_bullet1_pass, "dd5b": dd_pass,
            "clausef": ann >= 8.0, "sharpe1": agg.median_sharpe >= 1.0,
            "pct_pos": agg.pct_positive, "pct_beat": agg.pct_beat_bh_basket}


if __name__ == "__main__":
    # Baseline reproduce
    agg, params = run("xsec_ss_meanrev_lc20")
    report("xsec_ss_meanrev_lc20 (BASELINE)", agg, params)
