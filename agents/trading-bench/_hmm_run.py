"""HMM confirm-or-kill — main experiment runner (calls into _hmm_confirm.py).
Writes reports/HMM_VERDICT_<UTCSTAMP>.md and reports/_hmm_result.json.
RESEARCH-ONLY. No runner/strategies/crontab/.db mutation. No pip install.
"""
from __future__ import annotations

import bisect
import json
import math
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

import sys
sys.path.insert(0, ".")

import _hmm_confirm as H
from runner import daily_bars_cache as dbc
from runner import fp_sharpe as fps
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    breadth_fraction,
)

TRADING_DAYS = 252
BPY = H.BPY
COST_BPS = 2.0
OOS = "2020-01-01"       # IS <= 2019, OOS 2020+
OOS_ALT = "2019-01-01"
THETAS = [0.5, 0.6, 0.7, 0.8]
KS = [2, 3]


def split_stats(dates: List[str], rets: np.ndarray, split: str) -> Dict:
    idx = bisect.bisect_left(dates, split)
    is_d, is_r = dates[:idx], rets[:idx]
    oos_d, oos_r = dates[idx:], rets[idx:]
    return {
        "is": H._stats_from_daily_returns(is_d, is_r) if len(is_r) else {},
        "oos": H._stats_from_daily_returns(oos_d, oos_r) if len(oos_r) else {},
    }


def make_breadth_gate():
    under_bars = dbc.get_daily("QQQ")
    und = [b["date"] for b in under_bars]
    uc = [b["adjclose"] for b in under_bars]

    def g(d_prev: str) -> float:
        idx = bisect.bisect_right(und, d_prev)
        return breadth_fraction(uc[:idx], [30, 90, 180])
    return g


def make_sma200_binary_gate():
    under_bars = dbc.get_daily("QQQ")
    und = [b["date"] for b in under_bars]
    uc = np.array([b["adjclose"] for b in under_bars], dtype=float)

    def g(d_prev: str) -> float:
        idx = bisect.bisect_right(und, d_prev)
        if idx < 200:
            return 0.0
        sma = float(np.mean(uc[idx - 200:idx]))
        return 1.0 if uc[idx - 1] > sma else 0.0
    return g


def make_hmm_gate(pbear_dates: List[str], pbear: np.ndarray, theta: float, lag: int = 0):
    """g=1.0 if P(bear through d_prev) < theta else 0.0. `lag` = extra bars of
    delay for the +1-bar canary. PAST-ONLY: held bar uses d_prev posterior."""
    pmap_idx = {d: i for i, d in enumerate(pbear_dates)}

    def g(d_prev: str) -> float:
        i = pmap_idx.get(d_prev)
        if i is None:
            i = bisect.bisect_right(pbear_dates, d_prev) - 1
        i = i - lag
        if i < 0:
            return 1.0
        return 1.0 if pbear[i] < theta else 0.0
    return g


def bear_fire_frac(pdates, pbear, theta, book_dates, min_train=504) -> float:
    pmap = {d: i for i, d in enumerate(pdates)}
    fires = 0
    live_n = 0
    for d in book_dates:
        i = pmap.get(d)
        if i is not None and i >= min_train:
            live_n += 1
            if pbear[i] >= theta:
                fires += 1
    return (fires / live_n) if live_n else 0.0


def lead_lag_analysis(pbear_dates, pbear, theta, sma_gate_fn, cal, min_train=504) -> Dict:
    """HMM de-risk onsets vs SMA-200 off-flips: signed day offset (HMM - SMA;
    negative => HMM LEADS / earlier warning)."""
    pmap = {d: i for i, d in enumerate(pbear_dates)}
    hmm_off = []
    sma_off = []
    for d in cal:
        i = pmap.get(d)
        fired = bool(i is not None and i >= min_train and pbear[i] >= theta)
        hmm_off.append(fired)
        sma_off.append(sma_gate_fn(d) < 0.5)
    hmm_off = np.array(hmm_off)
    sma_off = np.array(sma_off)

    def onsets(x):
        return [i for i in range(1, len(x)) if x[i] and not x[i - 1]]
    hmm_on = onsets(hmm_off)
    sma_on = onsets(sma_off)
    offsets = []
    for hi in hmm_on:
        if not sma_on:
            continue
        nearest = min(sma_on, key=lambda si: abs(si - hi))
        offsets.append(hi - nearest)
    offsets = np.array(offsets) if offsets else np.array([])
    both = int(np.sum(hmm_off & sma_off))
    hmm_days = int(np.sum(hmm_off))
    sma_days = int(np.sum(sma_off))
    return {
        "n_hmm_derisk_onsets": int(len(hmm_on)),
        "n_sma_off_onsets": int(len(sma_on)),
        "median_offset_days": float(np.median(offsets)) if len(offsets) else None,
        "mean_offset_days": float(np.mean(offsets)) if len(offsets) else None,
        "pct_hmm_leads": float(np.mean(offsets < 0) * 100.0) if len(offsets) else None,
        "pct_hmm_lags": float(np.mean(offsets > 0) * 100.0) if len(offsets) else None,
        "pct_coincide_5d": float(np.mean(np.abs(offsets) <= 5) * 100.0) if len(offsets) else None,
        "hmm_derisk_days": hmm_days, "sma_off_days": sma_days, "overlap_days": both,
        "jaccard": float(both / max(hmm_days + sma_days - both, 1)),
    }


def book_row(name, bk):
    st = bk["stats"]
    sp = split_stats(bk["dates"], bk["daily_ret"], OOS)
    sp_alt = split_stats(bk["dates"], bk["daily_ret"], OOS_ALT)
    return {
        "name": name, "fp_sharpe": st["fp_sharpe"], "cagr_pct": st["cagr_pct"],
        "max_drawdown_pct": st["max_drawdown_pct"], "ann_vol_pct": st["ann_vol_pct"],
        "avg_weight": st["avg_weight"], "turnover_units": st["turnover_units"],
        "turnover_cost_pct": st["turnover_cost_pct"],
        "oos_fp_sharpe": sp["oos"].get("fp_sharpe"), "oos_maxdd_pct": sp["oos"].get("max_drawdown_pct"),
        "oos_cagr_pct": sp["oos"].get("cagr_pct"),
        "is_fp_sharpe": sp["is"].get("fp_sharpe"), "is_maxdd_pct": sp["is"].get("max_drawdown_pct"),
        "oos2019_fp_sharpe": sp_alt["oos"].get("fp_sharpe"), "oos2019_maxdd_pct": sp_alt["oos"].get("max_drawdown_pct"),
    }


def decide(inc_row, sma_row, best, canary) -> Tuple[str, List[str]]:
    reasons = []
    if best is None:
        return "KILL", ["No non-degenerate HMM cell exists (all bear-states fire <2% or >98% of days) -> KILL #4 degenerate."]
    inc_s = inc_row["oos_fp_sharpe"]; inc_dd = inc_row["oos_maxdd_pct"]
    sma_s = sma_row["oos_fp_sharpe"]; sma_dd = sma_row["oos_maxdd_pct"]
    bs = best["oos_fp_sharpe"]; bdd = best["oos_maxdd_pct"]
    if bs is None or bs <= inc_s:
        reasons.append("KILL #1 (Occam): best HMM OOS FP-Sharpe %.4f <= incumbent-breadth OOS %.4f." % (bs or 0.0, inc_s))
    if bs is not None and bs <= sma_s:
        reasons.append("KILL #1b: best HMM OOS FP-Sharpe %.4f <= pure-SMA200 OOS %.4f." % (bs, sma_s))
    if bdd is None or bdd <= inc_dd:
        reasons.append("KILL #2: best HMM OOS maxDD %.2f%% not better than incumbent-breadth %.2f%%." % (bdd or 0.0, inc_dd))
    if canary is not None:
        edge_nolag = (bs or 0.0) - inc_s
        edge_lag = (canary["oos_fp_sharpe"] or 0.0) - inc_s
        if edge_lag <= 0.02 or (edge_nolag > 0 and edge_lag <= 0):
            reasons.append("KILL #3 (+1-bar canary): edge over incumbent collapses to %.4f under lag (<=0.02 floor)." % edge_lag)
    if not (2.0 <= best["bear_fire_frac_pct"] <= 98.0):
        reasons.append("KILL #4: bear-state fires %.1f%% of live days (degenerate)." % best["bear_fire_frac_pct"])
    verdict = "GO" if not reasons else "KILL"
    return verdict, reasons


def main():
    t0 = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result: Dict = {"stamp": stamp, "cost_bps": COST_BPS, "thetas": THETAS, "ks": KS}

    print(">>> Synthetic sanity check ...", flush=True)
    result["sanity"] = H.sanity_check_synthetic()
    print("    " + ("PASS" if result["sanity"]["PASS"] else "FAIL"), flush=True)

    print(">>> Loading QQQ features ...", flush=True)
    dates, logret, close = H.load_underlying_logrets("QQQ")
    rv20 = H.realized_vol_channel(logret, 20)
    vix = H.load_vix_channel(dates)
    result["vix_available"] = vix is not None
    feat_sets = {"ret": logret.reshape(-1, 1),
                 "ret+vol": np.column_stack([logret, rv20])}
    if vix is not None:
        feat_sets["ret+vol+vix"] = np.column_stack([logret, rv20, vix])

    print(">>> Building incumbent / sma200 / ungated books ...", flush=True)
    sma_gate = make_sma200_binary_gate()
    inc = H.simulate_voltarget_gated(make_breadth_gate())
    sma = H.simulate_voltarget_gated(sma_gate)
    ung = H.simulate_voltarget_gated(None)
    cal = inc["dates"]

    print(">>> Fitting HMM signals (monthly refit, expanding, forward-filter) ...", flush=True)
    hmm_signals = {}
    for K in KS:
        for fname, feat in feat_sets.items():
            key = "K%d_%s" % (K, fname)
            tt = time.time()
            pbear, flog = H.build_hmm_pbear(dates, feat, K=K, min_train=504)
            hmm_signals[key] = (dates, pbear, flog)
            live = pbear[504:]
            fire05 = float(np.mean(live >= 0.5)) if len(live) else 0.0
            print("    %-16s %.1fs  live_fire@0.5=%.1f%% n_fits=%d" % (
                key, time.time() - tt, fire05 * 100.0, len(flog)), flush=True)
    result["hmm_fit_summary"] = {
        k: {"n_fits": len(v[2]), "live_fire_p05_pct": float(np.mean(v[1][504:] >= 0.5) * 100.0)}
        for k, v in hmm_signals.items()}

    print(">>> Running HMM-gated books (theta grid) ...", flush=True)
    grid = []
    for key, (pdates, pbear, flog) in hmm_signals.items():
        for theta in THETAS:
            bk = H.simulate_voltarget_gated(make_hmm_gate(pdates, pbear, theta, lag=0))
            st = bk["stats"]
            sp = split_stats(bk["dates"], bk["daily_ret"], OOS)
            sp_alt = split_stats(bk["dates"], bk["daily_ret"], OOS_ALT)
            ff = bear_fire_frac(pdates, pbear, theta, bk["dates"])
            grid.append({
                "key": key, "theta": theta,
                "fp_sharpe": st["fp_sharpe"], "cagr_pct": st["cagr_pct"],
                "max_drawdown_pct": st["max_drawdown_pct"], "ann_vol_pct": st["ann_vol_pct"],
                "avg_weight": st["avg_weight"], "turnover_units": st["turnover_units"],
                "turnover_cost_pct": st["turnover_cost_pct"],
                "oos_fp_sharpe": sp["oos"].get("fp_sharpe"), "oos_maxdd_pct": sp["oos"].get("max_drawdown_pct"),
                "oos_cagr_pct": sp["oos"].get("cagr_pct"),
                "is_fp_sharpe": sp["is"].get("fp_sharpe"), "is_maxdd_pct": sp["is"].get("max_drawdown_pct"),
                "oos2019_fp_sharpe": sp_alt["oos"].get("fp_sharpe"), "oos2019_maxdd_pct": sp_alt["oos"].get("max_drawdown_pct"),
                "bear_fire_frac_pct": ff * 100.0,
            })
    result["grid"] = grid
    result["benchmarks"] = {
        "incumbent_breadth": book_row("incumbent_breadth", inc),
        "sma200_binary": book_row("sma200_binary", sma),
        "ungated": book_row("ungated", ung),
    }

    nondegen = [g for g in grid if 2.0 <= g["bear_fire_frac_pct"] <= 98.0 and g["oos_fp_sharpe"] is not None]
    best = max(nondegen, key=lambda g: g["oos_fp_sharpe"]) if nondegen else None
    best_full = max(nondegen, key=lambda g: g["fp_sharpe"]) if nondegen else None
    result["best_oos"] = best
    result["best_full"] = best_full
    result["n_nondegen"] = len(nondegen)

    canary = None
    if best is not None:
        pdates, pbear, _ = hmm_signals[best["key"]]
        bk_lag = H.simulate_voltarget_gated(make_hmm_gate(pdates, pbear, best["theta"], lag=1))
        sp_lag = split_stats(bk_lag["dates"], bk_lag["daily_ret"], OOS)
        canary = {
            "key": best["key"], "theta": best["theta"],
            "full_fp_sharpe": bk_lag["stats"]["fp_sharpe"],
            "oos_fp_sharpe": sp_lag["oos"].get("fp_sharpe"),
            "oos_maxdd_pct": sp_lag["oos"].get("max_drawdown_pct"),
            "delta_oos_sharpe_vs_nolag": (sp_lag["oos"].get("fp_sharpe") or 0.0) - (best["oos_fp_sharpe"] or 0.0),
        }
    result["canary_plus1bar"] = canary

    ll = None
    if best is not None:
        pdates, pbear, _ = hmm_signals[best["key"]]
        ll = lead_lag_analysis(pdates, pbear, best["theta"], sma_gate, cal)
    result["lead_lag"] = ll

    def best_for(K):
        cells = [g for g in nondegen if g["key"].startswith("K%d_" % K)]
        return max(cells, key=lambda g: g["oos_fp_sharpe"]) if cells else None
    result["k2_vs_k3"] = {"K2_best": best_for(2), "K3_best": best_for(3)}

    verdict, kill_reasons = decide(result["benchmarks"]["incumbent_breadth"],
                                   result["benchmarks"]["sma200_binary"], best, canary)
    result["verdict"] = verdict
    result["kill_reasons"] = kill_reasons
    result["elapsed_sec"] = time.time() - t0

    with open("reports/_hmm_result.json", "w") as f:
        json.dump(result, f, indent=2, default=float)
    write_report(result, stamp)
    print(">>> wrote reports/_hmm_result.json + report  (%.1fs)" % result["elapsed_sec"], flush=True)
    print(">>> VERDICT:", verdict, flush=True)
    for r in kill_reasons:
        print("    -", r, flush=True)
    return result


if __name__ == "__main__":
    from _hmm_report import write_report
    main()
