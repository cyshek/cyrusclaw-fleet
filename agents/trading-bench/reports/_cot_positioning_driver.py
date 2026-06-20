"""Throwaway driver for the COT-POSITIONING lane (orthogonal-signal hunt, Tier-1 #2).

Composes PUBLIC runner.backtest_xsec.backtest_xsec + runner.fp_sharpe.
fp_continuous_sharpe over the canonical 8-window NAMED_WINDOWS panel with the
active Alpaca stock cost model. ZERO edits to protected/evaluator files.

Adapted from reports/_macro_nowcast_driver.py. The only structural change vs that
template: the COT candidate exposes `signal(date_str, params)` (the crowding
z-score), NOT `composite(...)`, so the relabel diagnostic calls MOD.signal.

THE SIGNAL is exogenous weekly speculator positioning (CFTC COT, TFF), read
POINT-IN-TIME via cot_cache.released_asof / released_history (release-gated: a
Tuesday snapshot cannot inform a trade before its Friday release). Forward-filled
onto the daily bar clock. The hypothesis: speculator (leveraged-fund) positioning
EXTREMES mean-revert. GATE = full-panel FP-cont-Sharpe >= 1.0 (unchanged).

RELABEL DIAGNOSTIC: correlation of the COT crowding-z series with (a) SPY trailing
return and (b) SPY trailing realized vol. Positioning SHOULD be orthogonal
(|r| <~0.3) -- that is the whole point of leaving the price/vol lane. High |r|
=> the signal is a price lane in disguise -> FLAG.

- spy_timing mode: single-name {SPY} deployment via the xsec idle-cash mechanism.
- cross_asset mode: {SPY, IEF, TLT, GLD} passed to backtest_xsec; strategy rotates
  the deployed notional among them (one at a time, exposure <= notional).
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
# COT weekly z-window default = 156 weeks (~3yr). Daily warmup must prime enough
# RELEASED weekly reports for that window: 156 weeks ~= 1095 calendar days, plus
# slack for holidays/the release lag.
WARMUP = 1200


def _load(cdir_name):
    cdir = WS / "strategies_candidates" / cdir_name
    spec = importlib.util.spec_from_file_location(
        f"cand_{cdir_name}", str(cdir / "strategy.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    params = json.loads((cdir / "params.json").read_text())
    return mod, params


MOD, BASE = _load("cot_positioning")
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
        bt = backtest_xsec("cot", bbs, params, decide_xsec_fn=wrapped,
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
    """Correlate the COT crowding-z series with SPY trailing return + realized vol.

    Uses MOD.signal (the COT candidate's public signal == crowding z-score),
    NOT composite (that was the macro-nowcast interface). High |r| => the
    positioning signal is really a price lane -> FLAG.
    """
    sc = _spy_closes()
    dates = [d for (d, _) in sc]
    closes = {d: c for (d, c) in sc}
    grid = dates[WARMUP::5] if len(dates) > WARMUP else dates[::5]
    comp_s, ret_s, vol_s = [], [], []
    for d in grid:
        comp = MOD.signal(d, params)
        if comp is None:
            continue
        idx = dates.index(d)
        if idx < max(ret_lb, vol_lb) + 1:
            continue
        p0 = closes[dates[idx - ret_lb]]; p1 = closes[d]
        tr = p1 / p0 - 1.0 if p0 > 0 else None
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
            ann = (ret_on_dep / years) * 100.0
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

    # provenance: exact contract names matched, per market
    from runner import cot_cache
    print("\n=== COT CONTRACT PROVENANCE ===")
    prov = {}
    for mkt in ("ES", "NQ", "ZN"):
        try:
            names = cot_cache.matched_contract_names(mkt)
        except Exception as e:
            names = [f"ERR {type(e).__name__}: {e}"]
        prov[mkt] = names
        print(f"  {mkt}: {names}")

    print("\n=== RELABEL DIAGNOSTIC (COT crowding-z vs SPY return / vol) ===")
    diag_cfgs = {
        "lev_net_oi z156": {"market": "ES", "feature": "lev_net_oi", "z_weeks": 156},
        "lev_net_oi z104": {"market": "ES", "feature": "lev_net_oi", "z_weeks": 104},
        "am_net_oi z156": {"market": "ES", "feature": "am_net_oi", "z_weeks": 156},
        "deal_net_oi z156": {"market": "ES", "feature": "deal_net_oi", "z_weeks": 156},
        "NQ lev_net_oi z156": {"market": "NQ", "feature": "lev_net_oi", "z_weeks": 156},
    }
    diag_out = {}
    for name, cfg in diag_cfgs.items():
        p = dict(BASE); p.update(cfg)
        d = relabel_diag(p)
        diag_out[name] = d
        rv = d["corr_vs_spy_return"]; vv = d["corr_vs_spy_vol"]
        rv_s = f"{rv:+.3f}" if rv is not None else "  n/a"
        vv_s = f"{vv:+.3f}" if vv is not None else "  n/a"
        print(f"  {name:22s} n={d['n']:4d} corr_vs_SPYret={rv_s} corr_vs_SPYvol={vv_s}")

    out = {"bh": {"fp": bh["fp"], "trades": bh["total_trades"],
                  "per_win": [[w[0], w[1], w[2]] for w in bh["per_win"]]},
           "provenance": prov, "relabel": diag_out, "sweeps": {}}

    # Honest, bounded sweep over the COT signal's REAL params. Contrarian vs
    # momentum, both exposure modes, both single-name and cross-asset.
    sweeps = {
        "spy_contrarian_lev": {
            "mode": ["spy_timing"], "market": ["ES"], "feature": ["lev_net_oi"],
            "direction": ["contrarian"], "exposure_mode": ["binary"],
            "z_weeks": [104, 156], "thr_z": [0.0, 0.5, 1.0],
        },
        "spy_momentum_lev": {
            "mode": ["spy_timing"], "market": ["ES"], "feature": ["lev_net_oi"],
            "direction": ["momentum"], "exposure_mode": ["binary"],
            "z_weeks": [104, 156], "thr_z": [0.0, 0.5, 1.0],
        },
        "spy_contrarian_lev_prop": {
            "mode": ["spy_timing"], "market": ["ES"], "feature": ["lev_net_oi"],
            "direction": ["contrarian"], "exposure_mode": ["proportional"],
            "z_weeks": [104, 156], "ramp_band": [1.0, 1.5],
        },
        "spy_contrarian_am": {
            "mode": ["spy_timing"], "market": ["ES"], "feature": ["am_net_oi"],
            "direction": ["contrarian"], "exposure_mode": ["binary"],
            "z_weeks": [104, 156], "thr_z": [0.0, 0.5, 1.0],
        },
        "spy_contrarian_deal": {
            "mode": ["spy_timing"], "market": ["ES"], "feature": ["deal_net_oi"],
            "direction": ["contrarian"], "exposure_mode": ["binary"],
            "z_weeks": [156], "thr_z": [0.0, 0.5, 1.0],
        },
        "xa_ief_contrarian_lev": {
            "mode": ["cross_asset"], "safe_asset": ["IEF"], "market": ["ES"],
            "feature": ["lev_net_oi"], "direction": ["contrarian"],
            "exposure_mode": ["binary"], "z_weeks": [104, 156], "thr_z": [0.0, 0.5],
        },
        "xa_gld_contrarian_lev": {
            "mode": ["cross_asset"], "safe_asset": ["GLD"], "market": ["ES"],
            "feature": ["lev_net_oi"], "direction": ["contrarian"],
            "exposure_mode": ["binary"], "z_weeks": [104, 156], "thr_z": [0.0, 0.5],
        },
    }

    best = {"fp": -1e9}
    for label, g in sweeps.items():
        is_xa = label.startswith("xa_")
        symbols = ("SPY", "IEF", "GLD") if is_xa else ("SPY",)
        print(f"\n=== {label} (symbols={symbols}) ===")
        rows = []
        for override in _grid(g):
            params = dict(BASE); params.update(override)
            r = _run_panel(DECIDE, params, symbols=symbols, track_deploy=True)
            beats = sum(1 for w in r["per_win"] if w[2] > bh_win.get(w[0], -1e9))
            nwin = len(r["per_win"])
            ann, tot_pnl = _ann_on_deployed(r)
            rows.append({
                "params": override, "fp": round(r["fp"], 3),
                "avg_deploy": round(r["avg_deploy"], 3) if r["avg_deploy"] is not None else None,
                "worst_dd": round(r["worst_inst_dd"], 2), "trades": r["total_trades"],
                "beats_bh_win": f"{beats}/{nwin}", "ann_deployed": round(ann, 2),
                "tot_pnl_usd": round(tot_pnl, 2),
            })
            if r["fp"] > best["fp"]:
                best = {"fp": r["fp"], "label": label, "params": override,
                        "trades": r["total_trades"], "avg_deploy": r["avg_deploy"],
                        "worst_dd": r["worst_inst_dd"]}
        rows.sort(key=lambda x: -x["fp"])
        out["sweeps"][label] = rows
        for rr in rows[:5]:
            dep = rr["avg_deploy"]
            print(f"  FP={rr['fp']:+.3f} dep={dep} ann={rr['ann_deployed']:+.2f} "
                  f"dd={rr['worst_dd']:.1f} tr={rr['trades']} beatBH={rr['beats_bh_win']} "
                  f"pnl=${rr['tot_pnl_usd']:+.1f} {rr['params']}")

    out["best"] = best
    print("\n=== BEST CELL ACROSS ALL SWEEPS ===")
    print(f"  FP={best['fp']:+.3f} {best.get('label')} {best.get('params')} "
          f"trades={best.get('trades')} dep={best.get('avg_deploy')} "
          f"worst_dd={best.get('worst_dd')}")
    print(f"  GATE = 1.0 FP-cont-Sharpe -> "
          f"{'PROMOTE' if best['fp'] >= 1.0 else 'REJECT'}")

    (WS / "reports" / "_cot_positioning_results.json").write_text(
        json.dumps(out, indent=2, default=str))
    print("\nwrote reports/_cot_positioning_results.json")


if __name__ == "__main__":
    main()
