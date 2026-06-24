#!/usr/bin/env python3
"""HAVEN SLEEVE PROTOTYPE — standalone GLD/TLT defensive leg.

Assignment (main, 2026-06-23 10:30 mgmt-check): the weekly tournament report
flagged the book as eff-N≈2.2 with ~65% NASDAQ-tech beta concentration — every
live sleeve is long-equity-biased and all went red together on a correlated
risk-off day. The proposed structural fix: a genuinely-uncorrelated GLD/TLT
"haven" leg.

This is DISTINCT from the closed 3rd-sleeve study (2026-06-23), which tested
TREND/CTA/CREDIT sleeves via inverse-vol and found 2-sleeve wins on raw return.
GLD/TLT today only appear INSIDE sector-rotation as 2 of 4 momentum-ranked
assets (often NOT selected). A clean standalone GLD+TLT haven sleeve, and the
eff-N / correlation-structure question, has never been evaluated directly.

HONEST MEASUREMENT (non-negotiable):
  - daily adjusted-close returns (split+div adjusted; leveraged-ETF rule N/A here
    but GLD/TLT pay distributions so adjclose is the right series),
  - 2bps one-way rebalance cost on inter-asset turnover (same as the validated blend),
  - OOS split at 2018-12-31 (same constant the blend uses),
  - SPX (^GSPC) buy-&-hold on the SAME traded path as the benchmark,
  - no lookahead: weights set at month-open from PAST-only trailing vol.

Reuses the validated engine verbatim where possible:
  _allocator_blend_tests.build_sleeves()  -> TQQQ vol-target + sector-rotation legs
  _allocator_blend_tests.blend_portfolio()-> monthly-rebalanced N-sleeve blend
  _allocator_blend_tests.report_blend()   -> IS/OOS/full stat block
  _allocator_blend_tests.stats_from_returns / correlation_report / pearson

Outputs JSON to reports/_haven_sleeve_result.json. No protected/live files touched.
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from typing import Dict, List, Optional, Tuple

# Reuse the validated allocator engine wholesale.
import _allocator_blend_tests as AB
from _allocator_blend_tests import (
    build_sleeves, blend_portfolio, report_blend,
    stats_from_returns, pearson, equity_to_daily_returns,
    annualized_vol, slice_equity_stats, OOS_SPLIT,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    _stats_from_equity,
)

CACHE = "data_cache/yahoo/%s_parsed.json"
TRADING_DAYS = 252.0


# --------------------------------------------------------------------------- #
# Load an adjclose daily-return series for a cached Yahoo symbol.
# --------------------------------------------------------------------------- #
def load_adjclose_returns(sym: str) -> Dict[str, float]:
    rows = json.load(open(CACHE % sym))
    rows = [r for r in rows if r.get("adjclose") not in (None, 0)]
    rows.sort(key=lambda r: r["date"])
    out: Dict[str, float] = {}
    prev = None
    for r in rows:
        px = float(r["adjclose"])
        if prev is not None and prev > 0:
            out[r["date"]] = px / prev - 1.0
        prev = px
    return out


# --------------------------------------------------------------------------- #
# Build the standalone HAVEN sleeve (GLD + TLT) as a daily-return series on a
# given common calendar, under a chosen weighting scheme. Monthly rebalanced,
# 2bps one-way cost on inter-asset turnover, intramonth drift (same honest
# behavior as blend_portfolio's sleeve handling).
#
# scheme:
#   "5050"     fixed 50/50
#   "invvol"   inverse-vol parity over a trailing lookback (default 63d)
#   "6040"     fixed 60% TLT / 40% GLD  (classic bond-heavy haven tilt)
# Returns: (dates, haven_daily_returns, meta)
# --------------------------------------------------------------------------- #
def build_haven_sleeve(common: List[str],
                       gld_ret: Dict[str, float],
                       tlt_ret: Dict[str, float],
                       scheme: str = "invvol",
                       vol_lookback: int = 63,
                       cost_bps: float = 2.0) -> Tuple[List[str], List[float], Dict]:
    g = [gld_ret[d] for d in common]
    t = [tlt_ret[d] for d in common]
    n = len(common)

    # month-open indices
    month_open = []
    seen = set()
    for i, d in enumerate(common):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym); month_open.append(i)
    month_open_set = set(month_open)

    def target_w(i: int) -> Tuple[float, float]:
        """target (w_gld, w_tlt) from PAST-only data through i-1."""
        if scheme == "5050":
            return (0.5, 0.5)
        if scheme == "6040":
            return (0.4, 0.6)
        # inverse-vol parity over trailing lookback (past only)
        lo = max(0, i - vol_lookback)
        gw = g[lo:i]; tw = t[lo:i]
        if len(gw) < 10 or len(tw) < 10:
            return (0.5, 0.5)
        vg = annualized_vol(gw); vt = annualized_vol(tw)
        if vg <= 0 or vt <= 0:
            return (0.5, 0.5)
        ig, it = 1.0 / vg, 1.0 / vt
        s = ig + it
        return (ig / s, it / s)

    # walk the blend (2 assets), drift intramonth, snap to target monthly.
    equity = [1.0]
    eq_dates = [common[0]]
    wg, wt = target_w(0)
    bg, bt = wg, wt  # bucket values, sum to 1
    n_rebal = 0
    turn_total = 0.0
    wlog: List[Dict] = []
    for i in range(1, n):
        d = common[i]
        if i in month_open_set:
            tot = bg + bt
            cwg = bg / tot if tot > 0 else 0.0
            cwt = bt / tot if tot > 0 else 0.0
            tg, tt = target_w(i)
            turn = abs(tg - cwg) + abs(tt - cwt)
            cost = (cost_bps / 10000.0) * turn
            if turn > 1e-9:
                n_rebal += 1; turn_total += turn
            tot_after = tot * (1.0 - cost)
            bg, bt = tg * tot_after, tt * tot_after
            wlog.append({"date": d, "w_gld": tg, "w_tlt": tt})
        bg *= (1.0 + g[i])
        bt *= (1.0 + t[i])
        equity.append(bg + bt)
        eq_dates.append(d)

    # convert equity -> daily returns on the common calendar (len n, first = 0)
    hav_ret = [0.0]
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        hav_ret.append(equity[i] / prev - 1.0 if prev > 0 else 0.0)

    meta = {
        "scheme": scheme, "vol_lookback": vol_lookback,
        "n_rebal": n_rebal,
        "avg_turnover_per_rebal": (turn_total / n_rebal) if n_rebal else 0.0,
        "weight_log_tail": wlog[-3:],
    }
    return eq_dates, hav_ret, meta


# --------------------------------------------------------------------------- #
# Effective number of bets (eff-N) from a correlation matrix of sleeve returns.
# Two standard measures:
#   - eff_N_corr = (sum of |corr|)^-1 style is fragile; use the participation-ratio
#     of the eigenvalues of the correlation matrix:  (Σλ)^2 / Σλ^2  = N^2 / Σλ^2
#     (since Σλ = N for a corr matrix). This is the classic "effective number of
#     independent bets" (participation ratio). Ranges 1..N.
# --------------------------------------------------------------------------- #
def corr_matrix(series: List[List[float]]) -> List[List[float]]:
    k = len(series)
    M = [[1.0] * k for _ in range(k)]
    for a in range(k):
        for b in range(a + 1, k):
            c = pearson(series[a], series[b])
            c = 0.0 if c is None else c
            M[a][b] = M[b][a] = c
    return M


def _eigs_symmetric(M: List[List[float]]) -> List[float]:
    """Eigenvalues of a small symmetric matrix via Jacobi rotation (no numpy)."""
    import copy
    n = len(M)
    A = [row[:] for row in M]
    for _ in range(100):
        # find largest off-diagonal
        p, q, mx = 0, 1, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                if abs(A[i][j]) > mx:
                    mx = abs(A[i][j]); p, q = i, j
        if mx < 1e-12:
            break
        app, aqq, apq = A[p][p], A[q][q], A[p][q]
        if abs(app - aqq) < 1e-18:
            theta = math.pi / 4
        else:
            theta = 0.5 * math.atan2(2 * apq, app - aqq)
        c, s = math.cos(theta), math.sin(theta)
        for i in range(n):
            aip, aiq = A[i][p], A[i][q]
            A[i][p] = c * aip + s * aiq
            A[i][q] = -s * aip + c * aiq
        for i in range(n):
            api, aqi = A[p][i], A[q][i]
            A[p][i] = c * api + s * aqi
            A[q][i] = -s * api + c * aqi
    return [A[i][i] for i in range(n)]


def effective_n(M: List[List[float]]) -> float:
    eigs = [max(0.0, e) for e in _eigs_symmetric(M)]
    s1 = sum(eigs)
    s2 = sum(e * e for e in eigs)
    if s2 <= 0:
        return float(len(M))
    return (s1 * s1) / s2


# --------------------------------------------------------------------------- #
# Slice a return series to [start, end) and compute stats.
# --------------------------------------------------------------------------- #
def slice_ret_stats(dates: List[str], rets: List[float], start: str, end: str) -> Dict:
    sub_d, sub_r = [], []
    for d, r in zip(dates, rets):
        if start <= d < end:
            sub_d.append(d); sub_r.append(r)
    if len(sub_r) < 20:
        return {"n": len(sub_r)}
    st = stats_from_returns(sub_d, sub_r)["stats"]
    return {"n": len(sub_r), "sharpe": st["sharpe"], "cagr_pct": st["cagr_pct"],
            "maxdd_pct": st["max_drawdown_pct"], "total_return_pct": st["total_return_pct"],
            "ann_vol_pct": st["ann_vol_pct"]}


# Named risk-off / regime windows (the killer battery for a HAVEN: it must earn
# its keep when equities are falling). Dates are [start, end).
HAVEN_WINDOWS = [
    ("2020-Q1 covid crash",  "2020-02-01", "2020-04-01"),
    ("2022 bear (full yr)",  "2022-01-01", "2023-01-01"),
    ("2022-H1 bear",         "2022-01-01", "2022-07-01"),
    ("2025-Q1 tariff bear",  "2025-02-01", "2025-05-01"),
    ("2011 debt-ceiling",    "2011-07-01", "2011-10-01"),
    ("2018-Q4 selloff",      "2018-10-01", "2019-01-01"),
    ("2013 taper-tantrum",   "2013-05-01", "2013-09-01"),  # bonds-AND-gold-hit stress
    ("2008 GFC",             "2008-09-01", "2009-04-01"),
]


def main():
    print(">>> Building validated 2-sleeve legs (TQQQ vol-target + sector-rotation) ...", flush=True)
    S = build_sleeves()
    common2 = S["common_dates"]
    tqqq_r = S["tqqq_r"]; rot_r = S["rot_r"]; spx_r = S["spx_r"]

    print(">>> Loading GLD/TLT adjclose returns ...", flush=True)
    gld = load_adjclose_returns("GLD")
    tlt = load_adjclose_returns("TLT")
    spy = load_adjclose_returns("SPY")  # for standalone-haven-vs-SPX on the haven's OWN deep window

    # ----- (1) STANDALONE HAVEN on its OWN deep window (GLD/TLT both exist) -----
    deep_common = sorted(set(gld) & set(tlt) & set(spy))
    print("    Haven deep window: %s -> %s (%d days)" % (deep_common[0], deep_common[-1], len(deep_common)))
    spy_deep = [spy[d] for d in deep_common]

    standalone = {}
    for scheme in ("5050", "6040", "invvol"):
        hd, hr, hmeta = build_haven_sleeve(deep_common, gld, tlt, scheme=scheme)
        full = stats_from_returns(hd, hr)["stats"]
        oos = slice_ret_stats(hd, hr, "2019-01-01", "2099-12-31")
        is_ = slice_ret_stats(hd, hr, "2000-01-01", "2018-12-31")
        spx_full = stats_from_returns(deep_common, spy_deep)["stats"]
        spx_oos = slice_ret_stats(deep_common, spy_deep, "2019-01-01", "2099-12-31")
        standalone[scheme] = {
            "meta": hmeta,
            "full": {"sharpe": full["sharpe"], "cagr_pct": full["cagr_pct"],
                     "maxdd_pct": full["max_drawdown_pct"], "ann_vol_pct": full["ann_vol_pct"],
                     "total_return_pct": full["total_return_pct"]},
            "is_pre2019": is_, "oos_2019plus": oos,
            "spx_full": {"sharpe": spx_full["sharpe"], "cagr_pct": spx_full["cagr_pct"],
                         "maxdd_pct": spx_full["max_drawdown_pct"],
                         "total_return_pct": spx_full["total_return_pct"]},
            "spx_oos": spx_oos,
            "beats_spx_raw_full": full["total_return_pct"] > spx_full["total_return_pct"],
        }
        print("    [%s] full Sharpe %.3f CAGR %.1f%% maxDD %.1f%% rawRet %.0f%% | SPX raw %.0f%%  beats=%s" % (
            scheme, full["sharpe"], full["cagr_pct"], full["max_drawdown_pct"],
            full["total_return_pct"], spx_full["total_return_pct"],
            standalone[scheme]["beats_spx_raw_full"]))

    # ----- (2) KILLER BATTERY: haven behavior in named risk-off windows -----
    # Use the inv-vol haven as the canonical sleeve for the battery; also report 50/50.
    battery = {}
    for label, st, en in HAVEN_WINDOWS:
        row = {}
        for scheme in ("5050", "invvol"):
            hd, hr, _ = build_haven_sleeve(deep_common, gld, tlt, scheme=scheme)
            row["haven_" + scheme] = slice_ret_stats(hd, hr, st, en)
        row["spy"] = slice_ret_stats(deep_common, spy_deep, st, en)
        battery[label] = row
        h = row.get("haven_invvol", {})
        s = row.get("spy", {})
        if "total_return_pct" in h and "total_return_pct" in s:
            print("    [%-22s] haven %+6.1f%%  vs SPY %+6.1f%%  (haven maxDD %+.1f%%)" % (
                label, h["total_return_pct"], s["total_return_pct"], h.get("maxdd_pct", 0.0)))

    # ----- (3) CORRELATION GATE + eff-N: does a haven leg de-concentrate the book? -----
    # Build the haven sleeve on the 2-SLEEVE common window so all four align.
    hav_d2, hav_r2, hav_meta2 = build_haven_sleeve(common2, gld, tlt, scheme="invvol")
    # align: common2 IS the calendar for tqqq_r/rot_r/spx_r; hav_r2 is on common2 too
    assert hav_d2 == common2, "haven calendar must equal 2-sleeve common window"

    # 2-sleeve blend return series (inverse-vol 63d) to correlate the haven against it
    def invvol2_wfn(i):
        # replicate the validated 2-sleeve inv-vol weighting
        lo = max(0, i - 63)
        a = tqqq_r[lo:i]; b = rot_r[lo:i]
        if len(a) < 10:
            return [0.5, 0.5]
        va = annualized_vol(a); vb = annualized_vol(b)
        if va <= 0 or vb <= 0:
            return [0.5, 0.5]
        ia, ib = 1.0 / va, 1.0 / vb
        s = ia + ib
        return [ia / s, ib / s]

    blend2 = blend_portfolio(common2, [tqqq_r, rot_r], invvol2_wfn,
                             blend_cost_bps=2.0, vol_lookback_days=63)
    blend2_ret = equity_to_daily_returns(blend2["dates"], blend2["equity"])
    blend2_r = [blend2_ret.get(d, 0.0) for d in common2]

    def corr_in(a, b, start, end):
        sa, sb = [], []
        for d, x, y in zip(common2, a, b):
            if start <= d < end:
                sa.append(x); sb.append(y)
        c = pearson(sa, sb) if len(sa) > 20 else None
        return None if c is None else round(c, 3)

    corr = {
        "haven_vs_tqqqleg_full": round(pearson(hav_r2, tqqq_r) or 0.0, 3),
        "haven_vs_rotleg_full": round(pearson(hav_r2, rot_r) or 0.0, 3),
        "haven_vs_2sleeveblend_full": round(pearson(hav_r2, blend2_r) or 0.0, 3),
        "haven_vs_spx_full": round(pearson(hav_r2, spx_r) or 0.0, 3),
        "haven_vs_blend_2020covid": corr_in(hav_r2, blend2_r, "2020-02-01", "2020-04-01"),
        "haven_vs_blend_2022bear": corr_in(hav_r2, blend2_r, "2022-01-01", "2023-01-01"),
        "haven_vs_blend_2025tariff": corr_in(hav_r2, blend2_r, "2025-02-01", "2025-05-01"),
    }
    print("    CORR haven vs: TQQQleg %.3f  ROTleg %.3f  2-sleeve-blend %.3f  SPX %.3f" % (
        corr["haven_vs_tqqqleg_full"], corr["haven_vs_rotleg_full"],
        corr["haven_vs_2sleeveblend_full"], corr["haven_vs_spx_full"]))
    print("    CORR haven vs blend in stress:  covid %s  2022bear %s  2025tariff %s" % (
        corr["haven_vs_blend_2020covid"], corr["haven_vs_blend_2022bear"], corr["haven_vs_blend_2025tariff"]))

    # eff-N: 2-leg (TQQQ,ROT) vs 3-leg (TQQQ,ROT,HAVEN), full window
    M2 = corr_matrix([tqqq_r, rot_r])
    M3 = corr_matrix([tqqq_r, rot_r, hav_r2])
    effN2 = effective_n(M2)
    effN3 = effective_n(M3)
    print("    eff-N: 2-leg %.3f -> 3-leg(+haven) %.3f   (corr matrix participation ratio)" % (effN2, effN3))

    # ----- (4) 3-SLEEVE BLEND with haven — does raw return still beat SPX? -----
    # Several allocation schemes for the 3-sleeve (TQQQ, ROT, HAVEN):
    spx_dates_full = common2  # benchmark path: SPX on the 2-sleeve common window
    # build an SPX equity for report_blend
    spx_eq = [1.0]
    for i in range(1, len(common2)):
        spx_eq.append(spx_eq[-1] * (1.0 + spx_r[i]))

    three = {}

    # 4a. naive inv-vol 63d over all 3 sleeves
    def invvol3_wfn(i):
        lo = max(0, i - 63)
        legs = [tqqq_r[lo:i], rot_r[lo:i], hav_r2[lo:i]]
        if any(len(x) < 10 for x in legs):
            return [1/3, 1/3, 1/3]
        vols = [annualized_vol(x) for x in legs]
        if any(v <= 0 for v in vols):
            return [1/3, 1/3, 1/3]
        inv = [1.0 / v for v in vols]
        s = sum(inv)
        return [x / s for x in inv]

    b3_invvol = blend_portfolio(common2, [tqqq_r, rot_r, hav_r2], invvol3_wfn,
                                blend_cost_bps=2.0, vol_lookback_days=63)
    three["invvol_naive"] = report_blend(b3_invvol, "3-sleeve inv-vol naive",
                                         spx_dates_full, spx_eq)

    # 4b. CAPPED haven: clip the haven sleeve weight to `cap`, redistribute the
    #     excess to TQQQ/ROT by their inv-vol share (mirrors the capped-allocator
    #     primitive from the third-sleeve follow-up). Sweep a few caps.
    def capped_wfn_factory(cap: float):
        def wfn(i):
            base = invvol3_wfn(i)  # [w_tqqq, w_rot, w_haven]
            wh = base[2]
            if wh <= cap:
                return base
            excess = wh - cap
            # redistribute excess to legs 0,1 by their inv-vol share
            lo = max(0, i - 63)
            a = tqqq_r[lo:i]; b = rot_r[lo:i]
            va = annualized_vol(a) if len(a) >= 10 else 0.0
            vb = annualized_vol(b) if len(b) >= 10 else 0.0
            if va > 0 and vb > 0:
                ia, ib = 1.0 / va, 1.0 / vb
                s = ia + ib
                sh = [ia / s, ib / s]
            else:
                sh = [0.5, 0.5]
            return [base[0] + excess * sh[0], base[1] + excess * sh[1], cap]
        return wfn

    for cap in (0.10, 0.15, 0.20, 0.25):
        bc = blend_portfolio(common2, [tqqq_r, rot_r, hav_r2], capped_wfn_factory(cap),
                             blend_cost_bps=2.0, vol_lookback_days=63)
        rep = report_blend(bc, "3-sleeve haven cap=%.0f%%" % (cap * 100),
                           spx_dates_full, spx_eq)
        # average haven weight realized
        wl = bc["weight_log"]
        avg_h = sum(w["w"][2] for w in wl) / len(wl) if wl else 0.0
        rep["avg_haven_weight"] = round(avg_h, 3)
        three["cap_%02d" % int(cap * 100)] = rep

    # 4c. fixed small sleeve: haven at a fixed 10% / 15% / 20%, rest split
    #     between TQQQ/ROT by inv-vol (a "permanent insurance allocation").
    def fixed_haven_wfn_factory(hw: float):
        def wfn(i):
            lo = max(0, i - 63)
            a = tqqq_r[lo:i]; b = rot_r[lo:i]
            va = annualized_vol(a) if len(a) >= 10 else 0.0
            vb = annualized_vol(b) if len(b) >= 10 else 0.0
            if va > 0 and vb > 0:
                ia, ib = 1.0 / va, 1.0 / vb
                s = ia + ib
                sh = [ia / s, ib / s]
            else:
                sh = [0.5, 0.5]
            rest = 1.0 - hw
            return [rest * sh[0], rest * sh[1], hw]
        return wfn

    for hw in (0.10, 0.15, 0.20):
        bf = blend_portfolio(common2, [tqqq_r, rot_r, hav_r2], fixed_haven_wfn_factory(hw),
                             blend_cost_bps=2.0, vol_lookback_days=63)
        rep = report_blend(bf, "3-sleeve fixed-haven %.0f%%" % (hw * 100),
                           spx_dates_full, spx_eq)
        three["fixed_%02d" % int(hw * 100)] = rep

    # 2-sleeve baseline on the same window for head-to-head
    base2 = report_blend(blend2, "2-sleeve baseline (TQQQ+ROT inv-vol)",
                         spx_dates_full, spx_eq)
    spx_full_stats = _stats_from_equity(common2, spx_eq)
    spx_raw_full = spx_full_stats.total_return_pct

    # mark beats-SPX-raw on each 3-sleeve variant
    for k, rep in three.items():
        rep["beats_spx_raw_full"] = rep["full"]["total_return_pct"] > spx_raw_full
    base2["beats_spx_raw_full"] = base2["full"]["total_return_pct"] > spx_raw_full

    print("\n    === 3-SLEEVE (with HAVEN) vs 2-SLEEVE vs SPX raw (full %s->%s) ===" % (
        common2[0], common2[-1]))
    print("    SPX raw full: %.0f%%" % spx_raw_full)
    print("    2-sleeve baseline: raw %.0f%%  Sharpe %.3f  maxDD %.1f%%  beats=%s" % (
        base2["full"]["total_return_pct"], base2["full"]["sharpe"],
        base2["full"]["maxdd_pct"], base2["beats_spx_raw_full"]))
    for k in sorted(three):
        rep = three[k]
        print("    %-26s raw %5.0f%%  Sharpe %.3f  OOS %.3f  maxDD %6.1f%%  beats=%s" % (
            k, rep["full"]["total_return_pct"], rep["full"]["sharpe"],
            rep["oos_2019_today"]["sharpe"], rep["full"]["maxdd_pct"],
            rep["beats_spx_raw_full"]))

    # ----- assemble result -----
    result = {
        "generated_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "two_sleeve_common_window": {"start": common2[0], "end": common2[-1], "n_days": len(common2)},
        "haven_deep_window": {"start": deep_common[0], "end": deep_common[-1], "n_days": len(deep_common)},
        "standalone_haven": standalone,
        "killer_battery_riskoff": battery,
        "correlation": corr,
        "eff_n": {"two_leg": round(effN2, 4), "three_leg_with_haven": round(effN3, 4),
                  "corr_matrix_2leg": M2, "corr_matrix_3leg": M3},
        "two_sleeve_baseline": base2,
        "three_sleeve_variants": three,
        "spx_raw_full_pct": spx_raw_full,
        "haven_sleeve_meta_on_2sleeve_window": hav_meta2,
    }
    out_path = "reports/_haven_sleeve_result.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print("\n>>> Wrote %s" % out_path)


if __name__ == "__main__":
    main()
