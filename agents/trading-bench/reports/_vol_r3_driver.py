"""Throwaway R3 driver: vol-regime proportional sizing + cleaner vol input.

HARNESS-GAP NOTE (documented as a finding in the memo): runner.sweep.run_sweep
routes the xsec family through runner.walk_forward_xsec.walk_forward_xsec, which
SKIPS any window with <2 symbols (line 308: `if len(bars_by_sym) < 2: continue`)
because cross-sectional RANKING needs >=2 names. A single-name {SPY} vol-managed
sleeve therefore yields n_windows_with_data=0 through the harness — it cannot be
swept via run_sweep as-is. The underlying runner.backtest_xsec.backtest_xsec
DOES support single-name fractional deployment + idle cash perfectly (verified).
So this driver composes the PUBLIC backtest_xsec + the canonical
fp_sharpe.fp_continuous_sharpe over NAMED_WINDOWS directly (import-only, no
evaluator/protected edit) — the same composition pattern the prior throwaway
drivers used. Every number is over the identical 8-window panel + active cost
model the harness would have used.
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
WARMUP = 120  # calendar days primed before each window so vol lookbacks compute


def _load(cdir_name):
    cdir = WS / "strategies_candidates" / cdir_name
    spec = importlib.util.spec_from_file_location(
        f"cand_{cdir_name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod.decide_xsec, params


DECIDE, BASE = _load("vol_regime_spy_prop")


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


def _run_panel(decide_fn, params, track_deploy=False):
    """Run decide_fn over all NAMED_WINDOWS via backtest_xsec on {SPY}.
    Returns dict with per-window backtests, concatenated FP-cont Sharpe,
    avg deployment fraction, worst instrument DD, total trades, per-window
    returns + beats-BH list."""
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
    cm = CostModel.alpaca_stocks()
    for label, end_dt, days, regime in NAMED_WINDOWS:
        fetch_days = days + WARMUP
        bars = bars_cache.get_bars("SPY", "1Day", days=fetch_days, end_dt=end_dt)
        if not bars or len(bars) < 10:
            continue
        bt = backtest_xsec("vrp", {"SPY": bars}, params,
                           decide_xsec_fn=wrapped, starting_cash=START_CASH,
                           default_cost_model=cm)
        window_bts.append(bt)
        per_win.append((label, regime, bt.total_return_pct, bt.worst_instrument_dd_pct))
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct)
        total_trades += bt.n_trades

    # FP-cont Sharpe over concatenated per-tick equity returns (canonical).
    class _W:
        def __init__(s, bt): s.backtest = bt
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in window_bts],
                                     timeframe="1Day", is_crypto=False)
    avg_deploy = (acc["sum"] / acc["n"]) if acc["n"] else None
    return {
        "fp": fps, "nret": nret, "avg_deploy": avg_deploy,
        "worst_inst_dd": worst_inst, "total_trades": total_trades,
        "per_win": per_win, "window_bts": window_bts,
    }


def _bench():
    return _run_panel(_bh_decide, {"timeframe": "1Day", "notional_usd": NOTIONAL,
                                   "basket": ["SPY"]}, track_deploy=False)


def _grid(g):
    keys = list(g.keys())
    for combo in itertools.product(*[g[k] for k in keys]):
        yield dict(zip(keys, combo))


def main():
    print("=== BH-SPY bench (single-name backtest_xsec, full panel) ===")
    bh = _bench()
    bh_win = {w[0]: w[2] for w in bh["per_win"]}
    print(f"BH-SPY FP-cont={bh['fp']:+.3f} nret={bh['nret']} trades={bh['total_trades']}")
    for w in bh["per_win"]:
        print(f"   {w[0]:20s} {w[1]:5s} ret={w[2]*100:+.2f}% dd={w[3]:.2f}%")

    sweeps = {
        "ratio_prop": {
            "vol_source": ["vixy_ratio"], "exposure_mode": ["proportional"],
            "ratio_lookback": [10, 20, 40], "resize_band": [0.1, 0.2, 0.3],
        },
        "ratio_binary": {
            "vol_source": ["vixy_ratio"], "exposure_mode": ["binary"],
            "ratio_lookback": [10, 20, 40], "band": [0.0, 0.05, 0.10],
        },
        "vixy_prop": {
            "vol_source": ["vixy"], "exposure_mode": ["proportional"],
            "vixy_lookback": [10, 20, 40], "resize_band": [0.1, 0.2, 0.3],
        },
        "vixy_binary": {
            "vol_source": ["vixy"], "exposure_mode": ["binary"],
            "vixy_lookback": [10, 20, 40], "band": [0.0, 0.05, 0.10],
        },
        "realized_prop": {
            "vol_source": ["realized"], "exposure_mode": ["proportional"],
            "vol_lookback": [10, 20, 40], "target_vol": [0.10, 0.15, 0.20],
        },
    }

    out = {"bh": {"fp": bh["fp"], "trades": bh["total_trades"],
                  "per_win": [[w[0], w[1], w[2]] for w in bh["per_win"]]},
           "sweeps": {}}

    for label, g in sweeps.items():
        print(f"\n=== {label} ===")
        rows = []
        for override in _grid(g):
            params = dict(BASE); params.update(override)
            r = _run_panel(DECIDE, params, track_deploy=True)
            # beats-BH per window (risk-adjusted proxy: per-window return vs BH)
            beats = 0; nwin = 0
            for w in r["per_win"]:
                nwin += 1
                if w[2] > bh_win.get(w[0], -1e9):
                    beats += 1
            # ann on deployed: compound total pnl / deployed over the panel span
            tot_pnl = sum(bt.total_return_usd for bt in r["window_bts"])
            tot_days = sum(w[2] for w in NAMED_WINDOWS)  # calendar days proxy
            ret_on_dep = tot_pnl / NOTIONAL
            years = (sum(bt.n_ticks for bt in r["window_bts"])) / 252.0
            try:
                ann = ((1.0 + ret_on_dep) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0
            except (ValueError, OverflowError):
                ann = (ret_on_dep / years) * 100.0 if years > 0 else 0.0
            rows.append({
                "params": override, "fp": round(r["fp"], 3),
                "avg_deploy": round(r["avg_deploy"], 3) if r["avg_deploy"] is not None else None,
                "worst_dd": round(r["worst_inst_dd"], 2),
                "trades": r["total_trades"],
                "beats_bh_win": f"{beats}/{nwin}",
                "ann_deployed": round(ann, 2),
                "tot_pnl_usd": round(tot_pnl, 2),
            })
        rows.sort(key=lambda x: -x["fp"])
        out["sweeps"][label] = rows
        for rr in rows[:6]:
            print(f"  FP={rr['fp']:+.3f} dep={rr['avg_deploy']} ann={rr['ann_deployed']:+.2f} dd={rr['worst_dd']:.1f} "
                  f"tr={rr['trades']} beatBH={rr['beats_bh_win']} pnl=${rr['tot_pnl_usd']:+.1f} "
                  f"{rr['params']}")

    (WS / "reports" / "_vol_r3_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_vol_r3_results.json")


if __name__ == "__main__":
    main()
