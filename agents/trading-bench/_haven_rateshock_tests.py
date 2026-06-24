#!/usr/bin/env python3
"""HAVEN RATE-SHOCK PATCH -- extend GLD/TLT haven with rate-shock-resistant assets.

The GLD/TLT haven is a PARTIAL PASS: hedges 6/8 risk-off windows but FAILS
rate-shock regimes (2022 -14.9%, 2013 taper -10.2%) because rising real rates
hit BOTH bonds AND gold. This tests DBC/UUP/SHY/TIP/DBMF patches for whether
they turn 2022/2013 toward flat WITHOUT wrecking the equity-crash hedge.
Reuses _allocator_blend_tests engine verbatim. Honest controls: adjclose,
2bps one-way, monthly rebal w/ intramonth drift, inv-vol parity past-only,
OOS split 2018-12-31, SPX on SAME traded path, NO lookahead.
"""
from __future__ import annotations

import json
import math
from typing import Dict, List, Tuple

import _allocator_blend_tests as AB
from _allocator_blend_tests import (
    build_sleeves, blend_portfolio, report_blend,
    stats_from_returns, pearson, equity_to_daily_returns,
    annualized_vol,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    _stats_from_equity,
)

CACHE = "data_cache/yahoo/%s_parsed.json"


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


def build_hardened_haven(common, assets, scheme="invvol", vol_lookback=63,
                         cost_bps=2.0, floor_label=None, floor_w=0.0):
    """Generalized N-asset haven sleeve. scheme=invvol (parity all assets) or
    shyfloor (fixed floor_w in floor_label, inv-vol parity the rest). Monthly
    rebal, cost_bps one-way on inter-asset turnover, intramonth drift, past-only."""
    labels = [a[0] for a in assets]
    series = [[a[1][d] for d in common] for a in assets]
    na = len(assets)
    n = len(common)
    floor_idx = labels.index(floor_label) if (scheme == "shyfloor" and floor_label in labels) else None
    month_open_set = set()
    seen = set()
    for i, d in enumerate(common):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open_set.add(i)

    def target_w(i):
        if scheme == "shyfloor":
            rest_idx = [k for k in range(na) if k != floor_idx]
            lo = max(0, i - vol_lookback)
            inv = []
            ok = True
            for k in rest_idx:
                w = series[k][lo:i]
                if len(w) < 10:
                    ok = False
                    break
                v = annualized_vol(w)
                if v <= 0:
                    ok = False
                    break
                inv.append(1.0 / v)
            out = [0.0] * na
            out[floor_idx] = floor_w
            if not ok:
                for k in rest_idx:
                    out[k] = (1.0 - floor_w) / len(rest_idx)
            else:
                s = sum(inv)
                for j, k in enumerate(rest_idx):
                    out[k] = (1.0 - floor_w) * (inv[j] / s)
            return out
        lo = max(0, i - vol_lookback)
        inv = []
        ok = True
        for k in range(na):
            w = series[k][lo:i]
            if len(w) < 10:
                ok = False
                break
            v = annualized_vol(w)
            if v <= 0:
                ok = False
                break
            inv.append(1.0 / v)
        if not ok:
            return [1.0 / na] * na
        s = sum(inv)
        return [x / s for x in inv]

    equity = [1.0]
    eq_dates = [common[0]]
    w0 = target_w(0)
    bucket = [w0[k] for k in range(na)]
    n_rebal = 0
    turn_total = 0.0
    wlog = []
    for i in range(1, n):
        d = common[i]
        if i in month_open_set:
            tot = sum(bucket)
            cur = [b / tot for b in bucket] if tot > 0 else [0.0] * na
            tgt = target_w(i)
            turn = sum(abs(tgt[k] - cur[k]) for k in range(na))
            cost = (cost_bps / 10000.0) * turn
            if turn > 1e-9:
                n_rebal += 1
                turn_total += turn
            tot_after = tot * (1.0 - cost)
            bucket = [tgt[k] * tot_after for k in range(na)]
            wlog.append({"date": d, "w": {labels[k]: round(tgt[k], 4) for k in range(na)}})
        for k in range(na):
            bucket[k] *= (1.0 + series[k][i])
        equity.append(sum(bucket))
        eq_dates.append(d)
    hav_ret = [0.0]
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        hav_ret.append(equity[i] / prev - 1.0 if prev > 0 else 0.0)
    meta = {
        "scheme": scheme, "assets": labels, "vol_lookback": vol_lookback,
        "floor_label": floor_label, "floor_w": floor_w, "n_rebal": n_rebal,
        "avg_turnover_per_rebal": (turn_total / n_rebal) if n_rebal else 0.0,
        "weight_log_tail": wlog[-3:],
    }
    return eq_dates, hav_ret, meta


def corr_matrix(series):
    k = len(series)
    M = [[1.0] * k for _ in range(k)]
    for a in range(k):
        for b in range(a + 1, k):
            c = pearson(series[a], series[b])
            c = 0.0 if c is None else c
            M[a][b] = M[b][a] = c
    return M


def _eigs_symmetric(M):
    n = len(M)
    Amat = [row[:] for row in M]
    for _ in range(100):
        p, q, mx = 0, 1, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                if abs(Amat[i][j]) > mx:
                    mx = abs(Amat[i][j])
                    p, q = i, j
        if mx < 1e-12:
            break
        app, aqq, apq = Amat[p][p], Amat[q][q], Amat[p][q]
        if abs(app - aqq) < 1e-18:
            theta = math.pi / 4
        else:
            theta = 0.5 * math.atan2(2 * apq, app - aqq)
        c, s = math.cos(theta), math.sin(theta)
        for i in range(n):
            aip, aiq = Amat[i][p], Amat[i][q]
            Amat[i][p] = c * aip + s * aiq
            Amat[i][q] = -s * aip + c * aiq
        for i in range(n):
            api, aqi = Amat[p][i], Amat[q][i]
            Amat[p][i] = c * api + s * aqi
            Amat[q][i] = -s * api + c * aqi
    return [Amat[i][i] for i in range(n)]


def effective_n(M):
    eigs = [max(0.0, e) for e in _eigs_symmetric(M)]
    s1 = sum(eigs)
    s2 = sum(e * e for e in eigs)
    if s2 <= 0:
        return float(len(M))
    return (s1 * s1) / s2


def slice_ret_stats(dates, rets, start, end):
    sub_d, sub_r = [], []
    for d, r in zip(dates, rets):
        if start <= d < end:
            sub_d.append(d)
            sub_r.append(r)
    if len(sub_r) < 20:
        return {"n": len(sub_r)}
    st = stats_from_returns(sub_d, sub_r)["stats"]
    return {"n": len(sub_r), "sharpe": st["sharpe"], "cagr_pct": st["cagr_pct"],
            "maxdd_pct": st["max_drawdown_pct"], "total_return_pct": st["total_return_pct"],
            "ann_vol_pct": st["ann_vol_pct"]}

HAVEN_WINDOWS = [
    ("2020-Q1 covid crash",  "2020-02-01", "2020-04-01"),
    ("2022 bear (full yr)",  "2022-01-01", "2023-01-01"),
    ("2022-H1 bear",         "2022-01-01", "2022-07-01"),
    ("2025-Q1 tariff bear",  "2025-02-01", "2025-05-01"),
    ("2011 debt-ceiling",    "2011-07-01", "2011-10-01"),
    ("2018-Q4 selloff",      "2018-10-01", "2019-01-01"),
    ("2013 taper-tantrum",   "2013-05-01", "2013-09-01"),
    ("2008 GFC",             "2008-09-01", "2009-04-01"),
]

CANDIDATES = [
    ("plain_GLD_TLT",      "invvol",   ["GLD", "TLT"],               None,  0.0,  "baseline (the partial-pass haven)"),
    ("GLD_TLT_DBC",        "invvol",   ["GLD", "TLT", "DBC"],        None,  0.0,  "commodities patch (2006+ common)"),
    ("GLD_TLT_DBC_UUP",    "invvol",   ["GLD", "TLT", "DBC", "UUP"], None,  0.0,  "commodities + dollar (2007+ common)"),
    ("GLD_TLT_TIP",        "invvol",   ["GLD", "TLT", "TIP"],        None,  0.0,  "TIPS patch (2003+ common)"),
    ("GLD_TLT_SHYfloor25", "shyfloor", ["GLD", "TLT", "SHY"],        "SHY", 0.25, "25pct SHY floor, rest inv-vol GLD/TLT"),
    ("GLD_TLT_SHYfloor40", "shyfloor", ["GLD", "TLT", "SHY"],        "SHY", 0.40, "40pct SHY floor, rest inv-vol GLD/TLT"),
    ("GLD_TLT_DBMF",       "invvol",   ["GLD", "TLT", "DBMF"],       None,  0.0,  "managed-futures patch (2019+ ONLY - short window)"),
]


def main():
    print(">>> Building validated 2-sleeve legs (TQQQ vol-target + sector-rotation) ...", flush=True)
    S = build_sleeves()
    common2 = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]
    spx_r = S["spx_r"]
    print(">>> Loading adjclose returns for all candidate assets ...", flush=True)
    R = {}
    for sym in ("GLD", "TLT", "DBC", "UUP", "SHY", "IEF", "TIP", "DBMF", "SPY"):
        R[sym] = load_adjclose_returns(sym)
        print("    %-5s n=%d  %s -> %s" % (sym, len(R[sym]),
              min(R[sym]) if R[sym] else "-", max(R[sym]) if R[sym] else "-"))
    spy = R["SPY"]
    deep_common = sorted(set(R["GLD"]) & set(R["TLT"]) & set(spy))
    print("    GLD/TLT/SPY deep window: %s -> %s (%d days)" % (deep_common[0], deep_common[-1], len(deep_common)))

    results = {}
    for key, scheme, labels, floor_label, floor_w, note in CANDIDATES:
        assets = [(lab, R[lab]) for lab in labels]
        sets = [set(R[lab]) for lab in labels] + [set(spy)]
        cand_common = sorted(set.intersection(*sets))
        hd, hr, meta = build_hardened_haven(cand_common, assets, scheme=scheme,
                                            floor_label=floor_label, floor_w=floor_w)
        spy_c = [spy[d] for d in cand_common]
        full = stats_from_returns(hd, hr)["stats"]
        oos = slice_ret_stats(hd, hr, "2019-01-01", "2099-12-31")
        is_ = slice_ret_stats(hd, hr, "2000-01-01", "2018-12-31")
        spx_full = stats_from_returns(cand_common, spy_c)["stats"]
        spx_oos = slice_ret_stats(cand_common, spy_c, "2019-01-01", "2099-12-31")
        battery = {}
        for label, st, en in HAVEN_WINDOWS:
            h = slice_ret_stats(hd, hr, st, en)
            sp = slice_ret_stats(cand_common, spy_c, st, en)
            battery[label] = {"haven": h, "spy": sp}
        results[key] = {
            "scheme": scheme, "assets": labels, "note": note,
            "window": {"start": cand_common[0], "end": cand_common[-1], "n_days": len(cand_common)},
            "meta": meta,
            "standalone": {
                "full": {"sharpe": full["sharpe"], "cagr_pct": full["cagr_pct"],
                         "maxdd_pct": full["max_drawdown_pct"], "ann_vol_pct": full["ann_vol_pct"],
                         "total_return_pct": full["total_return_pct"]},
                "is_pre2019": is_, "oos_2019plus": oos,
                "spx_full": {"sharpe": spx_full["sharpe"], "cagr_pct": spx_full["cagr_pct"],
                             "maxdd_pct": spx_full["max_drawdown_pct"],
                             "total_return_pct": spx_full["total_return_pct"]},
                "spx_oos": spx_oos,
                "beats_spx_raw_full": full["total_return_pct"] > spx_full["total_return_pct"],
            },
            "killer_battery": battery,
        }
        bb = battery
        def g(w):
            return bb[w]["haven"].get("total_return_pct", float("nan"))
        print("    [%-20s] %s" % (key, note))
        print("        2022yr %+6.1f%%  2013taper %+6.1f%% || covid %+6.1f%%  GFC %+6.1f%%  2011 %+6.1f%%  2018Q4 %+6.1f%%  2025 %+6.1f%%  (%s->%s)" % (
            g("2022 bear (full yr)"), g("2013 taper-tantrum"),
            g("2020-Q1 covid crash"), g("2008 GFC"), g("2011 debt-ceiling"),
            g("2018-Q4 selloff"), g("2025-Q1 tariff bear"),
            results[key]["window"]["start"], results[key]["window"]["end"]))

    # ----- 2-sleeve blend return series for corr / eff-N -----
    def invvol2_wfn(i):
        lo = max(0, i - 63)
        a = tqqq_r[lo:i]
        b = rot_r[lo:i]
        if len(a) < 10:
            return [0.5, 0.5]
        va = annualized_vol(a)
        vb = annualized_vol(b)
        if va <= 0 or vb <= 0:
            return [0.5, 0.5]
        ia, ib = 1.0 / va, 1.0 / vb
        s = ia + ib
        return [ia / s, ib / s]
    blend2 = blend_portfolio(common2, [tqqq_r, rot_r], invvol2_wfn, blend_cost_bps=2.0, vol_lookback_days=63)
    blend2_ret = equity_to_daily_returns(blend2["dates"], blend2["equity"])
    blend2_r = [blend2_ret.get(d, 0.0) for d in common2]

    effn_block = {}
    M2 = corr_matrix([tqqq_r, rot_r])
    effN2 = effective_n(M2)
    effn_block["two_leg"] = round(effN2, 4)
    effn_block["per_candidate"] = {}
    idx = {d: i for i, d in enumerate(common2)}
    for key, scheme, labels, floor_label, floor_w, note in CANDIDATES:
        assets = [(lab, R[lab]) for lab in labels]
        sets = [set(R[lab]) for lab in labels]
        hav_window = [d for d in common2 if all(d in s for s in sets)]
        if len(hav_window) < 200:
            effn_block["per_candidate"][key] = {"note": "insufficient overlap"}
            continue
        hd2, hr2, _ = build_hardened_haven(hav_window, assets, scheme=scheme,
                                           floor_label=floor_label, floor_w=floor_w)
        tq = [tqqq_r[idx[d]] for d in hav_window]
        ro = [rot_r[idx[d]] for d in hav_window]
        sp = [spx_r[idx[d]] for d in hav_window]
        bl = [blend2_r[idx[d]] for d in hav_window]
        M3 = corr_matrix([tq, ro, hr2])
        effN3 = effective_n(M3)
        def corr_sub(a, b, s, e):
            sa, sb = [], []
            for d, x, y in zip(hav_window, a, b):
                if s <= d < e:
                    sa.append(x)
                    sb.append(y)
            c = pearson(sa, sb) if len(sa) > 20 else None
            return None if c is None else round(c, 3)
        effn_block["per_candidate"][key] = {
            "window": [hav_window[0], hav_window[-1], len(hav_window)],
            "short_window": len(hav_window) < 3000,
            "corr_vs_tqqqleg_full": round(pearson(hr2, tq) or 0.0, 3),
            "corr_vs_rotleg_full": round(pearson(hr2, ro) or 0.0, 3),
            "corr_vs_2sleeveblend_full": round(pearson(hr2, bl) or 0.0, 3),
            "corr_vs_spx_full": round(pearson(hr2, sp) or 0.0, 3),
            "corr_vs_blend_2022bear": corr_sub(hr2, bl, "2022-01-01", "2023-01-01"),
            "corr_vs_blend_2020covid": corr_sub(hr2, bl, "2020-02-01", "2020-04-01"),
            "eff_n_3leg": round(effN3, 4),
            "corr_matrix_3leg": M3,
        }
        flag = "  *SHORT*" if effn_block["per_candidate"][key]["short_window"] else ""
        print("    eff-N[%-20s] 2-leg %.3f -> 3-leg %.3f  corr_TQQQ %.3f  (%s->%s)%s" % (
            key, effN2, effN3, effn_block["per_candidate"][key]["corr_vs_tqqqleg_full"],
            hav_window[0], hav_window[-1], flag))

    # ----- (E) 3-SLEEVE BLEND: TQQQ + ROT + HARDENED-HAVEN at fixed 10% -----
    # Mirror the prototype: haven as a fixed 10% 3rd sleeve, rest TQQQ/ROT by
    # inv-vol. Compare raw-vs-SPX + maxDD to the plain-GLD/TLT 10% baseline.
    spx_eq = [1.0]
    for i in range(1, len(common2)):
        spx_eq.append(spx_eq[-1] * (1.0 + spx_r[i]))
    spx_full_stats = _stats_from_equity(common2, spx_eq)
    spx_raw_full = spx_full_stats.total_return_pct

    def fixed_haven_blend(hav_r_on_common2, hw):
        def wfn(i):
            lo = max(0, i - 63)
            a = tqqq_r[lo:i]
            b = rot_r[lo:i]
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
        return blend_portfolio(common2, [tqqq_r, rot_r, hav_r_on_common2], wfn,
                               blend_cost_bps=2.0, vol_lookback_days=63)

    # For the 3-sleeve blend each candidate haven must be a return series on the
    # FULL common2 calendar. For short-window candidates (DBMF) we pad pre-
    # inception days with 0.0 (no position) so the blend is well-defined, and we
    # ALSO report a 3-sleeve on the candidate-restricted window for honesty.
    three_sleeve = {}
    for key, scheme, labels, floor_label, floor_w, note in CANDIDATES:
        assets = [(lab, R[lab]) for lab in labels]
        sets = [set(R[lab]) for lab in labels]
        hav_window = [d for d in common2 if all(d in s for s in sets)]
        if len(hav_window) < 200:
            continue
        hd2, hr2, _ = build_hardened_haven(hav_window, assets, scheme=scheme,
                                           floor_label=floor_label, floor_w=floor_w)
        short = len(hav_window) < 3000
        rmap = {d: r for d, r in zip(hav_window, hr2)}
        # FULL-window blend: pad missing days with 0.0 (haven flat before inception)
        hav_full = [rmap.get(d, 0.0) for d in common2]
        bf = fixed_haven_blend(hav_full, 0.10)
        rep_full = report_blend(bf, "3sl fixed10 %s (full pad)" % key, common2, spx_eq)
        rep_full["beats_spx_raw_full"] = rep_full["full"]["total_return_pct"] > spx_raw_full
        # 2022-specific maxDD of the 3-sleeve blend
        bf_ret = equity_to_daily_returns(bf["dates"], bf["equity"])
        bf_r = [bf_ret.get(d, 0.0) for d in common2]
        dd2022 = slice_ret_stats(common2, bf_r, "2022-01-01", "2023-01-01")
        rep_full["blend_2022_maxdd_pct"] = dd2022.get("maxdd_pct")
        rep_full["blend_2022_ret_pct"] = dd2022.get("total_return_pct")
        entry = {"full_pad": rep_full, "short_window": short, "note": note}
        # RESTRICTED-window blend (only on the candidate window) for short ones
        if short:
            spx_eq_r = [1.0]
            for i in range(1, len(hav_window)):
                spx_eq_r.append(spx_eq_r[-1] * (1.0 + spx_r[idx[hav_window[i]]]))
            tqw = [tqqq_r[idx[d]] for d in hav_window]
            row = [rot_r[idx[d]] for d in hav_window]
            def wfn_r(i):
                lo = max(0, i - 63)
                a = tqw[lo:i]
                b = row[lo:i]
                va = annualized_vol(a) if len(a) >= 10 else 0.0
                vb = annualized_vol(b) if len(b) >= 10 else 0.0
                if va > 0 and vb > 0:
                    ia, ib = 1.0 / va, 1.0 / vb
                    ss = ia + ib
                    sh = [ia / ss, ib / ss]
                else:
                    sh = [0.5, 0.5]
                return [0.9 * sh[0], 0.9 * sh[1], 0.10]
            bfr = blend_portfolio(hav_window, [tqw, row, hr2], wfn_r,
                                  blend_cost_bps=2.0, vol_lookback_days=63)
            spx_raw_r = _stats_from_equity(hav_window, spx_eq_r).total_return_pct
            rep_r = report_blend(bfr, "3sl fixed10 %s (restricted win)" % key, hav_window, spx_eq_r)
            rep_r["beats_spx_raw_restricted"] = rep_r["full"]["total_return_pct"] > spx_raw_r
            rep_r["spx_raw_restricted_pct"] = spx_raw_r
            entry["restricted_win"] = rep_r
        three_sleeve[key] = entry

    print("")
    print("    === 3-SLEEVE fixed-10pct haven vs SPX raw (full %s->%s, SPX raw %.0f%%) ===" % (
        common2[0], common2[-1], spx_raw_full))
    print("    plain-GLD/TLT 10pct baseline target: raw 864pct Sharpe 1.032 maxDD -21.7pct (from prototype)")
    for key in three_sleeve:
        rp = three_sleeve[key]["full_pad"]
        flag = "  *SHORT/pad*" if three_sleeve[key]["short_window"] else ""
        print("    %-20s raw %5.0f%%  Sharpe %.3f  OOS %.3f  maxDD %6.1f%%  2022maxDD %6.1f%%  beats=%s%s" % (
            key, rp["full"]["total_return_pct"], rp["full"]["sharpe"],
            rp["oos_2019_today"]["sharpe"], rp["full"]["maxdd_pct"],
            rp.get("blend_2022_maxdd_pct") or 0.0, rp["beats_spx_raw_full"], flag))

    result = {
        "generated_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "two_sleeve_common_window": {"start": common2[0], "end": common2[-1], "n_days": len(common2)},
        "candidates": results,
        "eff_n": effn_block,
        "three_sleeve_fixed10": three_sleeve,
        "spx_raw_full_pct": spx_raw_full,
    }
    out_path = "reports/_haven_rateshock_result.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print("")
    print(">>> Wrote %s" % out_path)


if __name__ == "__main__":
    main()
