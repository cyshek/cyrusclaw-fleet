"""Throwaway driver — REAL multi-name single-stock CROSS-SECTIONAL UNIVERSE lane.

Composes the PUBLIC runner.backtest_xsec + canonical fp_continuous_sharpe over
NAMED_WINDOWS (import-only, NO protected-file edit) — same pattern as
reports/_lowturn_momentum_driver.py / _vol_r3_driver.py.

Tests TWO cross-sectional anomalies on a 40-name large-cap universe:
  (1) Jegadeesh-Titman 12-1 momentum (rank top-K trailing return)
  (2) AHXZ low-vol (rank bottom-K trailing realized vol)
Long-only, monthly rebalance, $1000 book / $100 deployed.

Discipline applied (same as every other lane):
  - honest FP-continuous-span Sharpe (the load-bearing ruler)
  - 8-window panel
  - beat-BH-SPX per window + full-span
  - cost model ON (CostModel.alpaca_stocks)
  - plateau-vs-knife (neighbor cells around any winner)
  - instrument-level (un-diluted) DD
  - RELABEL guard: PnL correlation to SPY (is this disguised BH-SPX beta?)
  - ann-return-on-deployed (clause f honesty)
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
from runner.fp_sharpe import fp_continuous_sharpe, equity_curve_returns
from runner import bars_cache

NOTIONAL = 100.0
START_CASH = 1000.0
WARMUP = 480  # calendar days primed so 252+21 lookback computes from tick 0

# Fixed liquid large-cap universe KNOWN to exist across the whole window
# (all 40 verified 1461-1464 bars from 2020-07-27). SURVIVORSHIP CAVEAT:
# this is a fixed set of names that SURVIVED to 2026 -> introduces
# survivorship bias (no delisted/failed names, no index reconstitution).
# Flagged honestly in the report; NOT hidden.
UNIVERSE = ["AAPL","MSFT","AMZN","GOOGL","META","NVDA","JPM","JNJ","V","PG",
            "HD","MA","UNH","XOM","BAC","DIS","KO","PEP","CSCO","WMT",
            "ADBE","CRM","NFLX","INTC","CMCSA","T","VZ","ABT","NKE","MRK",
            "PFE","TMO","AVGO","COST","MCD","QCOM","TXN","HON","ORCL","WFC"]


def _load(modfile, fn="decide_xsec"):
    p = WS / "strategies_candidates" / "xsec_universe" / modfile
    spec = importlib.util.spec_from_file_location(modfile.replace(".", "_"), str(p))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, fn)


MOM = _load("strategy_momentum.py")
LOWVOL = _load("strategy_lowvol.py")


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


def _spy_window_returns(end_dt, days):
    """SPY per-tick equity returns over a window (for PnL-corr relabel guard),
    aligned to the window only (matches what BH bench would earn)."""
    b = bars_cache.get_bars("SPY", "1Day", days=days + WARMUP, end_dt=end_dt)
    return b


def _run_panel(decide_fn, params, basket, track_corr_spy=False):
    cm = CostModel.alpaca_stocks()
    window_bts = []
    per_win = []
    worst_inst = 0.0
    total_trades = 0
    strat_rets_all = []   # for relabel corr
    spy_rets_all = []

    for label, end_dt, days, regime in NAMED_WINDOWS:
        fetch_days = days + WARMUP
        bars_by = {}
        for sym in basket:
            b = bars_cache.get_bars(sym, "1Day", days=fetch_days, end_dt=end_dt)
            if b and len(b) >= 10:
                bars_by[sym] = b
        if not bars_by or (len(basket) >= 2 and len(bars_by) < 2):
            continue
        bt = backtest_xsec("xsecuni", bars_by, params, decide_xsec_fn=decide_fn,
                           starting_cash=START_CASH, default_cost_model=cm)
        window_bts.append(bt)
        per_win.append((label, regime, bt.total_return_pct,
                        bt.worst_instrument_dd_pct, bt.n_trades))
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct)
        total_trades += bt.n_trades

        if track_corr_spy:
            srets = equity_curve_returns(bt.equity_curve)
            spy_b = bars_cache.get_bars("SPY", "1Day", days=fetch_days, end_dt=end_dt)
            # align SPY closes to the window tick count of the strategy curve
            # by taking the LAST (len(srets)+1) SPY closes in this window span.
            if spy_b:
                spy_closes = [float(x["c"]) for x in spy_b]
                need = len(srets) + 1
                tail = spy_closes[-need:] if len(spy_closes) >= need else spy_closes
                spy_r = equity_curve_returns(tail)
                m = min(len(srets), len(spy_r))
                if m > 1:
                    strat_rets_all.extend(srets[-m:])
                    spy_rets_all.extend(spy_r[-m:])

    class _W:
        def __init__(s, bt): s.backtest = bt
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in window_bts],
                                     timeframe="1Day", is_crypto=False)

    corr = None
    if track_corr_spy and len(strat_rets_all) > 2:
        corr = _pearson(strat_rets_all, spy_rets_all)

    return {"fp": fps, "nret": nret, "worst_inst_dd": worst_inst,
            "total_trades": total_trades, "per_win": per_win,
            "window_bts": window_bts, "spy_corr": corr}


def _pearson(a, b):
    n = min(len(a), len(b))
    a = a[:n]; b = b[:n]
    if n < 2:
        return None
    ma = sum(a) / n; mb = sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return None
    return cov / (va ** 0.5 * vb ** 0.5)


def _ann_on_deployed(window_bts):
    tot_pnl = sum(bt.total_return_usd for bt in window_bts)
    years = sum(bt.n_ticks for bt in window_bts) / 252.0
    ret_on_dep = tot_pnl / NOTIONAL
    try:
        ann = ((1.0 + ret_on_dep) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0
    except (ValueError, OverflowError):
        ann = (ret_on_dep / years) * 100.0 if years > 0 else 0.0
    return ann, tot_pnl, years


def _sweep(decide_fn, base_params, grid, label):
    keys = list(grid.keys())
    rows = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        override = dict(zip(keys, combo))
        params = dict(base_params); params.update(override)
        r = _run_panel(decide_fn, params, basket=UNIVERSE, track_corr_spy=True)
        ann, pnl, years = _ann_on_deployed(r["window_bts"])
        rows.append({
            "params": override, "fp": round(r["fp"], 3),
            "worst_dd": round(r["worst_inst_dd"], 2),
            "trades": r["total_trades"],
            "ann_deployed": round(ann, 2), "tot_pnl_usd": round(pnl, 2),
            "spy_corr": round(r["spy_corr"], 3) if r["spy_corr"] is not None else None,
            "per_win": [[w[0], round(w[2] * 100, 2), round(w[3], 2), w[4]] for w in r["per_win"]],
        })
    rows.sort(key=lambda x: -x["fp"])
    return rows


def main():
    print("=== BH-SPY bench (full panel) ===")
    bh = _run_panel(_bh_decide, {"timeframe": "1Day", "notional_usd": NOTIONAL,
                                 "basket": ["SPY"], "xsec_basket_size": 1},
                    basket=["SPY"])
    bh_win = {w[0]: w[2] for w in bh["per_win"]}
    bh_ann, bh_pnl, _ = _ann_on_deployed(bh["window_bts"])
    print(f"BH-SPY FP-cont={bh['fp']:+.3f} trades={bh['total_trades']} ann={bh_ann:+.2f}% pnl=${bh_pnl:+.2f}")
    for w in bh["per_win"]:
        print(f"   {w[0]:20s} {w[1]:5s} ret={w[2]*100:+.2f}%")

    print(f"\nuniverse N={len(UNIVERSE)}")

    # ---- 12-1 momentum sweep ----
    mom_grid = {
        "lookback_bars": [126, 189, 252],
        "skip_bars": [21, 63],
        "top_k": [3, 5, 8],
    }
    mom_base = {"timeframe": "1Day", "notional_usd": NOTIONAL,
                "max_notional_usd": NOTIONAL, "universe": UNIVERSE,
                "xsec_basket_size": 8}
    print("\n=== sweeping 12-1 MOMENTUM ===")
    mom_rows = _sweep(MOM, mom_base, mom_grid, "momentum")

    # ---- low-vol sweep ----
    lv_grid = {
        "vol_lookback": [63, 126, 252],
        "top_k": [3, 5, 8],
    }
    lv_base = {"timeframe": "1Day", "notional_usd": NOTIONAL,
               "max_notional_usd": NOTIONAL, "universe": UNIVERSE,
               "xsec_basket_size": 8}
    print("=== sweeping LOW-VOL ===")
    lv_rows = _sweep(LOWVOL, lv_base, lv_grid, "lowvol")

    def beats_bh(rows):
        for rr in rows:
            rr["beats_bh_win"] = sum(1 for w in rr["per_win"]
                                     if w[1] > bh_win.get(w[0], -1e9) * 100)
            rr["nwin"] = len(rr["per_win"])

    beats_bh(mom_rows); beats_bh(lv_rows)

    out = {
        "universe": UNIVERSE,
        "bh": {"fp": round(bh["fp"], 3), "ann": round(bh_ann, 2),
               "pnl": round(bh_pnl, 2),
               "per_win": [[w[0], w[1], round(w[2] * 100, 2)] for w in bh["per_win"]]},
        "momentum": {"grid": mom_grid, "rows": mom_rows},
        "lowvol": {"grid": lv_grid, "rows": lv_rows},
    }
    (WS / "reports" / "_xsec_universe_results.json").write_text(
        json.dumps(out, indent=2, default=str))

    print("\n=== TOP 8 MOMENTUM cells by FP-cont ===")
    for rr in mom_rows[:8]:
        print(f"  FP={rr['fp']:+.3f} ann={rr['ann_deployed']:+.2f}% dd={rr['worst_dd']:.1f} "
              f"tr={rr['trades']} beatBH={rr['beats_bh_win']}/{rr['nwin']} "
              f"spyCorr={rr['spy_corr']} {rr['params']}")
    print("\n=== TOP 8 LOW-VOL cells by FP-cont ===")
    for rr in lv_rows[:8]:
        print(f"  FP={rr['fp']:+.3f} ann={rr['ann_deployed']:+.2f}% dd={rr['worst_dd']:.1f} "
              f"tr={rr['trades']} beatBH={rr['beats_bh_win']}/{rr['nwin']} "
              f"spyCorr={rr['spy_corr']} {rr['params']}")
    print("\nwrote reports/_xsec_universe_results.json")


if __name__ == "__main__":
    main()
