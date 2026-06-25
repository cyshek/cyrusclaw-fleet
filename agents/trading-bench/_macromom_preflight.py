"""MACRO MOMENTUM cross-sectional L/S PRE-FLIGHT (GO/NO-GO) — single file.

Idea #4, AQR_READING_SPRINT_20260624.md. AQR "Macro Momentum" (Brooks 2017):
rank a multi-asset macro basket on a BLENDED trailing-momentum score, go LONG
top-half / SHORT bottom-half, DOLLAR-NEUTRAL, monthly rebal, market-neutral.

THE HONEST TEST (standing cross-sec gate): the LONG-TOP MINUS SHORT-BOTTOM
SPREAD return. Long-only "beats basket" does NOT count.

Free-data framing: AQR blends trailing macro fundamentals + price momentum.
With free adjclose-only data the defensible proxy is a BLENDED multi-horizon
PRICE momentum score (the price-momentum leg, which Brooks shows carries most
of the cross-sectional rank signal). Blend = mean of 3/6/12-month trailing
total returns, each skipping the most recent month (21 td) to avoid 1-month
reversal, then z-scored across the basket each rebalance.

Self-contained spread backtest composed directly from adjclose (documented
workaround: walk_forward_xsec skips <2-sym baskets / raises ZeroTradesError on
warmup, and the long-top-K harness doesn't expose a clean dollar-neutral L/S
SPREAD). Monthly rebal on the first trading day of each month. Hold the L/S
book for the month, realize next-month forward returns per leg, spread =
long-leg mean fwd return MINUS short-leg mean fwd return.

Window: 2008-01-01 .. present. Full 11-asset macro basket (UUP from 2007-03 so
2008+ is clean), compared against the prior failed 6-asset set.

IS/OOS: IS = pre-2019, OOS = 2019+. Costs: 2 bps per side applied to the
turnover of BOTH legs.
"""
from __future__ import annotations

import json
import math
import sys
from bisect import bisect_right
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS))

from runner import daily_bars_cache as dbc

# ----------------------------------------------------------------- config
BROAD = [
    "SPY", "EFA", "EEM",   # equities
    "TLT", "IEF",          # rates
    "DBC", "GLD", "USO",   # commodities
    "LQD", "VNQ",          # credit / REIT
    "UUP",                 # dollar
]
PRIOR6 = ["SPY", "EFA", "TLT", "VNQ", "DBC", "GLD"]  # failed Sharpe-0.41 set

START = "2008-01-01"
OOS_SPLIT = "2019-01-01"
SKIP_TD = 21          # skip most-recent month (reversal guard)
H_SHORT = 63          # ~3 months trading days
H_MED = 126           # ~6 months
H_LONG = 252          # ~12 months
COST_BPS_PER_SIDE = 2.0


# ----------------------------------------------------------------- data
def load_series(symbols: List[str]):
    """Return ({sym: {date: adjclose}}, {sym: [sorted dates]})."""
    prices: Dict[str, Dict[str, float]] = {}
    dates: Dict[str, List[str]] = {}
    for s in symbols:
        bars = dbc.get_daily(s)
        d = {b["date"]: float(b["adjclose"]) for b in bars
             if b.get("adjclose") is not None}
        prices[s] = d
        dates[s] = sorted(d.keys())
    return prices, dates


def union_calendar(dates: Dict[str, List[str]], start: str) -> List[str]:
    alld = set()
    for ds in dates.values():
        alld.update(ds)
    return sorted(x for x in alld if x >= start)


def px_asof(prices_s: Dict[str, float], dates_s: List[str], target: str
            ) -> Optional[float]:
    """adjclose with date <= target (forward-fill, no lookahead)."""
    pos = bisect_right(dates_s, target)
    if pos <= 0:
        return None
    return prices_s.get(dates_s[pos - 1])


def idx_asof(dates_s: List[str], target: str) -> int:
    """Index of most-recent symbol date <= target, or -1."""
    pos = bisect_right(dates_s, target)
    return pos - 1  # -1 if none


def horizon_return(prices_s: Dict[str, float], dates_s: List[str],
                   asof: str, skip: int, lookback: int) -> Optional[float]:
    """Trailing total return over `lookback` trading days ending `skip` td ago.

    End point  = dates_s[i - skip]
    Start point= dates_s[i - skip - lookback]
    where i = idx_asof(asof). Uses the symbol's OWN observed trading dates so
    the horizon is a true N-trading-day window (not calendar-day approximate).
    """
    i = idx_asof(dates_s, asof)
    if i < 0:
        return None
    end_i = i - skip
    start_i = i - skip - lookback
    if start_i < 0:
        return None
    p_end = prices_s.get(dates_s[end_i])
    p_start = prices_s.get(dates_s[start_i])
    if not p_end or not p_start or p_start <= 0:
        return None
    return (p_end / p_start) - 1.0


def blended_score(prices_s, dates_s, asof: str) -> Optional[float]:
    """Mean of 3/6/12-month skip-1m trailing returns. None if any leg missing."""
    r3 = horizon_return(prices_s, dates_s, asof, SKIP_TD, H_SHORT)
    r6 = horizon_return(prices_s, dates_s, asof, SKIP_TD, H_MED)
    r12 = horizon_return(prices_s, dates_s, asof, SKIP_TD, H_LONG)
    if r3 is None or r6 is None or r12 is None:
        return None
    return (r3 + r6 + r12) / 3.0


def fwd_return(prices_s, dates_s, d0: str, d1: str) -> Optional[float]:
    """Total return from price-asof(d0) to price-asof(d1)."""
    p0 = px_asof(prices_s, dates_s, d0)
    p1 = px_asof(prices_s, dates_s, d1)
    if not p0 or not p1 or p0 <= 0:
        return None
    return (p1 / p0) - 1.0


# ----------------------------------------------------------------- rebal
def rebalance_days(cal: List[str]) -> List[str]:
    seen = set()
    out = []
    for d in cal:
        ym = d[:7]
        if ym not in seen:
            seen.add(ym)
            out.append(d)
    return out


def zscore(vals: Dict[str, float]) -> Dict[str, float]:
    xs = list(vals.values())
    n = len(xs)
    if n < 2:
        return {k: 0.0 for k in vals}
    mu = sum(xs) / n
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var) if var > 0 else 1.0
    return {k: (v - mu) / sd for k, v in vals.items()}


def ann_sharpe(returns: List[float], ppy: float = 12.0) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mu = sum(returns) / n
    var = sum((r - mu) ** 2 for r in returns) / (n - 1)
    if var <= 0:
        return 0.0
    return (mu / math.sqrt(var)) * math.sqrt(ppy)


def cum_return(returns: List[float]) -> float:
    c = 1.0
    for r in returns:
        c *= (1.0 + r)
    return c - 1.0


# ----------------------------------------------------------------- engine
def run_ls(symbols: List[str], start: str = START,
           cost_bps_per_side: float = 0.0) -> dict:
    """Run the dollar-neutral L/S spread backtest.

    Returns dict with the monthly spread series, long-leg series, short-leg
    series, dates, plus a long-only-top series (for the 'beats basket' contrast)
    and selection-frequency per symbol.
    """
    prices, dates = load_series(symbols)
    cal = union_calendar(dates, start)
    rebs = rebalance_days(cal)

    # Need at least one forward month, so iterate to len-1.
    spread_rets: List[float] = []
    long_rets: List[float] = []
    short_rets: List[float] = []
    longonly_rets: List[float] = []
    bh_rets: List[float] = []           # equal-weight all-asset (the "basket")
    reb_used: List[str] = []
    sel_count = {s: 0 for s in symbols}
    n_months = 0
    prev_long: set = set()
    prev_short: set = set()

    for k in range(len(rebs) - 1):
        d0 = rebs[k]
        d1 = rebs[k + 1]
        # Score each symbol that has data + sufficient history.
        scores = {}
        for s in symbols:
            sc = blended_score(prices[s], dates[s], d0)
            if sc is not None:
                scores[s] = sc
        if len(scores) < 4:        # need a meaningful cross-section
            continue
        z = zscore(scores)
        ranked = sorted(z.keys(), key=lambda s: z[s], reverse=True)
        half = len(ranked) // 2
        longs = ranked[:half]
        shorts = ranked[len(ranked) - half:]   # bottom half (same size)
        if not longs or not shorts:
            continue

        # Forward returns for this month (d0 -> d1), each leg equal-weight.
        def leg_ret(members):
            rs = []
            for s in members:
                fr = fwd_return(prices[s], dates[s], d0, d1)
                if fr is not None:
                    rs.append(fr)
            return (sum(rs) / len(rs)) if rs else None

        lr = leg_ret(longs)
        sr = leg_ret(shorts)
        if lr is None or sr is None:
            continue
        # equal-weight whole basket forward return (the BH "basket")
        all_rs = []
        for s in symbols:
            fr = fwd_return(prices[s], dates[s], d0, d1)
            if fr is not None:
                all_rs.append(fr)
        bh = (sum(all_rs) / len(all_rs)) if all_rs else 0.0

        # Turnover cost: fraction of each leg that changed names. Approx the
        # dollar-neutral book turnover as (changed longs + changed shorts) /
        # (len longs + len shorts); each unit of turnover pays cost per side.
        cur_long = set(longs)
        cur_short = set(shorts)
        changed = len(cur_long.symmetric_difference(prev_long)) + \
            len(cur_short.symmetric_difference(prev_short))
        denom = (len(cur_long) + len(cur_short)) * 2  # both open & close sides
        turn_frac = (changed / denom) if denom else 0.0
        cost = turn_frac * (cost_bps_per_side / 1e4) * 2.0  # in+out
        prev_long, prev_short = cur_long, cur_short

        spread = (lr - sr) - cost
        spread_rets.append(spread)
        long_rets.append(lr)
        short_rets.append(sr)
        longonly_rets.append(lr - cost / 2.0)   # long-only pays one side
        bh_rets.append(bh)
        reb_used.append(d1)
        for s in longs:
            sel_count[s] += 1
        n_months += 1

    return {
        "symbols": symbols,
        "n_assets": len(symbols),
        "n_months": n_months,
        "start": start,
        "dates": reb_used,
        "spread_rets": spread_rets,
        "long_rets": long_rets,
        "short_rets": short_rets,
        "longonly_rets": longonly_rets,
        "bh_rets": bh_rets,
        "sel_count": sel_count,
    }


def split_is_oos(dates: List[str], rets: List[float], split: str
                 ) -> Tuple[List[float], List[float]]:
    is_r, oos_r = [], []
    for d, r in zip(dates, rets):
        (is_r if d < split else oos_r).append(r)
    return is_r, oos_r


def summarize(res: dict, label: str) -> dict:
    d = res["dates"]
    sp = res["spread_rets"]
    fp_sh = ann_sharpe(sp)
    is_sp, oos_sp = split_is_oos(d, sp, OOS_SPLIT)
    out = {
        "label": label,
        "n_assets": res["n_assets"],
        "n_months": res["n_months"],
        "span": (d[0] if d else None, d[-1] if d else None),
        "spread_fp_sharpe": fp_sh,
        "spread_fp_cum_pct": cum_return(sp) * 100.0,
        "spread_fp_mean_monthly_bps": (sum(sp) / len(sp) * 1e4) if sp else 0.0,
        "is_n": len(is_sp),
        "is_sharpe": ann_sharpe(is_sp),
        "is_cum_pct": cum_return(is_sp) * 100.0,
        "oos_n": len(oos_sp),
        "oos_sharpe": ann_sharpe(oos_sp),
        "oos_cum_pct": cum_return(oos_sp) * 100.0,
        "long_fp_sharpe": ann_sharpe(res["long_rets"]),
        "short_fp_sharpe": ann_sharpe(res["short_rets"]),
        "longonly_fp_sharpe": ann_sharpe(res["longonly_rets"]),
        "bh_fp_sharpe": ann_sharpe(res["bh_rets"]),
        "longonly_cum_pct": cum_return(res["longonly_rets"]) * 100.0,
        "bh_cum_pct": cum_return(res["bh_rets"]) * 100.0,
        "sel_count": res["sel_count"],
    }
    return out


def main() -> None:
    out_all = {}

    print("=" * 70)
    print("BROAD 11-asset basket — ZERO cost")
    r_broad0 = run_ls(BROAD, cost_bps_per_side=0.0)
    s_broad0 = summarize(r_broad0, "broad11_0bps")
    out_all["broad11_0bps"] = s_broad0
    print(json.dumps(s_broad0, indent=2, default=str))

    print("=" * 70)
    print("BROAD 11-asset basket — 2 bps/side")
    r_broad2 = run_ls(BROAD, cost_bps_per_side=COST_BPS_PER_SIDE)
    s_broad2 = summarize(r_broad2, "broad11_2bps")
    out_all["broad11_2bps"] = s_broad2
    print(json.dumps(s_broad2, indent=2, default=str))

    print("=" * 70)
    print("PRIOR 6-asset basket — ZERO cost (the Sharpe-0.41 set)")
    r_p6_0 = run_ls(PRIOR6, cost_bps_per_side=0.0)
    s_p6_0 = summarize(r_p6_0, "prior6_0bps")
    out_all["prior6_0bps"] = s_p6_0
    print(json.dumps(s_p6_0, indent=2, default=str))

    print("=" * 70)
    print("PRIOR 6-asset basket — 2 bps/side")
    r_p6_2 = run_ls(PRIOR6, cost_bps_per_side=COST_BPS_PER_SIDE)
    s_p6_2 = summarize(r_p6_2, "prior6_2bps")
    out_all["prior6_2bps"] = s_p6_2
    print(json.dumps(s_p6_2, indent=2, default=str))

    Path(WS / "_macromom_results.json").write_text(
        json.dumps(out_all, indent=2, default=str))
    print("\n[driver] wrote _macromom_results.json")


if __name__ == "__main__":
    main()
