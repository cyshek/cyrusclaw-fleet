"""Robustness of the QUARTERLY cadence win (the cleanest raw-return beater).

Three tests:
  1. IS/OOS split of quarterly vs monthly (must beat in BOTH, not one lucky era).
  2. Quarter-ANCHOR robustness: shift which months anchor the quarter
     (Jan-anchor = standard 1/4/7/10; Feb-anchor = 2/5/8/11; Mar-anchor = 3/6/9/12).
     Also a generic 'every-Nth-month' family (N=2,3,4,6) to see the cadence-period
     response curve -- is quarterly (N=3) a plateau or a lucky single point?
  3. Per-year net return: quarterly vs monthly, to locate WHERE the edge lives
     (one year carrying it = fragile; broad = robust).
"""
from __future__ import annotations

import bisect
import json
import sys
from typing import Callable, Dict, List

sys.path.insert(0, ".")
sys.path.insert(0, "tests")

import _cadence_sweep as cs
from strategies_candidates.leveraged_long_trend.backtest_daily import _stats_from_equity


def every_nth_month_set(dates: List[str], n: int, offset: int = 0) -> set:
    """First trading day of every Nth month (offset shifts the phase)."""
    mo = sorted(cs.month_open_set(dates))
    keep = set(mo[offset::n])
    return keep


def anchored_quarter_set(dates: List[str], anchor_month: int) -> set:
    """First trading day of each quarter where quarters start at anchor_month
    (anchor_month in 1..3 gives 1/4/7/10, 2/5/8/11, 3/6/9/12)."""
    seen = set()
    out = set()
    for i, d in enumerate(dates):
        mo = int(d[5:7])
        # quarter index relative to the anchor
        q = (mo - anchor_month) % 12 // 3
        # year-quarter key; need the year of the anchor period start
        yr = int(d[:4])
        key = (yr, anchor_month, q)
        if key not in seen:
            seen.add(key)
            out.add(i)
    return out


def cal(trigset):
    def fn(i, cur_w, tgt_w):
        return i in trigset
    return fn


def per_year_returns(dates: List[str], equity: List[float]) -> Dict[str, float]:
    """Net total return within each calendar year from the equity curve."""
    out: Dict[str, float] = {}
    years = sorted(set(d[:4] for d in dates))
    for y in years:
        lo = bisect.bisect_left(dates, y + "-01-01")
        hi = bisect.bisect_right(dates, y + "-12-31")
        if hi - lo < 2:
            continue
        out[y] = (equity[hi - 1] / equity[lo] - 1.0) * 100.0
    return out


def main() -> None:
    S = cs.load_sleeves()
    dates = S["common_dates"]
    sleeves = [S["tqqq_r"], S["rot_r"]]
    moset = cs.month_open_set(dates)
    qset = cs.quarter_open_set(dates)

    OOS_SPLIT = "2018-12-31"

    def split_stats(b):
        ds, eq = b["dates"], b["equity"]
        full = b["stats"]
        is_ = cs.slice_stats(ds, eq, "2000-01-01", OOS_SPLIT)
        oos = cs.slice_stats(ds, eq, "2019-01-01", "2099-12-31")
        return {
            "full_totret": full["total_return_pct"], "full_sharpe": full["sharpe"],
            "full_maxdd": full["max_drawdown_pct"],
            "is_totret": is_.get("total_return_pct"), "is_sharpe": is_.get("sharpe"),
            "is_maxdd": is_.get("max_drawdown_pct"),
            "oos_totret": oos.get("total_return_pct"), "oos_sharpe": oos.get("sharpe"),
            "oos_maxdd": oos.get("max_drawdown_pct"),
        }

    out: Dict = {}

    # ----- 1. IS/OOS monthly vs quarterly -----
    print(">>> 1. IS/OOS monthly vs quarterly")
    mb = cs.blend_with_cadence(dates, sleeves, cal(moset))
    qb = cs.blend_with_cadence(dates, sleeves, cal(qset))
    out["monthly"] = split_stats(mb)
    out["quarterly"] = split_stats(qb)
    for nm, st in (("monthly", out["monthly"]), ("quarterly", out["quarterly"])):
        print("   %-10s full %.1f%% (Sh %.3f DD %.1f%%) | IS %.1f%% (Sh %.3f) | OOS %.1f%% (Sh %.3f)" % (
            nm, st["full_totret"], st["full_sharpe"], st["full_maxdd"],
            st["is_totret"], st["is_sharpe"], st["oos_totret"], st["oos_sharpe"]))

    # ----- 2. quarter-anchor + every-Nth-month robustness -----
    print(">>> 2. anchor + cadence-period robustness (does quarterly survive phase shifts?)")
    out["anchor_robustness"] = {}
    for am in (1, 2, 3):
        qs = anchored_quarter_set(dates, am)
        b = cs.blend_with_cadence(dates, sleeves, cal(qs))
        st = split_stats(b)
        out["anchor_robustness"]["quarter_anchor_m%d" % am] = st
        print("   quarter_anchor m=%d  full %.1f%% (Sh %.3f DD %.1f%%) | OOS %.1f%% (Sh %.3f) | n_rebal %d" % (
            am, st["full_totret"], st["full_sharpe"], st["full_maxdd"],
            st["oos_totret"], st["oos_sharpe"], b["n_rebal"]))

    out["cadence_period_curve"] = {}
    print("   --- every-Nth-month family (cadence-period response) ---")
    for n in (1, 2, 3, 4, 6):
        # average over all phase offsets to remove anchor luck
        offs = list(range(n))
        sub = []
        for off in offs:
            ms = every_nth_month_set(dates, n, off)
            b = cs.blend_with_cadence(dates, sleeves, cal(ms))
            sub.append(split_stats(b))
        avg = {k: (sum(s[k] for s in sub) / len(sub)) for k in
               ("full_totret", "full_sharpe", "full_maxdd", "oos_totret", "oos_sharpe")}
        spread = max(s["full_totret"] for s in sub) - min(s["full_totret"] for s in sub)
        out["cadence_period_curve"]["every_%dmo" % n] = {"avg": avg,
                                                         "totret_spread_across_phase": spread,
                                                         "n_phases": len(offs)}
        print("   every_%dmo  avg full %.1f%% (Sh %.3f DD %.1f%%) OOS %.1f%% (Sh %.3f) | phase-spread %.1fpts" % (
            n, avg["full_totret"], avg["full_sharpe"], avg["full_maxdd"],
            avg["oos_totret"], avg["oos_sharpe"], spread))

    # ----- 3. per-year quarterly vs monthly -----
    print(">>> 3. per-year net return: quarterly - monthly (where does the edge live?)")
    my = per_year_returns(mb["dates"], mb["equity"])
    qy = per_year_returns(qb["dates"], qb["equity"])
    diffs = {}
    for y in sorted(my):
        if y in qy:
            diffs[y] = qy[y] - my[y]
    out["per_year_quarterly_minus_monthly"] = diffs
    out["per_year_monthly"] = my
    out["per_year_quarterly"] = qy
    pos = sum(1 for v in diffs.values() if v > 0)
    print("   year | monthly | quarterly | q-m")
    for y in sorted(diffs):
        print("   %s | %7.1f%% | %8.1f%% | %+6.1f%%" % (y, my[y], qy[y], diffs[y]))
    print("   quarterly beat monthly in %d / %d years" % (pos, len(diffs)))
    out["quarterly_beats_monthly_years"] = "%d/%d" % (pos, len(diffs))

    with open("reports/_cadence_robustness.json", "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("wrote reports/_cadence_robustness.json")


if __name__ == "__main__":
    main()
