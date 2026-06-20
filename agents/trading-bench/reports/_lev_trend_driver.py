"""Throwaway driver: leveraged-instrument trend (lane 7b).

Composes the PUBLIC runner.backtest_xsec + canonical runner.fp_sharpe over
(1) the FULL continuous 2020-12->2026 span per instrument (the real raw-return
and INSTRUMENT-LEVEL MaxDD test) and (2) the 8 NAMED_WINDOWS panel (FP-cont
Sharpe consistent with the gate). Zero edits to any protected/evaluator file.

Single-name basket = {ETF}; full $1000 deploy on risk-on, idle cash on
risk-off. BH bench = buy-and-hold the same ETF (raw-return reference) AND
buy-and-hold SPY (the SPX beat target).
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
WARMUP = 260  # calendar days primed so slow SMA/momentum lookbacks compute
INSTRUMENTS = ["TQQQ", "SOXL", "UPRO"]


def _load():
    cdir = WS / "strategies_candidates" / "leveraged_trend"
    spec = importlib.util.spec_from_file_location("cand_lev_trend", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


DECIDE, BASE = _load()


class _BHAction:
    def __init__(s, action, symbol, notional_usd=0.0):
        s.action = action; s.symbol = symbol
        s.notional_usd = notional_usd; s.qty = None; s.reason = "bh"


def _make_bh(sym):
    def _bh(ms, ps, p):
        sv = (ms.get("symbols") or {}).get(sym) or {}
        if not sv.get("has_bar"):
            return {}
        if ps.get(sym):
            return {}
        return {sym: _BHAction("buy", sym, NOTIONAL)}
    return _bh


class _W:
    def __init__(s, bt): s.backtest = bt


def _fp(bts):
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in bts], timeframe="1Day", is_crypto=False)
    return fps, nret


# ---- FULL continuous-span single backtest per instrument ----
def _full_bars(sym):
    return bars_cache.get_bars(sym, "1Day", days=2000)


def _full_run(sym, decide_fn, params):
    bars = _full_bars(sym)
    cm = CostModel.alpaca_stocks()
    bt = backtest_xsec("lev", {sym: bars}, params, decide_xsec_fn=decide_fn,
                       starting_cash=START_CASH, default_cost_model=cm)
    fps, nret = _fp([bt])
    return {
        "ret_pct": bt.total_return_pct * 100.0,
        "inst_dd": bt.worst_instrument_dd_pct * 100.0,
        "nav_dd": bt.max_drawdown_pct * 100.0,
        "trades": bt.n_trades,
        "fp": fps, "nret": nret, "n_ticks": bt.n_ticks,
        "bt": bt,
    }


# ---- 8-window panel per instrument (gate-style FP-cont) ----
def _panel_run(sym, decide_fn, params):
    cm = CostModel.alpaca_stocks()
    bts = []
    worst_inst = 0.0
    total_trades = 0
    per_win = []
    for label, end_dt, days, regime in NAMED_WINDOWS:
        bars = bars_cache.get_bars(sym, "1Day", days=days + WARMUP, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt = backtest_xsec("lev", {sym: bars}, params, decide_xsec_fn=decide_fn,
                           starting_cash=START_CASH, default_cost_model=cm)
        bts.append(bt)
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct * 100.0)
        total_trades += bt.n_trades
        per_win.append((label, regime, bt.total_return_pct * 100.0, bt.worst_instrument_dd_pct * 100.0))
    fps, nret = _fp(bts)
    return {"fp": fps, "nret": nret, "worst_inst_dd": worst_inst,
            "trades": total_trades, "per_win": per_win}


def _grid(g):
    keys = list(g.keys())
    for combo in itertools.product(*[g[k] for k in keys]):
        yield dict(zip(keys, combo))


def main():
    out = {"bench": {}, "sweeps": {}}

    # --- benchmarks: BH-ETF (full span) + BH-SPY (full span & panel) ---
    print("=== BENCHMARKS (full continuous span) ===")
    for sym in INSTRUMENTS:
        bh = _full_run(sym, _make_bh(sym), {"timeframe": "1Day", "notional_usd": NOTIONAL, "basket": [sym]})
        out["bench"][f"BH_{sym}_full"] = {k: bh[k] for k in ("ret_pct", "inst_dd", "nav_dd", "trades", "fp", "n_ticks")}
        print(f"  BH-{sym}: ret={bh['ret_pct']:+.1f}% instDD={bh['inst_dd']:.1f}% navDD={bh['nav_dd']:.1f}% FP={bh['fp']:+.3f} ticks={bh['n_ticks']}")

    spy_full = _full_run("SPY", _make_bh("SPY"), {"timeframe": "1Day", "notional_usd": NOTIONAL, "basket": ["SPY"]})
    out["bench"]["BH_SPY_full"] = {k: spy_full[k] for k in ("ret_pct", "inst_dd", "nav_dd", "trades", "fp", "n_ticks")}
    print(f"  BH-SPY (full): ret={spy_full['ret_pct']:+.1f}% instDD={spy_full['inst_dd']:.1f}% FP={spy_full['fp']:+.3f} ticks={spy_full['n_ticks']}")

    # SPY full span MATCHED to leveraged-ETF inception (2020-12) for a fair raw-return compare
    lev_ticks = out["bench"]["BH_TQQQ_full"]["n_ticks"]
    print(f"  (note: leveraged ETFs have ~{lev_ticks} bars from 2020-12; SPY full has {spy_full['n_ticks']})")

    spy_panel = _panel_run("SPY", _make_bh("SPY"), {"timeframe": "1Day", "notional_usd": NOTIONAL, "basket": ["SPY"]})
    out["bench"]["BH_SPY_panel"] = {"fp": spy_panel["fp"], "trades": spy_panel["trades"],
                                    "per_win": [[w[0], w[1], w[2]] for w in spy_panel["per_win"]]}
    spy_panel_win = {w[0]: w[2] for w in spy_panel["per_win"]}
    print(f"  BH-SPY (8-win panel): FP-cont={spy_panel['fp']:+.3f}")
    for w in spy_panel["per_win"]:
        print(f"     {w[0]:22s} {w[1]:5s} ret={w[2]:+.2f}%")

    # --- sweep grid ---
    grid = {
        "filter_mode": ["sma", "sma_cross", "momentum", "donchian"],
        "slow": [50, 100, 150, 200],
        "fast": [10, 20, 50],
        "regime_filter": [False, True],
    }

    for sym in INSTRUMENTS:
        print(f"\n===== SWEEP {sym} =====")
        rows = []
        for ov in _grid(grid):
            # fast only matters for sma_cross / donchian; collapse duplicates
            if ov["filter_mode"] in ("sma", "momentum") and ov["fast"] != 20:
                continue
            params = dict(BASE); params["symbol"] = sym; params["basket"] = [sym]; params.update(ov)
            full = _full_run(sym, DECIDE, params)
            panel = _panel_run(sym, DECIDE, params)
            rows.append({
                "params": ov,
                "full_ret": round(full["ret_pct"], 1),
                "full_inst_dd": round(full["inst_dd"], 1),
                "full_nav_dd": round(full["nav_dd"], 1),
                "full_fp": round(full["fp"], 3),
                "full_trades": full["trades"],
                "panel_fp": round(panel["fp"], 3),
                "panel_inst_dd": round(panel["worst_inst_dd"], 1),
                "panel_trades": panel["trades"],
            })
        rows.sort(key=lambda x: -x["full_fp"])
        out["sweeps"][sym] = rows
        print(f"  top by full-span FP-cont Sharpe (BH-{sym} ret={out['bench']['BH_'+sym+'_full']['ret_pct']:+.0f}% instDD={out['bench']['BH_'+sym+'_full']['inst_dd']:.0f}% FP={out['bench']['BH_'+sym+'_full']['fp']:+.2f}):")
        for r in rows[:8]:
            print(f"   fullFP={r['full_fp']:+.2f} ret={r['full_ret']:+6.0f}% instDD={r['full_inst_dd']:6.1f}% panelFP={r['panel_fp']:+.2f} tr={r['full_trades']:3d} {r['params']}")

    (WS / "reports" / "_lev_trend_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_lev_trend_results.json")


if __name__ == "__main__":
    main()
