"""Driver for the DISPERSED-UNIVERSE cross-sectional momentum confirm-or-kill.

Reuses the $1000-correct momentum candidate (strategies_candidates/
xsec_ss_momentum_lc20_v2) UNCHANGED — only points it at the wider 95-name
dispersed universe (baskets/dispersed_xsec.txt) and sweeps K for the bigger N.

Reports per variant (identical methodology to the prior 20-name memo so the
numbers are directly comparable):
  - FP-cont Sharpe (load-bearing clause-(a) number, continuous concatenated
    equity, sqrt(252))
  - median-window Sharpe (generous/secondary)
  - worst_instrument_dd_pct (#5(b))
  - annualized return on DEPLOYED notional (clause (f))
  - round-trip trade count
  - per-window BH-basket delta + BarA#1

Cost model: CostModel.alpaca_stocks() (2bps spread one-way -> 4bps RT),
ASSERTED active. Warmup 420d primes the 252-bar lookback. NO protected files
touched (decide_xsec_fn+params override path).
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

CAND = "xsec_ss_momentum_lc20_v2"


def load_universe():
    path = WS / "baskets" / "dispersed_xsec.txt"
    syms = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            syms.append(line)
    return syms


UNIVERSE = load_universe()


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
    equity returns into ONE series, annualize with sqrt(252)."""
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


def run(params_override=None, warmup_days=420, universe=None):
    decide, params = load_candidate(CAND)
    params = dict(params)
    if params_override:
        params.update(params_override)
    # xsec_basket_size must track top_k so the per-day trade cap allows a full
    # K-leg rebalance (close K + open K) — else big-K rebalances truncate.
    params["xsec_basket_size"] = int(params.get("top_k", 5))
    cm = CostModel.alpaca_stocks()
    assert cm.spread_bps == 2.0 and cm.fee_bps == 0.0, "cost model not active!"
    agg = walk_forward_xsec(
        CAND, universe or UNIVERSE, params=params, decide_xsec_fn=decide,
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
          f"N={len(agg.basket)} notional={params.get('notional_usd')} deployed={deployed}")
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
    front_door = (fps >= 1.0) and dd_pass and (ann >= 8.0)
    print(f"    >>> FRONT-DOOR (Sharpe>=1.0 AND #5b AND ann>=8%): "
          f"{'*** PASS ***' if front_door else 'REJECT'}")
    return {"label": label, "fp_sharpe": fps, "med_sharpe": agg.median_sharpe,
            "ann": ann, "trades": agg.total_trades,
            "worst_dd": agg.worst_instrument_dd_pct,
            "fit": fit_pass, "barA1": agg.bar_a_bullet1_pass, "dd5b": dd_pass,
            "clausef": ann >= 8.0, "fpsharpe1": fps >= 1.0,
            "pos": agg.pct_positive, "beat": agg.pct_beat_bh_basket,
            "front_door": front_door}


# Core sweep for N=95: top-decile (K=10) and top-quintile (K=19),
# canonical 12-1 monthly + faster 6-1 monthly. Canonical 12-1 K10 is primary.
VARIANTS = {
    "12-1 monthly K10 (decile, canonical)": {"lookback_bars": 252, "skip_bars": 21, "rebalance_months": 1, "top_k": 10},
    "12-1 monthly K19 (quintile)":          {"lookback_bars": 252, "skip_bars": 21, "rebalance_months": 1, "top_k": 19},
    "6-1 monthly K10 (decile)":             {"lookback_bars": 126, "skip_bars": 21, "rebalance_months": 1, "top_k": 10},
    "6-1 monthly K19 (quintile)":           {"lookback_bars": 126, "skip_bars": 21, "rebalance_months": 1, "top_k": 19},
}

if __name__ == "__main__":
    print(f"UNIVERSE N={len(UNIVERSE)}: {' '.join(UNIVERSE)}")
    results = []
    for label, ov in VARIANTS.items():
        agg, params = run(ov)
        deployed = float(params.get("notional_usd", 1000.0))
        results.append(report(label, agg, params, deployed))
    print("\n\n===== SUMMARY TABLE =====")
    print(f"{'variant':<40}{'FPcont':>8}{'medWin':>8}{'ann%':>8}{'trd':>6}{'instrDD':>9}{'verdict':>9}")
    for r in results:
        verdict = "PASS?" if r["front_door"] else "REJECT"
        print(f"{r['label']:<40}{r['fp_sharpe']:>8.2f}{r['med_sharpe']:>8.2f}"
              f"{r['ann']:>8.1f}{r['trades']:>6}{r['worst_dd']:>9.2f}{verdict:>9}")
