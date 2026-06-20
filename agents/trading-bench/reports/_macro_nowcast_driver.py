"""Throwaway driver for the MACRO-NOWCAST lane (lane 5).

Composes PUBLIC runner.backtest_xsec.backtest_xsec + runner.fp_sharpe.
fp_continuous_sharpe over the canonical 8-window NAMED_WINDOWS panel with the
active Alpaca cost model. ZERO edits to protected/evaluator files.

- spy_timing mode: single-name {SPY} deployment via xsec idle-cash mechanism.
- cross_asset mode: {SPY, TLT, GLD} all passed to backtest_xsec; the strategy
  rotates the deployed notional among them (one at a time, exposure <= notional).

Also computes the RELABEL DIAGNOSTIC: correlation of the composite nowcast series
with (a) SPY's own trailing return and (b) SPY's trailing realized vol. High |r|
=> the nowcast is a relabel of an already-rejected price lane -> FLAG/REJECT.
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
WARMUP = 760  # calendar days primed so 60d mom + 500-sample z-window compute


def _load(cdir_name):
    cdir = WS / "strategies_candidates" / cdir_name
    spec = importlib.util.spec_from_file_location(
        f"cand_{cdir_name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod, params


MOD, BASE = _load("macro_nowcast")
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


def _run_panel(decide_fn, params, symbols=("SPY",), track_deploy=False):
    acc = {"sum": 0.0, "n": 0}

    def wrapped(ms, ps, p):
        if track_deploy:
            tot = 0.0
            for s in symbols:
                pos = ps.get(s)
                if pos:
                    tot += float(pos.get("market_value", 0.0))
            acc["sum"] += tot / NOTIONAL
            acc["n"] += 1
        return decide_fn(ms, ps, p)

    window_bts = []
    per_win = []
    worst_inst = 0.0
    total_trades = 0
    cm = CostModel.alpaca_stocks()
    for label, end_dt, days, regime in NAMED_WINDOWS:
        fetch_days = days + WARMUP
        bbs = {}
        for s in symbols:
            b = bars_cache.get_bars(s, "1Day", days=fetch_days, end_dt=end_dt)
            if b and len(b) >= 10:
                bbs[s] = b
        if "SPY" not in bbs:
            continue
        bt = backtest_xsec("mnc", bbs, params, decide_xsec_fn=wrapped,
                           starting_cash=START_CASH, default_cost_model=cm)
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
                                   "basket": ["SPY"]}, symbols=("SPY",))


# ---------- RELABEL DIAGNOSTIC ----------
def _pearson(a, b):
    n = min(len(a), len(b))
    if n < 5:
        return None
    a = a[-n:]; b = b[-n:]
    ma = sum(a) / n; mb = sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def _spy_closes():
    return [(str(b["t"])[:10], float(b["c"]))
            for b in (bars_cache.get_bars("SPY", "1Day", days=2400) or [])]


def relabel_diag(params, ret_lb=60, vol_lb=20):
    """Correlate composite series with SPY trailing return + SPY realized vol."""
    sc = _spy_closes()
    dates = [d for (d, _) in sc]
    closes = {d: c for (d, c) in sc}
    # dense grid every ~5 trading days over the comparable span
    grid = dates[760::5]
    comp_s, ret_s, vol_s = [], [], []
    for d in grid:
        comp = MOD.composite(d, params)
        if comp is None:
            continue
        idx = dates.index(d)
        if idx < max(ret_lb, vol_lb) + 1:
            continue
        # SPY trailing return
        p0 = closes[dates[idx - ret_lb]]; p1 = closes[d]
        tr = p1 / p0 - 1.0 if p0 > 0 else None
        # SPY realized vol (20d)
        seg = [closes[dates[k]] for k in range(idx - vol_lb, idx + 1)]
        rets = [math.log(seg[i] / seg[i - 1]) for i in range(1, len(seg))
                if seg[i] > 0 and seg[i - 1] > 0]
        if len(rets) < 5 or tr is None:
            continue
        m = sum(rets) / len(rets)
        rv = math.sqrt(sum((x - m) ** 2 for x in rets) / (len(rets) - 1)) * math.sqrt(252)
        comp_s.append(comp); ret_s.append(tr); vol_s.append(rv)
    return {
        "n": len(comp_s),
        "corr_vs_spy_return": _pearson(comp_s, ret_s),
        "corr_vs_spy_vol": _pearson(comp_s, vol_s),
    }


def _grid(g):
    keys = list(g.keys())
    for combo in itertools.product(*[g[k] for k in keys]):
        yield dict(zip(keys, combo))


def _ann_on_deployed(r):
    tot_pnl = sum(bt.total_return_usd for bt in r["window_bts"])
    ret_on_dep = tot_pnl / NOTIONAL
    years = sum(bt.n_ticks for bt in r["window_bts"]) / 252.0
    base = 1.0 + ret_on_dep
    try:
        if years > 0 and base > 0:
            ann = (base ** (1.0 / years) - 1.0) * 100.0
        elif years > 0:
            ann = (ret_on_dep / years) * 100.0  # fallback: linearize when base<=0
        else:
            ann = 0.0
    except (ValueError, OverflowError):
        ann = (ret_on_dep / years) * 100.0 if years > 0 else 0.0
    return ann, tot_pnl


def main():
    print("=== BH-SPY bench ===")
    bh = _bench()
    bh_win = {w[0]: w[2] for w in bh["per_win"]}
    print(f"BH-SPY FP-cont={bh['fp']:+.3f} trades={bh['total_trades']}")
    for w in bh["per_win"]:
        print(f"   {w[0]:22s} {w[1]:5s} ret={w[2]*100:+.2f}%")

    print("\n=== RELABEL DIAGNOSTIC (composite vs SPY return / vol) ===")
    diag_cfgs = {
        "growth+credit+curve lb60": {"proxies": ["growth", "credit", "curve"], "lookback": 60},
        "all5 lb60": {"proxies": ["growth", "credit", "curve", "inflation", "usd"], "lookback": 60},
        "growth lb60": {"proxies": ["growth"], "lookback": 60},
        "credit lb60": {"proxies": ["credit"], "lookback": 60},
        "curve lb60": {"proxies": ["curve"], "lookback": 60},
        "growth+credit+curve lb120": {"proxies": ["growth", "credit", "curve"], "lookback": 120},
    }
    diag_out = {}
    for name, cfg in diag_cfgs.items():
        p = dict(BASE); p.update(cfg)
        d = relabel_diag(p)
        diag_out[name] = d
        rv = d["corr_vs_spy_return"]; vv = d["corr_vs_spy_vol"]
        print(f"  {name:30s} n={d['n']:4d} corr_vs_SPYret={rv:+.3f} corr_vs_SPYvol={vv:+.3f}")

    out = {"bh": {"fp": bh["fp"], "trades": bh["total_trades"],
                  "per_win": [[w[0], w[1], w[2]] for w in bh["per_win"]]},
           "relabel": diag_out, "sweeps": {}}

    sweeps = {
        "spy_binary_gcc": {
            "mode": ["spy_timing"], "exposure_mode": ["binary"], "threshold": ["pct"],
            "proxies": [["growth", "credit", "curve"]],
            "lookback": [20, 60, 120], "threshold_pct": [0.4, 0.5, 0.6],
        },
        "spy_binary_all5": {
            "mode": ["spy_timing"], "exposure_mode": ["binary"], "threshold": ["pct"],
            "proxies": [["growth", "credit", "curve", "inflation", "usd"]],
            "lookback": [20, 60, 120], "threshold_pct": [0.4, 0.5, 0.6],
        },
        "spy_binary_zero": {
            "mode": ["spy_timing"], "exposure_mode": ["binary"], "threshold": ["zero"],
            "proxies": [["growth", "credit", "curve"], ["credit", "curve"]],
            "lookback": [20, 60, 120],
        },
        "spy_prop_gcc": {
            "mode": ["spy_timing"], "exposure_mode": ["proportional"], "threshold": ["pct"],
            "proxies": [["growth", "credit", "curve"]],
            "lookback": [20, 60, 120], "resize_band": [0.15, 0.25],
        },
        "xa_tlt_binary": {
            "mode": ["cross_asset"], "safe_asset": ["TLT"], "exposure_mode": ["binary"],
            "threshold": ["pct"], "proxies": [["growth", "credit", "curve"]],
            "lookback": [20, 60, 120], "threshold_pct": [0.4, 0.5, 0.6],
        },
        "xa_gld_binary": {
            "mode": ["cross_asset"], "safe_asset": ["GLD"], "exposure_mode": ["binary"],
            "threshold": ["pct"], "proxies": [["growth", "credit", "curve"]],
            "lookback": [20, 60, 120], "threshold_pct": [0.4, 0.5, 0.6],
        },
    }

    for label, g in sweeps.items():
        is_xa = "xa_" in label
        symbols = ("SPY", "TLT", "GLD") if is_xa else ("SPY",)
        print(f"\n=== {label} (symbols={symbols}) ===")
        rows = []
        for override in _grid(g):
            params = dict(BASE); params.update(override)
            r = _run_panel(DECIDE, params, symbols=symbols, track_deploy=True)
            beats = sum(1 for w in r["per_win"] if w[2] > bh_win.get(w[0], -1e9))
            nwin = len(r["per_win"])
            ann, tot_pnl = _ann_on_deployed(r)
            # make params JSON-friendly (proxies is a list)
            po = {k: (v if not isinstance(v, list) else "+".join(v)) for k, v in override.items()}
            rows.append({
                "params": po, "fp": round(r["fp"], 3),
                "avg_deploy": round(r["avg_deploy"], 3) if r["avg_deploy"] is not None else None,
                "worst_dd": round(r["worst_inst_dd"], 2), "trades": r["total_trades"],
                "beats_bh_win": f"{beats}/{nwin}", "ann_deployed": round(ann, 2),
                "tot_pnl_usd": round(tot_pnl, 2),
            })
        rows.sort(key=lambda x: -x["fp"])
        out["sweeps"][label] = rows
        for rr in rows[:6]:
            print(f"  FP={rr['fp']:+.3f} dep={rr['avg_deploy']} ann={rr['ann_deployed']:+.2f} "
                  f"dd={rr['worst_dd']:.1f} tr={rr['trades']} beatBH={rr['beats_bh_win']} "
                  f"pnl=${rr['tot_pnl_usd']:+.1f} {rr['params']}")

    (WS / "reports" / "_macro_nowcast_results.json").write_text(
        json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_macro_nowcast_results.json")


if __name__ == "__main__":
    main()
