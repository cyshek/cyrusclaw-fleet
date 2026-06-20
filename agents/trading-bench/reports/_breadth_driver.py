"""Throwaway breadth-internals driver: SPY long-or-cash overlay, full panel.

Composes the PUBLIC runner.backtest_xsec + canonical fp_continuous_sharpe over
the 8 NAMED_WINDOWS on a single-name {SPY} basket (same import-only pattern as
reports/_vol_r3_driver.py and _xsec_universe_driver.py). The breadth SIGNAL is
computed from the 40-name universe inside the candidate strategy; the only
INSTRUMENT traded is SPY. Strictly causal: breadth(d) -> trade SPY(d+1).

Reports per cell: FP-cont Sharpe, avg deployment fraction (cash-mirage guard),
worst instrument DD, trades, beats-BH per window, ann/deployed, and SPY-relative
excess return + information ratio (runner.spy_relative) over the concatenated
panel. BH-SPY bench printed first (the bar to beat, risk-adjusted).

No protected edits. Pre-committed sweep grids below (lookbacks/thresholds) —
demand a PLATEAU, not a knife-edge.
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

from runner.backtest_xsec import backtest_xsec  # noqa: E402
from runner.backtest import CostModel, bars_per_year  # noqa: E402
from runner.walk_forward import NAMED_WINDOWS  # noqa: E402
from runner.fp_sharpe import fp_continuous_sharpe  # noqa: E402
from runner import bars_cache  # noqa: E402
from runner.spy_relative import (  # noqa: E402
    spy_relative_metrics, returns_from_closes, align_returns_by_date,
)

NOTIONAL = 1000.0
START_CASH = 1000.0
WARMUP = 320  # calendar days primed before each window so 200-SMA + z-window compute

CDIR = WS / "strategies_candidates" / "breadth_internals"
spec = importlib.util.spec_from_file_location("cand_breadth", str(CDIR / "strategy.py"))
B = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = B
spec.loader.exec_module(B)
DECIDE = B.decide_xsec
BASE = json.loads((CDIR / "params.json").read_text())


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


def _equity_returns(bt):
    """Per-tick equity returns from a backtest's equity_curve."""
    eq = [float(p.get("equity", p.get("v", 0.0))) if isinstance(p, dict) else float(p)
          for p in bt.equity_curve]
    out = []
    for i in range(1, len(eq)):
        if eq[i - 1] > 0:
            out.append(eq[i] / eq[i - 1] - 1.0)
    return out


def _run_panel(decide_fn, params, track_deploy=False, collect_spy=False):
    acc = {"sum": 0.0, "n": 0}

    def wrapped(ms, ps, p):
        if track_deploy:
            spy = ps.get("SPY")
            val = float(spy.get("market_value", 0.0)) if spy else 0.0
            acc["sum"] += val / NOTIONAL
            acc["n"] += 1
        return decide_fn(ms, ps, p)

    window_bts = []
    per_win = []
    worst_inst = 0.0
    total_trades = 0
    strat_ret = []   # concatenated per-tick strategy equity returns
    spy_ret = []     # concatenated per-tick SPY buy-hold returns (aligned by window)
    cm = CostModel.alpaca_stocks()
    for label, end_dt, days, regime in NAMED_WINDOWS:
        fetch_days = days + WARMUP
        bars = bars_cache.get_bars("SPY", "1Day", days=fetch_days, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt = backtest_xsec("brd", {"SPY": bars}, params,
                           decide_xsec_fn=wrapped, starting_cash=START_CASH,
                           default_cost_model=cm)
        window_bts.append(bt)
        per_win.append((label, regime, bt.total_return_pct, bt.worst_instrument_dd_pct))
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct)
        total_trades += bt.n_trades
        if collect_spy:
            sr = _equity_returns(bt)
            strat_ret.extend(sr)
            # SPY BH returns over the SAME visible window the harness stepped.
            # The harness steps ticks over bars; equity_curve has n_ticks points.
            n_pts = len(bt.equity_curve)
            spy_closes = [float(b["c"]) for b in bars][-n_pts:]
            spy_r = returns_from_closes(spy_closes)
            # align lengths defensively
            k = min(len(sr), len(spy_r))
            if k > 0:
                # truncate both to k from the end to keep them date-aligned tail
                if len(strat_ret) >= len(sr):
                    pass
                spy_ret.extend(spy_r[-k:] if len(spy_r) > k else spy_r)

    class _W:
        def __init__(s, bt): s.backtest = bt
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in window_bts],
                                     timeframe="1Day", is_crypto=False)
    avg_deploy = (acc["sum"] / acc["n"]) if acc["n"] else None
    out = {
        "fp": fps, "nret": nret, "avg_deploy": avg_deploy,
        "worst_inst_dd": worst_inst, "total_trades": total_trades,
        "per_win": per_win, "window_bts": window_bts,
    }
    if collect_spy:
        out["strat_ret"] = strat_ret
        out["spy_ret"] = spy_ret
    return out


def _bench():
    return _run_panel(_bh_decide, {"timeframe": "1Day", "notional_usd": NOTIONAL,
                                   "basket": ["SPY"]}, track_deploy=False)


def _grid(g):
    keys = list(g.keys())
    for combo in itertools.product(*[g[k] for k in keys]):
        yield dict(zip(keys, combo))


def main():
    bpy = bars_per_year("1Day", False)
    print("=== BH-SPY bench (single-name backtest_xsec, full panel) ===")
    bh = _bench()
    bh_win = {w[0]: w[2] for w in bh["per_win"]}
    print(f"BH-SPY FP-cont={bh['fp']:+.3f} nret={bh['nret']} trades={bh['total_trades']}")
    for w in bh["per_win"]:
        print(f"   {w[0]:20s} {w[1]:5s} ret={w[2]*100:+.2f}% dd={w[3]:.2f}%")

    # Pre-committed sweeps (lookbacks + thresholds). PLATEAU demanded.
    sweeps = {
        "pct50_binary": {
            "breadth_mode": ["pct_above_50sma"], "sma_len": [50],
            "exposure_mode": ["binary"],
            "z_lookback": [60, 120], "enter_z": [-0.25, 0.0, 0.25],
            "exit_z": [-0.5, -0.25],
        },
        "pct50_prop": {
            "breadth_mode": ["pct_above_50sma"], "sma_len": [50],
            "exposure_mode": ["proportional"],
            "z_lookback": [60, 120], "floor_z": [-1.5, -1.0],
            "cap_z": [0.5, 1.0],
        },
        "pct200_binary": {
            "breadth_mode": ["pct_above_200sma"], "sma_len": [200],
            "exposure_mode": ["binary"],
            "z_lookback": [60, 120], "enter_z": [-0.25, 0.0, 0.25],
            "exit_z": [-0.5, -0.25],
        },
        "ad_binary": {
            "breadth_mode": ["ad_line"], "ad_slope_lb": [10, 20],
            "exposure_mode": ["binary"],
            "z_lookback": [60, 120], "enter_z": [0.0, 0.25],
            "exit_z": [-0.5, -0.25],
        },
    }

    out = {"bh": {"fp": bh["fp"], "trades": bh["total_trades"],
                  "per_win": [[w[0], w[1], w[2]] for w in bh["per_win"]]},
           "sweeps": {}}

    best_overall = None
    for label, g in sweeps.items():
        print(f"\n=== {label} ===")
        rows = []
        for override in _grid(g):
            params = dict(BASE); params.update(override)
            r = _run_panel(DECIDE, params, track_deploy=True)
            beats = 0; nwin = 0
            for w in r["per_win"]:
                nwin += 1
                if w[2] > bh_win.get(w[0], -1e9):
                    beats += 1
            tot_pnl = sum(bt.total_return_usd for bt in r["window_bts"])
            years = (sum(bt.n_ticks for bt in r["window_bts"])) / 252.0
            ret_on_dep = tot_pnl / NOTIONAL
            try:
                ann = ((1.0 + ret_on_dep) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0
            except (ValueError, OverflowError):
                ann = (ret_on_dep / years) * 100.0 if years > 0 else 0.0
            row = {
                "params": override, "fp": round(r["fp"], 3),
                "avg_deploy": round(r["avg_deploy"], 3) if r["avg_deploy"] is not None else None,
                "worst_dd": round(r["worst_inst_dd"], 2),
                "trades": r["total_trades"],
                "beats_bh_win": f"{beats}/{nwin}",
                "ann_deployed": round(ann, 2),
            }
            rows.append(row)
            if best_overall is None or r["fp"] > best_overall[0]:
                best_overall = (r["fp"], label, dict(params))
        rows.sort(key=lambda x: -x["fp"])
        out["sweeps"][label] = rows
        for rr in rows[:8]:
            print(f"  FP={rr['fp']:+.3f} dep={rr['avg_deploy']} ann={rr['ann_deployed']:+.2f} "
                  f"dd={rr['worst_dd']:.1f} tr={rr['trades']} beatBH={rr['beats_bh_win']} "
                  f"{rr['params']}")

    # SPY-relative metrics for the SINGLE best cell (concatenated panel).
    if best_overall is not None:
        bfp, blabel, bparams = best_overall
        print(f"\n=== SPY-relative for best cell ({blabel}) FP={bfp:+.3f} ===")
        rr = _run_panel(DECIDE, bparams, track_deploy=True, collect_spy=True)
        sr, spyr = rr["strat_ret"], rr["spy_ret"]
        k = min(len(sr), len(spyr))
        sr, spyr = sr[:k], spyr[:k]
        try:
            srm = spy_relative_metrics(sr, spyr, timeframe="1Day", is_crypto=False)
        except ValueError as e:
            srm = {"error": str(e)}
        print(f"  best params: {bparams}")
        print(f"  strat_ann={srm.get('strategy_ann_return')} spy_ann={srm.get('spy_ann_return')} "
              f"excess={srm.get('excess_return_annualized')} IR={srm.get('information_ratio')} "
              f"n={srm.get('n_periods')}")
        out["best_cell"] = {"label": blabel, "fp": round(bfp, 3),
                            "params": bparams, "spy_relative": srm}

    (WS / "reports" / "_breadth_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_breadth_results.json")


if __name__ == "__main__":
    main()
