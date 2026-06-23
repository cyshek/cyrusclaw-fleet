"""
_finra_shortvol_run.py - drive the full pre-registered FINRA short-vol experiment.

Outputs a JSON blob (_finra_shortvol_results.json) with:
  - data span + caveats per symbol
  - buy&hold benchmark (full + OOS train/test)
  - full param sweep response surface (both H1/H2, windows, thresholds, holds)
  - best configs (full + OOS-selected) with strat-vs-benchmark table
  - orthogonality correlations (SVR & its z vs SPY trailing return + realized vol)

NO lookahead: signal -> 1-bar lag handled in backtest_overlay. OOS = train 2019-2022,
test 2023-2026; best config is SELECTED on train and REPORTED on test (true OOS).
"""

from __future__ import annotations

import json
import math
from itertools import product
from typing import Dict, List

import numpy as np

from runner import finra_shortvol_backtest as bt

OOS_SPLIT = "2023-01-01"   # train < this, test >= this
WINDOWS = [21, 42, 63, 126, 252]
Z_THRESHOLDS = [0.5, 1.0, 1.5, 2.0]
HOLDS = [1, 3, 5, 10]
DIRECTIONS = ["H1", "H2"]


def _res_row(r: bt.StratResult) -> dict:
    return {
        "total_return": round(r.total_return, 4),
        "cagr": round(r.cagr, 4) if not math.isnan(r.cagr) else None,
        "sharpe": round(r.sharpe, 3),
        "max_drawdown": round(r.max_drawdown, 4),
        "n_roundtrips": round(r.n_roundtrips, 1),
        "exposure": round(r.exposure, 3),
        "n_days": r.n_days,
        "start": r.start, "end": r.end,
    }


def orthogonality(data: Dict[str, np.ndarray], window: int = 63) -> dict:
    """Corr of SVR and its trailing z to (a) SPY trailing return, (b) SPY realized vol.
    All trailing windows are causal. Uses the SAME aligned series (so same symbol)."""
    svr = data["svr"]
    ret = data["ret"]
    n = len(ret)
    z = bt.rolling_z(svr, window)
    # trailing cumulative return over `window` (causal): product of (1+ret) - 1
    trail_ret = np.full(n, np.nan)
    trail_vol = np.full(n, np.nan)
    for t in range(window, n):
        w = ret[t - window + 1: t + 1]
        trail_ret[t] = np.prod(1.0 + w) - 1.0
        trail_vol[t] = w.std(ddof=0) * math.sqrt(bt.TRADING_DAYS)

    def _corr(a, b):
        m = ~np.isnan(a) & ~np.isnan(b)
        if m.sum() < 10:
            return None
        aa, bb = a[m], b[m]
        if aa.std() < 1e-12 or bb.std() < 1e-12:
            return None
        return float(np.corrcoef(aa, bb)[0, 1])

    return {
        "window": window,
        "corr_svr_vs_trailret": _round(_corr(svr, trail_ret)),
        "corr_svr_vs_trailvol": _round(_corr(svr, trail_vol)),
        "corr_svrz_vs_trailret": _round(_corr(z, trail_ret)),
        "corr_svrz_vs_trailvol": _round(_corr(z, trail_vol)),
    }


def _round(x):
    return round(x, 3) if isinstance(x, float) else x


def sweep_symbol(symbol: str) -> dict:
    data_full = bt.build_aligned(symbol)
    out: dict = {"symbol": symbol}
    if len(data_full["dates"]) < 300:
        out["error"] = f"insufficient data: {len(data_full['dates'])} aligned days"
        return out

    dates = data_full["dates"]
    out["span"] = {"n": int(len(dates)), "first": str(dates[0]), "last": str(dates[-1])}

    # benchmark full + OOS
    train_mask = dates < OOS_SPLIT
    test_mask = ~train_mask

    def _slice(data, mask):
        return {k: (v[mask] if isinstance(v, np.ndarray) else v) for k, v in data.items()}

    data_train = _slice(data_full, train_mask)
    data_test = _slice(data_full, test_mask)

    out["benchmark"] = {
        "full": _res_row(bt.backtest_buyhold(data_full, symbol)),
        "train": _res_row(bt.backtest_buyhold(data_train, symbol)),
        "test": _res_row(bt.backtest_buyhold(data_test, symbol)),
    }
    out["orthogonality"] = orthogonality(data_full, window=63)

    # ---- full sweep (report whole surface) ----
    surface: List[dict] = []
    for direction, window, zt, hold in product(DIRECTIONS, WINDOWS, Z_THRESHOLDS, HOLDS):
        sig_full = bt.make_signal(data_full["svr"], window, zt, direction, hold, use_pct=False)
        r_full = bt.backtest_overlay(data_full, sig_full,
                                     f"{direction}_w{window}_z{zt}_h{hold}", symbol)
        # OOS: build signal on FULL series (so trailing stats are continuous) then slice.
        # Selection happens on train; we record both train and test metrics per config.
        sig_train = sig_full[train_mask]
        sig_test = sig_full[test_mask]
        r_train = bt.backtest_overlay(data_train, sig_train, "train", symbol)
        r_test = bt.backtest_overlay(data_test, sig_test, "test", symbol)
        surface.append({
            "direction": direction, "window": window, "z": zt, "hold": hold,
            "full_total": round(r_full.total_return, 4),
            "full_sharpe": round(r_full.sharpe, 3),
            "full_maxdd": round(r_full.max_drawdown, 4),
            "full_trips": round(r_full.n_roundtrips, 1),
            "full_expo": round(r_full.exposure, 3),
            "train_total": round(r_train.total_return, 4),
            "train_sharpe": round(r_train.sharpe, 3),
            "test_total": round(r_test.total_return, 4),
            "test_sharpe": round(r_test.sharpe, 3),
            "test_maxdd": round(r_test.max_drawdown, 4),
            "test_trips": round(r_test.n_roundtrips, 1),
            "test_expo": round(r_test.exposure, 3),
        })
    out["surface"] = surface

    # ---- best configs ----
    bench_full = out["benchmark"]["full"]
    bench_test = out["benchmark"]["test"]

    # best by FULL raw return (in-sample optimistic) and by FULL sharpe
    best_full_ret = max(surface, key=lambda s: s["full_total"])
    best_full_sharpe = max(surface, key=lambda s: s["full_sharpe"])

    # HONEST OOS: pick config that maximizes TRAIN raw return, then report its TEST result.
    best_by_train_ret = max(surface, key=lambda s: s["train_total"])
    best_by_train_sharpe = max(surface, key=lambda s: s["train_sharpe"])

    out["best"] = {
        "by_full_return": best_full_ret,
        "by_full_sharpe": best_full_sharpe,
        "oos_selected_on_train_return": {
            "config": best_by_train_ret,
            "beats_bench_test_return": bool(best_by_train_ret["test_total"] > bench_test["total_return"]),
            "bench_test_return": bench_test["total_return"],
            "bench_test_sharpe": bench_test["sharpe"],
        },
        "oos_selected_on_train_sharpe": {
            "config": best_by_train_sharpe,
            "beats_bench_test_return": bool(best_by_train_sharpe["test_total"] > bench_test["total_return"]),
            "bench_test_return": bench_test["total_return"],
            "bench_test_sharpe": bench_test["sharpe"],
        },
    }
    return out


def _sanitize(o):
    """Recursively coerce numpy scalars/bools to native Python types for JSON."""
    import numpy as _np
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    if isinstance(o, (_np.bool_,)):
        return bool(o)
    if isinstance(o, (_np.integer,)):
        return int(o)
    if isinstance(o, (_np.floating,)):
        return float(o)
    return o


def main():
    results = {}
    for sym in ["SPY", "QQQ"]:
        print(f"=== sweeping {sym} ===")
        results[sym] = sweep_symbol(sym)
        if "error" in results[sym]:
            print(f"  {results[sym]['error']}")
            continue
        b = results[sym]["benchmark"]
        print(f"  span {results[sym]['span']['first']}..{results[sym]['span']['last']} "
              f"n={results[sym]['span']['n']}")
        print(f"  bench full ret={b['full']['total_return']:.3f} sharpe={b['full']['sharpe']:.3f}; "
              f"test ret={b['test']['total_return']:.3f} sharpe={b['test']['sharpe']:.3f}")
        oos = results[sym]["best"]["oos_selected_on_train_return"]
        c = oos["config"]
        print(f"  OOS(sel train-ret) -> {c['direction']} w{c['window']} z{c['z']} h{c['hold']}: "
              f"test ret={c['test_total']:.3f} sharpe={c['test_sharpe']:.3f} "
              f"(beats bench: {oos['beats_bench_test_return']})")
        o = results[sym]["orthogonality"]
        print(f"  ortho: svr~ret={o['corr_svr_vs_trailret']} svr~vol={o['corr_svr_vs_trailvol']} "
              f"z~ret={o['corr_svrz_vs_trailret']} z~vol={o['corr_svrz_vs_trailvol']}")

    with open("_finra_shortvol_results.json", "w") as f:
        json.dump(_sanitize(results), f, indent=2)
    print("\nwrote _finra_shortvol_results.json")


if __name__ == "__main__":
    main()
