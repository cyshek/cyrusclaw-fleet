"""Two-sleeve allocator backtest: TQQQ vol-target + sector rotation.

The bench's first real MULTI-SLEEVE allocator test. Hypothesis: the levered-
Nasdaq sleeve (crushes in bull, goes to cash in downtrend) and the defensive
rotation sleeve (rotates into GLD/TLT when equities weaken) are uncorrelated /
negatively correlated in stress, so a blend should have a HIGHER Sharpe than
either alone and a MUCH lower drawdown.

Sleeves reproduced EXACTLY from the validated engines (same caches, same stats):
  1. TQQQ vol-target: strategies_candidates/leveraged_long_trend/backtest_daily_voltarget
     (TQQQ + QQQ SMA-200 gate + inverse-vol size to 25% ann vol, 20d window,
      2bps abs-weight cost, VIX gate off) -> the live leveraged_long_trend_paper.
  2. Sector rotation top-2: _sigimprove_tests.run_sector_rotation
     (SPY/QQQ/GLD/TLT, monthly, trailing 3-mo momentum, hold top-2 equal-wt,
      2bps one-way on monthly turnover).

BLEND MECHANICS
- Both sleeves are run standalone to get their daily equity -> daily return
  series. We then form a portfolio of the TWO SLEEVE RETURN STREAMS on the
  COMMON calendar (intersection of both sleeves' dates = TQQQ inception 2010-02
  onward), rebalanced MONTHLY to target sleeve weights.
- Between rebalances the sleeve weights DRIFT with their realized returns (a real
  book does not magically hold fixed weights intramonth). At each month-open we
  snap back to target and charge a rebalancing cost on the |weight change|
  between sleeves (the inter-sleeve turnover), at blend_cost_bps one-way.
  NOTE: the *intra-sleeve* trading costs (TQQQ daily rebal 2bps, rotation monthly
  2bps) are ALREADY baked into each sleeve's standalone return stream. The blend
  cost here is ONLY the additional top-level cost of moving capital BETWEEN the
  two sleeves at the monthly allocator rebalance -> no double counting.

WEIGHTING SCHEMES
- Fixed 50/50, 60/40, 40/60 (TQQQ / rotation), rebalanced monthly.
- Inverse-vol (risk parity): monthly weight_i proportional to 1/realized_vol_i,
  where realized_vol_i is each sleeve's trailing-63d annualized vol computed from
  returns STRICTLY THROUGH the prior month-end (lookahead-safe). Normalized to
  sum 1. This tilts toward the calmer sleeve (rotation) and downweights the wild
  TQQQ sleeve, but lets it ride when TQQQ vol is low.

NO-LOOKAHEAD
- Each sleeve's own engine is already lookahead-safe (gate/vol on data<=D, rank
  on prior month-end). The blend layer only uses PAST sleeve returns: the monthly
  target weights are set at month-open from realized vols through the prior month-
  end close; the held weights apply to that month's forward returns. A future
  sleeve return cannot change this month's target weight.

CORRELATION
- We report the correlation of the two sleeve DAILY RETURN series: full period,
  and within each named drawdown window (2011, 2015-16, 2018-Q4, 2020-Q1, 2022).

Run: python3 _allocator_blend_tests.py
Writes: reports/_allocator_blend_result.json
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, run_backtest_voltarget,
)
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    _stats_from_equity, TRADING_DAYS,
)
from _sigimprove_tests import run_sector_rotation

OOS_SPLIT = "2018-12-31"


# --------------------------------------------------------------------------- #
# Helpers to turn an equity curve into a {date: daily_return} map.
# --------------------------------------------------------------------------- #
def equity_to_daily_returns(dates: List[str], equity: List[float]) -> Dict[str, float]:
    """Map each date d (i>=1) -> simple return equity[i]/equity[i-1]-1. The
    return at date d is realized OVER the period ending at close of d (i.e. it is
    the return earned by holding from close of d-1 to close of d). dates[0] has no
    return (it's the base)."""
    out: Dict[str, float] = {}
    for i in range(1, len(dates)):
        if equity[i - 1] != 0:
            out[dates[i]] = equity[i] / equity[i - 1] - 1.0
    return out


def annualized_vol(returns: List[float]) -> float:
    """Population-stdev annualized (matches _stats_from_equity convention)."""
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


def stats_from_returns(dates: List[str], rets: List[float],
                       n_rebal: int = 0) -> Dict:
    """Build an equity curve from a date-aligned return series and compute stats
    via the shared _stats_from_equity. dates[i] corresponds to rets[i] (the
    return earned ending on dates[i]); we prepend a base date/equity 1.0."""
    eq = [1.0]
    ds = [dates[0]] if dates else ["base"]
    for i, r in enumerate(rets):
        eq.append(eq[-1] * (1.0 + r))
        ds.append(dates[i])
    st = _stats_from_equity(ds, eq, None, n_rebal)
    return {"stats": dict(st.__dict__), "dates": ds, "equity": eq}


def slice_equity_stats(dates: List[str], equity: List[float],
                       start: str, end: str) -> Dict:
    lo = bisect.bisect_left(dates, start)
    hi = bisect.bisect_right(dates, end)
    if hi - lo < 3:
        return {"n": hi - lo}
    sub_ds = dates[lo:hi]
    base = equity[lo]
    sub_eq = [v / base for v in equity[lo:hi]]
    st = _stats_from_equity(sub_ds, sub_eq)
    return dict(st.__dict__)


# --------------------------------------------------------------------------- #
# Build the two sleeve return series on a COMMON calendar.
# --------------------------------------------------------------------------- #
def build_sleeves() -> Dict:
    print(">>> Reproducing TQQQ vol-target sleeve ...", flush=True)
    vt = run_backtest_voltarget(VolTargetParams(
        target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
        vix_gate=False, switch_cost_bps=2.0))
    tqqq_dates = vt["strategy"]["dates"]
    tqqq_eq = vt["strategy"]["equity"]
    tqqq_ret_map = equity_to_daily_returns(tqqq_dates, tqqq_eq)
    spx_eq = vt["spx"]["equity"]
    spx_ret_map = equity_to_daily_returns(tqqq_dates, spx_eq)
    print("    TQQQ sleeve: %s -> %s  Sharpe %.3f CAGR %.1f%% maxDD %.1f%%" % (
        tqqq_dates[0], tqqq_dates[-1], vt["strategy"]["stats"]["sharpe"],
        vt["strategy"]["stats"]["cagr_pct"], vt["strategy"]["stats"]["max_drawdown_pct"]))

    print(">>> Reproducing sector-rotation top-2 sleeve ...", flush=True)
    rot = run_sector_rotation(["SPY", "QQQ", "GLD", "TLT"], bench="^GSPC",
                              cost_bps=2.0, start="2005-01-01",
                              hold_top=2, lookback_months=3)
    rot_dates = rot["strategy"]["dates"]
    rot_eq = rot["strategy"]["equity"]
    rot_ret_map = equity_to_daily_returns(rot_dates, rot_eq)
    print("    ROT sleeve:  %s -> %s  Sharpe %.3f CAGR %.1f%% maxDD %.1f%%" % (
        rot_dates[0], rot_dates[-1], rot["strategy"]["stats"]["sharpe"],
        rot["strategy"]["stats"]["cagr_pct"], rot["strategy"]["stats"]["max_drawdown_pct"]))

    # Common calendar = dates where BOTH sleeves have a daily return (intersection
    # of the two return maps). This is the TQQQ-inception-bounded window.
    common = sorted(set(tqqq_ret_map) & set(rot_ret_map))
    # Also need SPX on the same common dates for the benchmark.
    common = [d for d in common if d in spx_ret_map]

    tqqq_r = [tqqq_ret_map[d] for d in common]
    rot_r = [rot_ret_map[d] for d in common]
    spx_r = [spx_ret_map[d] for d in common]

    # Standalone stats RE-COMPUTED on the common window so the comparison vs the
    # blends is apples-to-apples (identical date set).
    tqqq_solo = stats_from_returns(common, tqqq_r)
    rot_solo = stats_from_returns(common, rot_r)
    spx_solo = stats_from_returns(common, spx_r)

    print("    Common window: %s -> %s  (%d days)" % (common[0], common[-1], len(common)))
    print("    [common-window] TQQQ solo Sharpe %.3f | ROT solo Sharpe %.3f | SPX Sharpe %.3f" % (
        tqqq_solo["stats"]["sharpe"], rot_solo["stats"]["sharpe"], spx_solo["stats"]["sharpe"]))

    return {
        "common_dates": common,
        "tqqq_r": tqqq_r, "rot_r": rot_r, "spx_r": spx_r,
        "tqqq_solo": tqqq_solo, "rot_solo": rot_solo, "spx_solo": spx_solo,
        "tqqq_full_window": (tqqq_dates[0], tqqq_dates[-1]),
        "rot_full_window": (rot_dates[0], rot_dates[-1]),
    }


# --------------------------------------------------------------------------- #
# Blend a list of sleeve return series into a monthly-rebalanced portfolio.
# weight_fn(month_open_idx, dates, sleeve_returns_so_far) -> {sleeve_idx: weight}
# For fixed schemes weight_fn returns the constant target.
# --------------------------------------------------------------------------- #
def blend_portfolio(dates: List[str], sleeves: List[List[float]],
                    target_weight_fn, blend_cost_bps: float = 2.0,
                    vol_lookback_days: int = 63) -> Dict:
    """Monthly-rebalanced blend of N sleeve daily-return series.

    - dates[i] aligns to sleeves[k][i] (return of sleeve k ending on dates[i]).
    - At each month-open we compute target weights via target_weight_fn, snap the
      drifted weights back to target, and charge blend_cost_bps one-way on the
      total |weight change| across sleeves (inter-sleeve turnover).
    - Intramonth, weights DRIFT: after earning day i, the value of each sleeve
      bucket grows by (1+r_i); next day's effective weights are renormalized
      from the drifted bucket values. This is the honest "let it ride, rebalance
      monthly" behavior.

    target_weight_fn(month_open_idx) -> list[float] summing to 1 over sleeves.
    It may use dates[:month_open_idx] and sleeves[k][:month_open_idx] (PAST only).
    """
    n = len(dates)
    ns = len(sleeves)

    # month-open indices (first occurrence of each YYYY-MM in dates)
    month_open = []
    seen = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_open.append(i)
    month_open_set = set(month_open)

    # Start fully allocated at the first month-open target (or at i=0).
    # bucket[k] = current dollar value attributed to sleeve k; total tracked = equity.
    equity = [1.0]
    # initialize weights from the first available target (at i=0 use first target)
    w = target_weight_fn(0)
    bucket = [w[k] for k in range(ns)]  # sums to 1.0
    eq_dates = [dates[0]]
    n_rebal = 0
    turnover_total = 0.0
    weight_log: List[Dict] = []

    for i in range(1, n):
        d = dates[i]
        # rebalance at month-open (snap drifted bucket -> target, charge cost)
        if i in month_open_set:
            tot = sum(bucket)
            cur_w = [b / tot for b in bucket] if tot > 0 else [0.0] * ns
            tgt = target_weight_fn(i)
            turn = sum(abs(tgt[k] - cur_w[k]) for k in range(ns))
            cost = (blend_cost_bps / 10000.0) * turn
            if turn > 1e-9:
                n_rebal += 1
                turnover_total += turn
            # apply cost to total, then reset buckets to target proportions
            tot_after = tot * (1.0 - cost)
            bucket = [tgt[k] * tot_after for k in range(ns)]
            weight_log.append({"date": d, "w": list(tgt)})

        # earn the day's returns -> drift the buckets
        for k in range(ns):
            bucket[k] *= (1.0 + sleeves[k][i])
        equity.append(sum(bucket))
        eq_dates.append(d)

    in_market = [True] * (len(eq_dates) - 1)
    st = _stats_from_equity(eq_dates, equity, in_market, n_rebal)
    return {
        "dates": eq_dates, "equity": equity,
        "stats": dict(st.__dict__),
        "n_rebal": n_rebal,
        "avg_turnover_per_rebal": (turnover_total / n_rebal) if n_rebal else 0.0,
        "weight_log": weight_log,
    }


def report_blend(blend: Dict, label: str, spx_dates: List[str],
                 spx_equity: List[float]) -> Dict:
    ds = blend["dates"]; eq = blend["equity"]
    full = blend["stats"]
    oos = slice_equity_stats(ds, eq, "2019-01-01", "2099-12-31")
    is_ = slice_equity_stats(ds, eq, "2000-01-01", OOS_SPLIT)
    spx_full = _stats_from_equity(spx_dates, spx_equity)
    spx_oos = slice_equity_stats(spx_dates, spx_equity, "2019-01-01", "2099-12-31")
    return {
        "label": label,
        "window": {"start": ds[0], "end": ds[-1], "n_days": len(ds)},
        "n_rebal": blend["n_rebal"],
        "avg_turnover_per_rebal": blend["avg_turnover_per_rebal"],
        "full": {"sharpe": full["sharpe"], "cagr_pct": full["cagr_pct"],
                 "maxdd_pct": full["max_drawdown_pct"], "vol_pct": full["ann_vol_pct"],
                 "total_return_pct": full["total_return_pct"]},
        "is_2010_2018": {"sharpe": is_.get("sharpe"), "cagr_pct": is_.get("cagr_pct"),
                         "maxdd_pct": is_.get("max_drawdown_pct")},
        "oos_2019_today": {"sharpe": oos.get("sharpe"), "cagr_pct": oos.get("cagr_pct"),
                           "maxdd_pct": oos.get("max_drawdown_pct"),
                           "total_return_pct": oos.get("total_return_pct")},
        "spx_full": {"sharpe": spx_full.sharpe, "cagr_pct": spx_full.cagr_pct,
                     "maxdd_pct": spx_full.max_drawdown_pct},
        "spx_oos": {"sharpe": spx_oos.get("sharpe"), "cagr_pct": spx_oos.get("cagr_pct")},
    }


# --------------------------------------------------------------------------- #
# Correlation in named drawdown windows.
# --------------------------------------------------------------------------- #
DD_WINDOWS = {
    "2011_summer_crisis": ("2011-05-01", "2011-12-31"),
    "2015_2016_selloff":  ("2015-07-01", "2016-02-29"),
    "2018_Q4":            ("2018-10-01", "2018-12-31"),
    "2020_Q1_covid":      ("2020-02-01", "2020-04-30"),
    "2022_bear":          ("2022-01-01", "2022-12-31"),
}


def correlation_report(dates: List[str], a: List[float], b: List[float]) -> Dict:
    out = {"full": pearson(a, b), "n_full": len(dates)}
    wins = {}
    for name, (s, e) in DD_WINDOWS.items():
        idxs = [i for i, d in enumerate(dates) if s <= d <= e]
        if len(idxs) < 5:
            wins[name] = {"corr": None, "n": len(idxs)}
            continue
        aa = [a[i] for i in idxs]
        bb = [b[i] for i in idxs]
        wins[name] = {"corr": pearson(aa, bb), "n": len(idxs),
                      "window": [dates[idxs[0]], dates[idxs[-1]]]}
    out["drawdown_windows"] = wins
    return out


def _full_block(solo: Dict) -> Dict:
    """Extract the standard full-period block from a stats_from_returns result."""
    s = solo["stats"]
    return {"sharpe": s["sharpe"], "cagr_pct": s["cagr_pct"],
            "maxdd_pct": s["max_drawdown_pct"], "vol_pct": s["ann_vol_pct"],
            "total_return_pct": s["total_return_pct"]}


# --------------------------------------------------------------------------- #
# DRIVER
# --------------------------------------------------------------------------- #
def main():
    S = build_sleeves()
    dates = S["common_dates"]
    tqqq_r = S["tqqq_r"]
    rot_r = S["rot_r"]
    spx_r = S["spx_r"]

    # SPX equity on common window (for blend benchmark slices)
    spx_curve = stats_from_returns(dates, spx_r)
    spx_dates = spx_curve["dates"]
    spx_equity = spx_curve["equity"]

    out: Dict = {}
    out["meta"] = {
        "common_window": [dates[0], dates[-1]],
        "n_days": len(dates),
        "tqqq_full_window": list(S["tqqq_full_window"]),
        "rot_full_window": list(S["rot_full_window"]),
        "note": ("Sleeve return streams reproduced from validated engines; intra-"
                 "sleeve costs already in each stream; blend adds only inter-sleeve "
                 "monthly rebalance cost (2bps one-way on sleeve turnover)."),
    }

    # ---------- standalone (common-window) ----------
    out["standalone_common_window"] = {
        "tqqq_voltarget": {
            "full": _full_block(S["tqqq_solo"]),
            "is_2010_2018": slice_equity_stats(S["tqqq_solo"]["dates"], S["tqqq_solo"]["equity"], "2000-01-01", OOS_SPLIT),
            "oos_2019_today": slice_equity_stats(S["tqqq_solo"]["dates"], S["tqqq_solo"]["equity"], "2019-01-01", "2099-12-31"),
        },
        "sector_rotation_top2": {
            "full": _full_block(S["rot_solo"]),
            "is_2010_2018": slice_equity_stats(S["rot_solo"]["dates"], S["rot_solo"]["equity"], "2000-01-01", OOS_SPLIT),
            "oos_2019_today": slice_equity_stats(S["rot_solo"]["dates"], S["rot_solo"]["equity"], "2019-01-01", "2099-12-31"),
        },
        "spx_raw": {
            "full": _full_block(S["spx_solo"]),
            "oos_2019_today": slice_equity_stats(S["spx_solo"]["dates"], S["spx_solo"]["equity"], "2019-01-01", "2099-12-31"),
        },
    }

    # ---------- correlation ----------
    print(">>> Correlation full + drawdown windows ...", flush=True)
    out["correlation"] = correlation_report(dates, tqqq_r, rot_r)
    print("    Full-period corr(TQQQ, ROT) = %.3f" % (out["correlation"]["full"] or float("nan")))
    for name, w in out["correlation"]["drawdown_windows"].items():
        c = w.get("corr")
        cs = ("%.3f" % c) if c is not None else "n/a"
        print("      %-22s corr %s (n=%d)" % (name, cs, w.get("n", 0)))

    # ---------- realized vols (common window, for risk-parity context) ----------
    tqqq_full_vol = annualized_vol(tqqq_r)
    rot_full_vol = annualized_vol(rot_r)
    out["sleeve_full_vols"] = {"tqqq": tqqq_full_vol, "rot": rot_full_vol}
    print("    Full-window ann vol: TQQQ %.1f%%  ROT %.1f%%" % (tqqq_full_vol * 100, rot_full_vol * 100))

    # ---------- weight functions ----------
    sleeves = [tqqq_r, rot_r]  # index 0 = TQQQ, 1 = rotation

    def fixed_wfn(w_tqqq):
        def fn(_idx):
            return [w_tqqq, 1.0 - w_tqqq]
        return fn

    def invvol_wfn(lookback=63):
        # weight_i ∝ 1/vol_i using returns STRICTLY BEFORE month-open idx.
        def fn(idx):
            if idx < 2:
                return [0.5, 0.5]
            lo = max(0, idx - lookback)
            v0 = annualized_vol(sleeves[0][lo:idx])
            v1 = annualized_vol(sleeves[1][lo:idx])
            if v0 <= 0 or v1 <= 0:
                return [0.5, 0.5]
            iv0, iv1 = 1.0 / v0, 1.0 / v1
            s = iv0 + iv1
            return [iv0 / s, iv1 / s]
        return fn

    # ---------- run blends ----------
    print(">>> Running blends ...", flush=True)
    out["blends"] = {}
    blend_specs = {
        "50_50":        fixed_wfn(0.50),
        "60_40_tqqq":   fixed_wfn(0.60),
        "40_60_tqqq":   fixed_wfn(0.40),
        "70_30_tqqq":   fixed_wfn(0.70),
        "30_70_tqqq":   fixed_wfn(0.30),
        "invvol_63d":   invvol_wfn(63),
    }
    for name, wfn in blend_specs.items():
        b = blend_portfolio(dates, sleeves, wfn, blend_cost_bps=2.0)
        out["blends"][name] = report_blend(b, name, spx_dates, spx_equity)
        # record realized avg weights for the inv-vol blend
        if b["weight_log"]:
            avg_w0 = sum(wl["w"][0] for wl in b["weight_log"]) / len(b["weight_log"])
            out["blends"][name]["avg_w_tqqq"] = avg_w0
        s = out["blends"][name]["full"]
        print("   %-14s full Sharpe %.3f CAGR %.1f%% maxDD %.1f%% vol %.1f%% | OOS Sharpe %.3f" % (
            name, s["sharpe"], s["cagr_pct"], s["maxdd_pct"], s["vol_pct"],
            out["blends"][name]["oos_2019_today"].get("sharpe") or float("nan")))

    # ---------- verdict helpers ----------
    tqqq_full_sh = S["tqqq_solo"]["stats"]["sharpe"]
    rot_full_sh = S["rot_solo"]["stats"]["sharpe"]
    best_blend = max(out["blends"].items(), key=lambda kv: kv[1]["full"]["sharpe"])
    out["verdict"] = {
        "tqqq_solo_full_sharpe": tqqq_full_sh,
        "rot_solo_full_sharpe": rot_full_sh,
        "best_blend_name": best_blend[0],
        "best_blend_full_sharpe": best_blend[1]["full"]["sharpe"],
        "best_blend_full_maxdd": best_blend[1]["full"]["maxdd_pct"],
        "beats_both_standalone_sharpe": (best_blend[1]["full"]["sharpe"] > tqqq_full_sh
                                         and best_blend[1]["full"]["sharpe"] > rot_full_sh),
    }
    print("")
    print(">>> Best blend by full Sharpe: %s (%.3f). TQQQ solo %.3f, ROT solo %.3f. Beats both: %s" % (
        best_blend[0], best_blend[1]["full"]["sharpe"], tqqq_full_sh, rot_full_sh,
        out["verdict"]["beats_both_standalone_sharpe"]))

    with open("reports/_allocator_blend_result.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("wrote reports/_allocator_blend_result.json")
    return out


if __name__ == "__main__":
    main()
