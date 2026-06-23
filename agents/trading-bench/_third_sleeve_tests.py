"""THIRD-SLEEVE SCOPE — does the validated 2-sleeve inverse-vol blend get a
genuine OOS lift from a 3rd low-correlation sleeve?

REUSES the validated engine in `_allocator_blend_tests.py`:
  - build_sleeves()      -> TQQQ vol-target + sector-rotation sleeves on common cal
  - blend_portfolio()    -> the SAME monthly inverse-vol risk-parity machinery
  - report_blend / correlation helpers / stats_from_returns

We extend the SAME blend_portfolio to N sleeves (it already takes a list of
sleeves + a weight_fn over N), add candidate 3rd sleeves, and compare
3-sleeve vs the validated 2-sleeve vs SPX on the path traded, net of the same
2bps inter-sleeve cost. Honest measurement: no lookahead, walk-forward/OOS
split at 2018-12-31, benchmark on the traded path, costs applied.

CANDIDATES (priority order):
  P1a  DBMF/KMLM   real managed-futures ETFs (clean, SHORT: 2019-05 / 2020-12+)
  P1b  SYN_TREND   synthetic 12-1 time-series-momentum long/flat basket across
                   liquid futures-like ETFs (DBC/GLD/TLT/UUP) -> DEEP history,
                   crude CTA replication (approximate)
  P2   CREDIT      FRED BAA10Y credit-spread risk-on/off sleeve (deep); long
                   defensive (IEF) when credit stress, long SPY when calm.
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from typing import Dict, List, Optional

sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from _allocator_blend_tests import (
    build_sleeves, blend_portfolio, report_blend, correlation_report,
    stats_from_returns, slice_equity_stats, annualized_vol,
    equity_to_daily_returns,
)


def _adjclose_map(symbol: str) -> Dict[str, float]:
    bars = dbc.get_daily(symbol)
    return {b["date"]: b["adjclose"] for b in bars if b.get("adjclose") is not None}


def real_etf_sleeve(symbol: str) -> Dict[str, float]:
    """Daily simple returns of a buy-&-hold real ETF (DBMF/KMLM). Expense ratio
    already in adjclose; blend adds only inter-sleeve cost. No lookahead."""
    ac = _adjclose_map(symbol)
    dates = sorted(ac)
    out: Dict[str, float] = {}
    for i in range(1, len(dates)):
        p0, p1 = ac[dates[i - 1]], ac[dates[i]]
        if p0 and p0 > 0:
            out[dates[i]] = p1 / p0 - 1.0
    return out


def synthetic_trend_sleeve(symbols: List[str], lookback_days: int = 252,
                           skip_days: int = 21, cost_bps: float = 2.0,
                           start: str = "2005-01-01") -> Dict[str, float]:
    """Crude managed-futures replication: monthly 12-1 TSM long/flat basket.
    Lookahead-safe: momentum measured through prior month-end; weight applied to
    forward month. Each asset 1/N of book if 12-1>0 else cash. 2bps on turnover."""
    ac = {s: _adjclose_map(s) for s in symbols}
    date_sets = [set(d for d in ac[s] if d >= start) for s in symbols]
    common = sorted(set.intersection(*date_sets))
    if len(common) < lookback_days + skip_days + 5:
        return {}
    dret: Dict[str, List[float]] = {}
    for s in symbols:
        r = [0.0]
        for i in range(1, len(common)):
            p0, p1 = ac[s][common[i - 1]], ac[s][common[i]]
            r.append(p1 / p0 - 1.0 if p0 and p0 > 0 else 0.0)
        dret[s] = r
    closes = {s: [ac[s][d] for d in common] for s in symbols}
    month_open_set = set()
    seen = set()
    for i, d in enumerate(common):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open_set.add(i)
    nS = len(symbols)
    per = 1.0 / nS
    w = {s: 0.0 for s in symbols}
    out: Dict[str, float] = {}
    for i in range(1, len(common)):
        d = common[i]
        if i in month_open_set:
            new_w = {}
            for s in symbols:
                j_now = i - 1 - skip_days
                j_then = i - 1 - skip_days - lookback_days
                if j_then < 0:
                    new_w[s] = 0.0
                    continue
                p_then, p_now = closes[s][j_then], closes[s][j_now]
                mom = (p_now / p_then - 1.0) if (p_then and p_then > 0) else -1.0
                new_w[s] = per if mom > 0 else 0.0
            turn = sum(abs(new_w[s] - w[s]) for s in symbols)
            w = new_w
            day_ret = -(cost_bps / 10000.0) * turn
        else:
            day_ret = 0.0
        day_ret += sum(w[s] * dret[s][i] for s in symbols)
        out[d] = day_ret
    return out


def credit_macro_sleeve(risk_on_sym: str = "SPY", risk_off_sym: str = "IEF",
                        series_id: str = "BAA10Y", lookback_z: int = 252,
                        z_thresh: float = 1.0, start: str = "2005-01-01") -> Dict[str, float]:
    """Credit-stress risk-on/off sleeve. Signal: trailing z-score of BAA10Y
    (daily market-priced -> un-revised) using data through PRIOR day. z>thresh
    (stress) -> IEF; else -> SPY. Leak-free: decision uses prior-day spread."""
    from runner import fred_cache
    spread_rows = fred_cache.get_values(series_id, start, "2026-12-31", vintage="latest")
    spread = {d: v for d, v in spread_rows}
    ac_on = _adjclose_map(risk_on_sym)
    ac_off = _adjclose_map(risk_off_sym)
    px_dates = sorted(set(ac_on) & set(ac_off))
    px_dates = [d for d in px_dates if d >= start]
    if len(px_dates) < lookback_z + 5:
        return {}
    sp_dates = sorted(spread)

    def spread_asof(d: str) -> Optional[float]:
        j = bisect.bisect_right(sp_dates, d) - 1
        return spread[sp_dates[j]] if j >= 0 else None

    spread_series = [spread_asof(d) for d in px_dates]
    out: Dict[str, float] = {}
    for i in range(1, len(px_dates)):
        d = px_dates[i]
        lo = max(0, i - 1 - lookback_z)
        window = [s for s in spread_series[lo:i] if s is not None]
        cur = spread_series[i - 1]
        if cur is None or len(window) < 30:
            w_on, w_off = 1.0, 0.0
        else:
            mu = sum(window) / len(window)
            var = sum((x - mu) ** 2 for x in window) / len(window)
            sd = math.sqrt(var)
            z = (cur - mu) / sd if sd > 0 else 0.0
            if z > z_thresh:
                w_on, w_off = 0.0, 1.0
            else:
                w_on, w_off = 1.0, 0.0
        p0_on, p1_on = ac_on[px_dates[i - 1]], ac_on[d]
        p0_off, p1_off = ac_off[px_dates[i - 1]], ac_off[d]
        r_on = p1_on / p0_on - 1.0 if p0_on and p0_on > 0 else 0.0
        r_off = p1_off / p0_off - 1.0 if p0_off and p0_off > 0 else 0.0
        out[d] = w_on * r_on + w_off * r_off
    return out


# ------------------------------------------------------------------ #
# Head-to-head harness: 2-sleeve vs 3-sleeve (adding candidate) vs SPX.
# ------------------------------------------------------------------ #

def invvol_wfn_factory(sleeves: List[List[float]], lookback: int = 63):
    """Inverse-vol risk-parity weight fn over N sleeves using PAST returns only."""
    ns = len(sleeves)

    def fn(idx):
        if idx < 2:
            return [1.0 / ns] * ns
        lo = max(0, idx - lookback)
        ivs = []
        for k in range(ns):
            v = annualized_vol(sleeves[k][lo:idx])
            ivs.append(1.0 / v if v > 0 else 0.0)
        s = sum(ivs)
        if s <= 0:
            return [1.0 / ns] * ns
        return [iv / s for iv in ivs]
    return fn


def _solo_block(dates, rets):
    curve = stats_from_returns(dates, rets)
    s = curve["stats"]
    oos = slice_equity_stats(curve["dates"], curve["equity"], "2019-01-01", "2099-12-31")
    return {
        "full": {"sharpe": s["sharpe"], "cagr_pct": s["cagr_pct"],
                 "maxdd_pct": s["max_drawdown_pct"], "vol_pct": s["ann_vol_pct"],
                 "total_return_pct": s["total_return_pct"]},
        "oos": {"sharpe": oos.get("sharpe"), "cagr_pct": oos.get("cagr_pct"),
                "maxdd_pct": oos.get("max_drawdown_pct")},
    }


def run_head_to_head(label: str, third_map: Dict[str, float], S: Dict,
                     lookback: int = 63) -> Dict:
    """Align the candidate 3rd sleeve onto the common calendar of the 2 existing
    sleeves, build 2-sleeve and 3-sleeve inverse-vol blends on the SHARED window
    (intersection with the 3rd sleeve's dates) so the comparison is apples-to-
    apples on identical dates."""
    tqqq_full = dict(zip(S["common_dates"], S["tqqq_r"]))
    rot_full = dict(zip(S["common_dates"], S["rot_r"]))
    spx_full = dict(zip(S["common_dates"], S["spx_r"]))

    shared = [d for d in S["common_dates"] if d in third_map]
    if len(shared) < 200:
        return {"label": label, "error": "too few shared days (%d)" % len(shared)}

    tqqq_r = [tqqq_full[d] for d in shared]
    rot_r = [rot_full[d] for d in shared]
    spx_r = [spx_full[d] for d in shared]
    third_r = [third_map[d] for d in shared]

    spx_curve = stats_from_returns(shared, spx_r)
    spx_dates, spx_equity = spx_curve["dates"], spx_curve["equity"]

    sleeves2 = [tqqq_r, rot_r]
    wfn2 = invvol_wfn_factory(sleeves2, lookback)
    blend2 = blend_portfolio(shared, sleeves2, wfn2, blend_cost_bps=2.0)
    blend2_ret = equity_to_daily_returns(blend2["dates"], blend2["equity"])
    blend2_r = [blend2_ret.get(d, 0.0) for d in shared]

    corr = {
        "vs_tqqq_leg": correlation_report(shared, third_r, tqqq_r),
        "vs_rotation_leg": correlation_report(shared, third_r, rot_r),
        "vs_2sleeve_blend": correlation_report(shared, third_r, blend2_r),
    }

    sleeves3 = [tqqq_r, rot_r, third_r]
    wfn3 = invvol_wfn_factory(sleeves3, lookback)
    blend3 = blend_portfolio(shared, sleeves3, wfn3, blend_cost_bps=2.0)

    rep2 = report_blend(blend2, "2sleeve_on_%s_window" % label, spx_dates, spx_equity)
    rep3 = report_blend(blend3, "3sleeve_%s" % label, spx_dates, spx_equity)

    avg_w3 = None
    if blend3["weight_log"]:
        avg_w3 = sum(wl["w"][2] for wl in blend3["weight_log"]) / len(blend3["weight_log"])

    return {
        "label": label,
        "shared_window": [shared[0], shared[-1], len(shared)],
        "correlation": corr,
        "blend2": rep2,
        "blend3": rep3,
        "avg_third_weight": avg_w3,
        "third_solo": _solo_block(shared, third_r),
    }


def _print_cand(c: Dict):
    if "error" in c:
        print("   ERROR:", c["error"], flush=True)
        return
    w = c["shared_window"]
    cu = c["correlation"]
    b2, b3 = c["blend2"], c["blend3"]
    nan = float("nan")
    print("   shared %s->%s (%dd)  3rd-solo Sharpe %.2f CAGR %.1f%% maxDD %.1f%%" % (
        w[0], w[1], w[2], c["third_solo"]["full"]["sharpe"],
        c["third_solo"]["full"]["cagr_pct"], c["third_solo"]["full"]["maxdd_pct"]), flush=True)
    print("   corr 3rd vs TQQQ-leg %.2f | vs ROT-leg %.2f | vs 2-blend %.2f" % (
        cu["vs_tqqq_leg"]["full"] or nan, cu["vs_rotation_leg"]["full"] or nan,
        cu["vs_2sleeve_blend"]["full"] or nan), flush=True)
    print("   2-sleeve(window): full Sh %.3f OOS Sh %.3f ret %.0f%% maxDD %.1f%% CAGR %.1f%%" % (
        b2["full"]["sharpe"], b2["oos_2019_today"].get("sharpe") or nan,
        b2["full"]["total_return_pct"], b2["full"]["maxdd_pct"], b2["full"]["cagr_pct"]), flush=True)
    print("   3-sleeve(+%s): full Sh %.3f OOS Sh %.3f ret %.0f%% maxDD %.1f%% CAGR %.1f%% (3rd-wt %.2f)" % (
        c["label"], b3["full"]["sharpe"], b3["oos_2019_today"].get("sharpe") or nan,
        b3["full"]["total_return_pct"], b3["full"]["maxdd_pct"], b3["full"]["cagr_pct"],
        c["avg_third_weight"] or nan), flush=True)


def main():
    print(">>> Building validated 2 sleeves (reusing _allocator_blend_tests) ...", flush=True)
    S = build_sleeves()
    print("", flush=True)

    out: Dict = {"meta": {
        "common_window": [S["common_dates"][0], S["common_dates"][-1]],
        "n_common_days": len(S["common_dates"]),
        "note": ("3rd sleeve added to the SAME inverse-vol(63d) risk-parity blend; "
                 "same 2bps inter-sleeve cost. Each candidate evaluated on the "
                 "intersection of the 2-sleeve common window with the candidate's "
                 "own data (apples-to-apples on identical dates)."),
    }, "candidates": {}}

    print(">>> P1a DBMF (real managed-futures ETF) ...", flush=True)
    out["candidates"]["P1a_DBMF_real"] = run_head_to_head("DBMF_real", real_etf_sleeve("DBMF"), S)
    _print_cand(out["candidates"]["P1a_DBMF_real"])

    print(">>> P1a2 KMLM (real managed-futures ETF, shorter) ...", flush=True)
    out["candidates"]["P1a_KMLM_real"] = run_head_to_head("KMLM_real", real_etf_sleeve("KMLM"), S)
    _print_cand(out["candidates"]["P1a_KMLM_real"])

    print(">>> P1b SYN_TREND 12-1 TSM long/flat [DBC,GLD,TLT,UUP] (deep) ...", flush=True)
    syn = synthetic_trend_sleeve(["DBC", "GLD", "TLT", "UUP"], start="2005-01-01")
    out["candidates"]["P1b_SYN_TREND"] = run_head_to_head("SYN_TREND", syn, S)
    out["candidates"]["P1b_SYN_TREND"]["syn_full_span"] = (
        [min(syn), max(syn), len(syn)] if syn else None)
    _print_cand(out["candidates"]["P1b_SYN_TREND"])

    print(">>> P2 CREDIT BAA10Y risk-on/off [SPY/IEF] (deep) ...", flush=True)
    try:
        credit = credit_macro_sleeve("SPY", "IEF", "BAA10Y", start="2005-01-01")
        out["candidates"]["P2_CREDIT"] = run_head_to_head("CREDIT", credit, S)
        out["candidates"]["P2_CREDIT"]["credit_full_span"] = (
            [min(credit), max(credit), len(credit)] if credit else None)
        _print_cand(out["candidates"]["P2_CREDIT"])
    except Exception as e:
        out["candidates"]["P2_CREDIT"] = {"label": "CREDIT", "error": str(e)}
        print("   CREDIT failed:", str(e)[:200], flush=True)

    with open("reports/_third_sleeve_result.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("wrote reports/_third_sleeve_result.json", flush=True)
    return out


if __name__ == "__main__":
    main()
