"""ALLOCATOR BREADTH-PORT driver (paper-research, read-only on live code).

QUESTION: Does putting the {30,90,180} breadth gate on the allocator's TQQQ
vol-target sleeve (sleeve A) improve the inv-vol-63d BLEND out-of-sample vs the
live binary-SMA200 sleeve A? Evidence for flipping the live allocator sleeve-A
gate.

NON-DESTRUCTIVE: imports _allocator_blend_tests as `ab` and REUSES its
blend_portfolio() / stats helpers / inv-vol weight fn verbatim. The only thing
that differs between arms is sleeve A: BASELINE-A = binary SMA200 vol-target
sleeve EXACTLY as ab.build_sleeves() builds it; BREADTH-A = identical
VolTargetParams PLUS breadth_windows=[30,90,180] (engine native, lookahead-safe).
Sleeve B (sector rotation top-2) and the inv-vol-63d blend layer are IDENTICAL.

HONESTY RAILS: headline Sharpe = full-period continuous-span pop-std*sqrt(252)
(_stats_from_equity), not median-of-windows; same path/blend/cost both arms;
baseline reproduced FIRST vs known allocator numbers (stop if not); breadth g
uses underlying closes <= D (engine guarantee); blend weights use only past
sleeve returns; +1-bar canary on the breadth signal.

Writes: reports/_allocator_breadth_port_result.json
Run:    python3 reports/_allocator_breadth_port_driver.py
"""
from __future__ import annotations

import bisect
import json
import sys
from typing import Dict, List

sys.path.insert(0, ".")

import _allocator_blend_tests as ab
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, run_backtest_voltarget,
)
from strategies_candidates.leveraged_long_trend import backtest_daily as bd

OOS_SPLIT = ab.OOS_SPLIT          # "2018-12-31" -> OOS = 2019-01-01 onward
BREADTH_WINDOWS = [30, 90, 180]
BASE_A_PARAMS = dict(target_ann_vol=0.25, vol_window=20, sma_window=200,
                     w_max=1.0, vix_gate=False, switch_cost_bps=2.0)


def build_sleeve_a(breadth, lag_extra=0):
    """Run vol-target sleeve A. breadth=False -> binary SMA200 gate EXACTLY as
    ab.build_sleeves does. breadth=True -> add breadth_windows=[30,90,180].
    lag_extra>0 (with breadth) steps the decision date back N trading days
    (canary). Returns (dates, equity, ret_map, stats, spx_ret_map)."""
    kw = dict(BASE_A_PARAMS)
    if breadth:
        kw["breadth_windows"] = list(BREADTH_WINDOWS)
    p = VolTargetParams(**kw)
    if lag_extra and breadth:
        vt = _run_voltarget_lagged(p, lag_extra)
    else:
        vt = run_backtest_voltarget(p)
    dates = vt["strategy"]["dates"]
    eq = vt["strategy"]["equity"]
    ret_map = ab.equity_to_daily_returns(dates, eq)
    spx_ret_map = ab.equity_to_daily_returns(dates, vt["spx"]["equity"])
    return dates, eq, ret_map, vt["strategy"]["stats"], spx_ret_map


def build_sleeve_b():
    """Sector rotation top-2 sleeve. Built ONCE; identical for both arms."""
    rot = ab.run_sector_rotation(["SPY", "QQQ", "GLD", "TLT"], bench="^GSPC",
                                 cost_bps=2.0, start="2005-01-01",
                                 hold_top=2, lookback_months=3)
    dates = rot["strategy"]["dates"]
    eq = rot["strategy"]["equity"]
    return ab.equity_to_daily_returns(dates, eq), rot["strategy"]["stats"]


def _run_voltarget_lagged(p, lag_extra):
    """CANARY: identical to the engine BREADTH path but the DECISION day is
    stepped back lag_extra extra trading days (weight held over D+1 decided from
    data <= D-lag_extra). The sleeve RETURN realization is unchanged (real D->D+1
    move); only the SIGNAL is lagged. A +1-day lag that erases the blend edge =>
    timing artifact. Re-implements the sim loop (read-only on the engine, which
    has no lag knob); math matches the engine BREADTH branch exactly except the
    decision-day step-back."""
    from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
        realized_ann_vol, breadth_fraction, target_weight, _clamp)
    from strategies_candidates.leveraged_long_trend.backtest_daily import _stats_from_equity
    sleeve_bars = bd.dbc.get_daily(p.sleeve)
    under_bars = bd.dbc.get_daily(p.underlying)
    bench_bars = bd.dbc.get_daily(p.benchmark)
    sleeve_by = {b["date"]: b for b in sleeve_bars}
    bench_by = {b["date"]: b for b in bench_bars}
    start = p.start or sleeve_bars[0]["date"]
    end = p.end or sleeve_bars[-1]["date"]
    cal = [b["date"] for b in sleeve_bars if start <= b["date"] <= end]
    under_dates = [b["date"] for b in under_bars]
    under_close = [b["adjclose"] for b in under_bars]
    sleeve_dates = [b["date"] for b in sleeve_bars]
    sleeve_close = [b["adjclose"] for b in sleeve_bars]
    sret_end_dates = []
    sret_vals = []
    for k in range(1, len(sleeve_close)):
        if sleeve_close[k - 1] > 0:
            sret_end_dates.append(sleeve_dates[k])
            sret_vals.append(sleeve_close[k] / sleeve_close[k - 1] - 1.0)
    equity = [1.0]
    strat_dates = [cal[0]]
    weights = []
    in_market_flags = []
    prev_w = 0.0
    n_rebalances = 0
    REBAL_EPS = 1e-9
    for i in range(1, len(cal)):
        dec_idx = max(0, (i - 1) - lag_extra)
        d_prev = cal[dec_idx]
        d = cal[i]
        uidx = bisect.bisect_right(under_dates, d_prev)
        uc = under_close[:uidx]
        sidx = bisect.bisect_right(sret_end_dates, d_prev)
        srets = sret_vals[:sidx]
        rv = realized_ann_vol(srets, p.vol_window) if p.target_ann_vol is not None else None
        g = breadth_fraction(uc, p.breadth_windows)
        if p.vix_gate and g > 0.0 and bd._vix_risk_off(d_prev, p.vix_ratio_thr):
            g = 0.0
        vt_w = target_weight(True, rv, p.target_ann_vol, p.w_max)
        w = _clamp(g * vt_w, 0.0, p.w_max)
        bn = sleeve_by.get(d)
        bp = sleeve_by.get(cal[i - 1])
        sleeve_ret = (bn["adjclose"] / bp["adjclose"] - 1.0) if (bn and bp and bp["adjclose"] > 0) else 0.0
        cash_ret = bd._tbill_daily_rate(cal[i - 1]) if p.use_tbill_cash else 0.0
        blended = w * sleeve_ret + (1.0 - w) * cash_ret
        dw = abs(w - prev_w)
        cost = (p.switch_cost_bps / 10000.0) * dw
        if dw > REBAL_EPS:
            n_rebalances += 1
        equity.append(equity[-1] * (1.0 + blended) * (1.0 - cost))
        strat_dates.append(d)
        weights.append(w)
        in_market_flags.append(w > 0.0)
        prev_w = w
    strat_stats = _stats_from_equity(strat_dates, equity, in_market_flags, n_rebalances)
    spx_eq = [1.0]
    for j in range(1, len(strat_dates)):
        bn = bench_by.get(strat_dates[j])
        bp = bench_by.get(strat_dates[j - 1])
        r = (bn["adjclose"] / bp["adjclose"] - 1.0) if (bn and bp and bp["adjclose"] > 0) else 0.0
        spx_eq.append(spx_eq[-1] * (1.0 + r))
    sdict = dict(strat_stats.__dict__)
    sdict["avg_weight"] = (sum(weights) / len(weights)) if weights else 0.0
    sdict["n_rebalances"] = n_rebalances
    return {"strategy": {"stats": sdict, "dates": strat_dates, "equity": equity,
                         "weights": weights},
            "spx": {"equity": spx_eq}}


def make_blend(a_ret_map, a_spx_ret_map, b_ret_map):
    """Build the inv-vol-63d blend for sleeve-A ret_map (binary or breadth)
    using the EXACT ab.blend_portfolio + ab inv-vol fn. Returns (report_block,
    common_dates, a_returns, b_returns)."""
    common = sorted(set(a_ret_map) & set(b_ret_map))
    common = [d for d in common if d in a_spx_ret_map]
    a_r = [a_ret_map[d] for d in common]
    b_r = [b_ret_map[d] for d in common]
    spx_r = [a_spx_ret_map[d] for d in common]
    sleeves = [a_r, b_r]            # 0 = sleeve A (TQQQ), 1 = rotation

    def invvol_wfn(lookback=63):
        # IDENTICAL to ab.main() invvol_wfn(63): weight_i ~ 1/ann_vol_i over the
        # trailing 63 returns STRICTLY BEFORE month-open idx, normalized. Uses
        # ab.annualized_vol (population stdev * sqrt252). Lookahead-safe.
        def fn(idx):
            if idx < 2:
                return [0.5, 0.5]
            lo = max(0, idx - lookback)
            v0 = ab.annualized_vol(sleeves[0][lo:idx])
            v1 = ab.annualized_vol(sleeves[1][lo:idx])
            if v0 <= 0 or v1 <= 0:
                return [0.5, 0.5]
            iv0, iv1 = 1.0 / v0, 1.0 / v1
            s = iv0 + iv1
            return [iv0 / s, iv1 / s]
        return fn

    spx_curve = ab.stats_from_returns(common, spx_r)
    b = ab.blend_portfolio(common, sleeves, invvol_wfn(63), blend_cost_bps=2.0,
                           vol_lookback_days=63)
    rep = ab.report_blend(b, "invvol_63d", spx_curve["dates"], spx_curve["equity"])
    if b["weight_log"]:
        rep["avg_w_tqqq"] = sum(wl["w"][0] for wl in b["weight_log"]) / len(b["weight_log"])
        rep["avg_w_rot"] = sum(wl["w"][1] for wl in b["weight_log"]) / len(b["weight_log"])
    rep["common_window"] = [common[0], common[-1]]
    rep["n_common_days"] = len(common)
    rep["sleeveA_full_annvol"] = ab.annualized_vol(a_r)
    rep["sleeveB_full_annvol"] = ab.annualized_vol(b_r)
    oos_idx = [i for i, d in enumerate(common) if d >= "2019-01-01"]
    if oos_idx:
        rep["sleeveA_oos_annvol"] = ab.annualized_vol([a_r[i] for i in oos_idx])
        rep["sleeveB_oos_annvol"] = ab.annualized_vol([b_r[i] for i in oos_idx])
    return rep, common, a_r, b_r


def standalone_block(dates, eq):
    """Full + IS + OOS standalone stats for a sleeve-A equity curve, sliced on
    the allocator OOS_SPLIT (2018-12-31)."""
    full = ab.slice_equity_stats(dates, eq, "2000-01-01", "2099-12-31")
    is_ = ab.slice_equity_stats(dates, eq, "2000-01-01", OOS_SPLIT)
    oos = ab.slice_equity_stats(dates, eq, "2019-01-01", "2099-12-31")
    return {
        "full": {"sharpe": full.get("sharpe"), "cagr_pct": full.get("cagr_pct"),
                 "maxdd_pct": full.get("max_drawdown_pct"),
                 "vol_pct": full.get("ann_vol_pct"),
                 "total_return_pct": full.get("total_return_pct")},
        "is_2010_2018": {"sharpe": is_.get("sharpe"), "cagr_pct": is_.get("cagr_pct"),
                         "maxdd_pct": is_.get("max_drawdown_pct")},
        "oos_2019_today": {"sharpe": oos.get("sharpe"), "cagr_pct": oos.get("cagr_pct"),
                           "maxdd_pct": oos.get("max_drawdown_pct"),
                           "total_return_pct": oos.get("total_return_pct")},
    }


def main():
    out = {}
    out["meta"] = {
        "question": ("Does {30,90,180} breadth on allocator sleeve A improve the "
                     "inv-vol-63d BLEND OOS vs binary SMA200 sleeve A?"),
        "oos_split": OOS_SPLIT,
        "breadth_windows": BREADTH_WINDOWS,
        "base_a_params": BASE_A_PARAMS,
        "blend": "inv-vol-63d monthly, blend_cost_bps=2.0, VOL_LOOKBACK_DAYS=63 (ab.blend_portfolio + ab invvol fn)",
        "headline_sharpe": "full-period continuous-span pop-std*sqrt252 (_stats_from_equity), NOT median-of-windows",
    }

    print(">>> sleeve B (sector rotation top-2; identical both arms) ...", flush=True)
    b_ret_map, b_stats = build_sleeve_b()
    print("    ROT Sharpe %.3f CAGR %.1f%% maxDD %.1f%%" % (
        b_stats["sharpe"], b_stats["cagr_pct"], b_stats["max_drawdown_pct"]))

    print(">>> sleeve A BINARY (SMA200, exactly as build_sleeves) ...", flush=True)
    a0_dates, a0_eq, a0_ret, a0_stats, a0_spx = build_sleeve_a(breadth=False)
    print("    binary-A standalone Sharpe %.3f maxDD %.1f%% avgW %.3f" % (
        a0_stats["sharpe"], a0_stats["max_drawdown_pct"], a0_stats.get("avg_weight", 0.0)))

    print(">>> sleeve A BREADTH {30,90,180} ...", flush=True)
    a1_dates, a1_eq, a1_ret, a1_stats, a1_spx = build_sleeve_a(breadth=True)
    print("    breadth-A standalone Sharpe %.3f maxDD %.1f%% avgW %.3f" % (
        a1_stats["sharpe"], a1_stats["max_drawdown_pct"], a1_stats.get("avg_weight", 0.0)))

    out["standalone_sleeveA"] = {
        "binary_sma200": standalone_block(a0_dates, a0_eq),
        "breadth_30_90_180": standalone_block(a1_dates, a1_eq),
        "binary_avg_weight": a0_stats.get("avg_weight"),
        "breadth_avg_weight": a1_stats.get("avg_weight"),
        "ref_tiebreak_split_2018_01_01": {
            "note": "from reports/_ens_breadth_tiebreak_result.json (split 2018-01-01, NOT allocator split)",
            "binary_oos_sharpe": 0.8370, "binary_oos_maxdd": -34.52,
            "breadth_oos_sharpe": 0.8553, "breadth_oos_maxdd": -22.55,
        },
    }

    print(">>> BLEND with binary-A (reproduce allocator baseline FIRST) ...", flush=True)
    blend0, common0, a0r, b0r = make_blend(a0_ret, a0_spx, b_ret_map)
    print("    binary-A blend: full Sharpe %.4f OOS Sharpe %.4f maxDD %.2f%% w_tqqq %.4f" % (
        blend0["full"]["sharpe"], blend0["oos_2019_today"]["sharpe"],
        blend0["full"]["maxdd_pct"], blend0["avg_w_tqqq"]))

    KNOWN_FULL_SHARPE = 1.012478598814084
    KNOWN_OOS_SHARPE = 1.1424972297107936
    KNOWN_MAXDD = -23.897251590900126
    KNOWN_W_TQQQ = 0.348525857325614
    repro_ok = (abs(blend0["full"]["sharpe"] - KNOWN_FULL_SHARPE) < 0.02
                and abs(blend0["oos_2019_today"]["sharpe"] - KNOWN_OOS_SHARPE) < 0.03
                and abs(blend0["full"]["maxdd_pct"] - KNOWN_MAXDD) < 1.0
                and abs(blend0["avg_w_tqqq"] - KNOWN_W_TQQQ) < 0.02)
    out["baseline_reproduction"] = {
        "known_full_sharpe": KNOWN_FULL_SHARPE, "got_full_sharpe": blend0["full"]["sharpe"],
        "known_oos_sharpe": KNOWN_OOS_SHARPE, "got_oos_sharpe": blend0["oos_2019_today"]["sharpe"],
        "known_full_maxdd": KNOWN_MAXDD, "got_full_maxdd": blend0["full"]["maxdd_pct"],
        "known_w_tqqq": KNOWN_W_TQQQ, "got_w_tqqq": blend0["avg_w_tqqq"],
        "reproduced": bool(repro_ok),
    }
    if not repro_ok:
        out["FATAL"] = "Binary-A blend did NOT reproduce known allocator numbers; STOPPED per honesty rail."
        with open("reports/_allocator_breadth_port_result.json", "w") as f:
            json.dump(out, f, indent=2, default=str)
        print("!!! BASELINE DID NOT REPRODUCE -- STOP. See JSON.")
        return out
    print("    baseline reproduced OK.")

    print(">>> BLEND with breadth-A {30,90,180} ...", flush=True)
    blend1, common1, a1r, b1r = make_blend(a1_ret, a1_spx, b_ret_map)
    print("    breadth-A blend: full Sharpe %.4f OOS Sharpe %.4f maxDD %.2f%% w_tqqq %.4f" % (
        blend1["full"]["sharpe"], blend1["oos_2019_today"]["sharpe"],
        blend1["full"]["maxdd_pct"], blend1["avg_w_tqqq"]))

    out["blend_binary_A"] = blend0
    out["blend_breadth_A"] = blend1

    # ---------- canary: +1-bar lag on breadth-A signal, rebuild blend ----------
    print(">>> CANARY: +1-bar lag on breadth-A signal, rebuild blend ...", flush=True)
    c_dates, c_eq, c_ret, c_stats, c_spx = build_sleeve_a(breadth=True, lag_extra=1)
    blendC, _, _, _ = make_blend(c_ret, c_spx, b_ret_map)
    print("    canary(+1) breadth-A blend: full Sharpe %.4f OOS Sharpe %.4f maxDD %.2f%%" % (
        blendC["full"]["sharpe"], blendC["oos_2019_today"]["sharpe"], blendC["full"]["maxdd_pct"]))
    out["blend_breadth_A_canary_plus1"] = blendC
    out["canary_standalone_plus1"] = standalone_block(c_dates, c_eq)

    # ---------- deltas (breadth - binary) ----------
    def d(a, b):
        if a is None or b is None:
            return None
        return a - b
    out["deltas_breadth_minus_binary"] = {
        "blend_full_sharpe": d(blend1["full"]["sharpe"], blend0["full"]["sharpe"]),
        "blend_oos_sharpe": d(blend1["oos_2019_today"]["sharpe"], blend0["oos_2019_today"]["sharpe"]),
        "blend_full_maxdd": d(blend1["full"]["maxdd_pct"], blend0["full"]["maxdd_pct"]),
        "blend_oos_maxdd": d(blend1["oos_2019_today"]["maxdd_pct"], blend0["oos_2019_today"]["maxdd_pct"]),
        "blend_full_cagr": d(blend1["full"]["cagr_pct"], blend0["full"]["cagr_pct"]),
        "blend_oos_cagr": d(blend1["oos_2019_today"]["cagr_pct"], blend0["oos_2019_today"]["cagr_pct"]),
        "avg_w_tqqq": d(blend1["avg_w_tqqq"], blend0["avg_w_tqqq"]),
        "sleeveA_full_annvol": d(blend1.get("sleeveA_full_annvol"), blend0.get("sleeveA_full_annvol")),
        "sleeveA_oos_annvol": d(blend1.get("sleeveA_oos_annvol"), blend0.get("sleeveA_oos_annvol")),
    }

    # ---------- verdict ----------
    dd = out["deltas_breadth_minus_binary"]
    sharpe_oos_better = (dd["blend_oos_sharpe"] or 0) > 0.005
    maxdd_oos_better = (dd["blend_oos_maxdd"] or 0) > 0.1   # less-negative maxDD = improvement
    sharpe_full_better = (dd["blend_full_sharpe"] or 0) > 0.005
    maxdd_full_better = (dd["blend_full_maxdd"] or 0) > 0.1
    canary_holds = (blendC["oos_2019_today"]["sharpe"] is not None
                    and abs(blendC["oos_2019_today"]["sharpe"] - blend1["oos_2019_today"]["sharpe"]) < 0.15)
    go = bool((sharpe_oos_better or maxdd_oos_better))
    out["verdict"] = {
        "blend_oos_sharpe_better": bool(sharpe_oos_better),
        "blend_oos_maxdd_better": bool(maxdd_oos_better),
        "blend_full_sharpe_better": bool(sharpe_full_better),
        "blend_full_maxdd_better": bool(maxdd_full_better),
        "canary_plus1_holds": bool(canary_holds),
        "recommendation": "GO" if go else "NO-GO",
        "note": ("GO iff breadth-A blend beats binary-A blend OOS on Sharpe OR maxDD "
                 "net of cost; a +1-bar canary collapse flips to NO-GO (timing artifact)."),
    }
    if go and not canary_holds:
        out["verdict"]["recommendation"] = "NO-GO (canary collapse)"

    with open("reports/_allocator_breadth_port_result.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("")
    print(">>> VERDICT: %s | OOS Sharpe d=%+.4f maxDD d=%+.2fpp | full Sharpe d=%+.4f maxDD d=%+.2fpp" % (
        out["verdict"]["recommendation"], dd["blend_oos_sharpe"] or 0, dd["blend_oos_maxdd"] or 0,
        dd["blend_full_sharpe"] or 0, dd["blend_full_maxdd"] or 0))
    print("    w_tqqq: binary %.4f -> breadth %.4f (d=%+.4f)" % (
        blend0["avg_w_tqqq"], blend1["avg_w_tqqq"], dd["avg_w_tqqq"] or 0))
    print("wrote reports/_allocator_breadth_port_result.json")
    return out


if __name__ == "__main__":
    main()
