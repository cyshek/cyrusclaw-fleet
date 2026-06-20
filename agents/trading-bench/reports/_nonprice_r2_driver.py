"""Throwaway sweep driver for non-price round 2 (B1 vol-regime, B2 credit veto).
Harness public-API only. Computes BH-SPY FP-cont Sharpe on the SAME concatenated
WF span for honest comparison, then runs both families through run_sweep.
"""
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS))

from runner.backtest import CostModel, backtest
from runner.walk_forward import NAMED_WINDOWS, walk_forward
from runner.fp_sharpe import fp_continuous_sharpe
from runner.sweep import SweepSpec, run_sweep
from runner import bars_cache


def load(cdir_name):
    cdir = WS / "strategies_candidates" / cdir_name
    spec = importlib.util.spec_from_file_location(f"cand_{cdir_name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide, params


# ---- BH-SPY benchmark on the concatenated WF span ----
def bh_spy_fp_sharpe():
    # Buy-and-hold SPY: a decide that buys once and holds. Reuse the existing
    # buy_and_hold_spy strategy semantics by a trivial decide.
    from dataclasses import dataclass
    @dataclass
    class A:
        action: str; symbol: str; notional_usd: float = 0.0; qty=None; reason: str = ""
    def decide_bh(ms, ps, p):
        sym = p.get("symbol","SPY")
        pos = ps.get(sym)
        held = float(pos.get("qty",0)) if pos else 0.0
        if held <= 0:
            return A("buy", sym, notional_usd=float(p.get("notional_usd",100.0)), reason="bh")
        return A("hold", sym, reason="bh hold")
    params = {"symbol":"SPY","timeframe":"1Day","notional_usd":100.0}
    agg = walk_forward("bh_spy_bench", params=params, decide_fn=decide_bh,
                       windows=NAMED_WINDOWS, cost_model=CostModel.alpaca_stocks())
    fps, n = fp_continuous_sharpe(agg.windows, timeframe="1Day", is_crypto=False)
    sumret = sum(w.backtest.total_return_pct for w in agg.windows) * 100
    return fps, n, sumret, agg


if __name__ == "__main__":
    bh_fps, bh_n, bh_sumret, bh_agg = bh_spy_fp_sharpe()
    print(f"=== BH-SPY benchmark (concat span) ===")
    print(f"FP-cont Sharpe = {bh_fps:+.4f} over n={bh_n} ticks; sum-window ret = {bh_sumret:+.2f}%")
    for w in bh_agg.windows:
        print(f"  {w.label:24s} ret={w.backtest.total_return_pct*100:+.2f}% dd={w.backtest.max_drawdown_pct*100:+.2f}%")

    print("\n\n############## B1: VOL-REGIME (Moreira-Muir) ##############")
    decide_b1, base_b1 = load("vol_regime_spy_mm")

    # Grid 1: VIXY-level binary, sweep lookback x band
    spec_vixy = SweepSpec(
        family="single", decide_fn=decide_b1,
        base_params={**base_b1, "vol_source":"vixy", "exposure_mode":"binary"},
        grid={"vixy_lookback":[10,20,40,60,100], "band":[0.0,0.05,0.10,0.20]},
        strategy_label="vol_regime_vixy")
    rep_vixy = run_sweep(spec_vixy, verbose=True)
    print(rep_vixy.to_markdown())

    # Grid 2: realized-vol binary, sweep vol_lookback x vol_sma x band
    spec_rv = SweepSpec(
        family="single", decide_fn=decide_b1,
        base_params={**base_b1, "vol_source":"realized", "exposure_mode":"binary"},
        grid={"vol_lookback":[10,20,40], "vol_sma":[40,60,120], "band":[0.0,0.10]},
        strategy_label="vol_regime_realized")
    rep_rv = run_sweep(spec_rv, verbose=True)
    print(rep_rv.to_markdown())

    # Grid 3: proportional inverse-vol sizing (Moreira-Muir literal), sweep vol_lookback x target_vol
    spec_prop = SweepSpec(
        family="single", decide_fn=decide_b1,
        base_params={**base_b1, "vol_source":"realized", "exposure_mode":"proportional"},
        grid={"vol_lookback":[10,20,40], "target_vol":[0.10,0.15,0.20]},
        strategy_label="vol_regime_proportional")
    rep_prop = run_sweep(spec_prop, verbose=True)
    print(rep_prop.to_markdown())

    print("\n\n############## B2: ASYMMETRIC CREDIT VETO ##############")
    decide_b2, base_b2 = load("credit_veto_spy_asym")
    spec_b2 = SweepSpec(
        family="single", decide_fn=decide_b2, base_params=base_b2,
        grid={"veto_lookback":[40,60,90], "confirm_days":[2,3,5],
              "reentry_lookback":[90,120], "reentry_days":[3,5]},
        strategy_label="credit_veto_asym")
    rep_b2 = run_sweep(spec_b2, verbose=True)
    print(rep_b2.to_markdown())

    # also a veto_band sweep variant
    spec_b2b = SweepSpec(
        family="single", decide_fn=decide_b2,
        base_params={**base_b2, "veto_lookback":60, "reentry_lookback":120},
        grid={"veto_band":[0.0,0.005,0.01], "confirm_days":[2,3,5], "reentry_days":[3,5,10]},
        strategy_label="credit_veto_asym_band")
    rep_b2b = run_sweep(spec_b2b, verbose=True)
    print(rep_b2b.to_markdown())

    print("\n=== DONE ===")
