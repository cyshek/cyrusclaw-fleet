"""Driver for the single-stock MOMENTUM monthly-cadence swing.

Runs the v2 momentum candidate (from strategies_candidates/) through the
full 8-window walk_forward_xsec on the corrected ruler. Reports per-variant:
  - full-period CONTINUOUS-SPAN Sharpe (the load-bearing clause-(a) number)
  - median-window Sharpe (clearly the generous/secondary number)
  - worst_instrument_dd_pct (GATE #5(b))
  - annualized return on DEPLOYED notional (clause (f))
  - round-trip trade count
  - per-window BH-basket delta + BarA#1 verdict

Cost model: CostModel.alpaca_stocks() (2bps spread one-way -> 4bps RT),
asserted active. Warmup defaults to 420d so the 252-bar lookback variants
can prime (avoids the ZeroTradesError warmup-starvation trap). NO protected
runner files are touched — we use the decide_xsec_fn+params override path.
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

UNIVERSE = ["AAPL", "MSFT", "JNJ", "XOM", "JPM", "PG", "KO", "WMT", "CVX", "HD",
            "MRK", "PEP", "CSCO", "VZ", "DIS", "MCD", "NKE", "UNH", "BA", "CAT"]

CAND = "xsec_ss_momentum_lc20_v2"


def load_candidate(name: str):
    cdir = WS / "strategies_candidates" / name
    spec = importlib.util.spec_from_file_location(
        f"cand_{name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


def fp_continuous_sharpe(agg):
    """Full-period continuous-span Sharpe: concatenate every window's per-tick
    equity returns into ONE series, annualize with sqrt(252). This is the
    honest clause-(a) number, NOT median-of-windows."""
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


def deployed_ann_return(agg, deployed):
    """Annualized (compound) return on DEPLOYED notional over the full WF
    span. total_return_usd is direct USD pnl on each window; divide by the
    deployed notional cap (NOT bench equity), annualize by total days."""
    total_pnl = sum(w.backtest.total_return_usd for w in agg.windows)
    total_days = sum(w.days for w in agg.windows)
    if total_days <= 0 or deployed <= 0:
        return 0.0
    ret_on_deployed = total_pnl / deployed
    years = total_days / 252.0
    if years <= 0:
        return 0.0
    try:
        return ((1.0 + ret_on_deployed) ** (1.0 / years) - 1.0) * 100.0
    except (ValueError, OverflowError):
        return ret_on_deployed / years * 100.0


def run(params_override=None, warmup_days=420):
    decide, params = load_candidate(CAND)
    if params_override:
        params = dict(params)
        params.update(params_override)
    cm = CostModel.alpaca_stocks()
    assert cm.spread_bps == 2.0 and cm.fee_bps == 0.0, "cost model not active!"
    agg = walk_forward_xsec(
        CAND, UNIVERSE, params=params, decide_xsec_fn=decide,
        warmup_days=warmup_days, cost_model=cm)
    return agg, params


def report(label, agg, params, deployed):
    fit_pass, _ = passes_fitness_gate_xsec(agg)
    dd_pass, _ = passes_bar_a_5b(agg)
    fps, nret = fp_continuous_sharpe(agg)
    ann = deployed_ann_return(agg, deployed)
    print(f"\n===== {label} =====")
    print(f"params: lb={params.get('lookback_bars')} skip={params.get('skip_bars')} "
          f"reb_months={params.get('rebalance_months')} K={params.get('top_k')} "
          f"notional={params.get('notional_usd')} deployed_basis={deployed}")
    print(f"{'window':<22}{'reg':<6}{'trd':>5}{'ret%':>8}{'shrp':>7}"
          f"{'instrDD':>9}{'bh%':>8}{'beat':>5}{'A#1':>5}")
    for w in agg.windows:
        r = w.to_row()
        print(f"{r['label']:<22}{r['regime']:<6}{r['n_trades']:>5}"
              f"{r['return_pct']:>8.2f}{r['sharpe']:>7.2f}"
              f"{w.backtest.worst_instrument_dd_pct*100:>9.2f}"
              f"{r['bh_basket_pct']:>8.2f}{('Y' if r['beats_bh_basket'] else 'n'):>5}"
              f"{('Y' if r['bar_a_pass'] else 'n'):>5}")
    print(f"--- AGG: FPcont_Sharpe={fps:+.2f} (nret={nret}) | medWinSharpe={agg.median_sharpe:+.2f} "
          f"| medRet={agg.median_return_pct:+.2f}% pos={agg.pct_positive*100:.0f}% "
          f"beatBH={agg.pct_beat_bh_basket*100:.0f}% trades={agg.total_trades} "
          f"worstInstrDD={agg.worst_instrument_dd_pct:.2f}% annDeployed={ann:+.2f}%/yr")
    print(f"    GATES: Fitness={'P' if fit_pass else 'F'} | "
          f"BarA#1={'P' if agg.bar_a_bullet1_pass else 'F'} | "
          f"#5b-DD={'P' if dd_pass else 'F'} | "
          f"clause(f)>=8%/yr={'P' if ann >= 8.0 else 'F'} | "
          f"FPcont-Sharpe>=1.0={'P' if fps >= 1.0 else 'F'}")
    return {"label": label, "fp_sharpe": fps, "med_sharpe": agg.median_sharpe,
            "ann": ann, "trades": agg.total_trades,
            "worst_dd": agg.worst_instrument_dd_pct,
            "fit": fit_pass, "barA1": agg.bar_a_bullet1_pass, "dd5b": dd_pass,
            "clausef": ann >= 8.0, "fpsharpe1": fps >= 1.0,
            "pos": agg.pct_positive, "beat": agg.pct_beat_bh_basket}


# The 5 core variants: lookback x cadence x K sweep.
VARIANTS = {
    "12-1 monthly K5 (baseline-corrected)": {"lookback_bars": 252, "skip_bars": 21, "rebalance_months": 1, "top_k": 5},
    "6-1 monthly K5":  {"lookback_bars": 126, "skip_bars": 21, "rebalance_months": 1, "top_k": 5},
    "3-1 monthly K5":  {"lookback_bars": 63,  "skip_bars": 21, "rebalance_months": 1, "top_k": 5},
    "12-1 quarterly K5": {"lookback_bars": 252, "skip_bars": 21, "rebalance_months": 3, "top_k": 5},
    "12-1 monthly K3": {"lookback_bars": 252, "skip_bars": 21, "rebalance_months": 1, "top_k": 3},
    "12-1 monthly K8": {"lookback_bars": 252, "skip_bars": 21, "rebalance_months": 1, "top_k": 8},
}

if __name__ == "__main__":
    results = []
    for label, ov in VARIANTS.items():
        agg, params = run(ov)
        deployed = float(params.get("notional_usd", 1000.0))
        results.append(report(label, agg, params, deployed))
    print("\n\n===== SUMMARY TABLE =====")
    print(f"{'variant':<38}{'FPcont':>8}{'medWin':>8}{'ann%':>8}{'trd':>5}{'instrDD':>9}{'verdict':>9}")
    for r in results:
        passes = r["fpsharpe1"] and r["dd5b"] and r["clausef"]
        verdict = "PASS?" if passes else "REJECT"
        print(f"{r['label']:<38}{r['fp_sharpe']:>8.2f}{r['med_sharpe']:>8.2f}"
              f"{r['ann']:>8.1f}{r['trades']:>5}{r['worst_dd']:>9.2f}{verdict:>9}")
