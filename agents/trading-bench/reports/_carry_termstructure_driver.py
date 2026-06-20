"""Throwaway driver: VIX term-structure CARRY sweep.

Composes the PUBLIC runner.backtest_xsec + canonical fp_sharpe over the 8
NAMED_WINDOWS (import-only, NO edits to any protected/evaluator file) — the
same composition pattern reports/_vol_r3_driver.py used. Multi-symbol basket
{VIXY, VIXM, SVXY}: VIXY/VIXM drive the carry signal, SVXY is the traded
roll-harvest leg. Active Alpaca cost model. warmup primes the ratio lookback
inside each window.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import sys
from pathlib import Path

WS = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace")
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

from runner.backtest_xsec import backtest_xsec
from runner.backtest import CostModel
from runner.walk_forward import NAMED_WINDOWS
from runner.fp_sharpe import fp_continuous_sharpe
from runner import bars_cache

NOTIONAL = 1000.0
START_CASH = 1000.0
WARMUP = 200  # calendar days primed before each window so the ratio lookback fills
BASKET = ["VIXY", "VIXM", "SVXY"]


def _load():
    cdir = WS / "strategies_candidates" / "carry_termstructure"
    spec = importlib.util.spec_from_file_location("cand_carry", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


DECIDE, BASE = _load()


class _A:
    def __init__(s, action, symbol, notional_usd=0.0):
        s.action = action; s.symbol = symbol
        s.notional_usd = notional_usd; s.qty = None; s.reason = "bh"


def _bh_decide(sym_target):
    def d(ms, ps, p):
        sv = (ms.get("symbols") or {}).get(sym_target) or {}
        if not sv.get("has_bar"):
            return {}
        if ps.get(sym_target):
            return {}
        return {sym_target: _A("buy", sym_target, NOTIONAL)}
    return d


def _fetch_basket(end_dt, days):
    out = {}
    for s in BASKET:
        b = bars_cache.get_bars(s, "1Day", days=days + WARMUP, end_dt=end_dt)
        if b and len(b) >= 10:
            out[s] = b
    return out


def _run_panel(decide_fn, params, track_deploy=False):
    acc = {"sum": 0.0, "n": 0}
    traded = params.get("traded_symbol", "SVXY")

    def wrapped(ms, ps, p):
        if track_deploy:
            pos = ps.get(traded)
            val = float(pos.get("market_value", 0.0)) if pos else 0.0
            acc["sum"] += val / NOTIONAL
            acc["n"] += 1
        return decide_fn(ms, ps, p)

    window_bts = []
    per_win = []
    worst_inst = 0.0
    total_trades = 0
    cm = CostModel.alpaca_stocks()
    for label, end_dt, days, regime in NAMED_WINDOWS:
        bbs = _fetch_basket(end_dt, days)
        if len(bbs) < 1:
            continue
        bt = backtest_xsec("carry", bbs, params, decide_xsec_fn=wrapped,
                           starting_cash=START_CASH, default_cost_model=cm)
        window_bts.append(bt)
        per_win.append((label, regime, bt.total_return_pct, bt.worst_instrument_dd_pct, bt.n_trades))
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct)
        total_trades += bt.n_trades

    class _W:
        def __init__(s, bt): s.backtest = bt
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in window_bts],
                                     timeframe="1Day", is_crypto=False)
    avg_deploy = (acc["sum"] / acc["n"]) if acc["n"] else None
    return {"fp": fps, "nret": nret, "avg_deploy": avg_deploy,
            "worst_inst_dd": worst_inst, "total_trades": total_trades,
            "per_win": per_win}


def _grid(g):
    keys = list(g.keys())
    for combo in itertools.product(*[g[k] for k in keys]):
        yield dict(zip(keys, combo))


def main():
    print("=== BENCHES (single-name backtest_xsec, full panel) ===")
    for bsym in ["SPY", "SVXY", "VIXY"]:
        # benches still need the basket present so the clock is identical;
        # just run BH on the one symbol within the same fetched panel.
        bres = _run_panel(_bh_decide(bsym),
                          {"timeframe": "1Day", "notional_usd": NOTIONAL,
                           "basket": BASKET, "traded_symbol": bsym},
                          track_deploy=False)
        print(f"BH-{bsym:4s} FP-cont={bres['fp']:+.3f} nret={bres['nret']} trades={bres['total_trades']}")
        if bsym == "SPY":
            for w in bres["per_win"]:
                print(f"     {w[0]:20s} {w[1]:5s} ret={w[2]*100:+.2f}%")

    grid = {
        "ratio_lookback": [20, 40, 60, 90, 120],
        "enter_mult": [0.95, 1.00, 1.05],
        "exit_level": [0.95, 1.00, 1.05],
        "band": [0.0, 0.05],
    }
    results = []
    for cell in _grid(grid):
        params = dict(BASE)
        params.update(cell)
        r = _run_panel(DECIDE, params, track_deploy=True)
        results.append((cell, r))
        print(f"lb={cell['ratio_lookback']:3d} em={cell['enter_mult']:.2f} "
              f"ex={cell['exit_level']:.2f} band={cell['band']:.2f} | "
              f"FP={r['fp']:+.3f} dep={r['avg_deploy'] or 0:.2f} "
              f"trades={r['total_trades']:3d} wDD={r['worst_inst_dd']:.1f}%")

    results.sort(key=lambda x: x[1]["fp"], reverse=True)
    print("\n=== TOP 8 by FP-cont ===")
    for cell, r in results[:8]:
        print(f"FP={r['fp']:+.3f} dep={r['avg_deploy'] or 0:.2f} trades={r['total_trades']:3d} "
              f"wDD={r['worst_inst_dd']:5.1f}% :: {cell}")
        for w in r["per_win"]:
            print(f"        {w[0]:20s} {w[1]:5s} ret={w[2]*100:+6.2f}% trades={w[4]}")

    out = {"results": [{"cell": c, "fp": r["fp"], "dep": r["avg_deploy"],
                        "trades": r["total_trades"], "wDD": r["worst_inst_dd"],
                        "per_win": [[w[0], w[1], w[2], w[4]] for w in r["per_win"]]}
                       for c, r in results]}
    (WS / "reports" / "_carry_termstructure_results.json").write_text(json.dumps(out, indent=2))
    print("\nwrote reports/_carry_termstructure_results.json")


if __name__ == "__main__":
    main()
