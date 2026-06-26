"""Rotation-sleeve LOOKBACK x CADENCE sweep.

Generalizes _sigimprove_tests.run_sector_rotation (the VALIDATED TEST 3 builder)
along two axes WITHOUT reimplementing the sleeve math: same ETF set
(SPY/QQQ/GLD/TLT), same top-2 equal-weight, same 2bps one-way turnover cost,
same daily-marking + _stats_from_equity ruler, same lookahead contract (rank on
data through the PRIOR period-end close, hold the next period).

AXES
  lookback : trailing-return window (trading days) for ranking the 4 ETFs.
             63d == the live 3-mo baseline (run_sector_rotation uses
             lb_days = lookback_months*21, so 3mo => 63d exactly -> my 63d cell
             MUST match the validated baseline; that's the sanity control).
  cadence  : how often to reselect/rebalance the top-2.
             monthly (every month-open, the baseline), bimonthly (every 2nd
             month-open), quarterly (every 3rd month-open). Slower than monthly
             only -- the rotation signal is monthly momentum; sub-monthly churns.

Also: a DUAL-LOOKBACK blend (average the RANK of two windows) reported as one
extra column, not the headline.

RULER: _stats_from_equity (population stdev, sqrt(252)) -- the SAME validated
ruler run_sector_rotation uses. fp_sharpe (sample stdev) reported as a cross-check.

SPLIT: OOS_SPLIT = 2018-12-31 (IS = 2005-01-01..2018-12-31, OOS = 2019-01-01..),
matching the validation. slice_stats rebases to 1.0 at slice start.

NO-LOOKAHEAD: ranking at a rebalance index i uses trailing returns through cal[i-1]
(the prior period-end close, strictly before the held period). Forward P&L is the
next period. Adjclose is PIT by construction (Yahoo v8 adjclose).

Run: python3 _rot_lookback_cadence_sweep.py
Writes: reports/_rot_lookback_cadence_result.json
"""
from __future__ import annotations

import bisect
import json
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from strategies_candidates.leveraged_long_trend.backtest_daily import (
    _stats_from_equity, TRADING_DAYS,
)
from runner.fp_sharpe import sharpe_from_returns

OOS_SPLIT = "2018-12-31"
ASSETS = ["SPY", "QQQ", "GLD", "TLT"]
OFFENSE = {"SPY", "QQQ"}
DEFENSE = {"GLD", "TLT"}


# --------------------------------------------------------------------------- #
# Generalized rotation builder. Mirrors run_sector_rotation EXACTLY except:
#   - lookback expressed directly in trading days (lb_days) instead of months*21
#   - cadence_months: reselect every `cadence_months`-th month-open
#   - dual_lb: optional second window; rank = average of the two windows' ranks
# Everything else (top-2 EW, 2bps one-way cost on turned-over notional, daily
# marking, _stats_from_equity) is identical to the validated builder.
# --------------------------------------------------------------------------- #
def run_rotation(assets: List[str], lb_days: int, cadence_months: int,
                 bench: str = "^GSPC", hold_top: int = 2, cost_bps: float = 2.0,
                 start: str = "2005-01-01", end: Optional[str] = None,
                 dual_lb: Optional[int] = None) -> Dict:
    bars = {a: dbc.get_daily(a) for a in assets}
    bench_bars = dbc.get_daily(bench)

    if end is None:
        end = min(b[-1]["date"] for b in bars.values())
    date_sets = [set(b["date"] for b in bars[a]) for a in assets]
    common = sorted(set.intersection(*date_sets))
    cal = [d for d in common if start <= d <= end]

    close = {a: {b["date"]: b["adjclose"] for b in bars[a]} for a in assets}
    bench_close = {b["date"]: b["adjclose"] for b in bench_bars}

    # month boundaries: first trading day of each month in cal
    month_first: List[int] = []
    seen = set()
    for idx, d in enumerate(cal):
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            month_first.append(idx)
    # cadence: keep every `cadence_months`-th month-open (anchored to first month)
    rebal_idx_set = set(month_first[::cadence_months])

    def trailing_return(a: str, end_idx: int, window: int) -> Optional[float]:
        if end_idx - window < 0:
            return None
        d_end = cal[end_idx]
        d_start = cal[end_idx - window]
        c_end = close[a].get(d_end)
        c_start = close[a].get(d_start)
        if c_end is None or c_start is None or c_start <= 0:
            return None
        return c_end / c_start - 1.0

    def rank_score(end_idx: int) -> Dict[str, Optional[float]]:
        """Higher score = stronger momentum (better). For a single window this is
        just the trailing return. For a dual-lookback it is the AVERAGE of the two
        windows' cross-sectional rank-fractions (0=worst..1=best), so the two
        timeframes are equally weighted regardless of scale."""
        r1 = {a: trailing_return(a, end_idx, lb_days) for a in assets}
        if dual_lb is None:
            return r1
        r2 = {a: trailing_return(a, end_idx, dual_lb) for a in assets}

        def rankfrac(rdict: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
            avail = [a for a in assets if rdict[a] is not None]
            if not avail:
                return {a: None for a in assets}
            order = sorted(avail, key=lambda a: rdict[a])  # ascending
            n = len(order)
            out: Dict[str, Optional[float]] = {a: None for a in assets}
            for pos, a in enumerate(order):
                out[a] = pos / (n - 1) if n > 1 else 0.5
            return out

        f1 = rankfrac(r1)
        f2 = rankfrac(r2)
        out: Dict[str, Optional[float]] = {}
        for a in assets:
            if f1[a] is None and f2[a] is None:
                out[a] = None
            elif f1[a] is None:
                out[a] = f2[a]
            elif f2[a] is None:
                out[a] = f1[a]
            else:
                out[a] = 0.5 * (f1[a] + f2[a])
        return out

    equity = [1.0]
    eq_dates = [cal[0]]
    cur_weights: Dict[str, float] = {a: 0.0 for a in assets}
    target_weights: Dict[str, float] = {a: 0.0 for a in assets}
    n_rebalances = 0
    turnover_total = 0.0
    holdings_log: List[Dict] = []
    # exposure tracking: time-weighted avg allocation to offense vs defense
    off_w_sum = 0.0
    def_w_sum = 0.0
    nday = 0

    for i in range(1, len(cal)):
        d = cal[i]
        if i in rebal_idx_set:
            scores = rank_score(i - 1)  # decision uses data through cal[i-1]
            ranked = sorted([a for a in assets if scores[a] is not None],
                            key=lambda a: scores[a], reverse=True)
            new_t = {a: 0.0 for a in assets}
            if ranked:
                top = ranked[:hold_top]
                wt = 1.0 / len(top)
                for a in top:
                    new_t[a] = wt
            turn = sum(abs(new_t[a] - cur_weights[a]) for a in assets)
            if turn > 1e-9:
                n_rebalances += 1
                turnover_total += turn
            target_weights = new_t
            holdings_log.append({
                "date": d,
                "lookback_window_end": cal[i - 1],
                "holds": [a for a in assets if new_t[a] > 0],
                "scores": {a: scores[a] for a in assets},
            })
            cost = (cost_bps / 10000.0) * turn
            cur_weights = dict(target_weights)
        else:
            cost = 0.0

        day_ret = 0.0
        for a in assets:
            cn = close[a].get(d)
            cp = close[a].get(cal[i - 1])
            rr = (cn / cp - 1.0) if (cn is not None and cp is not None and cp > 0) else 0.0
            day_ret += cur_weights[a] * rr
        new_eq = equity[-1] * (1.0 + day_ret) * (1.0 - cost)
        equity.append(new_eq)
        eq_dates.append(d)

        off_w_sum += sum(cur_weights[a] for a in assets if a in OFFENSE)
        def_w_sum += sum(cur_weights[a] for a in assets if a in DEFENSE)
        nday += 1

    in_market = [True] * (len(eq_dates) - 1)
    strat_stats = _stats_from_equity(eq_dates, equity, in_market, n_rebalances)

    spx_eq = [1.0]
    spx_ds = [eq_dates[0]]
    for j in range(1, len(eq_dates)):
        dn = eq_dates[j]
        dp = eq_dates[j - 1]
        cn = bench_close.get(dn)
        cp = bench_close.get(dp)
        rr = (cn / cp - 1.0) if (cn is not None and cp is not None and cp > 0) else 0.0
        spx_eq.append(spx_eq[-1] * (1.0 + rr))
        spx_ds.append(dn)
    spx_stats = _stats_from_equity(spx_ds, spx_eq)

    return {
        "window": {"start": eq_dates[0], "end": eq_dates[-1], "n_days": len(eq_dates)},
        "strategy": {"stats": dict(strat_stats.__dict__), "dates": eq_dates, "equity": equity},
        "spx": {"stats": dict(spx_stats.__dict__), "equity": spx_eq},
        "n_rebalances": n_rebalances,
        "avg_turnover_per_rebal": (turnover_total / n_rebalances) if n_rebalances else 0.0,
        "avg_offense_w": (off_w_sum / nday) if nday else 0.0,
        "avg_defense_w": (def_w_sum / nday) if nday else 0.0,
        "pos_log": holdings_log,
    }


# --------------------------------------------------------------------------- #
# slice_stats: rebase to 1.0 at slice start, then _stats_from_equity. Identical
# semantics to _sigimprove_tests.slice_stats. ALSO compute fp (sample-stdev)
# Sharpe over the slice as a cross-check.
# --------------------------------------------------------------------------- #
def slice_block(result: Dict, start: str, end: str) -> Dict:
    ds = result["strategy"]["dates"]
    eq = result["strategy"]["equity"]
    lo = bisect.bisect_left(ds, start)
    hi = bisect.bisect_right(ds, end)
    if hi - lo < 3:
        return {"n": hi - lo}
    sub_ds = ds[lo:hi]
    sub_eq = eq[lo:hi]
    base = sub_eq[0]
    sub_eq = [v / base for v in sub_eq]
    st = _stats_from_equity(sub_ds, sub_eq)
    rets = [sub_eq[k] / sub_eq[k - 1] - 1.0 for k in range(1, len(sub_eq))]
    fp = sharpe_from_returns(rets, TRADING_DAYS)
    return {
        "sharpe": st.sharpe,
        "fp_sharpe": fp,
        "cagr_pct": st.cagr_pct,
        "maxdd_pct": st.max_drawdown_pct,
        "total_return_pct": st.total_return_pct,
    }


def full_block(result: Dict) -> Dict:
    st = result["strategy"]["stats"]
    eq = result["strategy"]["equity"]
    rets = [eq[k] / eq[k - 1] - 1.0 for k in range(1, len(eq))]
    fp = sharpe_from_returns(rets, TRADING_DAYS)
    return {
        "sharpe": st["sharpe"],
        "fp_sharpe": fp,
        "cagr_pct": st["cagr_pct"],
        "maxdd_pct": st["max_drawdown_pct"],
        "total_return_pct": st["total_return_pct"],
        "ann_vol_pct": st["ann_vol_pct"],
    }


CADENCES = {"monthly": 1, "bimonthly": 2, "quarterly": 3}
LOOKBACKS = [21, 42, 63, 126, 189, 252]


def cell(lb_days: int, cadence_months: int, dual_lb: Optional[int] = None,
         end: Optional[str] = None) -> Dict:
    r = run_rotation(ASSETS, lb_days=lb_days, cadence_months=cadence_months,
                     hold_top=2, cost_bps=2.0, start="2005-01-01", end=end,
                     dual_lb=dual_lb)
    full = full_block(r)
    is_ = slice_block(r, "2005-01-01", OOS_SPLIT)
    oos = slice_block(r, "2019-01-01", "2099-12-31")
    spx = r["spx"]["stats"]
    return {
        "lb_days": lb_days,
        "dual_lb": dual_lb,
        "cadence_months": cadence_months,
        "window": r["window"],
        "n_rebalances": r["n_rebalances"],
        "avg_offense_w": r["avg_offense_w"],
        "avg_defense_w": r["avg_defense_w"],
        "full": full,
        "is_2005_2018": is_,
        "oos_2019_today": oos,
        "spx_full_sharpe": spx["sharpe"],
        "pos_log_head": r["pos_log"][:6],
    }


def main():
    out: Dict = {"meta": {"split": OOS_SPLIT, "assets": ASSETS,
                          "ruler": "population-stdev sqrt(252) (validated); fp=sample-stdev"}}

    print(">>> Baseline sanity: 63d / monthly (== validated 3-mo/monthly) ...", flush=True)
    base = cell(63, 1)
    out["baseline_63_monthly"] = base
    b = base
    print("    full S %.4f (fp %.4f) | IS %.4f | OOS %.4f | maxDD %.2f%% | raw %.1f%% | SPX %.4f | nreb %d" % (
        b["full"]["sharpe"], b["full"]["fp_sharpe"], b["is_2005_2018"]["sharpe"],
        b["oos_2019_today"]["sharpe"], b["full"]["maxdd_pct"],
        b["full"]["total_return_pct"], b["spx_full_sharpe"], b["n_rebalances"]))
    print("    REPORT (2026-06-18 window): full 0.916 / IS 0.929 / OOS 0.898 / maxDD -29.0 / SPX 0.542")

    print("\n>>> LOOKBACK x CADENCE grid ...", flush=True)
    grid: Dict[str, Dict[str, Dict]] = {}
    for lb in LOOKBACKS:
        grid[str(lb)] = {}
        for cname, cm in CADENCES.items():
            c = cell(lb, cm)
            grid[str(lb)][cname] = c
            print("    lb=%3dd  %-9s  full S %.4f  IS %.4f  OOS %.4f  maxDD %6.2f%%  raw %7.1f%%  off/def %.2f/%.2f  nreb %d" % (
                lb, cname, c["full"]["sharpe"], c["is_2005_2018"]["sharpe"],
                c["oos_2019_today"]["sharpe"], c["full"]["maxdd_pct"],
                c["full"]["total_return_pct"], c["avg_offense_w"], c["avg_defense_w"],
                c["n_rebalances"]))
    out["grid"] = grid

    print("\n>>> DUAL-LOOKBACK blends (rank-avg) ...", flush=True)
    duals = [(63, 126), (21, 252), (63, 252)]
    dual_out: Dict[str, Dict[str, Dict]] = {}
    for (a, bw) in duals:
        key = "%d+%d" % (a, bw)
        dual_out[key] = {}
        for cname, cm in CADENCES.items():
            c = cell(a, cm, dual_lb=bw)
            dual_out[key][cname] = c
            print("    dual=%-8s %-9s  full S %.4f  IS %.4f  OOS %.4f  maxDD %6.2f%%  raw %7.1f%%  off/def %.2f/%.2f" % (
                key, cname, c["full"]["sharpe"], c["is_2005_2018"]["sharpe"],
                c["oos_2019_today"]["sharpe"], c["full"]["maxdd_pct"],
                c["full"]["total_return_pct"], c["avg_offense_w"], c["avg_defense_w"]))
    out["dual_lookback"] = dual_out

    with open("reports/_rot_lookback_cadence_result.json", "w") as fout:
        json.dump(out, fout, indent=2, default=str)
    print("\nwrote reports/_rot_lookback_cadence_result.json")
    return out


if __name__ == "__main__":
    main()
