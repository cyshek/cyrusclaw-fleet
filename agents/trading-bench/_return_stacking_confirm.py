"""CONFIRM-OR-KILL: RETURN STACKING (portable-alpha overlay) on validated sleeves.

Mechanism (ReturnStacked.com published MONTHLY formula):
    R_stacked,t = R_core,t + StackSize * (R_div,t - Fee/12 - (R_TBill,t + Financing/12))

  R_core = CORE sleeve monthly return  = sector-rotation top-2 {SPY,QQQ,GLD,TLT}
           (_sigimprove_tests.run_sector_rotation, hold_top=2, lookback_months=3,
            cost_bps=2, start=2005-01-01). The VALIDATED rotation sleeve.
  R_div  = DIVERSIFIER sleeve monthly return = TQQQ vol-target sleeve
           (strategies_candidates/leveraged_long_trend/backtest_daily_voltarget,
            EXACT config reused from _allocator_blend_tests.build_sleeves:
            target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
            vix_gate=False, switch_cost_bps=2, breadth_windows=[30,90,180]).
  R_TBill = 3M T-bill financing, FRED DGS3MO (percent, daily) -> monthly = v/100/12.
  StackSize in {0.5, 1.0}.  Fee = 0 (we run our own sleeves).
  Financing spread = 0.50%/yr (50bp) added on top of the T-bill.

This is a PURE ARITHMETIC OVERLAY on monthly series we already compute. No
leverage product, no new price data beyond the T-bill rate.

THE KEY QUESTION: does stacked@X reach a risk/return point that a sum-to-1
inv-vol blend of the SAME two sleeves CANNOT, AFTER realistic financing drag,
OOS (2020+)? Financing drag is the falsifiable killer and is quantified in bps/yr.

Reference "best current point" = the inv-vol (63d) monthly-rebalanced blend of
[TQQQ-voltarget, rotation] from _allocator_blend_tests (sum-to-1, no financing).

Outputs:
  reports/_return_stacking_result.json   (all numbers, machine-readable)
  reports/RETURN_STACKING_VERDICT_<UTCSTAMP>.md  (verdict + tables)

Run: python3 _return_stacking_confirm.py
Research only. Does NOT touch protected files / strategies / dbs / cron.
"""
from __future__ import annotations

import json
import math
import sys
import datetime as _dt
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from runner import fred_cache as fc
from runner import fp_sharpe as fps
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, run_backtest_voltarget,
)
from _sigimprove_tests import run_sector_rotation

# ---- knobs ----
FINANCING_SPREAD_ANNUAL = 0.0050   # 50 bp/yr over T-bill
FEE_ANNUAL = 0.0                   # we run our own sleeves
STACK_SIZES = [0.5, 1.0]
OOS_START = "2020-01-01"           # task: train through 2019, OOS 2020+
IS_END = "2019-12-31"
BLEND_OOS_SPLIT = "2019-01-01"     # the blend file's native OOS split (for x-ref)
TRADING_DAYS = 252
MONTHS_PER_YEAR = 12


# --------------------------------------------------------------------------- #
# Series construction
# --------------------------------------------------------------------------- #
def equity_to_daily_ret_map(dates: List[str], equity: List[float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for i in range(1, len(dates)):
        if equity[i - 1] != 0:
            out[dates[i]] = equity[i] / equity[i - 1] - 1.0
    return out


def build_daily_sleeves() -> Dict:
    """Reproduce core (rotation) + diversifier (voltarget) + SPX daily return
    streams on a COMMON calendar (TQQQ-inception bounded), EXACTLY as
    _allocator_blend_tests.build_sleeves does."""
    vt = run_backtest_voltarget(VolTargetParams(
        target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
        vix_gate=False, switch_cost_bps=2.0,
        breadth_windows=[30, 90, 180]))
    div_dates = vt["strategy"]["dates"]
    div_eq = vt["strategy"]["equity"]
    div_ret = equity_to_daily_ret_map(div_dates, div_eq)
    spx_eq = vt["spx"]["equity"]
    spx_ret = equity_to_daily_ret_map(div_dates, spx_eq)

    rot = run_sector_rotation(["SPY", "QQQ", "GLD", "TLT"], bench="^GSPC",
                              cost_bps=2.0, start="2005-01-01",
                              hold_top=2, lookback_months=3)
    rot_dates = rot["strategy"]["dates"]
    rot_eq = rot["strategy"]["equity"]
    rot_ret = equity_to_daily_ret_map(rot_dates, rot_eq)

    common = sorted(set(div_ret) & set(rot_ret) & set(spx_ret))
    return {
        "common": common,
        "core_r": [rot_ret[d] for d in common],     # core = rotation
        "div_r":  [div_ret[d] for d in common],     # diversifier = voltarget
        "spx_r":  [spx_ret[d] for d in common],
        "div_solo_stats": vt["strategy"]["stats"],
        "rot_solo_stats": rot["strategy"]["stats"],
        "div_full_window": (div_dates[0], div_dates[-1]),
        "rot_full_window": (rot_dates[0], rot_dates[-1]),
    }


def tbill_daily_map(start: str, end: str) -> Dict[str, float]:
    """FRED DGS3MO (percent, daily) -> {date: ANNUAL decimal rate}, forward-filled.

    Units VERIFIED: DGS3MO is in PERCENT (e.g. 3.87 == 3.87%/yr). We return the
    ANNUAL decimal (v/100) per date; daily/monthly conversion happens at apply
    time. Forward-fill across non-publish days (weekends/holidays/'.' gaps) so
    every market date maps to the most recent published rate. vintage='latest':
    a financing RATE is a market quote, effectively un-revised; PIT vintage adds
    nothing here (noted in report)."""
    rows = fc.get_series("DGS3MO", start, end, vintage="latest")
    out: Dict[str, float] = {}
    last: Optional[float] = None
    for r in rows:
        v = r["value"]
        if v is not None:
            last = v / 100.0
        if last is not None:
            out[r["date"]] = last
    return out


def ffill_rate_for_dates(rate_map: Dict[str, float], dates: List[str]) -> List[float]:
    """Align an annual-rate map to an explicit date list, forward-filling. For a
    date earlier than the first rate, use the first available rate."""
    keys = sorted(rate_map.keys())
    out: List[float] = []
    import bisect
    first_rate = rate_map[keys[0]] if keys else 0.0
    for d in dates:
        j = bisect.bisect_right(keys, d) - 1
        out.append(rate_map[keys[j]] if j >= 0 else first_rate)
    return out


# --------------------------------------------------------------------------- #
# Monthly resampling
# --------------------------------------------------------------------------- #
def to_monthly_returns(dates: List[str], daily_rets: List[float]) -> Tuple[List[str], List[float]]:
    """Compound daily simple returns within each calendar month. Returns
    (month_end_label, monthly_return). month label = last trading date in month."""
    by_month: Dict[str, List[Tuple[str, float]]] = {}
    order: List[str] = []
    for d, r in zip(dates, daily_rets):
        ym = d[:7]
        if ym not in by_month:
            by_month[ym] = []
            order.append(ym)
        by_month[ym].append((d, r))
    m_labels: List[str] = []
    m_rets: List[float] = []
    for ym in order:
        comp = 1.0
        for _, r in by_month[ym]:
            comp *= (1.0 + r)
        m_labels.append(by_month[ym][-1][0])
        m_rets.append(comp - 1.0)
    return m_labels, m_rets


def monthly_avg_rate(dates: List[str], daily_annual_rate: List[float]) -> Tuple[List[str], List[float]]:
    """Per calendar month, the average ANNUAL T-bill rate over that month's
    trading days. Returned aligned to the same month labels as to_monthly_returns."""
    by_month: Dict[str, List[Tuple[str, float]]] = {}
    order: List[str] = []
    for d, r in zip(dates, daily_annual_rate):
        ym = d[:7]
        if ym not in by_month:
            by_month[ym] = []
            order.append(ym)
        by_month[ym].append((d, r))
    labels: List[str] = []
    rates: List[float] = []
    for ym in order:
        vals = [r for _, r in by_month[ym]]
        labels.append(by_month[ym][-1][0])
        rates.append(sum(vals) / len(vals) if vals else 0.0)
    return labels, rates


# --------------------------------------------------------------------------- #
# Stacking
# --------------------------------------------------------------------------- #
def stack_monthly(core_m: List[float], div_m: List[float], tbill_annual_m: List[float],
                  stack_size: float, financing_annual: float, fee_annual: float) -> List[float]:
    """Published MONTHLY formula:
        R_stacked = R_core + S*(R_div - Fee/12 - (R_TBill_month + Financing/12))
    R_TBill_month = annual_rate/12 (the monthly cost of the T-bill leg).
    """
    out: List[float] = []
    for rc, rd, ann in zip(core_m, div_m, tbill_annual_m):
        tbill_month = ann / MONTHS_PER_YEAR
        cost = fee_annual / MONTHS_PER_YEAR + (tbill_month + financing_annual / MONTHS_PER_YEAR)
        out.append(rc + stack_size * (rd - cost))
    return out


def stack_daily(core_d: List[float], div_d: List[float], tbill_annual_d: List[float],
                stack_size: float, financing_annual: float, fee_annual: float) -> List[float]:
    """Daily analogue (financing accrues per trading day). Used only to produce a
    DAILY-annualized Sharpe directly comparable to the existing inv-vol blend
    reference (whose Sharpe is daily/sqrt(252)). Economically identical overlay;
    the published monthly formula is its month-aggregation."""
    out: List[float] = []
    for rc, rd, ann in zip(core_d, div_d, tbill_annual_d):
        tbill_day = ann / TRADING_DAYS
        cost = fee_annual / TRADING_DAYS + (tbill_day + financing_annual / TRADING_DAYS)
        out.append(rc + stack_size * (rd - cost))
    return out


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def equity_from_returns(rets: List[float]) -> List[float]:
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1.0 + r))
    return eq


def maxdd(equity: List[float]) -> float:
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = v / peak - 1.0
            if dd < mdd:
                mdd = dd
    return mdd  # negative


def ann_return_from_monthly(rets: List[float]) -> Tuple[float, float]:
    """(total_return, annualized_return) from a monthly return series."""
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    total = eq - 1.0
    yrs = len(rets) / MONTHS_PER_YEAR
    ann = (eq ** (1.0 / yrs) - 1.0) if yrs > 0 and eq > 0 else float("nan")
    return total, ann


def ann_return_from_daily(rets: List[float]) -> Tuple[float, float]:
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    total = eq - 1.0
    yrs = len(rets) / TRADING_DAYS
    ann = (eq ** (1.0 / yrs) - 1.0) if yrs > 0 and eq > 0 else float("nan")
    return total, ann


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


def slice_by_date(labels: List[str], series: List[float], start: str, end: str) -> Tuple[List[str], List[float]]:
    out_l, out_s = [], []
    for lbl, v in zip(labels, series):
        if start <= lbl <= end:
            out_l.append(lbl)
            out_s.append(v)
    return out_l, out_s


def metrics_monthly(labels: List[str], m_rets: List[float], spx_m: List[float]) -> Dict:
    """Full metric block on a MONTHLY return series. Sharpe via canonical
    fps.sharpe_from_returns (the load-bearing primitive) with bpy=12 (excess=0,
    matching the bench Sharpe convention). maxDD on the monthly equity curve."""
    eq = equity_from_returns(m_rets)
    total, ann = ann_return_from_monthly(m_rets)
    sh = fps.sharpe_from_returns(m_rets, MONTHS_PER_YEAR)
    vol = (math.sqrt(sum((r - sum(m_rets) / len(m_rets)) ** 2 for r in m_rets) / (len(m_rets) - 1))
           * math.sqrt(MONTHS_PER_YEAR)) if len(m_rets) > 1 else 0.0
    corr = pearson(m_rets, spx_m) if spx_m and len(spx_m) == len(m_rets) else None
    return {
        "n_months": len(m_rets),
        "sharpe": sh,
        "ann_return_pct": ann * 100.0,
        "total_return_pct": total * 100.0,
        "ann_vol_pct": vol * 100.0,
        "maxdd_pct": maxdd(eq) * 100.0,
        "spy_corr": corr,
    }


def metrics_daily(d_rets: List[float], spx_d: List[float]) -> Dict:
    eq = equity_from_returns(d_rets)
    total, ann = ann_return_from_daily(d_rets)
    sh = fps.sharpe_from_returns(d_rets, TRADING_DAYS)
    mean = sum(d_rets) / len(d_rets)
    vol = (math.sqrt(sum((r - mean) ** 2 for r in d_rets) / (len(d_rets) - 1))
           * math.sqrt(TRADING_DAYS)) if len(d_rets) > 1 else 0.0
    corr = pearson(d_rets, spx_d) if spx_d and len(spx_d) == len(d_rets) else None
    return {
        "n_days": len(d_rets),
        "sharpe_daily_ann": sh,
        "ann_return_pct": ann * 100.0,
        "total_return_pct": total * 100.0,
        "ann_vol_pct": vol * 100.0,
        "maxdd_pct": maxdd(eq) * 100.0,
        "spy_corr": corr,
    }


def split_metrics(labels: List[str], m_rets: List[float], spx_labels: List[str],
                  spx_m: List[float]) -> Dict:
    """Full / IS (<=2019) / OOS (>=2020) monthly metric blocks, common to a series."""
    spx_map = dict(zip(spx_labels, spx_m))
    def aligned_spx(lbls):
        return [spx_map.get(l, 0.0) for l in lbls]
    full = metrics_monthly(labels, m_rets, aligned_spx(labels))
    is_l, is_r = slice_by_date(labels, m_rets, "1900-01-01", IS_END)
    oos_l, oos_r = slice_by_date(labels, m_rets, OOS_START, "2099-12-31")
    is_m = metrics_monthly(is_l, is_r, aligned_spx(is_l)) if len(is_r) > 2 else {"n_months": len(is_r)}
    oos_m = metrics_monthly(oos_l, oos_r, aligned_spx(oos_l)) if len(oos_r) > 2 else {"n_months": len(oos_r)}
    return {"full": full, "is_thru2019": is_m, "oos_2020plus": oos_m}


# --------------------------------------------------------------------------- #
# Inv-vol blend reference (sum-to-1, monthly rebalance, NO financing)
# --------------------------------------------------------------------------- #
def annualized_vol_daily(returns: List[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def invvol_blend_daily(common: List[str], core_r: List[float], div_r: List[float],
                       lookback: int = 63, blend_cost_bps: float = 2.0) -> List[float]:
    """Reproduce the inv-vol (63d) monthly-rebalanced, drift-between blend of
    [div, core] EXACTLY as _allocator_blend_tests.blend_portfolio + invvol_wfn.
    Returns the blend's DAILY return series aligned to common[1:] (i.e. the
    return earned ending each date). Sum-to-1 weights, no financing.

    NOTE on sleeve order: _allocator_blend_tests uses sleeves=[tqqq_r, rot_r]
    (index0=div, index1=core). We mirror that ordering so the inv-vol tilt is
    identical to the validated reference."""
    sleeves = [div_r, core_r]
    ns = 2
    n = len(common)
    month_open = []
    seen = set()
    for i, d in enumerate(common):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open.append(i)
    month_open_set = set(month_open)

    def wfn(idx):
        if idx < 2:
            return [0.5, 0.5]
        lo = max(0, idx - lookback)
        v0 = annualized_vol_daily(sleeves[0][lo:idx])
        v1 = annualized_vol_daily(sleeves[1][lo:idx])
        if v0 <= 0 or v1 <= 0:
            return [0.5, 0.5]
        iv0, iv1 = 1.0 / v0, 1.0 / v1
        s = iv0 + iv1
        return [iv0 / s, iv1 / s]

    equity = [1.0]
    w = wfn(0)
    bucket = [w[k] for k in range(ns)]
    daily_ret: List[float] = []
    for i in range(1, n):
        if i in month_open_set:
            tot = sum(bucket)
            cur_w = [b / tot for b in bucket] if tot > 0 else [0.0] * ns
            tgt = wfn(i)
            turn = sum(abs(tgt[k] - cur_w[k]) for k in range(ns))
            cost = (blend_cost_bps / 10000.0) * turn
            tot_after = tot * (1.0 - cost)
            bucket = [tgt[k] * tot_after for k in range(ns)]
        prev = equity[-1]
        for k in range(ns):
            bucket[k] *= (1.0 + sleeves[k][i])
        cur = sum(bucket)
        equity.append(cur)
        daily_ret.append(cur / prev - 1.0 if prev != 0 else 0.0)
    # daily_ret aligned to common[1:]
    return daily_ret


# --------------------------------------------------------------------------- #
# Canary: lag the DIVERSIFIER signal one extra trading day.
# The voltarget sleeve has daily timing (gate + vol size). Lagging its daily
# return stream by one bar simulates acting one bar late on its signal; if the
# stacked lift survives, it is not a one-bar-lookahead artifact.
# --------------------------------------------------------------------------- #
def lag_one_bar(series: List[float]) -> List[float]:
    """Shift a daily return series forward one bar (act one day late): r'[i]=r[i-1],
    r'[0]=0. Length preserved."""
    if not series:
        return series
    return [0.0] + series[:-1]


# --------------------------------------------------------------------------- #
# DRIVER
# --------------------------------------------------------------------------- #
def main() -> Dict:
    print(">>> Building daily sleeves (core=rotation, div=voltarget) ...", flush=True)
    S = build_daily_sleeves()
    common = S["common"]
    core_d = S["core_r"]
    div_d = S["div_r"]
    spx_d = S["spx_r"]
    print("    common window: %s -> %s  (%d days)" % (common[0], common[-1], len(common)))

    # T-bill annual rate aligned to common dates (daily, forward-filled)
    tb_map = tbill_daily_map(common[0], common[-1])
    tb_annual_d = ffill_rate_for_dates(tb_map, common)
    avg_tb = sum(tb_annual_d) / len(tb_annual_d)
    print("    DGS3MO avg annual rate over window: %.3f%%" % (avg_tb * 100.0))

    # ---- monthly series ----
    m_lbl, core_m = to_monthly_returns(common, core_d)
    _, div_m = to_monthly_returns(common, div_d)
    _, spx_m = to_monthly_returns(common, spx_d)
    tb_lbl, tb_annual_m = monthly_avg_rate(common, tb_annual_d)
    assert m_lbl == tb_lbl, "month label mismatch core vs tbill"

    out: Dict = {}
    out["meta"] = {
        "common_window": [common[0], common[-1]],
        "n_days": len(common),
        "n_months": len(m_lbl),
        "core_sleeve": "sector_rotation_top2 {SPY,QQQ,GLD,TLT} L3 hold2 (validated)",
        "div_sleeve": "TQQQ voltarget tgt0.25 vw20 sma200 breadth[30,90,180] (validated)",
        "financing_spread_annual_bps": FINANCING_SPREAD_ANNUAL * 10000,
        "fee_annual_bps": FEE_ANNUAL * 10000,
        "tbill_series": "FRED DGS3MO (percent, daily, vintage=latest=market-quote)",
        "tbill_avg_annual_pct": avg_tb * 100.0,
        "is_oos_split": {"is_thru": IS_END, "oos_from": OOS_START},
        "div_full_window": list(S["div_full_window"]),
        "rot_full_window": list(S["rot_full_window"]),
    }

    # ---- (i) CORE alone ----
    out["core_alone"] = split_metrics(m_lbl, core_m, m_lbl, spx_m)
    # ---- (iv) SPX benchmark ----
    out["spx_benchmark"] = split_metrics(m_lbl, spx_m, m_lbl, spx_m)
    # ---- diversifier solo (context) ----
    out["div_alone"] = split_metrics(m_lbl, div_m, m_lbl, spx_m)

    # ---- (ii,iii) STACKED @ each size ----
    out["stacked"] = {}
    out["stacked_canary_divlag1"] = {}
    # financing drag in bps/yr = StackSize * (Tbill_avg + Financing) applied to
    # the diversifier notional. The pure SPREAD drag (the part inv-vol blending
    # avoids by being unlevered) = StackSize * (Tbill_avg + Financing) - but the
    # T-bill portion is the cost of money the overlay borrows; the ECONOMIC drag
    # vs an unlevered sum-to-1 blend is the full borrow cost on the stacked
    # notional. We report total borrow cost bps/yr = S*(avg_tbill+financing).
    for s in STACK_SIZES:
        stk_m = stack_monthly(core_m, div_m, tb_annual_m, s, FINANCING_SPREAD_ANNUAL, FEE_ANNUAL)
        out["stacked"]["@%.1f" % s] = split_metrics(m_lbl, stk_m, m_lbl, spx_m)
        borrow_bps = s * (avg_tb + FINANCING_SPREAD_ANNUAL) * 10000.0
        spread_only_bps = s * FINANCING_SPREAD_ANNUAL * 10000.0
        out["stacked"]["@%.1f" % s]["financing_drag"] = {
            "total_borrow_cost_bps_per_yr": borrow_bps,
            "spread_only_bps_per_yr": spread_only_bps,
            "note": ("total = StackSize*(avg_Tbill+spread) on the stacked notional; "
                     "this is the gross cost the diversifier leg must out-earn."),
        }
        # canary: lag the diversifier daily stream one bar, re-aggregate monthly, re-stack
        div_d_lag = lag_one_bar(div_d)
        _, div_m_lag = to_monthly_returns(common, div_d_lag)
        stk_m_lag = stack_monthly(core_m, div_m_lag, tb_annual_m, s, FINANCING_SPREAD_ANNUAL, FEE_ANNUAL)
        out["stacked_canary_divlag1"]["@%.1f" % s] = split_metrics(m_lbl, stk_m_lag, m_lbl, spx_m)

    # ---- (v) inv-vol blend reference (DAILY + monthly) ----
    print(">>> Reproducing inv-vol(63d) sum-to-1 blend reference ...", flush=True)
    blend_daily = invvol_blend_daily(common, core_d, div_d, lookback=63, blend_cost_bps=2.0)
    blend_dates = common[1:]
    bl_lbl, blend_m = to_monthly_returns(blend_dates, blend_daily)
    # spx monthly aligned to blend month labels
    spx_map_m = dict(zip(m_lbl, spx_m))
    out["invvol_blend_reference"] = split_metrics(bl_lbl, blend_m,
                                                  list(spx_map_m.keys()), list(spx_map_m.values()))
    out["invvol_blend_reference"]["note"] = ("sum-to-1 monthly-rebalanced inv-vol(63d) "
        "blend of [voltarget, rotation]; NO financing. The best current point a "
        "sum-to-1 blend can reach.")

    # ---- DAILY-annualized comparison block (apples-to-apples vs blend's daily Sharpe) ----
    out["daily_annualized_xref"] = {"note": "Sharpe here is daily/sqrt(252), directly comparable to the bench's reported sleeve/blend Sharpes."}
    out["daily_annualized_xref"]["core_alone"] = metrics_daily(core_d, spx_d)
    out["daily_annualized_xref"]["invvol_blend"] = metrics_daily(blend_daily, spx_d[1:])
    for s in STACK_SIZES:
        stk_d = stack_daily(core_d, div_d, tb_annual_d, s, FINANCING_SPREAD_ANNUAL, FEE_ANNUAL)
        out["daily_annualized_xref"]["stacked@%.1f" % s] = metrics_daily(stk_d, spx_d)
        # OOS daily slice
        oos_idx = [i for i, d in enumerate(common) if d >= OOS_START]
        if len(oos_idx) > 5:
            lo = oos_idx[0]
            out["daily_annualized_xref"]["stacked@%.1f_OOS2020" % s] = metrics_daily(
                stk_d[lo:], spx_d[lo:])
    # blend + core OOS daily
    oos_idx_b = [i for i, d in enumerate(blend_dates) if d >= OOS_START]
    if len(oos_idx_b) > 5:
        lo = oos_idx_b[0]
        out["daily_annualized_xref"]["invvol_blend_OOS2020"] = metrics_daily(
            blend_daily[lo:], spx_d[1:][lo:])
    oos_idx_c = [i for i, d in enumerate(common) if d >= OOS_START]
    if len(oos_idx_c) > 5:
        lo = oos_idx_c[0]
        out["daily_annualized_xref"]["core_alone_OOS2020"] = metrics_daily(core_d[lo:], spx_d[lo:])

    # ---- VERDICT computation ----
    def g(block, path):
        cur = block
        for p in path:
            cur = cur.get(p, {}) if isinstance(cur, dict) else {}
        return cur
    blend_full_sh = out["invvol_blend_reference"]["full"].get("sharpe")
    blend_oos_sh = out["invvol_blend_reference"]["oos_2020plus"].get("sharpe")
    blend_oos_ret = out["invvol_blend_reference"]["oos_2020plus"].get("ann_return_pct")
    blend_full_dd = out["invvol_blend_reference"]["full"].get("maxdd_pct")
    verdict_rows = {}
    for s in STACK_SIZES:
        k = "@%.1f" % s
        st = out["stacked"][k]
        full_sh = st["full"].get("sharpe")
        oos_sh = st["oos_2020plus"].get("sharpe")
        oos_ret = st["oos_2020plus"].get("ann_return_pct")
        full_dd = st["full"].get("maxdd_pct")
        canary_oos_sh = out["stacked_canary_divlag1"][k]["oos_2020plus"].get("sharpe")
        canary_full_sh = out["stacked_canary_divlag1"][k]["full"].get("sharpe")
        verdict_rows[k] = {
            "full_sharpe": full_sh, "oos_sharpe": oos_sh, "oos_ann_return_pct": oos_ret,
            "full_maxdd_pct": full_dd,
            "canary_full_sharpe": canary_full_sh, "canary_oos_sharpe": canary_oos_sh,
            "borrow_drag_bps_per_yr": st["financing_drag"]["total_borrow_cost_bps_per_yr"],
            "beats_blend_oos_sharpe": (oos_sh is not None and blend_oos_sh is not None and oos_sh > blend_oos_sh),
            "beats_blend_oos_return": (oos_ret is not None and blend_oos_ret is not None and oos_ret > blend_oos_ret),
            "beats_blend_full_sharpe": (full_sh is not None and blend_full_sh is not None and full_sh > blend_full_sh),
        }
    out["verdict"] = {
        "blend_full_sharpe": blend_full_sh,
        "blend_oos_sharpe": blend_oos_sh,
        "blend_oos_ann_return_pct": blend_oos_ret,
        "blend_full_maxdd_pct": blend_full_dd,
        "stacked": verdict_rows,
    }

    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/_return_stacking_result.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("wrote reports/_return_stacking_result.json")
    return out


if __name__ == "__main__":
    main()
