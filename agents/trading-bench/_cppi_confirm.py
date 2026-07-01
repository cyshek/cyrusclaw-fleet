"""CPPI / TIPP convex crash-floor overlay -- CONFIRM-OR-KILL vs the live binary
-10%-trailing-DD/wh15 cash gate (runner/crash_sleeve_paper_tracker.py).

QUESTION: Does a CONTINUOUS, ratcheted CPPI/TIPP floor governor BEAT the existing
BINARY -10%-DD cash gate head-to-head on risk-adjusted terms, net of its higher
turnover cost, AND survive the +1-bar canary, AND avoid chronically
deleveraging-into-V-bottoms? If it only ties/trails the binary gate -> KILL
(Occam: the simpler binary gate is already on the forward clock).

ENGINE: reuses _allocator_blend_tests.build_sleeves / blend_portfolio VERBATIM
(self-contained: regenerates its cache via build_cache_inline; zero sleeve-math reimplementation)
and the SAME smooth_3mo inv-vol 2-sleeve base the crash-sleeve tracker uses. The
CPPI governor is a NEW daily exposure overlay on that blend's own equity curve +
a cash proxy (return 0).

RAILS: adjclose returns (inherited from the cached sleeves) - 2bps per turnover
unit (CPPI exposure churns DAILY -> turnover/cost is a PRIMARY kill axis, measured
explicitly) - PAST-ONLY: exposure for bar t uses cushion computed through bar t-1
(strictly before rebalance), mirroring the binary gate's idx-1 discipline - OOS
split reported at BOTH 2019-01-01 (matches the probe) and 2020-01-01 (task text) -
SPX (^GSPC) on the SAME traded path - +1-bar canary (lethal) on the best config.
Research-only: writes ONLY _cppi_confirm.py, reports/CPPI_VERDICT_*.md,
reports/_cppi_result.json. No protected/live files, crontab, .db, or trackers.
"""
from __future__ import annotations
import sys, json, math
sys.path.insert(0, ".")
from datetime import datetime, timezone

from strategies_candidates.leveraged_long_trend.backtest_daily import (
    _stats_from_equity, TRADING_DAYS,
)

OOS_2019 = "2019-01-01"
OOS_2020 = "2020-01-01"
IS_END_2019 = "2018-12-31"
IS_END_2020 = "2019-12-31"
COST_BPS = 2.0

# Incumbent binary gate constants (verbatim from runner/crash_sleeve_paper_tracker.py)
HEDGE_WEIGHT = 0.15
DD_TRIGGER_PCT = -0.10
VOL_LB = 63
SMOOTH = 3


def build_cache_inline():
    """Reproduce the cached daily return arrays from scratch, reusing
    _allocator_blend_tests.build_sleeves / blend_portfolio VERBATIM (zero sleeve-
    math reimplementation). Self-contained fallback: regenerated if the cache is
    absent. Risky asset = ungated smooth_3mo inv-vol 63d 2-sleeve blend (identical
    weighting to runner/crash_sleeve_paper_tracker.py)."""
    from _allocator_blend_tests import build_sleeves, blend_portfolio
    S = build_sleeves()
    dates = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]
    spx_r = S["spx_r"]
    nloc = len(dates)
    month_open = []
    seen = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open.append(i)
    risk = [tqqq_r, rot_r]

    def raw_iv(idx):
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - VOL_LB)
        v0 = annvol_pop(risk[0][lo:idx])
        v1 = annvol_pop(risk[1][lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv0, iv1 = 1.0 / v0, 1.0 / v1
        s = iv0 + iv1
        return [iv0 / s, iv1 / s]

    def base_w(idx):
        prev = [m for m in month_open if m <= idx]
        sel = prev[-SMOOTH:] if prev else [idx]
        if not sel:
            sel = [idx]
        a0 = a1 = 0.0
        for m in sel:
            w = raw_iv(m)
            a0 += w[0]
            a1 += w[1]
        c = len(sel)
        w = [a0 / c, a1 / c]
        s = w[0] + w[1]
        if s <= 0:
            return [0.5, 0.5]
        return [w[0] / s, w[1] / s]

    ung = blend_portfolio(dates, [tqqq_r, rot_r], base_w, blend_cost_bps=COST_BPS,
                          vol_lookback_days=VOL_LB)
    ung_eq = ung["equity"]
    g_r = [0.0] * nloc
    for i in range(1, nloc):
        if ung_eq[i - 1] != 0:
            g_r[i] = ung_eq[i] / ung_eq[i - 1] - 1.0
    cache = {
        "dates": dates, "g_r": g_r, "spx_r": spx_r,
        "tqqq_r": tqqq_r, "rot_r": rot_r, "month_open": month_open,
        "ungated_stats": ung["stats"],
        "ungated_avg_turnover_per_rebal": ung["avg_turnover_per_rebal"],
        "ungated_n_rebal": ung["n_rebal"],
    }
    fc = open("_cppi_cache.json", "w")
    json.dump(cache, fc)
    fc.close()
    return cache


def load_cache():
    import os
    if not os.path.exists("_cppi_cache.json"):
        return build_cache_inline()
    fh = open("_cppi_cache.json")
    data = json.load(fh)
    fh.close()
    return data


# --------------------------------------------------------------------------- #
# Shared stats helpers (single continuous equity curve -> FP continuous Sharpe
# is just the annualized Sharpe of the concatenated daily returns; for ONE span
# that equals sharpe_from_returns over the whole series -- exactly fp_sharpe's
# definition applied to a single window).
# --------------------------------------------------------------------------- #
def annvol_pop(returns):
    m = len(returns)
    if m < 2:
        return 0.0
    mean = sum(returns) / m
    var = sum((r - mean) ** 2 for r in returns) / m
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def sharpe_from_returns(returns):
    """Full-period continuous-span annualized Sharpe (sample stdev, ddof=1,
    sqrt(252)) -- the canonical fp_sharpe definition for a single continuous
    equity span. No risk-free adjustment (matches backtest_xsec.sharpe)."""
    nn = len(returns)
    if nn < 2:
        return 0.0
    mean = sum(returns) / nn
    var = sum((r - mean) ** 2 for r in returns) / (nn - 1)
    if var <= 0:
        return 0.0
    return (mean / math.sqrt(var)) * math.sqrt(TRADING_DAYS)


def eq_from_rets(dates, rets):
    eq = [1.0]
    for i in range(1, len(rets)):
        eq.append(eq[-1] * (1.0 + rets[i]))
    return eq


def slice_idx(dates, start, end):
    lo = 0
    while lo < len(dates) and dates[lo] < start:
        lo += 1
    hi = lo
    while hi < len(dates) and dates[hi] <= end:
        hi += 1
    return lo, hi


def span_stats(dates, rets, start, end):
    """Stats over a date sub-span using the shared _stats_from_equity ruler.
    rets[i] aligns to dates[i]; we rebase equity to 1.0 at the span start."""
    lo, hi = slice_idx(dates, start, end)
    if hi - lo < 3:
        return None
    sub_d = dates[lo:hi]
    sub_r = rets[lo:hi]
    eq = [1.0]
    ds = [sub_d[0]]
    for i in range(1, len(sub_r)):
        eq.append(eq[-1] * (1.0 + sub_r[i]))
        ds.append(sub_d[i])
    st = _stats_from_equity(ds, eq)
    return {
        "sharpe": st.sharpe, "cagr_pct": st.cagr_pct,
        "maxdd_pct": st.max_drawdown_pct, "vol_pct": st.ann_vol_pct,
        "total_return_pct": st.total_return_pct, "n": hi - lo,
    }


def pearson(xs, ys):
    nn = len(xs)
    if nn < 3 or nn != len(ys):
        return None
    mx = sum(xs) / nn
    my = sum(ys) / nn
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(nn))
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def full_block(dates, rets, spx_r, turnover_cost_total, n_turn_events):
    """Full-period metric block for a daily return series on the common path."""
    fp_sh = sharpe_from_returns(rets)
    eq = eq_from_rets(dates, rets)
    st = _stats_from_equity(dates, eq)
    corr = pearson(rets[1:], spx_r[1:])
    return {
        "fp_sharpe": fp_sh,
        "cagr_pct": st.cagr_pct,
        "maxdd_pct": st.max_drawdown_pct,
        "vol_pct": st.ann_vol_pct,
        "total_return_pct": st.total_return_pct,
        "spy_corr": corr,
        "turnover_cost_total_pct": turnover_cost_total * 100.0,
        "n_turn_events": n_turn_events,
        "is_2019": span_stats(dates, rets, "2000-01-01", IS_END_2019),
        "oos_2019": span_stats(dates, rets, OOS_2019, "2099-12-31"),
        "is_2020": span_stats(dates, rets, "2000-01-01", IS_END_2020),
        "oos_2020": span_stats(dates, rets, OOS_2020, "2099-12-31"),
    }


# --------------------------------------------------------------------------- #
# INCUMBENT: binary -10%-DD / wh15 cash gate, reconstructed on the SAME path.
# Monthly-rebalanced smooth_3mo inv-vol 2-sleeve base; when SPX trailing DD (past-
# only through idx-1) breaches -10%, overlay a cash 3rd sleeve at 15%, taken
# proportionally from the 2 risk sleeves. 2bps one-way on inter-sleeve turnover
# (incl hedge on/off). VERBATIM logic from runner/crash_sleeve_paper_tracker.py.
# --------------------------------------------------------------------------- #
def build_regime_flags(spx_r, dd_thresh, extra_lag=0):
    nn = len(spx_r)
    price = [1.0] * nn
    for i in range(1, nn):
        price[i] = price[i - 1] * (1.0 + spx_r[i])
    flags = [False] * nn
    for idx in range(nn):
        cut = idx - 1 - extra_lag
        if cut < 1:
            flags[idx] = False
            continue
        peak = max(price[: cut + 1])
        dd = price[cut] / peak - 1.0
        flags[idx] = dd <= dd_thresh
    return flags


def raw_invvol(idx, risk):
    if idx < 2:
        return [0.5, 0.5]
    lo = max(0, idx - VOL_LB)
    v0 = annvol_pop(risk[0][lo:idx])
    v1 = annvol_pop(risk[1][lo:idx])
    if v0 <= 0 or v1 <= 0:
        return [0.5, 0.5]
    iv0, iv1 = 1.0 / v0, 1.0 / v1
    s = iv0 + iv1
    return [iv0 / s, iv1 / s]


def smoothed_base(idx, risk, month_open):
    prev = [m for m in month_open if m <= idx]
    sel = prev[-SMOOTH:] if prev else [idx]
    if not sel:
        sel = [idx]
    a0 = a1 = 0.0
    for m in sel:
        w = raw_invvol(m, risk)
        a0 += w[0]
        a1 += w[1]
    c = len(sel)
    w = [a0 / c, a1 / c]
    s = w[0] + w[1]
    if s <= 0:
        return [0.5, 0.5]
    return [w[0] / s, w[1] / s]


def run_binary_gate(dates, tqqq_r, rot_r, spx_r, month_open, w_h=HEDGE_WEIGHT,
                    dd_thresh=DD_TRIGGER_PCT, extra_lag=0):
    """Monthly-rebalanced gated 3-sleeve [tqqq, rot, cash] blend with intramonth
    drift + 2bps one-way inter-sleeve turnover. Returns daily return series +
    turnover cost paid + exposure(=1-w_hedge) per day for V-bottom analysis."""
    nn = len(dates)
    risk = [tqqq_r, rot_r]
    cash_r = [0.0] * nn
    sleeves = [tqqq_r, rot_r, cash_r]
    flags = build_regime_flags(spx_r, dd_thresh, extra_lag=extra_lag)
    mo_set = set(month_open)

    def gated_w(idx):
        b = smoothed_base(idx, risk, month_open)
        on = flags[idx] if idx < len(flags) else False
        if on and w_h > 0:
            return [b[0] * (1.0 - w_h), b[1] * (1.0 - w_h), w_h]
        return [b[0], b[1], 0.0]

    equity = [1.0]
    w0 = gated_w(0)
    bucket = [w0[k] for k in range(3)]
    turnover_total = 0.0
    cost_total = 0.0
    n_events = 0
    exposure = [1.0 - bucket[2]]
    for i in range(1, nn):
        if i in mo_set:
            tot = sum(bucket)
            cur_w = [b / tot for b in bucket] if tot > 0 else [0.0] * 3
            tgt = gated_w(i)
            turn = sum(abs(tgt[k] - cur_w[k]) for k in range(3))
            cost = (COST_BPS / 10000.0) * turn
            if turn > 1e-9:
                n_events += 1
                turnover_total += turn
                cost_total += cost * tot
            tot_after = tot * (1.0 - cost)
            bucket = [tgt[k] * tot_after for k in range(3)]
        for k in range(3):
            bucket[k] *= (1.0 + sleeves[k][i])
        new_eq = sum(bucket)
        equity.append(new_eq)
        tot = sum(bucket)
        exposure.append((bucket[0] + bucket[1]) / tot if tot > 0 else 0.0)

    rets = [0.0] * nn
    for i in range(1, nn):
        if equity[i - 1] != 0:
            rets[i] = equity[i] / equity[i - 1] - 1.0
    return {
        "rets": rets, "equity": equity, "exposure": exposure,
        "turnover_total": turnover_total, "cost_total": cost_total,
        "n_turn_events": n_events, "flags": flags,
    }


# --------------------------------------------------------------------------- #
# CPPI / TIPP GOVERNOR  (the candidate).
# Risky asset = the ungated 2-sleeve blend (daily return g_r). Cash proxy = 0.
# Past-only: exposure for bar t uses cushion computed through bar t-1 (strictly
# before the rebalance), exactly mirroring the binary gate's idx-1 discipline.
#
#   floor_t   : TIPP-on  -> floor_ratio * running_peak(P) through t-1 (ratchets UP)
#               TIPP-off -> floor_ratio * P0 (classic fixed floor; rf~=0 here)
#   cushion   : C = P - floor   (computed on equity through t-1)
#   exposure  : e_t = clip( m * C_{t-1} / P_{t-1}, 0, exp_max )   exp_max=1.0
#   turnover  : |e_t - e_{t-1}| each day; cost = COST_BPS/1e4 * turnover (per unit)
#               applied to equity (CPPI churns exposure DAILY -> primary kill axis)
#
# Day t return earned = e_t * g_r[t] (cash leg = 0), minus that day's rebalance
# cost. e_t is decided BEFORE g_r[t] is known (uses P,floor through t-1).
# --------------------------------------------------------------------------- #
def run_cppi(dates, g_r, floor_ratio, m, tipp, exp_max=1.0,
             extra_lag=0, cost_bps=COST_BPS):
    """CPPI/TIPP exposure governor over the ungated 2-sleeve blend (risky asset
    daily return g_r) vs a cash proxy (return 0). PAST-ONLY: exposure applied to
    bar t is computed from equity/floor/cushion through bar t-1-extra_lag.

    floor_t : TIPP-on  -> floor_ratio * running_peak(P) through src (ratchets UP)
              TIPP-off -> floor_ratio * 1.0 (classic fixed floor; rf ~= 0)
    cushion : C = max(P_src - floor, 0)
    exposure: e = clip(m * C / P_src, 0, exp_max)
    cost    : COST_BPS/1e4 * |e - e_prev| each day (daily exposure churn).
    """
    nn = len(dates)
    P = [1.0] * nn
    peak_through = [1.0] * nn
    floor = [0.0] * nn
    cushion = [0.0] * nn
    exposure = [0.0] * nn
    rets = [0.0] * nn
    cost_total = 0.0
    turnover_total = 0.0
    n_events = 0

    # inception exposure at t=0 (no return earned at t=0; sets the e_prev baseline)
    fl0 = floor_ratio * 1.0
    cush0 = max(P[0] - fl0, 0.0)
    e0 = m * (cush0 / P[0]) if P[0] > 0 else 0.0
    e0 = min(max(e0, 0.0), exp_max)
    exposure[0] = e0
    floor[0] = fl0
    cushion[0] = cush0
    peak_through[0] = P[0]
    prev_e = e0

    for t in range(1, nn):
        src = t - 1 - extra_lag
        if src < 0:
            src = 0
        Psrc = P[src]
        pk = peak_through[src]
        fl = floor_ratio * pk if tipp else floor_ratio * 1.0
        cush = Psrc - fl
        if cush < 0.0:
            cush = 0.0
        e = m * (cush / Psrc) if Psrc > 0 else 0.0
        if e < 0.0:
            e = 0.0
        if e > exp_max:
            e = exp_max
        turn = abs(e - prev_e)
        cost = (cost_bps / 10000.0) * turn
        if turn > 1e-12:
            n_events += 1
            turnover_total += turn
        gross = 1.0 + e * g_r[t]
        net = gross * (1.0 - cost)
        P[t] = P[t - 1] * net
        rets[t] = (P[t] / P[t - 1] - 1.0) if P[t - 1] != 0 else 0.0
        cost_total += cost
        exposure[t] = e
        floor[t] = fl
        cushion[t] = cush
        prev_e = e
        pk_new = pk if pk > P[t] else P[t]
        peak_through[t] = pk_new

    return {
        "rets": rets, "equity": P, "exposure": exposure,
        "floor": floor, "cushion": cushion,
        "turnover_total": turnover_total, "cost_total": cost_total,
        "n_turn_events": n_events,
    }


# --------------------------------------------------------------------------- #
# Failure-mode instrumentation: V-bottom deleverage-and-never-recover.
# For a named crash window, find the SPX trough date, then measure CPPI exposure
# AT the trough and over the recovery leg (trough -> trough+R bars). If exposure
# is cut hard near the trough and stays low through the snapback, CPPI sold low
# and missed the recovery -- the lethal failure the AQR caveat flags.
# --------------------------------------------------------------------------- #
def spx_price_index(spx_r):
    nn = len(spx_r)
    px = [1.0] * nn
    for i in range(1, nn):
        px[i] = px[i - 1] * (1.0 + spx_r[i])
    return px


def vbottom_probe(dates, spx_r, exposure, win_start, win_end, recov_bars=63,
                  blend_r=None):
    """Return exposure at the SPX trough of [win_start,win_end] and the mean
    exposure over the recovery leg (trough .. trough+recov_bars), plus the SPX
    snapback return over that leg. Low exposure across a strong snapback = the
    deleverage-into-V failure.

    If blend_r is given (ungated risky-asset daily returns), also computes the
    RECOVERY CAPTURE RATIO = compounded (exposure*blend) return over the recovery
    leg / compounded blend return over the same leg -- how much of the snapback
    the governed book actually captured. <1 = left money on the table by being
    under-exposed into the recovery (the deleverage-into-V cost, quantified)."""
    px = spx_price_index(spx_r)
    lo, hi = slice_idx(dates, win_start, win_end)
    if hi - lo < 3:
        return None
    # trough = min px in window
    t_idx = lo
    for i in range(lo, hi):
        if px[i] < px[t_idx]:
            t_idx = i
    rec_hi = min(t_idx + recov_bars, len(dates) - 1)
    exp_at_trough = exposure[t_idx]
    rec_exps = exposure[t_idx:rec_hi + 1]
    mean_exp_recov = sum(rec_exps) / len(rec_exps) if rec_exps else 0.0
    spx_snapback = (px[rec_hi] / px[t_idx] - 1.0) if px[t_idx] > 0 else 0.0
    # also pre-crash baseline exposure (20 bars before window start)
    pre_lo = max(0, lo - 20)
    pre_exps = exposure[pre_lo:lo] if lo > pre_lo else [exposure[lo]]
    mean_exp_pre = sum(pre_exps) / len(pre_exps) if pre_exps else 0.0
    capture = None
    if blend_r is not None:
        gov = 1.0
        und = 1.0
        for i in range(t_idx + 1, rec_hi + 1):
            gov *= (1.0 + exposure[i] * blend_r[i])
            und *= (1.0 + blend_r[i])
        gr = gov - 1.0
        ur = und - 1.0
        capture = round(gr / ur, 3) if abs(ur) > 1e-9 else None
    return {
        "trough_date": dates[t_idx],
        "exp_pre_crash": round(mean_exp_pre, 4),
        "exp_at_trough": round(exp_at_trough, 4),
        "exp_mean_recovery": round(mean_exp_recov, 4),
        "spx_snapback_pct": round(spx_snapback * 100.0, 2),
        "recov_window": [dates[t_idx], dates[rec_hi]],
        "recovery_capture_ratio": capture,
        "deleveraged_into_v": bool(mean_exp_recov < 0.5 and spx_snapback > 0.08),
    }


def floored_episodes(exposure, low_thresh=0.10):
    """Count contiguous episodes where exposure sat at/under low_thresh (near-
    cash 'floored'), and the longest such run in bars. Chronic flooring =
    structurally de-risked = missing market exposure."""
    episodes = 0
    longest = 0
    cur = 0
    days_floored = 0
    for e in exposure:
        if e <= low_thresh:
            days_floored += 1
            cur += 1
            if cur == 1:
                episodes += 1
            if cur > longest:
                longest = cur
        else:
            cur = 0
    return {"episodes": episodes, "longest_run_bars": longest,
            "days_floored": days_floored, "pct_floored": None}


def cppi_block(dates, res, spx_r):
    fb = full_block(dates, res["rets"], spx_r, res["cost_total"], res["n_turn_events"])
    fb["turnover_total_units"] = res["turnover_total"]
    fl = floored_episodes(res["exposure"], 0.10)
    fl["pct_floored"] = round(100.0 * fl["days_floored"] / max(1, len(res["exposure"])), 2)
    fb["floored"] = fl
    exps = res["exposure"]
    fb["exposure_mean"] = round(sum(exps) / len(exps), 4)
    fb["exposure_min"] = round(min(exps), 4)
    return fb


def main():
    C = load_cache()
    dates = C["dates"]
    g_r = C["g_r"]
    spx_r = C["spx_r"]
    tqqq_r = C["tqqq_r"]
    rot_r = C["rot_r"]
    month_open = C["month_open"]
    nn = len(dates)

    # ---- benchmark 1: incumbent binary -10%-DD/wh15 gate ----
    binary = run_binary_gate(dates, tqqq_r, rot_r, spx_r, month_open)
    binary_block = full_block(dates, binary["rets"], spx_r, binary["cost_total"],
                              binary["n_turn_events"])
    binary_block["turnover_total_units"] = binary["turnover_total"]

    # ---- benchmark 2: ungated always-on 2-sleeve blend (no protection) ----
    # g_r IS the ungated blend's daily return stream (built in the cache). Its
    # turnover cost is already embedded in g_r (blend_portfolio charged 2bps).
    ungated_block = full_block(dates, g_r, spx_r, 0.0, 0)
    ungated_block["turnover_total_units"] = C.get("ungated_avg_turnover_per_rebal", 0.0) * C.get("ungated_n_rebal", 0)
    ungated_block["note"] = "always-on; turnover cost already embedded in g_r (monthly inter-sleeve only)"

    # ---- CPPI grid sweep ----
    floors = [0.80, 0.85, 0.90]
    mults = [3, 4, 5]
    tipps = [True, False]
    grid = []
    for fr in floors:
        for m in mults:
            for tipp in tipps:
                res = run_cppi(dates, g_r, fr, m, tipp)
                blk = cppi_block(dates, res, spx_r)
                cell = {
                    "floor_ratio": fr, "m": m, "tipp": tipp,
                    "fp_sharpe": blk["fp_sharpe"],
                    "cagr_pct": blk["cagr_pct"],
                    "maxdd_pct": blk["maxdd_pct"],
                    "vol_pct": blk["vol_pct"],
                    "total_return_pct": blk["total_return_pct"],
                    "spy_corr": blk["spy_corr"],
                    "turnover_units": blk["turnover_total_units"],
                    "turnover_cost_pct": blk["turnover_cost_total_pct"],
                    "oos_2019_sharpe": (blk["oos_2019"] or {}).get("sharpe"),
                    "oos_2019_maxdd": (blk["oos_2019"] or {}).get("maxdd_pct"),
                    "oos_2020_sharpe": (blk["oos_2020"] or {}).get("sharpe"),
                    "oos_2020_maxdd": (blk["oos_2020"] or {}).get("maxdd_pct"),
                    "exposure_mean": blk["exposure_mean"],
                    "pct_floored": blk["floored"]["pct_floored"],
                    "longest_floored_bars": blk["floored"]["longest_run_bars"],
                    "_full_block": blk,
                }
                grid.append(cell)

    # ---- pick BEST honest config: maximize full-period FP-Sharpe, tie-break by
    # better (less negative) maxDD. This is the risk-adjusted ranking the verdict
    # bar uses (FP-Sharpe and/or maxDD-per-unit-return). ----
    def rank_key(c):
        return (round(c["fp_sharpe"], 4), c["maxdd_pct"])
    best = max(grid, key=rank_key)

    # A config is DEGENERATE (CPPI-in-name-only) if it basically never deleverages
    # (mean exposure ~ 1.0 over the path) -> it just reproduces the ungated blend
    # and trivially 'wins' maxDD by being identical to it. A config PROTECTS only
    # if it actually cuts mean exposure materially below 1.0.
    for c in grid:
        c["degenerate_noop"] = bool(c["exposure_mean"] >= 0.98 and c["maxdd_pct"] <= -19.0)
    protective = [c for c in grid if c["exposure_mean"] < 0.95]
    best_prot = max(protective, key=rank_key) if protective else best
    def dd_eff(c):
        cg = c["cagr_pct"]
        return abs(c["maxdd_pct"]) / cg if cg and cg > 0 else float("inf")
    best_prot_eff = min(protective, key=dd_eff) if protective else best
    # the HARDEST-flooring config (lowest mean exposure) -- where the lethal
    # deleverage-into-V failure would show most clearly. Among configs that
    # actually cut maxDD into single digits (real tail protection).
    real_floor = [c for c in grid if c["maxdd_pct"] > -15.0]
    hardest = min(real_floor, key=lambda c: c["exposure_mean"]) if real_floor else best_prot

    # ---- +1-bar canary on the BEST config (lethal test) ----
    best_lag = run_cppi(dates, g_r, best["floor_ratio"], best["m"], best["tipp"],
                        extra_lag=1)
    best_lag_blk = cppi_block(dates, best_lag, spx_r)

    # also canary on the best-by-maxDD config (the protection use-case)
    best_dd = min(grid, key=lambda c: (c["maxdd_pct"], -c["fp_sharpe"]))
    best_dd_lag = run_cppi(dates, g_r, best_dd["floor_ratio"], best_dd["m"], best_dd["tipp"],
                           extra_lag=1)
    best_dd_lag_blk = cppi_block(dates, best_dd_lag, spx_r)

    # canary on the best PROTECTIVE config (the config that ACTUALLY floors)
    best_prot_lag = run_cppi(dates, g_r, best_prot["floor_ratio"], best_prot["m"],
                             best_prot["tipp"], extra_lag=1)
    best_prot_lag_blk = cppi_block(dates, best_prot_lag, spx_r)

    # ---- V-bottom failure-mode probes on the BEST config ----
    best_res = run_cppi(dates, g_r, best["floor_ratio"], best["m"], best["tipp"])
    best_dd_res = run_cppi(dates, g_r, best_dd["floor_ratio"], best_dd["m"], best_dd["tipp"])
    best_prot_res = run_cppi(dates, g_r, best_prot["floor_ratio"], best_prot["m"], best_prot["tipp"])
    hardest_res = run_cppi(dates, g_r, hardest["floor_ratio"], hardest["m"], hardest["tipp"])
    vb_windows = {
        "2018_Q4": ("2018-10-01", "2018-12-31"),
        "2020_COVID_V": ("2020-02-01", "2020-04-30"),
        "2022_slow_bear": ("2022-01-01", "2022-10-31"),
    }
    vbottom_best = {k: vbottom_probe(dates, spx_r, best_res["exposure"], a, b, blend_r=g_r)
                    for k, (a, b) in vb_windows.items()}
    vbottom_bestdd = {k: vbottom_probe(dates, spx_r, best_dd_res["exposure"], a, b, blend_r=g_r)
                      for k, (a, b) in vb_windows.items()}
    vbottom_prot = {k: vbottom_probe(dates, spx_r, best_prot_res["exposure"], a, b, blend_r=g_r)
                    for k, (a, b) in vb_windows.items()}
    vbottom_hardest = {k: vbottom_probe(dates, spx_r, hardest_res["exposure"], a, b, blend_r=g_r)
                       for k, (a, b) in vb_windows.items()}
    prot_floored = floored_episodes(best_prot_res["exposure"], 0.50)
    prot_floored["pct_under_0p5"] = round(100.0 * prot_floored["days_floored"] / max(1, nn), 2)
    hardest_floored = floored_episodes(hardest_res["exposure"], 0.50)
    hardest_floored["pct_under_0p5"] = round(100.0 * hardest_floored["days_floored"] / max(1, nn), 2)

    out = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window": [dates[0], dates[-1]], "n_days": nn,
            "cost_bps_per_turnover_unit": COST_BPS,
            "is_oos_splits": {"primary_2019": OOS_2019, "secondary_2020": OOS_2020},
            "engine": "_allocator_blend_tests.build_sleeves/blend_portfolio (cached) + CPPI daily governor",
            "risky_asset": "ungated smooth_3mo inv-vol 2-sleeve blend (TQQQ-voltarget + sector-rot top2)",
        },
        "benchmarks": {
            "binary_gate_wh15": binary_block,
            "ungated_2sleeve": ungated_block,
        },
        "cppi_grid": [{k: v for k, v in c.items() if k != "_full_block"} for c in grid],
        "cppi_best_by_fpsharpe": {k: v for k, v in best.items() if k != "_full_block"},
        "cppi_best_full_block": best["_full_block"],
        "cppi_best_canary_lag1": best_lag_blk,
        "cppi_best_by_maxdd": {k: v for k, v in best_dd.items() if k != "_full_block"},
        "cppi_best_by_maxdd_full_block": best_dd["_full_block"],
        "cppi_best_by_maxdd_canary_lag1": best_dd_lag_blk,
        "cppi_best_protective": {k: v for k, v in best_prot.items() if k != "_full_block"},
        "cppi_best_protective_full_block": best_prot["_full_block"],
        "cppi_best_protective_canary_lag1": best_prot_lag_blk,
        "cppi_best_protective_by_ddeff": {k: v for k, v in best_prot_eff.items() if k != "_full_block"},
        "cppi_best_protective_floored_under_0p5": prot_floored,
        "cppi_hardest_floor_config": {k: v for k, v in hardest.items() if k != "_full_block"},
        "cppi_hardest_floor_full_block": hardest["_full_block"],
        "cppi_hardest_floored_under_0p5": hardest_floored,
        "vbottom_best_by_fpsharpe": vbottom_best,
        "vbottom_best_by_maxdd": vbottom_bestdd,
        "vbottom_best_protective": vbottom_prot,
        "vbottom_hardest_floor": vbottom_hardest,
    }
    with open("reports/_cppi_result.json", "w") as fjson:
        json.dump(out, fjson, indent=2, default=lambda o: None)
    print("RESULT JSON written: reports/_cppi_result.json")
    # compact console summary
    print("\n=== BENCHMARKS (full period %s..%s, %d days) ===" % (dates[0], dates[-1], nn))
    for nm, b in (("binary_gate_wh15", binary_block), ("ungated_2sleeve", ungated_block)):
        print("  %-18s FP-Sharpe %.4f CAGR %.2f%% maxDD %.2f%% vol %.2f%% turnoverUnits %.2f cost %.3f%%" % (
            nm, b["fp_sharpe"], b["cagr_pct"], b["maxdd_pct"], b["vol_pct"],
            b["turnover_total_units"], b["turnover_cost_total_pct"]))
    print("\n=== CPPI GRID (sorted by FP-Sharpe desc) ===")
    for c in sorted(grid, key=lambda x: -x["fp_sharpe"]):
        print("  fr=%.2f m=%d tipp=%-5s | FP-Sh %.4f CAGR %.2f%% maxDD %.2f%% turnUnits %.1f cost %.3f%% exp_mean %.2f floored%% %.1f" % (
            c["floor_ratio"], c["m"], str(c["tipp"]), c["fp_sharpe"], c["cagr_pct"],
            c["maxdd_pct"], c["turnover_units"], c["turnover_cost_pct"],
            c["exposure_mean"], c["pct_floored"]))
    print("\nBEST by FP-Sharpe: fr=%.2f m=%d tipp=%s  FP-Sh %.4f vs binary %.4f vs ungated %.4f" % (
        best["floor_ratio"], best["m"], best["tipp"], best["fp_sharpe"],
        binary_block["fp_sharpe"], ungated_block["fp_sharpe"]))
    print("  canary lag+1 FP-Sharpe: %.4f (delta %.4f)" % (
        best_lag_blk["fp_sharpe"], best_lag_blk["fp_sharpe"] - best["fp_sharpe"]))
    print("BEST by maxDD: fr=%.2f m=%d tipp=%s  maxDD %.2f%% (binary %.2f%% ungated %.2f%%) FP-Sh %.4f degenerate_noop=%s" % (
        best_dd["floor_ratio"], best_dd["m"], best_dd["tipp"], best_dd["maxdd_pct"],
        binary_block["maxdd_pct"], ungated_block["maxdd_pct"], best_dd["fp_sharpe"],
        best_dd.get("degenerate_noop")))
    print("BEST PROTECTIVE (exp_mean<0.95): fr=%.2f m=%d tipp=%s FP-Sh %.4f CAGR %.2f%% maxDD %.2f%% turnUnits %.1f cost %.3f%% | canary lag+1 FP-Sh %.4f (d %.4f)" % (
        best_prot["floor_ratio"], best_prot["m"], best_prot["tipp"], best_prot["fp_sharpe"],
        best_prot["cagr_pct"], best_prot["maxdd_pct"], best_prot["turnover_units"],
        best_prot["turnover_cost_pct"], best_prot_lag_blk["fp_sharpe"],
        best_prot_lag_blk["fp_sharpe"] - best_prot["fp_sharpe"]))
    print("\n=== V-BOTTOM PROBE (best-by-FP-Sharpe exposure) ===")
    for k, v in vbottom_best.items():
        if v:
            print("  %-14s trough %s exp_pre %.2f exp_trough %.2f exp_recov %.2f spx_snapback %.1f%% deleveraged_into_v=%s" % (
                k, v["trough_date"], v["exp_pre_crash"], v["exp_at_trough"],
                v["exp_mean_recovery"], v["spx_snapback_pct"], v["deleveraged_into_v"]))
    print("\n=== V-BOTTOM PROBE (HARDEST-flooring config fr=%.2f m=%d tipp=%s maxDD %.2f%% exp_mean %.2f -- where deleverage-into-V would show) ===" % (
        hardest["floor_ratio"], hardest["m"], hardest["tipp"], hardest["maxdd_pct"], hardest["exposure_mean"]))
    for k, v in vbottom_hardest.items():
        if v:
            print("  %-14s trough %s exp_pre %.2f exp_trough %.2f exp_recov %.2f spx_snapback %.1f%% capture=%s deleveraged_into_v=%s" % (
                k, v["trough_date"], v["exp_pre_crash"], v["exp_at_trough"],
                v["exp_mean_recovery"], v["spx_snapback_pct"], v["recovery_capture_ratio"], v["deleveraged_into_v"]))
    print("  [hardest] days at exposure<=0.5: %d (%.1f%% of path); longest floored run %d bars" % (
        hardest_floored["days_floored"], hardest_floored["pct_under_0p5"], hardest_floored["longest_run_bars"]))
    print("  [best-protective] days at exposure<=0.5: %d (%.1f%% of path); longest floored run %d bars" % (
        prot_floored["days_floored"], prot_floored["pct_under_0p5"], prot_floored["longest_run_bars"]))
    return out


if __name__ == "__main__":
    main()
