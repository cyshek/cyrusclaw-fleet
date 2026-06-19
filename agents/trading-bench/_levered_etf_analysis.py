"""Levered-ETF trend research driver. Standalone, OFFLINE (bars_cache only).

Computes, over the SAME cache-floored window for every series:
  - SMA-trend overlay on each 3x ETF (hold when close>SMA(N), flat else), N in {50,100,200}
  - Buy-and-hold the 3x ETF (no timing)
  - Buy-and-hold SPY (the BAR)
  - Cross-sectional top-K rotation across the 3x basket (monthly)

Metrics per series: total return %, annualized Sharpe, Sortino, max drawdown %,
plus info ratio vs SPY for the active strategies.

Cost realism: alpaca_stocks-style spread (2 bps one-way) applied on each
position change (entry+exit). Expense-ratio drag (~0.9%/yr) noted qualitatively
AND optionally modeled as a daily NAV haircut for the 3x legs.
"""
from __future__ import annotations
import math
from datetime import datetime, timezone
from runner import bars_cache

END = datetime(2026, 5, 29, tzinfo=timezone.utc)
DAYS = 2600
BASKET = ["TQQQ", "SOXL", "UPRO", "TECL"]
TRADING_DAYS = 252
SPREAD_BPS = 2.0       # one-way, alpaca_stocks liquid-ETF estimate
EXPENSE_BPS_YR = 90.0  # ~0.9%/yr expense ratio for 3x ETFs (modeled as daily drag)


def load(sym):
    b = bars_cache.get_bars(sym, "1Day", days=DAYS, end_dt=END)
    return [(x["t"][:10], float(x["c"])) for x in b]


def align(series_map):
    """Intersect on common dates, return (dates, {sym: [close...]})."""
    common = None
    for s, rows in series_map.items():
        ds = set(d for d, _ in rows)
        common = ds if common is None else (common & ds)
    dates = sorted(common)
    out = {}
    for s, rows in series_map.items():
        m = dict(rows)
        out[s] = [m[d] for d in dates]
    return dates, out


def sma(vals, i, n):
    if i + 1 < n:
        return None
    return sum(vals[i + 1 - n:i + 1]) / n


def metrics(equity, dates):
    """Annualized Sharpe/Sortino from daily equity returns; total ret; maxDD.
    Returns dict + the daily return series (for info ratio)."""
    rets = []
    for i in range(1, len(equity)):
        p = equity[i - 1]
        rets.append((equity[i] - p) / p if p > 0 else 0.0)
    n = len(rets)
    mean = sum(rets) / n if n else 0.0
    var = sum((r - mean) ** 2 for r in rets) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(var)
    downside = [r for r in rets if r < 0]
    dvar = sum(r * r for r in downside) / (n - 1) if n > 1 else 0.0
    dstd = math.sqrt(dvar)
    ann = math.sqrt(TRADING_DAYS)
    sharpe = (mean / std) * ann if std > 0 else 0.0
    sortino = (mean / dstd) * ann if dstd > 0 else 0.0
    peak = -1e18
    maxdd = 0.0
    for e in equity:
        peak = max(peak, e)
        if peak > 0:
            dd = (e - peak) / peak
            maxdd = min(maxdd, dd)
    total = (equity[-1] - equity[0]) / equity[0]
    return {"total": total, "sharpe": sharpe, "sortino": sortino,
            "maxdd": maxdd}, rets


def info_ratio(strat_rets, bench_rets):
    """Annualized IR of strat vs bench (active-return mean / tracking error)."""
    n = min(len(strat_rets), len(bench_rets))
    active = [strat_rets[i] - bench_rets[i] for i in range(n)]
    m = sum(active) / n if n else 0.0
    v = sum((a - m) ** 2 for a in active) / (n - 1) if n > 1 else 0.0
    te = math.sqrt(v)
    return (m / te) * math.sqrt(TRADING_DAYS) if te > 0 else 0.0


def daily_drag(bps_yr):
    """Per-day multiplicative haircut for an annual expense ratio."""
    return (1.0 - bps_yr / 1e4) ** (1.0 / TRADING_DAYS)


def bh_equity(closes, apply_expense=False):
    """Buy-and-hold equity curve, normalized to 1.0 at start."""
    drag = daily_drag(EXPENSE_BPS_YR) if apply_expense else 1.0
    eq = [1.0]
    for i in range(1, len(closes)):
        r = closes[i] / closes[i - 1]
        eq.append(eq[-1] * r * drag)
    return eq


def sma_trend_equity(closes, n, apply_expense=True):
    """Hold (long) when prev close > SMA(N), else flat (cash). Decision uses
    only info available at close of day i-1 (no lookahead): position for day i
    is set by signal at i-1. Spread charged on each position change.
    Expense drag applies only while invested."""
    drag = daily_drag(EXPENSE_BPS_YR) if apply_expense else 1.0
    eq = [1.0]
    pos = 0  # 0 flat, 1 long
    spread = SPREAD_BPS / 1e4
    n_trades = 0
    days_in = 0
    for i in range(1, len(closes)):
        # signal from i-1
        s = sma(closes, i - 1, n)
        want = 1 if (s is not None and closes[i - 1] > s) else 0
        # apply day i return based on position held during day i (= want)
        if want != pos:
            # transition cost (spread on the traded notional)
            eq[-1] *= (1.0 - spread)
            n_trades += 1
            pos = want
        if pos == 1:
            r = closes[i] / closes[i - 1]
            eq.append(eq[-1] * r * drag)
            days_in += 1
        else:
            eq.append(eq[-1])
    pct_in = days_in / (len(closes) - 1) if len(closes) > 1 else 0.0
    return eq, n_trades, pct_in


def xsec_rotation_equity(closes_by_sym, dates, lookback, top_k,
                         apply_expense=True):
    """Monthly top-K rotation by trailing `lookback`-day return across the
    3x basket. Rebalance on month change. Equal weight across K legs.
    Spread on each leg change. Expense drag while invested."""
    syms = list(closes_by_sym.keys())
    nd = len(dates)
    drag = daily_drag(EXPENSE_BPS_YR) if apply_expense else 1.0
    spread = SPREAD_BPS / 1e4
    eq = [1.0]
    holdings = []  # current symbols held (equal weight)
    last_month = None
    n_trades = 0
    days_in = 0
    for i in range(1, nd):
        # apply day i return from holdings set at i-1
        if holdings:
            legret = 0.0
            for s in holdings:
                legret += closes_by_sym[s][i] / closes_by_sym[s][i - 1]
            legret /= len(holdings)
            eq.append(eq[-1] * legret * drag)
            days_in += 1
        else:
            eq.append(eq[-1])
        # rebalance decision at close of day i (effective next day)
        month = dates[i][:7]
        if month != last_month:
            last_month = month
            # rank by trailing lookback return using data through day i
            ranks = []
            for s in syms:
                if i - lookback < 0:
                    continue
                a = closes_by_sym[s][i - lookback]
                b = closes_by_sym[s][i]
                if a > 0:
                    ranks.append(((b - a) / a, s))
            ranks.sort(reverse=True)
            new_hold = [s for _, s in ranks[:top_k]]
            if set(new_hold) != set(holdings) and ranks:
                changed = len(set(new_hold) ^ set(holdings))
                eq[-1] *= (1.0 - spread) ** (changed if changed else 1)
                n_trades += changed
                holdings = new_hold
    pct_in = days_in / (nd - 1) if nd > 1 else 0.0
    return eq, n_trades, pct_in


def fmt(m):
    return (f"ret={m['total']*100:+8.1f}%  sharpe={m['sharpe']:5.2f}  "
            f"sortino={m['sortino']:5.2f}  maxDD={m['maxdd']*100:7.1f}%")


def main():
    raw = {s: load(s) for s in BASKET + ["SPY"]}
    dates, closes = align(raw)
    print(f"# Aligned span: {dates[0]} -> {dates[-1]}  ({len(dates)} bars)\n")

    # Benchmarks
    spy_eq = bh_equity(closes["SPY"], apply_expense=False)
    spy_m, spy_rets = metrics(spy_eq, dates)
    print("BENCHMARK  BH-SPY                    " + fmt(spy_m))
    print()

    rows = []  # (label, metrics, rets, extra)
    # BH each 3x ETF
    for s in BASKET:
        eq = bh_equity(closes[s], apply_expense=True)
        m, r = metrics(eq, dates)
        ir = info_ratio(r, spy_rets)
        print(f"BH-3x      {s:6s} (expense-adj)      " + fmt(m) + f"  IRvSPY={ir:5.2f}")
    print()

    # SMA trend per ETF per N
    best = {}
    for s in BASKET:
        for n in (50, 100, 200):
            eq, ntr, pin = sma_trend_equity(closes[s], n, apply_expense=True)
            m, r = metrics(eq, dates)
            ir = info_ratio(r, spy_rets)
            beat = (m['sharpe'] > spy_m['sharpe']) and (m['maxdd'] > spy_m['maxdd'])
            flag = "  <-- BEATS SPY (Sharpe&DD)" if beat else ""
            print(f"TREND      {s:6s} SMA{n:<3d}  trades={ntr:3d} in={pin*100:4.0f}%  "
                  + fmt(m) + f"  IRvSPY={ir:5.2f}{flag}")
            rows.append((f"{s} SMA{n}", m, r, {"trades": ntr, "in": pin, "ir": ir, "beat": beat}))
        print()

    # Cross-sectional rotation
    cbs = {s: closes[s] for s in BASKET}
    for lb in (63, 126, 252):
        for k in (1, 2):
            eq, ntr, pin = xsec_rotation_equity(cbs, dates, lb, k, apply_expense=True)
            m, r = metrics(eq, dates)
            ir = info_ratio(r, spy_rets)
            beat = (m['sharpe'] > spy_m['sharpe']) and (m['maxdd'] > spy_m['maxdd'])
            flag = "  <-- BEATS SPY (Sharpe&DD)" if beat else ""
            print(f"ROTATE     lb={lb:3d} K={k} trades={ntr:3d} in={pin*100:4.0f}%  "
                  + fmt(m) + f"  IRvSPY={ir:5.2f}{flag}")
    print()


if __name__ == "__main__":
    main()
