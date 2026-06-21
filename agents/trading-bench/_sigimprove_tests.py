"""Three signal-improvement add-on tests on the live TQQQ vol-target strategy.

TEST 1 - COT percentile-extreme multiplier on the leveraged_long_trend vol-target engine.
TEST 2 - VIX term-structure (VIX3M/VIX) regime multiplier on the same engine.
TEST 3 - Standalone 4-asset monthly momentum rotation (SPY/QQQ/GLD/TLT) baseline.

All reuse the verified lookahead-safe caches:
  runner.daily_bars_cache (Yahoo v8 adjclose)
  runner.cot_cache       (CFTC TFF, NQ contract, release-lagged PIT)
  runner.cboe_cache      (VIX / VIX3M, strictly-prior-close PIT)

Baseline (vol-target 0.25 / sma200 / vix-off / 2bps abs-weight cost):
  full Sharpe 0.864, CAGR 20.81%, maxDD -34.52%  vs SPX Sharpe 0.772.
(Task quotes 0.842/0.832 OOS as the baseline bar; we report both our reproduced
baseline and the deltas so it's apples-to-apples either way.)

OOS split = 2018-12-31 (in-sample <=2018, OOS 2019->today), matching the task.

NO-LOOKAHEAD: every overlay uses only data released/closed STRICTLY before the
held day (COT released_asof, VIX history with value_date < decision day). The
multiplier for day D+1 is computed from the SAME decision day D as the base
weight, so no future info leaks.

Run: python3 _sigimprove_tests.py
Writes: reports/_sigimprove_result.json
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from runner import cot_cache as cot
from runner import cboe_cache as cboe
from strategies_candidates.leveraged_long_trend import backtest_daily as bd
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    trend_is_up, _stats_from_equity, TRADING_DAYS,
)
from strategies_candidates.leveraged_long_trend.backtest_daily_voltarget import (
    VolTargetParams, realized_ann_vol, target_weight,
)

OOS_SPLIT = "2018-12-31"


# --------------------------------------------------------------------------- #
# Generic vol-target sim with an optional daily multiplier hook.
# The hook receives the decision day D (d_prev) and returns a scalar in [0, 1+]
# applied to the base sleeve weight. Returns multiplier=1.0 => identical to base.
# --------------------------------------------------------------------------- #
def run_voltarget_with_multiplier(p: VolTargetParams,
                                  multiplier_fn=None) -> Dict:
    """Mirror backtest_daily_voltarget.run_backtest_voltarget but allow an
    overlay multiplier on the sleeve weight. multiplier_fn(d_prev, base_w, ctx)
    -> float. ctx carries precomputed series handles for the overlay. If None,
    multiplier is 1.0 everywhere (reproduces the engine exactly)."""
    lev = p.to_lev()
    sleeve_bars = dbc.get_daily(p.sleeve)
    under_bars = dbc.get_daily(p.underlying)
    bench_bars = dbc.get_daily(p.benchmark)

    sleeve_by = {b["date"]: b for b in sleeve_bars}
    bench_by = {b["date"]: b for b in bench_bars}

    start = p.start or sleeve_bars[0]["date"]
    end = p.end or sleeve_bars[-1]["date"]
    cal = [b["date"] for b in sleeve_bars if start <= b["date"] <= end]

    under_dates = [b["date"] for b in under_bars]
    under_close = [b["adjclose"] for b in under_bars]

    def under_closes_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(under_dates, d_iso)
        return under_close[:idx]

    sleeve_dates = [b["date"] for b in sleeve_bars]
    sleeve_close = [b["adjclose"] for b in sleeve_bars]
    sret_end_dates: List[str] = []
    sret_vals: List[float] = []
    for k in range(1, len(sleeve_close)):
        if sleeve_close[k - 1] > 0:
            sret_end_dates.append(sleeve_dates[k])
            sret_vals.append(sleeve_close[k] / sleeve_close[k - 1] - 1.0)

    def sleeve_rets_through(d_iso: str) -> List[float]:
        idx = bisect.bisect_right(sret_end_dates, d_iso)
        return sret_vals[:idx]

    equity = [1.0]
    strat_dates = [cal[0]]
    weights: List[float] = []
    in_market_flags: List[bool] = []
    pos_log: List[Dict] = []
    prev_w = 0.0
    n_rebalances = 0
    REBAL_EPS = 1e-9

    for i in range(1, len(cal)):
        d_prev = cal[i - 1]
        d = cal[i]

        uc = under_closes_through(d_prev)
        up = trend_is_up(uc, lev)
        if p.vix_gate and up and bd._vix_risk_off(d_prev, p.vix_ratio_thr):
            up = False

        rv = realized_ann_vol(sleeve_rets_through(d_prev), p.vol_window) \
            if p.target_ann_vol is not None else None
        base_w = target_weight(up, rv, p.target_ann_vol, p.w_max)

        # ---- overlay multiplier (decision day D = d_prev, lookahead-safe) ----
        mult = 1.0
        if multiplier_fn is not None and base_w > 0.0:
            mult = multiplier_fn(d_prev)
        w = base_w * mult
        # never exceed w_max even after a >1 multiplier (we don't use >1 here)
        if w > p.w_max:
            w = p.w_max

        b_now = sleeve_by.get(d)
        b_prev = sleeve_by.get(d_prev)
        if b_now and b_prev and b_prev["adjclose"] > 0:
            sleeve_ret = b_now["adjclose"] / b_prev["adjclose"] - 1.0
        else:
            sleeve_ret = 0.0
        cash_ret = bd._tbill_daily_rate(d_prev) if p.use_tbill_cash else 0.0
        blended = w * sleeve_ret + (1.0 - w) * cash_ret

        dw = abs(w - prev_w)
        cost = (p.switch_cost_bps / 10000.0) * dw
        if dw > REBAL_EPS:
            n_rebalances += 1

        new_eq = equity[-1] * (1.0 + blended) * (1.0 - cost)
        equity.append(new_eq)
        strat_dates.append(d)
        weights.append(w)
        in_market_flags.append(w > 0.0)
        pos_log.append({"date": d, "weight": w})
        prev_w = w

    strat_stats = _stats_from_equity(strat_dates, equity, in_market_flags, n_rebalances)
    avg_weight = (sum(weights) / len(weights)) if weights else 0.0

    def bh_curve(by: Dict[str, Dict]) -> Tuple[List[str], List[float]]:
        eq = [1.0]
        ds = [strat_dates[0]]
        for j in range(1, len(strat_dates)):
            dn = strat_dates[j]; dp = strat_dates[j - 1]
            bn = by.get(dn); bp = by.get(dp)
            r = (bn["adjclose"] / bp["adjclose"] - 1.0) if (bn and bp and bp["adjclose"] > 0) else 0.0
            eq.append(eq[-1] * (1.0 + r)); ds.append(dn)
        return ds, eq

    spx_dates, spx_eq = bh_curve(bench_by)
    spx_stats = _stats_from_equity(spx_dates, spx_eq)

    sdict = dict(strat_stats.__dict__)
    sdict["avg_weight"] = avg_weight
    sdict["n_rebalances"] = n_rebalances

    return {
        "window": {"start": strat_dates[0], "end": strat_dates[-1], "n_days": len(strat_dates)},
        "strategy": {"stats": sdict, "dates": strat_dates, "equity": equity},
        "spx": {"stats": spx_stats.__dict__, "equity": spx_eq},
        "pos_log": pos_log,
    }


def slice_stats(result: Dict, start: str, end: str, key: str = "strategy") -> Dict:
    ds = result[key]["dates"] if key == "strategy" else result["strategy"]["dates"]
    eq = result[key]["equity"]
    lo = bisect.bisect_left(ds, start)
    hi = bisect.bisect_right(ds, end)
    if hi - lo < 3:
        return {"n": hi - lo}
    sub_ds = ds[lo:hi]; sub_eq = eq[lo:hi]
    # rebase to 1.0 at slice start for clean segment stats
    base = sub_eq[0]
    sub_eq = [v / base for v in sub_eq]
    st = _stats_from_equity(sub_ds, sub_eq)
    return dict(st.__dict__)


def report_block(result: Dict, label: str) -> Dict:
    full_s = result["strategy"]["stats"]
    full_spx = result["spx"]["stats"]
    oos_s = slice_stats(result, "2019-01-01", "2099-12-31", "strategy")
    oos_spx = slice_stats(result, "2019-01-01", "2099-12-31", "spx")
    is_s = slice_stats(result, "2010-01-01", OOS_SPLIT, "strategy")
    return {
        "label": label,
        "window": result["window"],
        "full": {"sharpe": full_s["sharpe"], "cagr_pct": full_s["cagr_pct"],
                 "maxdd_pct": full_s["max_drawdown_pct"], "vol_pct": full_s["ann_vol_pct"],
                 "total_return_pct": full_s["total_return_pct"],
                 "avg_weight": full_s.get("avg_weight"), "n_rebalances": full_s.get("n_rebalances")},
        "is_2010_2018": {"sharpe": is_s.get("sharpe"), "cagr_pct": is_s.get("cagr_pct"),
                         "maxdd_pct": is_s.get("max_drawdown_pct")},
        "oos_2019_today": {"sharpe": oos_s.get("sharpe"), "cagr_pct": oos_s.get("cagr_pct"),
                           "maxdd_pct": oos_s.get("max_drawdown_pct"),
                           "total_return_pct": oos_s.get("total_return_pct")},
        "spx_full": {"sharpe": full_spx["sharpe"], "cagr_pct": full_spx["cagr_pct"],
                     "maxdd_pct": full_spx["max_drawdown_pct"]},
        "spx_oos": {"sharpe": oos_spx.get("sharpe"), "cagr_pct": oos_spx.get("cagr_pct")},
    }


# =========================================================================== #
# TEST 1 — COT percentile-extreme multiplier
# =========================================================================== #
def build_cot_percentile_fn(pct_window: int = 52,
                            low_thr: float = 0.20, high_thr: float = 0.80,
                            long_mult: float = 1.0, caution_mult: float = 0.5,
                            field: str = "lev_net"):
    """Return a multiplier_fn(d_prev) for the COT percentile gate.

    Signal = absolute-percentile rank of the released-asof NQ net-long over the
    trailing `pct_window` RELEASED weekly snapshots (lookahead-safe via
    cot.released_history). The TASK frames this contrarian on COMMERCIALS:
      'commercials max short = contrarian buy' -> rank < low_thr  => long_mult
      'commercials max long  = caution'        -> rank > high_thr => caution_mult
    In the TFF report the dealer/intermediary book is the closest analog to the
    legacy 'commercials' (hedgers); leveraged funds are the speculators. We test
    BOTH interpretations (dealer-net = commercial-analog, and lev-net = spec) by
    swapping `field`; the report shows both. Default field is configurable.

    Percentile rank uses the FULL released history's trailing `pct_window` rows.
    rank in [0,1]; <low_thr extreme-short, >high_thr extreme-long.
    Between thresholds -> 1.0 (neutral, no change).

    Missing/insufficient COT history -> 1.0 (no change; never force a guess).
    """
    cache: Dict[str, float] = {}

    def fn(d_prev: str) -> float:
        if d_prev in cache:
            return cache[d_prev]
        try:
            hist = cot.released_history("NQ", d_prev, lookback=pct_window)
        except Exception:
            cache[d_prev] = 1.0
            return 1.0
        vals = [h.get(field) for h in hist if h.get(field) is not None]
        if len(vals) < max(8, pct_window // 2):
            cache[d_prev] = 1.0
            return 1.0
        cur = vals[-1]
        # absolute-percentile rank of current value within the window
        below = sum(1 for v in vals if v < cur)
        rank = below / (len(vals) - 1) if len(vals) > 1 else 0.5
        if rank < low_thr:
            m = long_mult
        elif rank > high_thr:
            m = caution_mult
        else:
            m = 1.0
        cache[d_prev] = m
        return m

    return fn


# =========================================================================== #
# TEST 2 — VIX term-structure regime multiplier (VIX3M/VIX)
# =========================================================================== #
def build_vix_ts_fn(backwardation_thr: float = 1.00, contango_thr: float = 1.05,
                    backward_mult: float = 0.5, contango_mult: float = 1.0,
                    mid_mult: float = 1.0):
    """multiplier_fn(d_prev) using the VIX3M/VIX ratio (term structure).

    ratio = VIX3M / VIX, using the strictly-prior close (cboe.level_asof which
    serves value_date < d_prev) -> lookahead-safe.
      ratio <  backwardation_thr (=1.0)  -> backwardation/inversion (fear) -> 0.5x
      ratio >  contango_thr      (=1.05) -> normal contango (calm)         -> 1.0x
      between                            -> mid_mult (1.0)

    Note: VIX3M/VIX > 1 is the NORMAL (contango) state; < 1 is backwardation
    (stress). This matches the task's spec: 'VIX3M/VIX < 1.0 = reduce; > 1.05 =
    full weight'. Missing VIX/VIX3M -> 1.0 (no change)."""
    cache: Dict[str, float] = {}

    def fn(d_prev: str) -> float:
        if d_prev in cache:
            return cache[d_prev]
        try:
            vix = cboe.level_asof("VIX", d_prev)
            vix3m = cboe.level_asof("VIX3M", d_prev)
        except Exception:
            cache[d_prev] = 1.0
            return 1.0
        if vix is None or vix3m is None or vix <= 0:
            cache[d_prev] = 1.0
            return 1.0
        ratio = vix3m / vix
        if ratio < backwardation_thr:
            m = backward_mult
        elif ratio > contango_thr:
            m = contango_mult
        else:
            m = mid_mult
        cache[d_prev] = m
        return m

    return fn


# =========================================================================== #
# TEST 3 — Standalone 4-asset monthly momentum rotation
# =========================================================================== #
def run_sector_rotation(assets: List[str], bench: str = "^GSPC",
                        lookback_months: int = 3, hold_top: int = 1,
                        cost_bps: float = 2.0, start: str = "2005-01-01",
                        end: Optional[str] = None) -> Dict:
    """Monthly momentum rotation. Each month, on the FIRST trading day, rank the
    assets by their trailing `lookback_months` (~21*M trading days) total return
    computed from data through the PRIOR month-end (lookahead-safe: the ranking
    uses closes strictly before the rebalance day's holding period — we rank on
    the close of the last trading day of the prior month, then hold from the
    first trading day of the new month). Hold top `hold_top` equal-weighted.
    Cost = cost_bps one-way on the fraction of book turned over each rebalance.

    Daily marking: equity compounds each asset's daily return * its weight.
    Lookahead contract: weights set at month-open use returns through prior
    month-end close; the held return over the month uses that month's daily
    closes. Rank decision day = last trading day of prior month (strictly before
    the first held day)."""
    bars = {a: dbc.get_daily(a) for a in assets}
    bench_bars = dbc.get_daily(bench)

    # common calendar = intersection of all asset dates within [start,end]
    if end is None:
        end = min(b[-1]["date"] for b in bars.values())
    date_sets = [set(b["date"] for b in bars[a]) for a in assets]
    common = sorted(set.intersection(*date_sets))
    cal = [d for d in common if start <= d <= end]

    close = {a: {b["date"]: b["adjclose"] for b in bars[a]} for a in assets}
    bench_close = {b["date"]: b["adjclose"] for b in bench_bars}

    lb_days = lookback_months * 21

    # month boundaries: first trading day of each month in cal
    month_first: List[int] = []
    seen = set()
    for idx, d in enumerate(cal):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_first.append(idx)
    month_first_set = set(month_first)

    def trailing_return(a: str, end_idx: int) -> Optional[float]:
        """Return of asset a over [end_idx - lb_days, end_idx] using cal dates."""
        if end_idx - lb_days < 0:
            return None
        d_end = cal[end_idx]
        d_start = cal[end_idx - lb_days]
        c_end = close[a].get(d_end)
        c_start = close[a].get(d_start)
        if c_end is None or c_start is None or c_start <= 0:
            return None
        return c_end / c_start - 1.0

    equity = [1.0]
    eq_dates = [cal[0]]
    cur_weights: Dict[str, float] = {a: 0.0 for a in assets}
    target_weights: Dict[str, float] = {a: 0.0 for a in assets}
    n_rebalances = 0
    turnover_total = 0.0
    holdings_log: List[Dict] = []

    for i in range(1, len(cal)):
        d = cal[i]
        # On the first trading day of a month, recompute target from PRIOR
        # month-end close (cal[i-1] is the last trading day of prior month when
        # cal[i] is a month-first). Decision uses returns through cal[i-1].
        if i in month_first_set:
            rets = {a: trailing_return(a, i - 1) for a in assets}
            ranked = sorted([a for a in assets if rets[a] is not None],
                            key=lambda a: rets[a], reverse=True)
            new_t = {a: 0.0 for a in assets}
            if ranked:
                top = ranked[:hold_top]
                wt = 1.0 / len(top)
                for a in top:
                    new_t[a] = wt
            # turnover = sum |new - cur| / ... charged one-way on changed fraction
            turn = sum(abs(new_t[a] - cur_weights[a]) for a in assets)
            if turn > 1e-9:
                n_rebalances += 1
                turnover_total += turn
            target_weights = new_t
            holdings_log.append({"date": d, "holds": [a for a in assets if new_t[a] > 0],
                                 "rets": {a: rets[a] for a in assets}})
            cost = (cost_bps / 10000.0) * turn  # one-way on changed notional
            cur_weights = dict(target_weights)
        else:
            cost = 0.0

        # daily blended return using cur_weights (held over day d)
        day_ret = 0.0
        for a in assets:
            cn = close[a].get(d); cp = close[a].get(cal[i - 1])
            r = (cn / cp - 1.0) if (cn is not None and cp is not None and cp > 0) else 0.0
            day_ret += cur_weights[a] * r
        new_eq = equity[-1] * (1.0 + day_ret) * (1.0 - cost)
        equity.append(new_eq)
        eq_dates.append(d)

    in_market = [True] * (len(eq_dates) - 1)
    strat_stats = _stats_from_equity(eq_dates, equity, in_market, n_rebalances)

    # SPX benchmark on same dates
    spx_eq = [1.0]; spx_ds = [eq_dates[0]]
    for j in range(1, len(eq_dates)):
        dn = eq_dates[j]; dp = eq_dates[j - 1]
        cn = bench_close.get(dn); cp = bench_close.get(dp)
        r = (cn / cp - 1.0) if (cn is not None and cp is not None and cp > 0) else 0.0
        spx_eq.append(spx_eq[-1] * (1.0 + r)); spx_ds.append(dn)
    spx_stats = _stats_from_equity(spx_ds, spx_eq)

    return {
        "window": {"start": eq_dates[0], "end": eq_dates[-1], "n_days": len(eq_dates)},
        "strategy": {"stats": dict(strat_stats.__dict__), "dates": eq_dates, "equity": equity},
        "spx": {"stats": dict(spx_stats.__dict__), "equity": spx_eq},
        "n_rebalances": n_rebalances,
        "avg_turnover_per_rebal": (turnover_total / n_rebalances) if n_rebalances else 0.0,
        "pos_log": holdings_log,
    }


# =========================================================================== #
# DRIVER
# =========================================================================== #
def main():
    out: Dict = {}

    base_p = dict(target_ann_vol=0.25, vol_window=20, sma_window=200, w_max=1.0,
                  vix_gate=False, switch_cost_bps=2.0)

    # ---- BASELINE (no overlay) ----
    print(">>> BASELINE vol-target 0.25 ...", flush=True)
    base = run_voltarget_with_multiplier(VolTargetParams(**base_p), multiplier_fn=None)
    out["baseline"] = report_block(base, "BASELINE vol-target 0.25 (sma200, vix-off, 2bps)")

    # ================= TEST 1: COT percentile extremes ===================== #
    print(">>> TEST 1 COT percentile extremes ...", flush=True)
    out["test1_cot_percentile"] = {}
    # Two field interpretations of 'commercials': dealer-net (hedger analog) and
    # lev-net (speculator). For each, the task's contrarian rule:
    #   rank<20% (max short) -> long_mult=1.0 (full; already capped at w_max)
    #   rank>80% (max long)  -> caution_mult=0.5
    # Since base long_mult=1.0 == no boost (w already <= w_max), the only ACTIVE
    # lever is the 0.5x caution at high extremes. We ALSO test a variant that
    # boosts at the low extreme (long_mult=1.25, still capped at w_max=1.0 so it
    # mostly lifts vol-suppressed weights) to give the contrarian-buy side teeth.
    cot_variants = {
        "dealer_net_caution": dict(field="deal_net", long_mult=1.0, caution_mult=0.5),
        "lev_net_caution":    dict(field="lev_net",  long_mult=1.0, caution_mult=0.5),
        "dealer_net_boost":   dict(field="deal_net", long_mult=1.25, caution_mult=0.5),
        "lev_net_boost":      dict(field="lev_net",  long_mult=1.25, caution_mult=0.5),
    }
    for name, kw in cot_variants.items():
        fn = build_cot_percentile_fn(pct_window=52, low_thr=0.20, high_thr=0.80, **kw)
        r = run_voltarget_with_multiplier(VolTargetParams(**base_p), multiplier_fn=fn)
        out["test1_cot_percentile"][name] = report_block(r, "COT-pctile " + name)
        s = out["test1_cot_percentile"][name]["full"]
        print("   %-20s full Sharpe %.3f (base 0.864)  maxDD %.1f%%  avgW %.3f" %
              (name, s["sharpe"], s["maxdd_pct"], s["avg_weight"]))

    # ================= TEST 2: VIX term-structure gate ===================== #
    print(">>> TEST 2 VIX term-structure ...", flush=True)
    out["test2_vix_termstructure"] = {}
    # As specified: VIX3M/VIX < 1.0 -> 0.5x, > 1.05 -> 1.0x, between -> 1.0x.
    # Also a continuous-ish sensitivity: a 0.75x mid band [1.0,1.05].
    vix_variants = {
        "spec_1.00_1.05": dict(backwardation_thr=1.00, contango_thr=1.05,
                               backward_mult=0.5, contango_mult=1.0, mid_mult=1.0),
        "midband_0.75":   dict(backwardation_thr=1.00, contango_thr=1.05,
                               backward_mult=0.5, contango_mult=1.0, mid_mult=0.75),
    }
    for name, kw in vix_variants.items():
        fn = build_vix_ts_fn(**kw)
        r = run_voltarget_with_multiplier(VolTargetParams(**base_p), multiplier_fn=fn)
        out["test2_vix_termstructure"][name] = report_block(r, "VIX-TS " + name)
        s = out["test2_vix_termstructure"][name]["full"]
        print("   %-16s full Sharpe %.3f (base 0.864)  maxDD %.1f%%  avgW %.3f" %
              (name, s["sharpe"], s["maxdd_pct"], s["avg_weight"]))

    # ================= TEST 3: Sector rotation ============================= #
    print(">>> TEST 3 sector rotation SPY/QQQ/GLD/TLT ...", flush=True)
    out["test3_sector_rotation"] = {}
    assets = ["SPY", "QQQ", "GLD", "TLT"]
    rot_variants = {
        "top1_3mo": dict(hold_top=1, lookback_months=3),
        "top2_3mo": dict(hold_top=2, lookback_months=3),
    }
    for name, kw in rot_variants.items():
        r = run_sector_rotation(assets, bench="^GSPC", cost_bps=2.0,
                                 start="2005-01-01", **kw)
        full_s = r["strategy"]["stats"]; full_spx = r["spx"]["stats"]
        oos_s = slice_stats(r, "2019-01-01", "2099-12-31", "strategy")
        oos_spx = slice_stats(r, "2019-01-01", "2099-12-31", "spx")
        is_s = slice_stats(r, "2005-01-01", OOS_SPLIT, "strategy")
        out["test3_sector_rotation"][name] = {
            "window": r["window"],
            "n_rebalances": r["n_rebalances"],
            "full": {"sharpe": full_s["sharpe"], "cagr_pct": full_s["cagr_pct"],
                     "maxdd_pct": full_s["max_drawdown_pct"], "vol_pct": full_s["ann_vol_pct"],
                     "total_return_pct": full_s["total_return_pct"]},
            "is_2005_2018": {"sharpe": is_s.get("sharpe"), "cagr_pct": is_s.get("cagr_pct"),
                             "maxdd_pct": is_s.get("max_drawdown_pct")},
            "oos_2019_today": {"sharpe": oos_s.get("sharpe"), "cagr_pct": oos_s.get("cagr_pct"),
                               "maxdd_pct": oos_s.get("max_drawdown_pct")},
            "spx_full": {"sharpe": full_spx["sharpe"], "cagr_pct": full_spx["cagr_pct"],
                         "maxdd_pct": full_spx["max_drawdown_pct"]},
            "spx_oos": {"sharpe": oos_spx.get("sharpe"), "cagr_pct": oos_spx.get("cagr_pct")},
        }
        s = out["test3_sector_rotation"][name]
        print("   %-10s full Sharpe %.3f CAGR %.1f%% maxDD %.1f%% | OOS Sharpe %.3f | SPX full Sharpe %.3f" %
              (name, s["full"]["sharpe"], s["full"]["cagr_pct"], s["full"]["maxdd_pct"],
               s["oos_2019_today"]["sharpe"], s["spx_full"]["sharpe"]))

    with open("reports/_sigimprove_result.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("")
    print("wrote reports/_sigimprove_result.json")
    return out


if __name__ == "__main__":
    main()
