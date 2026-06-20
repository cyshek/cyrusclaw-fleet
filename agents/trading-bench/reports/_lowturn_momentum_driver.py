"""Throwaway driver for the LOW-TURNOVER DUAL-MOMENTUM lane.

Composes the PUBLIC runner.backtest_xsec + canonical fp_continuous_sharpe over
NAMED_WINDOWS directly (import-only, no protected-file edit) — same pattern as
reports/_vol_r3_driver.py. Multi-symbol basket -> full xsec path.

WARMUP is set large (480 calendar days ~ 330 trading bars) so a 252-bar 12-1
lookback computes from the FIRST tick of each window. Data starts 2020-07-27,
so the 2022-H1 window (signal needs bars back to ~2021-02 for a 12mo lookback)
is the binding constraint — handled by the warmup fetch + has-signal guards.
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

NOTIONAL = 100.0
START_CASH = 1000.0
WARMUP = 480  # calendar days primed so 12-1 (252+21) lookback computes


def _load(cdir_name):
    cdir = WS / "strategies_candidates" / cdir_name
    spec = importlib.util.spec_from_file_location(
        f"cand_{cdir_name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


DECIDE, BASE = _load("lowturn_momentum")


class _BHAction:
    def __init__(s, action, symbol, notional_usd=0.0):
        s.action = action; s.symbol = symbol
        s.notional_usd = notional_usd; s.qty = None; s.reason = "bh"


def _bh_decide(ms, ps, p):
    sv = (ms.get("symbols") or {}).get("SPY") or {}
    if not sv.get("has_bar"):
        return {}
    if ps.get("SPY"):
        return {}
    return {"SPY": _BHAction("buy", "SPY", NOTIONAL)}


def _all_syms(params):
    s = set(params.get("risk_sleeve", []))
    s |= set(params.get("bond_sleeve", []))
    s.add(params.get("safe_asset", "BIL"))
    return sorted(s)


def _run_panel(decide_fn, params, basket, track_deploy=False, track_spy_corr=False):
    acc = {"sum": 0.0, "n": 0}
    cm = CostModel.alpaca_stocks()
    window_bts = []
    per_win = []
    worst_inst = 0.0
    total_trades = 0
    spy_exposure_ticks = {"in_spy": 0, "n": 0}

    def wrapped(ms, ps, p):
        if track_deploy:
            tot = 0.0
            for sym, pv in (ps or {}).items():
                tot += float(pv.get("market_value", 0.0))
            acc["sum"] += tot / NOTIONAL
            acc["n"] += 1
        if track_spy_corr:
            spy_exposure_ticks["n"] += 1
            for sym in ("SPY", "QQQ", "IWM"):
                if ps.get(sym):
                    spy_exposure_ticks["in_spy"] += 1
                    break
        return decide_fn(ms, ps, p)

    for label, end_dt, days, regime in NAMED_WINDOWS:
        fetch_days = days + WARMUP
        bars_by = {}
        for sym in basket:
            b = bars_cache.get_bars(sym, "1Day", days=fetch_days, end_dt=end_dt)
            if b and len(b) >= 10:
                bars_by[sym] = b
        if not bars_by or (len(basket) >= 2 and len(bars_by) < 2):
            continue
        bt = backtest_xsec("ltm", bars_by, params, decide_xsec_fn=wrapped,
                           starting_cash=START_CASH, default_cost_model=cm)
        window_bts.append(bt)
        per_win.append((label, regime, bt.total_return_pct, bt.worst_instrument_dd_pct,
                        bt.n_trades))
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct)
        total_trades += bt.n_trades

    class _W:
        def __init__(s, bt): s.backtest = bt
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in window_bts],
                                     timeframe="1Day", is_crypto=False)
    avg_deploy = (acc["sum"] / acc["n"]) if acc["n"] else None
    spy_occ = (spy_exposure_ticks["in_spy"] / spy_exposure_ticks["n"]) \
        if spy_exposure_ticks["n"] else None
    return {
        "fp": fps, "nret": nret, "avg_deploy": avg_deploy,
        "worst_inst_dd": worst_inst, "total_trades": total_trades,
        "per_win": per_win, "window_bts": window_bts, "spy_occ": spy_occ,
    }


def _ann_on_deployed(window_bts):
    tot_pnl = sum(bt.total_return_usd for bt in window_bts)
    years = sum(bt.n_ticks for bt in window_bts) / 252.0
    ret_on_dep = tot_pnl / NOTIONAL
    try:
        ann = ((1.0 + ret_on_dep) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0
    except (ValueError, OverflowError):
        ann = (ret_on_dep / years) * 100.0 if years > 0 else 0.0
    return ann, tot_pnl, years


def main():
    print("=== BH-SPY bench ===")
    bh = _run_panel(_bh_decide, {"timeframe": "1Day", "notional_usd": NOTIONAL,
                                 "basket": ["SPY"], "xsec_basket_size": 1},
                    basket=["SPY"])
    bh_win = {w[0]: w[2] for w in bh["per_win"]}
    bh_ann, bh_pnl, _ = _ann_on_deployed(bh["window_bts"])
    print(f"BH-SPY FP-cont={bh['fp']:+.3f} trades={bh['total_trades']} ann={bh_ann:+.2f}% pnl=${bh_pnl:+.2f}")
    for w in bh["per_win"]:
        print(f"   {w[0]:20s} {w[1]:5s} ret={w[2]*100:+.2f}% dd={w[3]:.2f}%")

    base_basket = _all_syms(BASE)
    print(f"\nbasket={base_basket}")

    # Pre-committed sweep grid (lookback x skip x top_k x abs_margin).
    grid = {
        "lookback_bars": [126, 189, 252],
        "skip_bars": [21, 63],
        "top_k": [1, 2, 3],
        "abs_margin": [0.0, 0.02],
    }
    keys = list(grid.keys())
    rows = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        override = dict(zip(keys, combo))
        params = dict(BASE); params.update(override)
        r = _run_panel(DECIDE, params, basket=base_basket,
                       track_deploy=True, track_spy_corr=True)
        beats = sum(1 for w in r["per_win"] if w[2] > bh_win.get(w[0], -1e9))
        nwin = len(r["per_win"])
        ann, pnl, years = _ann_on_deployed(r["window_bts"])
        # 2022-H1 bear behavior
        bear22 = next((w for w in r["per_win"] if w[0] == "2022-H1 bear"), None)
        rows.append({
            "params": override, "fp": round(r["fp"], 3),
            "avg_deploy": round(r["avg_deploy"], 3) if r["avg_deploy"] is not None else None,
            "spy_occ": round(r["spy_occ"], 3) if r["spy_occ"] is not None else None,
            "worst_dd": round(r["worst_inst_dd"], 2),
            "trades": r["total_trades"],
            "beats_bh_win": f"{beats}/{nwin}",
            "ann_deployed": round(ann, 2),
            "tot_pnl_usd": round(pnl, 2),
            "bear22_ret": round(bear22[2] * 100, 2) if bear22 else None,
            "per_win": [[w[0], round(w[2] * 100, 2), round(w[3], 2), w[4]] for w in r["per_win"]],
        })
    rows.sort(key=lambda x: -x["fp"])
    out = {
        "bh": {"fp": round(bh["fp"], 3), "trades": bh["total_trades"],
               "ann": round(bh_ann, 2),
               "per_win": [[w[0], w[1], round(w[2] * 100, 2)] for w in bh["per_win"]]},
        "basket": base_basket, "grid": grid, "rows": rows,
    }
    (WS / "reports" / "_lowturn_momentum_results.json").write_text(
        json.dumps(out, indent=2, default=str))
    print("\n=== top cells by FP-cont Sharpe ===")
    for rr in rows[:12]:
        print(f"  FP={rr['fp']:+.3f} dep={rr['avg_deploy']} spyOcc={rr['spy_occ']} "
              f"ann={rr['ann_deployed']:+.2f} dd={rr['worst_dd']:.1f} tr={rr['trades']} "
              f"beatBH={rr['beats_bh_win']} bear22={rr['bear22_ret']} {rr['params']}")
    print("\nwrote reports/_lowturn_momentum_results.json")


if __name__ == "__main__":
    main()
