"""Throwaway driver for the DISPERSION / IMPLIED-CORRELATION REGIME lane.

Composes PUBLIC backtest functions + runner.fp_sharpe.fp_continuous_sharpe over
the canonical 8-window NAMED_WINDOWS panel with the active Alpaca cost model.
ZERO edits to protected/evaluator files. Single-name {SPY} deployment via the
xsec idle-cash mechanism (same pattern as reports/_vol_r3_driver.py).

Also computes, per signal config, the correlation between the dispersion/corr
GAUGE series and SPY's own trailing realized vol -> the dispersion-NOT-vol-level
diagnostic the lane brief demands.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
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
WARMUP = 200  # calendar days primed so corr/disp lookbacks compute at window start


def _load(cdir_name):
    cdir = WS / "strategies_candidates" / cdir_name
    spec = importlib.util.spec_from_file_location(
        f"cand_{cdir_name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod, params


MOD, BASE = _load("dispersion_regime")
DECIDE = MOD.decide_xsec


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
        bt = backtest_xsec("disp", {"SPY": bars}, params,
                           decide_xsec_fn=wrapped, starting_cash=START_CASH,
                           default_cost_model=cm)
        window_bts.append(bt)
        per_win.append((label, regime, bt.total_return_pct, bt.worst_instrument_dd_pct))
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct)
        total_trades += bt.n_trades

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


# ---- dispersion-NOT-vol-level diagnostic --------------------------------
def _spy_realized_vol(date_str, lookback=20):
    closes = [(str(b["t"])[:10], float(b["c"]))
              for b in (bars_cache.get_bars("SPY", "1Day", days=2400) or [])]
    closes = [c for (d, c) in closes if d <= date_str]
    if len(closes) < lookback + 1:
        return None
    seg = closes[-(lookback + 1):]
    rets = [math.log(seg[i] / seg[i - 1]) for i in range(1, len(seg))
            if seg[i] > 0 and seg[i - 1] > 0]
    if len(rets) < 5:
        return None
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var * 252.0)


def _gauge_vs_vol_corr(params):
    """Pearson corr between the gauge series and SPY trailing realized vol over
    a dense date grid spanning the full sample. High |corr| => gauge is a vol
    proxy (the dead lane)."""
    grid = [str(b["t"])[:10] for b in (bars_cache.get_bars("XLK", "1Day", days=2400) or [])]
    grid = grid[200:]  # skip warmup
    step = max(1, len(grid) // 250)
    gs, vs = [], []
    for k in range(0, len(grid), step):
        d = grid[k]
        g = MOD._gauge(d, params)
        v = _spy_realized_vol(d, 20)
        if g is not None and v is not None:
            gs.append(g); vs.append(v)
    n = len(gs)
    if n < 10:
        return None, n
    mg = sum(gs) / n; mv = sum(vs) / n
    vg = sum((x - mg) ** 2 for x in gs)
    vv = sum((x - mv) ** 2 for x in vs)
    if vg <= 0 or vv <= 0:
        return None, n
    cov = sum((gs[i] - mg) * (vs[i] - mv) for i in range(n))
    return cov / math.sqrt(vg * vv), n


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
        # thesis: long index when CORRELATION is LOW (high dispersion)
        "corr_binary_pct": {
            "gauge": ["corr"], "exposure_mode": ["binary"],
            "regime_side": ["long_when_low_corr"],
            "corr_lookback": [20, 40, 60], "threshold_pct": [0.4, 0.5, 0.6, 0.7],
            "corr_threshold": [None],
        },
        "corr_prop": {
            "gauge": ["corr"], "exposure_mode": ["proportional"],
            "regime_side": ["long_when_low_corr"],
            "corr_lookback": [20, 40, 60],
            "lo_pct": [0.2], "hi_pct": [0.8],
        },
        "disp_binary_pct": {
            "gauge": ["dispersion"], "exposure_mode": ["binary"],
            "regime_side": ["long_when_low_corr"],
            "disp_lookback": [10, 20, 40], "threshold_pct": [0.4, 0.5, 0.6, 0.7],
            "corr_threshold": [None],
        },
        # anti-thesis (null): long when correlation HIGH -> should be WORSE
        "corr_binary_INVERTED": {
            "gauge": ["corr"], "exposure_mode": ["binary"],
            "regime_side": ["long_when_high_corr"],
            "corr_lookback": [40], "threshold_pct": [0.4, 0.5, 0.6],
            "corr_threshold": [None],
        },
    }

    out = {"bh": {"fp": bh["fp"], "trades": bh["total_trades"],
                  "per_win": [[w[0], w[1], w[2]] for w in bh["per_win"]]},
           "sweeps": {}, "gauge_vs_vol": {}}

    # diagnostic: gauge-vs-vol corr for the two gauge families
    for tag, gp in [("corr_lb40", dict(BASE, gauge="corr", corr_lookback=40)),
                    ("disp_lb20", dict(BASE, gauge="dispersion", disp_lookback=20))]:
        c, n = _gauge_vs_vol_corr(gp)
        out["gauge_vs_vol"][tag] = {"corr_with_spy_vol": (round(c, 3) if c is not None else None), "n": n}
        print(f"\n[diag] gauge_vs_SPYvol {tag}: corr={c} n={n}")

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
        for rr in rows[:8]:
            print(f"  FP={rr['fp']:+.3f} dep={rr['avg_deploy']} ann={rr['ann_deployed']:+.2f} "
                  f"dd={rr['worst_dd']:.1f} tr={rr['trades']} beatBH={rr['beats_bh_win']} "
                  f"pnl=${rr['tot_pnl_usd']:+.1f} {rr['params']}")

    (WS / "reports" / "_dispersion_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_dispersion_results.json")


if __name__ == "__main__":
    main()
