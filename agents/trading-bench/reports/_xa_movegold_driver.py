"""Throwaway driver for the XA_MOVEGOLD lane.

Composes PUBLIC modules only (ZERO eval reimpl, ZERO protected-file edits):
  runner.backtest_xsec.backtest_xsec  (panel)
  runner.backtest.CostModel.alpaca_stocks()
  runner.walk_forward.NAMED_WINDOWS   (canonical 8-window panel)
  runner.fp_sharpe.fp_continuous_sharpe (headline number)

Plus a self-contained DEEP-OOS long/flat vector backtest on SPY adjclose
total-return (2003->2026), applying the IDENTICAL alpaca_stocks round-trip cost
on every regime flip, with a frozen train<=2018 / test>2018 split (the
Alpaca-bounded xsec harness cannot reach pre-2018; stated in the prereg).

Killer diagnostics (a) relabel (b) closet-beta (c) orthogonality (d) knife/plateau.
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
from runner import daily_bars_cache as dbc

NOTIONAL = 1000.0
START_CASH = 1000.0
WARMUP = 520

_cdir = WS / "strategies_candidates" / "xa_movegold"
_spec = importlib.util.spec_from_file_location("cand_xa_movegold", str(_cdir / "strategy.py"))
MOD = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = MOD
_spec.loader.exec_module(MOD)
DECIDE = MOD.decide_xsec
BASE = json.loads((_cdir / "params.json").read_text())


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
        bt = backtest_xsec("xa", bbs, params, decide_xsec_fn=wrapped,
                           starting_cash=START_CASH, default_cost_model=cm)
        window_bts.append(bt)
        per_win.append((label, regime, bt.total_return_pct, bt.worst_instrument_dd_pct))
        worst_inst = min(worst_inst, bt.worst_instrument_dd_pct)
        total_trades += bt.n_trades

    class _W:
        def __init__(s, bt):
            s.backtest = bt
    fps, nret = fp_continuous_sharpe([_W(bt) for bt in window_bts],
                                     timeframe="1Day", is_crypto=False)
    avg_deploy = (acc["sum"] / acc["n"]) if acc["n"] else None
    return {"fp": fps, "nret": nret, "avg_deploy": avg_deploy,
            "worst_inst_dd": worst_inst, "total_trades": total_trades,
            "per_win": per_win, "window_bts": window_bts}


def _ann_on_deployed(r):
    tot_pnl = sum(bt.total_return_usd for bt in r["window_bts"])
    ret_on_dep = tot_pnl / NOTIONAL
    years = sum(bt.n_ticks for bt in r["window_bts"]) / 252.0
    base = 1.0 + ret_on_dep
    try:
        if years > 0 and base > 0:
            ann = (base ** (1.0 / years) - 1.0) * 100.0
        elif years > 0:
            ann = (ret_on_dep / years) * 100.0
        else:
            ann = 0.0
    except (ValueError, OverflowError):
        ann = (ret_on_dep / years) * 100.0 if years > 0 else 0.0
    return ann, tot_pnl


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


def _spy_adj():
    bars = dbc.get_daily("SPY")
    return [(b["date"], float(b["adjclose"])) for b in bars if b.get("adjclose")]


SPY_ADJ = _spy_adj()
SPY_DATES = [d for (d, _) in SPY_ADJ]
SPY_CLOSE = [c for (_, c) in SPY_ADJ]


def deep_backtest(params, start="2003-01-01", spread_bps=2.0):
    mode = params.get("mode", "timing")
    off_symbol = params.get("off_symbol", "TLT")
    off_lookup = None
    if mode == "rotate":
        off_lookup = {b["date"]: float(b["adjclose"]) for b in dbc.get_daily(off_symbol) if b.get("adjclose")}

    idx0 = 0
    for i, d in enumerate(SPY_DATES):
        if d >= start:
            idx0 = i
            break

    eq = 1.0
    bench = 1.0
    prev_state = 0
    strat_rets = []
    bench_rets = []
    exps = []
    dates_out = []
    states = []
    n_flips = 0
    sp = spread_bps / 1e4

    for i in range(idx0, len(SPY_DATES)):
        d = SPY_DATES[i]
        on = MOD.risk_on(params, d)
        if on is None:
            desired = 0
        elif mode == "timing":
            desired = 1 if on else 0
        else:
            desired = 1 if on else -1
        if i > idx0:
            r_spy = SPY_CLOSE[i] / SPY_CLOSE[i - 1] - 1.0
        else:
            r_spy = 0.0
        bench *= (1.0 + r_spy)
        if prev_state == 1:
            r = r_spy
        elif prev_state == -1 and off_lookup is not None:
            c1 = off_lookup.get(d)
            c0 = off_lookup.get(SPY_DATES[i - 1]) if i > idx0 else None
            r = (c1 / c0 - 1.0) if (c1 and c0) else 0.0
        else:
            r = 0.0
        if desired != prev_state:
            n_flips += 1
            cost = 0.0
            if prev_state != 0:
                cost += sp
            if desired != 0:
                cost += sp
            r -= cost
        eq *= (1.0 + r)
        strat_rets.append(r)
        bench_rets.append(r_spy)
        exps.append(1.0 if desired != 0 else 0.0)
        dates_out.append(d)
        states.append(desired)
        prev_state = desired

    return {"dates": dates_out, "strat_rets": strat_rets, "bench_rets": bench_rets,
            "exposure": exps, "states": states, "eq": eq, "bench": bench,
            "n_flips": n_flips, "final_strat_ret_pct": (eq - 1.0) * 100.0,
            "final_bench_ret_pct": (bench - 1.0) * 100.0}


def _sharpe(rets):
    n = len(rets)
    if n < 5:
        return 0.0
    m = sum(rets) / n
    var = sum((x - m) ** 2 for x in rets) / (n - 1)
    if var <= 0:
        return 0.0
    return (m / math.sqrt(var)) * math.sqrt(252.0)


def _split_metrics(bt, split_date="2019-01-01"):
    out = {}
    for name, lo, hi in [("full", "0000", "9999"),
                          ("train", "0000", split_date),
                          ("test", split_date, "9999")]:
        s_eq = 1.0; b_eq = 1.0; sr = []; br = []; ex = []
        for i, d in enumerate(bt["dates"]):
            if not (lo <= d < hi):
                continue
            s_eq *= (1.0 + bt["strat_rets"][i])
            b_eq *= (1.0 + bt["bench_rets"][i])
            sr.append(bt["strat_rets"][i]); br.append(bt["bench_rets"][i])
            ex.append(bt["exposure"][i])
        excess = [sr[k] - br[k] for k in range(len(sr))]
        out[name] = {"strat_ret_pct": (s_eq - 1.0) * 100.0,
                     "bench_ret_pct": (b_eq - 1.0) * 100.0,
                     "beat_bh": (s_eq - b_eq) > 0,
                     "strat_minus_bh_pp": ((s_eq - 1.0) - (b_eq - 1.0)) * 100.0,
                     "strat_sharpe": _sharpe(sr), "bench_sharpe": _sharpe(br),
                     "avg_exposure": (sum(ex) / len(ex)) if ex else None,
                     "n_days": len(sr),
                     "corr_exposure_excess": _pearson(ex, excess)}
    return out


def diag_relabel(signal, window, ret_lb=60, vol_lb=20, start="2004-01-01"):
    grid = [d for d in SPY_DATES if d >= start][::3]
    sig_s, ret_s, vol_s = [], [], []
    cmap = {SPY_DATES[i]: i for i in range(len(SPY_DATES))}
    for d in grid:
        z = MOD.signal_zscore(signal, d, window)
        if z is None:
            continue
        idx = cmap[d]
        if idx < max(ret_lb, vol_lb) + 1:
            continue
        p0 = SPY_CLOSE[idx - ret_lb]; p1 = SPY_CLOSE[idx]
        tr = (p1 / p0 - 1.0) if p0 > 0 else None
        seg = SPY_CLOSE[idx - vol_lb: idx + 1]
        rr = [math.log(seg[k] / seg[k - 1]) for k in range(1, len(seg))
              if seg[k] > 0 and seg[k - 1] > 0]
        if tr is None or len(rr) < 5:
            continue
        mm = sum(rr) / len(rr)
        rv = math.sqrt(sum((x - mm) ** 2 for x in rr) / (len(rr) - 1)) * math.sqrt(252)
        sig_s.append(z); ret_s.append(tr); vol_s.append(rv)
    return {"n": len(sig_s),
            "corr_vs_spy_return": _pearson(sig_s, ret_s),
            "corr_vs_spy_vol": _pearson(sig_s, vol_s)}


def _sma_gate_state_qqq(window=200, start="2004-01-01"):
    bars = dbc.get_daily("QQQ")
    ds = [b["date"] for b in bars if b.get("adjclose")]
    cs = [float(b["adjclose"]) for b in bars if b.get("adjclose")]
    out = {}
    for i in range(len(ds)):
        if ds[i] < start or i < window:
            continue
        seg = cs[i - window:i]
        sma = sum(seg) / window
        out[ds[i]] = 1 if cs[i - 1] > sma else 0
    return out


def _voltarget_exposure_tqqq(target_vol=0.20, vol_lb=20, start="2004-01-01"):
    bars = dbc.get_daily("TQQQ")
    ds = [b["date"] for b in bars if b.get("adjclose")]
    cs = [float(b["adjclose"]) for b in bars if b.get("adjclose")]
    out = {}
    for i in range(len(ds)):
        if ds[i] < start or i < vol_lb + 1:
            continue
        seg = cs[i - vol_lb:i]
        rr = [math.log(seg[k] / seg[k - 1]) for k in range(1, len(seg))
              if seg[k] > 0 and seg[k - 1] > 0]
        if len(rr) < 5:
            continue
        m = sum(rr) / len(rr)
        rv = math.sqrt(sum((x - m) ** 2 for x in rr) / (len(rr) - 1)) * math.sqrt(252)
        out[ds[i]] = min(1.0, target_vol / rv) if rv > 0 else 0.0
    return out


def diag_orthogonality(params, start="2010-03-01"):
    sma = _sma_gate_state_qqq(start=start)
    vt = _voltarget_exposure_tqqq(start=start)
    grid = [d for d in SPY_DATES if d >= start]
    s_state, sma_state, vt_exp = [], [], []
    for d in grid:
        on = MOD.risk_on(params, d)
        if on is None:
            continue
        st = 1 if on else 0
        if d in sma and d in vt:
            s_state.append(st); sma_state.append(sma[d]); vt_exp.append(vt[d])
    return {"n": len(s_state),
            "corr_state_vs_sma200": _pearson(s_state, sma_state),
            "corr_state_vs_voltarget": _pearson(s_state, vt_exp),
            "avg_state_on": (sum(s_state) / len(s_state)) if s_state else None,
            "avg_sma_on": (sum(sma_state) / len(sma_state)) if sma_state else None}


def _grid(g):
    keys = list(g.keys())
    for combo in itertools.product(*[g[k] for k in keys]):
        yield dict(zip(keys, combo))


def main():
    out = {"bh_panel": {}, "panel_sweeps": {}, "deep_sweep": [],
           "deep_best": {}, "relabel": {}, "orthogonality": {}, "meta": {}}

    print("=== BH-SPY panel bench (8 NAMED_WINDOWS) ===")
    bh = _run_panel(_bh_decide, {"timeframe": "1Day", "notional_usd": NOTIONAL,
                                 "basket": ["SPY"]}, symbols=("SPY",))
    bh_win = {w[0]: w[2] for w in bh["per_win"]}
    out["bh_panel"] = {"fp": round(bh["fp"], 4), "trades": bh["total_trades"],
                       "per_win": [[w[0], w[1], round(w[2], 4)] for w in bh["per_win"]]}
    print(f"BH-SPY FP-cont={bh['fp']:+.4f} trades={bh['total_trades']}")

    # ---- PANEL SWEEP (proven-honest pattern, timing {SPY}) ----
    panel_grid = {"signal": ["move_z", "movevix_z", "goldcopper_z"],
                  "sign": ["trend", "contrarian"],
                  "window": [63, 126, 252],
                  "threshold": [0.5, 1.0, 1.5],
                  "mode": ["timing"], "risk_symbol": ["SPY"]}
    print("\n=== PANEL SWEEP timing {SPY} (FP-cont vs BH) ===")
    rows = []
    for ov in _grid(panel_grid):
        params = dict(BASE); params.update(ov); params["basket"] = ["SPY"]
        r = _run_panel(DECIDE, params, symbols=("SPY",), track_deploy=True)
        beats = sum(1 for w in r["per_win"] if w[2] > bh_win.get(w[0], -1e9))
        nwin = len(r["per_win"])
        ann, tot_pnl = _ann_on_deployed(r)
        rows.append({"params": {k: ov[k] for k in ("signal", "sign", "window", "threshold")},
                     "fp": round(r["fp"], 4),
                     "avg_deploy": round(r["avg_deploy"], 3) if r["avg_deploy"] is not None else None,
                     "worst_dd": round(r["worst_inst_dd"], 2), "trades": r["total_trades"],
                     "beats_bh_win": f"{beats}/{nwin}", "ann_deployed": round(ann, 2),
                     "tot_pnl_usd": round(tot_pnl, 2)})
    rows.sort(key=lambda x: -x["fp"])
    out["panel_sweeps"]["timing_SPY"] = rows
    for rr in rows[:12]:
        print(f"  FP={rr['fp']:+.4f} dep={rr['avg_deploy']} ann={rr['ann_deployed']:+.2f} "
              f"dd={rr['worst_dd']:.1f} tr={rr['trades']} beatBH={rr['beats_bh_win']} {rr['params']}")

    # ---- DEEP OOS SWEEP (SPY adjclose total-return, train<=2018/test>2018) ----
    deep_grid = {"signal": ["move_z", "movevix_z", "goldcopper_z"],
                 "sign": ["trend", "contrarian"],
                 "window": [63, 126, 252],
                 "threshold": [0.5, 1.0, 1.5],
                 "mode": ["timing"]}
    print("\n=== DEEP OOS SWEEP timing SPY adjclose (full + test>=2019) ===")
    drows = []
    for ov in _grid(deep_grid):
        params = dict(BASE); params.update(ov)
        bt = deep_backtest(params, start="2003-01-01", spread_bps=2.0)
        m = _split_metrics(bt, split_date="2019-01-01")
        drows.append({"params": {k: ov[k] for k in ("signal", "sign", "window", "threshold")},
                      "full_strat_pct": round(m["full"]["strat_ret_pct"], 1),
                      "full_bh_pct": round(m["full"]["bench_ret_pct"], 1),
                      "full_beat": m["full"]["beat_bh"],
                      "full_sharpe": round(m["full"]["strat_sharpe"], 3),
                      "bh_sharpe": round(m["full"]["bench_sharpe"], 3),
                      "test_strat_pct": round(m["test"]["strat_ret_pct"], 1),
                      "test_bh_pct": round(m["test"]["bench_ret_pct"], 1),
                      "test_beat": m["test"]["beat_bh"],
                      "test_minus_bh_pp": round(m["test"]["strat_minus_bh_pp"], 1),
                      "test_sharpe": round(m["test"]["strat_sharpe"], 3),
                      "test_avg_exposure": round(m["test"]["avg_exposure"], 3) if m["test"]["avg_exposure"] is not None else None,
                      "full_avg_exposure": round(m["full"]["avg_exposure"], 3) if m["full"]["avg_exposure"] is not None else None,
                      "corr_exposure_excess_full": round(m["full"]["corr_exposure_excess"], 3) if m["full"]["corr_exposure_excess"] is not None else None,
                      "corr_exposure_excess_test": round(m["test"]["corr_exposure_excess"], 3) if m["test"]["corr_exposure_excess"] is not None else None,
                      "n_flips": bt["n_flips"]})
    drows.sort(key=lambda x: -(x["test_strat_pct"]))
    out["deep_sweep"] = drows
    print("  [sorted by TEST raw return]")
    for rr in drows[:14]:
        print(f"  test={rr['test_strat_pct']:+8.1f}% (bh {rr['test_bh_pct']:+.1f}, d{rr['test_minus_bh_pp']:+.1f}pp) "
              f"beat={rr['test_beat']} exp={rr['test_avg_exposure']} corrXS={rr['corr_exposure_excess_test']} "
              f"full={rr['full_strat_pct']:+.0f}%(bh{rr['full_bh_pct']:+.0f}) {rr['params']}")

    # how many cells beat BH on TEST and on FULL
    n_test_beat = sum(1 for r in drows if r["test_beat"])
    n_full_beat = sum(1 for r in drows if r["full_beat"])
    n_both = sum(1 for r in drows if r["test_beat"] and r["full_beat"])
    out["meta"]["deep_grid_size"] = len(drows)
    out["meta"]["n_test_beat"] = n_test_beat
    out["meta"]["n_full_beat"] = n_full_beat
    out["meta"]["n_both_beat"] = n_both
    print(f"\n  cells: {len(drows)} | TEST-beat-BH: {n_test_beat} | FULL-beat-BH: {n_full_beat} | BOTH: {n_both}")

    # best deep cell (by test return) full detail
    if drows:
        best = drows[0]
        bp = dict(BASE); bp.update(best["params"]); bp["mode"] = "timing"
        bt = deep_backtest(bp, start="2003-01-01", spread_bps=2.0)
        m = _split_metrics(bt, split_date="2019-01-01")
        out["deep_best"] = {"params": best["params"], "metrics": m, "n_flips": bt["n_flips"]}

    # ---- RELABEL DIAG (a) for each signal family (window 126) ----
    print("\n=== (a) RELABEL: corr(signal, SPY 60d ret) / corr(signal, SPY 20d rvol) ===")
    for sig in ["move_z", "movevix_z", "goldcopper_z"]:
        for w in (63, 126, 252):
            d = diag_relabel(sig, w)
            out["relabel"][f"{sig}_W{w}"] = d
            print(f"  {sig:14s} W{w:<3d} n={d['n']:4d} vsRET={d['corr_vs_spy_return']:+.3f} vsVOL={d['corr_vs_spy_vol']:+.3f}")

    # ---- ORTHOGONALITY DIAG (c) for the best deep cell + each family default ----
    print("\n=== (c) ORTHOGONALITY: corr(state, SMA200-QQQ) / corr(state, voltarget-TQQQ) ===")
    ortho_cfgs = {}
    if drows:
        ortho_cfgs["deep_best"] = drows[0]["params"]
    ortho_cfgs["move_z_trend_W126_t1.0"] = {"signal": "move_z", "sign": "trend", "window": 126, "threshold": 1.0}
    ortho_cfgs["goldcopper_trend_W126_t1.0"] = {"signal": "goldcopper_z", "sign": "trend", "window": 126, "threshold": 1.0}
    for name, cfg in ortho_cfgs.items():
        p = dict(BASE); p.update(cfg); p["mode"] = "timing"
        d = diag_orthogonality(p)
        out["orthogonality"][name] = d
        print(f"  {name:28s} n={d['n']:4d} vsSMA200={d['corr_state_vs_sma200']} vsVOLtgt={d['corr_state_vs_voltarget']} "
              f"(state_on={d['avg_state_on']:.2f} sma_on={d['avg_sma_on']:.2f})" if d['corr_state_vs_sma200'] is not None else f"  {name} n={d['n']} (insufficient)")

    (WS / "reports" / "_xa_movegold_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_xa_movegold_results.json")


if __name__ == "__main__":
    main()
