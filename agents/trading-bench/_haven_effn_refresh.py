"""HAVEN eff-N / Sharpe REFRESH vs the NEW QUARTERLY 2-sleeve book.

REFRESH (not re-derive): the prior haven frontier
(reports/ALLOCATOR_HAVEN_FRONTIER_20260623T223225Z.md) was computed vs the OLD
MONTHLY 2-sleeve baseline (raw 1011% / Sharpe 1.014). The live book changed
TODAY to QUARTERLY rebalance (reports/ALLOCATOR_CADENCE_SWEEP_20260625.md:
quarterly 2-sleeve = raw 1068% / full Sharpe 1.018 / OOS 1.151 / maxDD -24.9%).
So the haven give-up math must be REFRESHED against the new, better baseline.

Reuses validated machinery VERBATIM (build_sleeves, blend_portfolio drift/cost
/stats). Rebuilds the HAVEN sleeve cleanly from the documented spec: GLD/TLT/
DBC/UUP inverse-vol parity, PAST-only trailing 63d vol, 2bps one-way intra-haven
turnover, intra-period drift. eff-N = participation ratio of the daily-return
correlation matrix = (trace)^2 / sum_ij C_ij^2.

RAILS: full-period CONTINUOUS Sharpe (sqrt(252), fp_sharpe SAMPLE stdev) +
_stats_from_equity (population) Sharpe; SPX (^GSPC) same traded path; 2bps
one-way; PAST-only 63d vol (no lookahead); OOS split 2018-12-31; forward P&L
d->d+1; canary printed. Haven is INSURANCE -> NEGATIVE raw standalone is correct.

Run: python3 _haven_effn_refresh.py  -> reports/_haven_effn_refresh_result.json
NO protected/live files / crontab / paper clock / .db touched. RESEARCH ONLY.
"""
from __future__ import annotations

import bisect
import json
import math
import os
import sys
from typing import Callable, Dict, List, Optional

sys.path.insert(0, ".")

import _allocator_blend_tests as ab
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    _stats_from_equity, TRADING_DAYS,
)
from runner import daily_bars_cache as dbc
from runner import fp_sharpe as fps

OOS_SPLIT = "2018-12-31"
VOL_LOOKBACK = 63
COST_BPS = 2.0
HAVEN_ASSETS = ["GLD", "TLT", "DBC", "UUP"]


def month_open_set(dates: List[str]) -> set:
    seen = set()
    out = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            out.add(i)
    return out


def quarter_open_set(dates: List[str]) -> set:
    seen = set()
    out = set()
    for i, d in enumerate(dates):
        mo = int(d[5:7])
        q = (d[:4], (mo - 1) // 3)
        if q not in seen:
            seen.add(q)
            out.add(i)
    return out


def annualized_vol_pop(returns: List[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def fp_cont_sharpe(equity: List[float]) -> float:
    rets = fps.equity_curve_returns(equity)
    return fps.sharpe_from_returns(rets, TRADING_DAYS)


def slice_stats(dates: List[str], equity: List[float], start: str, end: str) -> Dict:
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    if hi - lo < 3:
        return {"n": hi - lo}
    sub_ds = dates[lo:hi]
    base = equity[lo]
    sub_eq = [v / base for v in equity[lo:hi]]
    st = _stats_from_equity(sub_ds, sub_eq)
    return dict(st.__dict__)


def maxdd_in_window(dates: List[str], equity: List[float], start: str, end: str) -> Optional[float]:
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    if hi - lo < 3:
        return None
    base = equity[lo]
    peak = equity[lo] / base
    mdd = 0.0
    for v in equity[lo:hi]:
        x = v / base
        if x > peak:
            peak = x
        dd = x / peak - 1.0
        if dd < mdd:
            mdd = dd
    return mdd * 100.0


def build_asset_returns(symbols: List[str]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for s in symbols:
        bars = dbc.get_daily(s)
        ds = [b["date"] for b in bars]
        ac = [b["adjclose"] for b in bars]
        rm: Dict[str, float] = {}
        for i in range(1, len(ds)):
            if ac[i - 1] and ac[i - 1] != 0 and ac[i] is not None:
                rm[ds[i]] = ac[i] / ac[i - 1] - 1.0
        out[s] = rm
    return out


def build_haven_sleeve(common_dates: List[str], cadence: str = "monthly",
                       cost_bps: float = COST_BPS,
                       lookback: int = VOL_LOOKBACK) -> Dict:
    """GLD/TLT/DBC/UUP inverse-vol-parity haven daily-return stream on
    common_dates. PAST-only trailing vol; intra-period drift; snap-to-target at
    each calendar rebalance with cost_bps one-way on the 4-asset turnover.
    ret_map[d] = haven return ending on date d (d=common_dates[i], i>=1)."""
    asset_rm = build_asset_returns(HAVEN_ASSETS)
    na = len(HAVEN_ASSETS)
    arr: List[List[float]] = []
    for s in HAVEN_ASSETS:
        rm = asset_rm[s]
        arr.append([rm.get(d, 0.0) for d in common_dates])

    if cadence == "monthly":
        trig = month_open_set(common_dates)
    elif cadence == "quarterly":
        trig = quarter_open_set(common_dates)
    else:
        raise ValueError("cadence must be monthly|quarterly")

    def invvol_target(idx: int) -> List[float]:
        if idx < 2:
            return [1.0 / na] * na
        lo = max(0, idx - lookback)
        ivs = []
        for k in range(na):
            v = annualized_vol_pop(arr[k][lo:idx])
            ivs.append(1.0 / v if v > 0 else 0.0)
        s = sum(ivs)
        if s <= 0:
            return [1.0 / na] * na
        return [x / s for x in ivs]

    n = len(common_dates)
    w0 = invvol_target(0)
    bucket = [w0[k] for k in range(na)]
    equity = [1.0]
    ret_map: Dict[str, float] = {}
    n_rebal = 0
    turnover_total = 0.0
    w_log: List[List[float]] = []
    cover_missing = 0

    for i in range(1, n):
        d = common_dates[i]
        if all(d not in asset_rm[HAVEN_ASSETS[k]] for k in range(na)):
            cover_missing += 1
        if i in trig:
            tot = sum(bucket)
            cur_w = [b / tot for b in bucket] if tot > 0 else [0.0] * na
            tgt = invvol_target(i)
            turn = sum(abs(tgt[k] - cur_w[k]) for k in range(na))
            if turn > 1e-9:
                cost = (cost_bps / 10000.0) * turn
                n_rebal += 1
                turnover_total += turn
                tot_after = tot * (1.0 - cost)
                bucket = [tgt[k] * tot_after for k in range(na)]
                w_log.append(list(tgt))
        prev_eq = sum(bucket)
        for k in range(na):
            bucket[k] *= (1.0 + arr[k][i])
        new_eq = sum(bucket)
        equity.append(new_eq)
        if prev_eq != 0:
            ret_map[d] = new_eq / prev_eq - 1.0

    avg_w = [0.0] * na
    if w_log:
        for k in range(na):
            avg_w[k] = sum(wl[k] for wl in w_log) / len(w_log)

    return {
        "dates": common_dates, "equity": equity, "ret_map": ret_map,
        "n_rebal": n_rebal, "turnover_total": turnover_total, "avg_w": avg_w,
        "cadence": cadence, "cover_missing": cover_missing,
        "asset_rm_keys": {s: len(asset_rm[s]) for s in HAVEN_ASSETS},
    }


def blend_cadence(dates: List[str], sleeves: List[List[float]],
                  target_weight_fn: Callable[[int], List[float]],
                  trigset: set, cost_bps: float = COST_BPS) -> Dict:
    """N-sleeve blend at a TOP-LEVEL calendar cadence (trigset). Mirrors
    ab.blend_portfolio drift/cost/stats EXACTLY; only the trigger set changes."""
    n = len(dates)
    ns = len(sleeves)
    w0 = target_weight_fn(0)
    bucket = [w0[k] for k in range(ns)]
    equity = [1.0]
    eq_dates = [dates[0]]
    n_rebal = 0
    turnover_total = 0.0
    w_log: List[List[float]] = []

    for i in range(1, n):
        d = dates[i]
        if i in trigset:
            tot = sum(bucket)
            cur_w = [b / tot for b in bucket] if tot > 0 else [0.0] * ns
            tgt = target_weight_fn(i)
            turn = sum(abs(tgt[k] - cur_w[k]) for k in range(ns))
            if turn > 1e-9:
                cost = (cost_bps / 10000.0) * turn
                n_rebal += 1
                turnover_total += turn
                tot_after = tot * (1.0 - cost)
                bucket = [tgt[k] * tot_after for k in range(ns)]
                w_log.append(list(tgt))
        for k in range(ns):
            bucket[k] *= (1.0 + sleeves[k][i])
        equity.append(sum(bucket))
        eq_dates.append(d)

    in_market = [True] * (len(eq_dates) - 1)
    st = _stats_from_equity(eq_dates, equity, in_market, n_rebal)
    avg_w = [0.0] * ns
    if w_log:
        for k in range(ns):
            avg_w[k] = sum(wl[k] for wl in w_log) / len(w_log)
    return {
        "dates": eq_dates, "equity": equity, "stats": dict(st.__dict__),
        "n_rebal": n_rebal, "turnover_total": turnover_total, "avg_w": avg_w,
    }


def summarize(blend: Dict, label: str, avg_haven_wt: Optional[float] = None) -> Dict:
    ds = blend["dates"]
    eq = blend["equity"]
    full = blend["stats"]
    oos = slice_stats(ds, eq, "2019-01-01", "2099-12-31")
    is_ = slice_stats(ds, eq, "2000-01-01", OOS_SPLIT)
    dd_2022 = maxdd_in_window(ds, eq, "2022-01-01", "2022-12-31")
    ret_2022 = slice_stats(ds, eq, "2022-01-01", "2022-12-31").get("total_return_pct")
    return {
        "label": label,
        "window": {"start": ds[0], "end": ds[-1], "n_days": len(ds)},
        "n_rebal": blend["n_rebal"],
        "avg_haven_wt": avg_haven_wt,
        "full": {
            "total_return_pct": full["total_return_pct"],
            "cagr_pct": full["cagr_pct"],
            "sharpe": full["sharpe"],
            "fp_cont_sharpe": fp_cont_sharpe(eq),
            "maxdd_pct": full["max_drawdown_pct"],
            "vol_pct": full["ann_vol_pct"],
        },
        "oos_2019_today": {"sharpe": oos.get("sharpe"), "cagr_pct": oos.get("cagr_pct"),
                           "maxdd_pct": oos.get("max_drawdown_pct"),
                           "total_return_pct": oos.get("total_return_pct")},
        "is_2010_2018": {"sharpe": is_.get("sharpe"), "maxdd_pct": is_.get("max_drawdown_pct")},
        "dd_2022_pct": dd_2022,
        "ret_2022_pct": ret_2022,
    }


def effn_from_corr(C: List[List[float]]) -> float:
    """Participation ratio of a correlation matrix = (trace)^2 / sum_ij C_ij^2.
    trace = N for a correlation matrix. Reproduces frontier 1.495 / 2.323."""
    N = len(C)
    tr = sum(C[i][i] for i in range(N))
    ss = sum(C[i][j] ** 2 for i in range(N) for j in range(N))
    if ss <= 0:
        return float("nan")
    return tr * tr / ss


def corr_matrix(streams: List[List[float]]) -> List[List[float]]:
    N = len(streams)
    C = [[1.0] * N for _ in range(N)]
    for i in range(N):
        for j in range(i + 1, N):
            c = pearson(streams[i], streams[j])
            c = c if c is not None else 0.0
            C[i][j] = c
            C[j][i] = c
    return C


def main() -> None:
    out: Dict = {}
    out["meta"] = {
        "purpose": "Refresh haven eff-N/Sharpe give-up vs the NEW QUARTERLY 2-sleeve book.",
        "haven_spec": "GLD/TLT/DBC/UUP inverse-vol parity, 63d past-only vol, 2bps, intra-period drift.",
        "vol_lookback_days": VOL_LOOKBACK, "cost_bps": COST_BPS, "oos_split": OOS_SPLIT,
        "effn_formula": "participation ratio = (trace)^2 / sum_ij C_ij^2 (= N^2/sum C_ij^2)",
    }

    print(">>> [0] building core 2 sleeves via build_sleeves() ...", flush=True)
    S = ab.build_sleeves()
    dates: List[str] = S["common_dates"]
    tqqq_r: List[float] = S["tqqq_r"]
    rot_r: List[float] = S["rot_r"]
    spx_r: List[float] = S["spx_r"]
    sleeves2 = [tqqq_r, rot_r]
    out["meta"]["core_common_window"] = [dates[0], dates[-1], len(dates)]

    moset_full = month_open_set(dates)
    qset_full = quarter_open_set(dates)

    def invvol2_target(idx: int) -> List[float]:
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - VOL_LOOKBACK)
        v0 = annualized_vol_pop(tqqq_r[lo:idx])
        v1 = annualized_vol_pop(rot_r[lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv0, iv1 = 1.0 / v0, 1.0 / v1
        s = iv0 + iv1
        return [iv0 / s, iv1 / s]

    print(">>> [1] SANITY: 2-sleeve monthly + quarterly on full core window ...", flush=True)
    monthly_ref = ab.blend_portfolio(dates, sleeves2, lambda i: invvol2_target(i),
                                     blend_cost_bps=COST_BPS, vol_lookback_days=VOL_LOOKBACK)
    monthly_cad = blend_cadence(dates, sleeves2, invvol2_target, moset_full)
    quarterly_2sl = blend_cadence(dates, sleeves2, invvol2_target, qset_full)

    repro_m = (abs(monthly_ref["stats"]["total_return_pct"]
                   - monthly_cad["stats"]["total_return_pct"]) < 1e-6
               and abs(monthly_ref["stats"]["sharpe"]
                       - monthly_cad["stats"]["sharpe"]) < 1e-9)
    out["sanity_control"] = {
        "monthly_2sleeve_validated_engine": summarize(
            {"dates": monthly_ref["dates"], "equity": monthly_ref["equity"],
             "stats": monthly_ref["stats"], "n_rebal": monthly_ref["n_rebal"],
             "turnover_total": 0.0, "avg_w": [0, 0]},
            "monthly 2sl (ab.blend_portfolio)"),
        "monthly_2sleeve_cadence_trigger": summarize(monthly_cad, "monthly 2sl (cadence trigger)"),
        "monthly_two_paths_match": repro_m,
        "quarterly_2sleeve": summarize(quarterly_2sl, "quarterly 2sl (THE NEW BASELINE)"),
        "quarterly_avg_w_tqqq": quarterly_2sl["avg_w"][0] if quarterly_2sl["avg_w"] else None,
        "target_quarterly_totret_approx": 1068.0,
        "target_quarterly_sharpe_approx": 1.018,
        "target_quarterly_maxdd_approx": -24.9,
    }
    q = out["sanity_control"]["quarterly_2sleeve"]["full"]
    print("    monthly 2sl two-paths match: %s" % repro_m)
    print("    QUARTERLY 2sl: raw %.1f%% Sharpe %.4f (fp %.4f) maxDD %.2f%% | target ~1068%%/1.018/-24.9%%" % (
        q["total_return_pct"], q["sharpe"], q["fp_cont_sharpe"], q["maxdd_pct"]))
    repro_q = (abs(q["total_return_pct"] - 1068.0) < 12.0
               and abs(q["sharpe"] - 1.018) < 0.01)
    out["sanity_control"]["quarterly_reproduces_target"] = repro_q
    print("    quarterly reproduces target (raw within 12pp AND Sharpe within 0.01): %s" % repro_q)

    print(">>> building haven sleeve monthly + quarterly (GLD/TLT/DBC/UUP inv-vol) ...", flush=True)
    haven_m = build_haven_sleeve(dates, cadence="monthly")
    haven_q = build_haven_sleeve(dates, cadence="quarterly")
    out["meta"]["haven_asset_coverage"] = haven_m["asset_rm_keys"]
    out["meta"]["haven_cover_missing_on_common"] = haven_m["cover_missing"]
    print("    haven monthly avg_w (GLD/TLT/DBC/UUP): %s ; cover_missing=%d" % (
        [round(x, 3) for x in haven_m["avg_w"]], haven_m["cover_missing"]))

    # aligned (traded) window: dates where ALL of {tqqq,rot,spx,haven} cover
    tqqq_map = {dates[i]: tqqq_r[i] for i in range(len(dates))}
    rot_map = {dates[i]: rot_r[i] for i in range(len(dates))}
    spx_map = {dates[i]: spx_r[i] for i in range(len(dates))}
    aligned = [d for d in dates if d in haven_m["ret_map"] and d in haven_q["ret_map"]
               and d in tqqq_map and d in rot_map and d in spx_map]
    aligned.sort()
    dropped = [d for d in dates if d not in set(aligned)]
    out["meta"]["aligned_window"] = [aligned[0], aligned[-1], len(aligned)]
    out["meta"]["dropped_core_dates"] = dropped[-5:]
    print("    aligned (traded) window: %s -> %s (%d days); dropped %d core date(s): %s" % (
        aligned[0], aligned[-1], len(aligned), len(dropped), dropped[-3:]))

    # aligned sleeve vectors (index i <-> aligned[i]); index 0 return discarded by loop
    a_tqqq = [tqqq_map[d] for d in aligned]
    a_rot = [rot_map[d] for d in aligned]
    a_spx = [spx_map[d] for d in aligned]
    a_hav_m = [haven_m["ret_map"][d] for d in aligned]
    a_hav_q = [haven_q["ret_map"][d] for d in aligned]

    moset_al = month_open_set(aligned)
    qset_al = quarter_open_set(aligned)

    # SPX on the aligned traded path (benchmark)
    spx_eq = [1.0]
    for i in range(1, len(aligned)):
        spx_eq.append(spx_eq[-1] * (1.0 + a_spx[i]))
    spx_full = _stats_from_equity(aligned, spx_eq)
    spx_raw = spx_full.total_return_pct
    out["spx_aligned"] = {"total_return_pct": spx_raw, "sharpe": spx_full.sharpe,
                          "fp_cont_sharpe": fp_cont_sharpe(spx_eq),
                          "maxdd_pct": spx_full.max_drawdown_pct,
                          "dd_2022_pct": maxdd_in_window(aligned, spx_eq, "2022-01-01", "2022-12-31")}
    print("    SPX aligned: raw %.1f%% Sharpe %.4f maxDD %.2f%% 2022DD %.2f%%" % (
        spx_raw, spx_full.sharpe, spx_full.max_drawdown_pct,
        out["spx_aligned"]["dd_2022_pct"]))

    # ---- standalone haven economics on the aligned window (insurance check) ----
    hav_m_eq = [1.0]
    for i in range(1, len(aligned)):
        hav_m_eq.append(hav_m_eq[-1] * (1.0 + a_hav_m[i]))
    hav_m_full = _stats_from_equity(aligned, hav_m_eq)
    hav_q_eq = [1.0]
    for i in range(1, len(aligned)):
        hav_q_eq.append(hav_q_eq[-1] * (1.0 + a_hav_q[i]))
    hav_q_full = _stats_from_equity(aligned, hav_q_eq)
    out["haven_standalone_aligned"] = {
        "monthly_cadence": {"total_return_pct": hav_m_full.total_return_pct,
                            "cagr_pct": hav_m_full.cagr_pct, "sharpe": hav_m_full.sharpe,
                            "fp_cont_sharpe": fp_cont_sharpe(hav_m_eq),
                            "maxdd_pct": hav_m_full.max_drawdown_pct,
                            "ann_vol_pct": hav_m_full.ann_vol_pct,
                            "oos_sharpe": slice_stats(aligned, hav_m_eq, "2019-01-01", "2099-12-31").get("sharpe"),
                            "avg_w_GLD_TLT_DBC_UUP": [round(x, 4) for x in haven_m["avg_w"]],
                            "n_rebal": haven_m["n_rebal"]},
        "quarterly_cadence": {"total_return_pct": hav_q_full.total_return_pct,
                              "cagr_pct": hav_q_full.cagr_pct, "sharpe": hav_q_full.sharpe,
                              "fp_cont_sharpe": fp_cont_sharpe(hav_q_eq),
                              "maxdd_pct": hav_q_full.max_drawdown_pct,
                              "ann_vol_pct": hav_q_full.ann_vol_pct,
                              "oos_sharpe": slice_stats(aligned, hav_q_eq, "2019-01-01", "2099-12-31").get("sharpe"),
                              "avg_w_GLD_TLT_DBC_UUP": [round(x, 4) for x in haven_q["avg_w"]],
                              "n_rebal": haven_q["n_rebal"]},
    }
    print("    haven standalone (aligned) monthly: raw %.1f%% Sharpe %.3f maxDD %.2f%% vol %.1f%% | quarterly: raw %.1f%% Sharpe %.3f maxDD %.2f%%" % (
        hav_m_full.total_return_pct, hav_m_full.sharpe, hav_m_full.max_drawdown_pct,
        hav_m_full.ann_vol_pct, hav_q_full.total_return_pct, hav_q_full.sharpe,
        hav_q_full.max_drawdown_pct))

    # leg full-window ann vols (aligned, index>=1 = real returns)
    leg_vol_tqqq = annualized_vol_pop(a_tqqq[1:])
    leg_vol_rot = annualized_vol_pop(a_rot[1:])
    leg_vol_hav_m = annualized_vol_pop(a_hav_m[1:])
    out["leg_full_vols_aligned"] = {"tqqq": leg_vol_tqqq, "rot": leg_vol_rot,
                                    "haven_monthly": leg_vol_hav_m}

    # ---- 3. eff-N refresh (2-leg -> 3-leg) on the aligned window ----
    # Use the haven cadence chosen as recommended later; compute eff-N with the
    # MONTHLY haven first (matches the prior frontier's convention) AND report
    # the quarterly-haven eff-N too. Daily-return correlation matrix.
    print(">>> [3] eff-N refresh (participation ratio) ...", flush=True)
    s_tqqq = a_tqqq[1:]
    s_rot = a_rot[1:]
    s_hav_m = a_hav_m[1:]
    s_hav_q = a_hav_q[1:]
    C2 = corr_matrix([s_tqqq, s_rot])
    C3_m = corr_matrix([s_tqqq, s_rot, s_hav_m])
    C3_q = corr_matrix([s_tqqq, s_rot, s_hav_q])
    effn_2 = effn_from_corr(C2)
    effn_3_m = effn_from_corr(C3_m)
    effn_3_q = effn_from_corr(C3_q)
    out["eff_n"] = {
        "formula": "(trace)^2 / sum_ij C_ij^2  (participation ratio of daily-return corr matrix)",
        "two_leg": effn_2,
        "three_leg_haven_monthly": effn_3_m,
        "three_leg_haven_quarterly": effn_3_q,
        "corr_2leg": [[round(x, 4) for x in r] for r in C2],
        "corr_3leg_haven_monthly": [[round(x, 4) for x in r] for r in C3_m],
        "corr_haven_to_tqqqleg": round(C3_m[0][2], 4),
        "corr_haven_to_rotleg": round(C3_m[1][2], 4),
        "prior_two_leg": 1.495, "prior_three_leg": 2.324,
    }
    print("    eff-N: 2-leg %.4f -> 3-leg(haven monthly) %.4f / 3-leg(haven quarterly) %.4f  [prior 1.495 -> 2.324]" % (
        effn_2, effn_3_m, effn_3_q))

    # ---- 2. FRONTIER refresh: 3-sleeve at fixed haven {0,5,10,15,20}%, TOP-LEVEL
    # QUARTERLY rebalance (the live book is now quarterly). Rest split TQQQ/ROT by
    # inv-vol. Run with BOTH haven cadences so we can pick the better one.
    print(">>> [2] frontier refresh: 3-sleeve fixed-haven {0,5,10,15,20}% @ TOP-LEVEL QUARTERLY ...", flush=True)

    def make_3sleeve_target(haven_wt: float):
        # sleeves order: [tqqq, rot, haven]; haven fixed at haven_wt, rest by inv-vol
        def fn(idx: int) -> List[float]:
            base = invvol2_target(idx)  # [w_tqqq, w_rot] over the 2 core legs
            rest = 1.0 - haven_wt
            return [base[0] * rest, base[1] * rest, haven_wt]
        return fn

    haven_weights = [0.0, 0.05, 0.10, 0.15, 0.20]
    out["frontier_quarterly"] = {"haven_monthly_sleeve": {}, "haven_quarterly_sleeve": {}}
    for hav_stream, hav_label, store_key in (
            (a_hav_m, "haven-sleeve MONTHLY", "haven_monthly_sleeve"),
            (a_hav_q, "haven-sleeve QUARTERLY", "haven_quarterly_sleeve")):
        sleeves3 = [a_tqqq, a_rot, hav_stream]
        for hw in haven_weights:
            tgt = make_3sleeve_target(hw)
            b = blend_cadence(aligned, sleeves3, tgt, qset_al, cost_bps=COST_BPS)
            summ = summarize(b, "%s haven %d%% (top-level quarterly)" % (hav_label, int(hw * 100)),
                             avg_haven_wt=hw)
            out["frontier_quarterly"][store_key]["haven_%02d" % int(hw * 100)] = summ
            f = summ["full"]
            print("   [%s] haven %2d%%: raw %.1f%% Sharpe %.4f (fp %.4f) OOS %.4f maxDD %.2f%% 2022DD %.2f%% | beats SPX raw: %s" % (
                store_key, int(hw * 100), f["total_return_pct"], f["sharpe"],
                f["fp_cont_sharpe"], summ["oos_2019_today"]["sharpe"], f["maxdd_pct"],
                summ["dd_2022_pct"], f["total_return_pct"] > spx_raw))

    # ---- monotonicity + give-up math vs the aligned quarterly baseline (haven 0%)
    fm = out["frontier_quarterly"]["haven_monthly_sleeve"]
    base0 = fm["haven_00"]["full"]["total_return_pct"]
    h10 = fm["haven_10"]["full"]["total_return_pct"]
    sweep_raw = [fm["haven_%02d" % w]["full"]["total_return_pct"] for w in (0, 5, 10, 15, 20)]
    sweep_sh = [fm["haven_%02d" % w]["full"]["sharpe"] for w in (0, 5, 10, 15, 20)]
    monotonic_raw_down = all(sweep_raw[i] > sweep_raw[i + 1] for i in range(len(sweep_raw) - 1))
    monotonic_sh_up = all(sweep_sh[i] <= sweep_sh[i + 1] + 1e-9 for i in range(len(sweep_sh) - 1))
    interior_sharpe_opt = (not monotonic_sh_up) and (max(range(len(sweep_sh)), key=lambda k: sweep_sh[k]) not in (0, len(sweep_sh) - 1))
    out["monotonicity"] = {
        "sweep_raw_pct": sweep_raw, "sweep_full_sharpe": sweep_sh,
        "raw_monotonic_decreasing_in_haven": monotonic_raw_down,
        "sharpe_monotonic_increasing_in_haven": monotonic_sh_up,
        "interior_sharpe_optimum": interior_sharpe_opt,
        "per_5pp_raw_giveup_avg_pp": (sweep_raw[0] - sweep_raw[-1]) / 4.0,
        "per_5pp_sharpe_gain_avg": (sweep_sh[-1] - sweep_sh[0]) / 4.0,
    }
    out["giveup_vs_quarterly_baseline"] = {
        "aligned_quarterly_baseline_raw_pct": base0,
        "full_core_quarterly_baseline_raw_pct": q["total_return_pct"],
        "haven10_raw_pct": h10,
        "haven10_giveup_vs_aligned_baseline_pp": base0 - h10,
        "haven10_giveup_vs_fullcore_baseline_pp": q["total_return_pct"] - h10,
        "haven10_cushion_over_spx_pp": h10 - spx_raw,
        "spx_raw_pct": spx_raw,
        "prior_giveup_vs_monthly_pp": 161.0,
    }
    print("")
    print(">>> GIVE-UP: aligned quarterly baseline (haven 0%%) raw %.1f%% ; haven-10 raw %.1f%% -> giveup %.1fpp ; SPX raw %.1f%% -> cushion %.1fpp" % (
        base0, h10, base0 - h10, spx_raw, h10 - spx_raw))
    print("    sweep raw: %s" % [round(x, 1) for x in sweep_raw])
    print("    sweep Sharpe: %s | raw monotonic-down: %s | Sharpe monotonic-up: %s | interior Sharpe optimum: %s" % (
        [round(x, 4) for x in sweep_sh], monotonic_raw_down, monotonic_sh_up, interior_sharpe_opt))

    # ---- haven cadence pick (monthly vs quarterly haven sleeve) at the 10% op point
    hm10 = out["frontier_quarterly"]["haven_monthly_sleeve"]["haven_10"]
    hq10 = out["frontier_quarterly"]["haven_quarterly_sleeve"]["haven_10"]
    haven_cadence_better = ("quarterly" if (hq10["full"]["total_return_pct"]
                                            > hm10["full"]["total_return_pct"]) else "monthly")
    out["haven_cadence_pick"] = {
        "at_haven_10pct": {
            "haven_monthly": {"raw": hm10["full"]["total_return_pct"],
                              "sharpe": hm10["full"]["sharpe"],
                              "oos_sharpe": hm10["oos_2019_today"]["sharpe"],
                              "maxdd": hm10["full"]["maxdd_pct"],
                              "dd_2022": hm10["dd_2022_pct"]},
            "haven_quarterly": {"raw": hq10["full"]["total_return_pct"],
                                "sharpe": hq10["full"]["sharpe"],
                                "oos_sharpe": hq10["oos_2019_today"]["sharpe"],
                                "maxdd": hq10["full"]["maxdd_pct"],
                                "dd_2022": hq10["dd_2022_pct"]},
        },
        "haven_standalone_monthly_vs_quarterly": out["haven_standalone_aligned"],
        "better_haven_cadence_by_raw": haven_cadence_better,
    }
    print("    HAVEN CADENCE @10%%: monthly raw %.1f%% Sh %.4f vs quarterly raw %.1f%% Sh %.4f -> better(raw): %s" % (
        hm10["full"]["total_return_pct"], hm10["full"]["sharpe"],
        hq10["full"]["total_return_pct"], hq10["full"]["sharpe"], haven_cadence_better))

    # ---- no-lookahead canary ----
    out["canary"] = {
        "past_only_trailing_vol": True,
        "lookahead_free": True,
        "forward_pnl_d_to_d1": True,
        "oos_split": OOS_SPLIT,
        "benchmark_same_traded_path": True,
        "note": ("inv-vol target at index i uses sleeves[k][i-63:i] (strictly < i); "
                 "haven asset weights at index i use arr[k][i-63:i] (strictly < i); "
                 "buckets earn return ending on i AFTER any rebalance at i -> no day "
                 "feeds its own rebalance; monthly 2sl two-paths match to machine "
                 "precision (harness-faithfulness proof of no introduced leak)."),
        "harness_faithful_monthly_match": repro_m,
        "harness_faithful_quarterly_repro": repro_q,
    }

    os.makedirs("reports", exist_ok=True)
    with open("reports/_haven_effn_refresh_result.json", "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("wrote reports/_haven_effn_refresh_result.json")


if __name__ == "__main__":
    main()
