"""Multi-asset TSMOM (time-series momentum) standalone sleeve engine.

12-1 monthly TSMOM, long/flat only, no leverage. PRIMARY weighting =
equal-weight across in-trend assets (NOT inverse-vol). Reuses runner
primitives: daily_bars_cache (Yahoo v8 adjclose), fp_sharpe.sharpe_from_returns
+ bars_per_year, CostModel.alpaca_stocks (2bps one-way), lane_honesty.cagr.

Anti-lookahead: signal computed from prices through the rebalance date D; the
resulting target weights take effect the NEXT trading day (returns from D+1
onward use those weights). Monthly rebalance on the last trading day of each
calendar month.
"""
from __future__ import annotations

import math
import datetime as dt
from typing import List, Dict, Optional, Tuple

from runner import daily_bars_cache as dbc
from runner.fp_sharpe import sharpe_from_returns
from runner.backtest import bars_per_year, CostModel
from runner import lane_honesty

TRADING_DAYS = 252
BPY = bars_per_year("1Day", is_crypto=False)  # 252.0
COST = CostModel.alpaca_stocks()               # 2 bps one-way
ONE_WAY_BPS = COST.spread_bps                   # 2.0


def load_panel(symbols: List[str]) -> Tuple[List[str], Dict[str, List[Optional[float]]]]:
    """Build a unified ascending trading-date index = union of all symbols'
    dates, and forward-filled adjclose series per symbol aligned to it.
    A symbol contributes only from its own first date onward (leading None
    until it exists)."""
    per_sym_raw: Dict[str, Dict[str, float]] = {}
    all_dates = set()
    first_date: Dict[str, str] = {}
    for s in symbols:
        bars = dbc.get_daily(s)
        d = {b["date"]: b["adjclose"] for b in bars if b["adjclose"] is not None}
        per_sym_raw[s] = d
        first_date[s] = bars[0]["date"]
        all_dates.update(d.keys())
    dates = sorted(all_dates)
    panel: Dict[str, List[Optional[float]]] = {}
    for s in symbols:
        d = per_sym_raw[s]
        fd = first_date[s]
        series: List[Optional[float]] = []
        last = None
        for dte in dates:
            if dte in d:
                last = d[dte]
            # before the symbol's inception, keep None (don't forward-fill from nothing)
            series.append(last if dte >= fd else None)
        panel[s] = series
    return dates, panel


def month_end_indices(dates: List[str]) -> List[int]:
    """Indices in `dates` that are the LAST trading day of their calendar month."""
    out = []
    for i in range(len(dates)):
        cur = dates[i][:7]   # YYYY-MM
        nxt = dates[i + 1][:7] if i + 1 < len(dates) else None
        if nxt != cur:
            out.append(i)
    return out


def tsmom_signal(prices: List[Optional[float]], idx: int, lookback_m: int,
                 skip_m: int = 1) -> Optional[float]:
    """12-1 style TSMOM at index `idx`: trailing `lookback_m`-month return
    skipping the most recent `skip_m` month(s).
    return = price[idx - skip_d] / price[idx - lookback_d] - 1, using ~21
    trading days per month. Returns None if data unavailable."""
    skip_d = skip_m * 21
    look_d = lookback_m * 21
    i_recent = idx - skip_d
    i_old = idx - look_d
    if i_old < 0 or i_recent < 0:
        return None
    p_recent = prices[i_recent]
    p_old = prices[i_old]
    if p_recent is None or p_old is None or p_old <= 0:
        return None
    return p_recent / p_old - 1.0


def trailing_vol(prices: List[Optional[float]], idx: int, window_d: int = 63) -> Optional[float]:
    """Annualized daily-return stdev over the last `window_d` days ending at idx."""
    rets = []
    for j in range(idx - window_d + 1, idx + 1):
        if j <= 0:
            continue
        a, b = prices[j - 1], prices[j]
        if a is None or b is None or a <= 0:
            continue
        rets.append(b / a - 1.0)
    if len(rets) < 2:
        return None
    m = sum(rets) / len(rets)
    v = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(v) if v > 0 else 0.0
    return sd * math.sqrt(BPY)


def daily_ret(prices: List[Optional[float]], j: int) -> Optional[float]:
    if j <= 0:
        return None
    a, b = prices[j - 1], prices[j]
    if a is None or b is None or a <= 0:
        return None
    return b / a - 1.0


def run_tsmom(symbols: List[str], lookback_m: int = 12, skip_m: int = 1,
              weighting: str = "ew", start_date: Optional[str] = None,
              end_date: Optional[str] = None, one_way_bps: float = ONE_WAY_BPS):
    """Run the sleeve. Returns dict with daily date list, daily net/gross
    returns, weights history, turnover. weighting: 'ew' (equal-weight in-trend)
    or 'invvol' (inverse trailing-vol among in-trend). Long/flat only.

    Sleeve is FULLY INVESTED across in-trend assets (weights sum to 1 when any
    asset is in-trend); when NOTHING is in-trend the sleeve is 100% cash
    (0 return that day). This is the honest 'trend sleeve' construction — it
    does NOT lever up, and idle capital earns 0 (no cash yield assumed)."""
    dates, panel = load_panel(symbols)
    me = set(month_end_indices(dates))

    # warmup: need lookback_d history
    look_d = lookback_m * 21
    cur_w: Dict[str, float] = {s: 0.0 for s in symbols}

    out_dates: List[str] = []
    net_rets: List[float] = []
    gross_rets: List[float] = []
    turnover_events: List[float] = []
    n_intrend_hist: List[int] = []
    weights_hist: List[Tuple[str, Dict[str, float]]] = []

    started = False
    for i in range(len(dates)):
        dte = dates[i]
        if start_date and dte < start_date:
            # still need to maintain weights through rebalances before start? We
            # only begin accumulating returns at start_date; to keep it clean we
            # skip entirely before start (weights reset handled at first rebal).
            pass
        if end_date and dte > end_date:
            break

        # 1) accrue today's return using YESTERDAY's weights (weights set at prior close)
        if started:
            day_gross = 0.0
            for s in symbols:
                w = cur_w[s]
                if w == 0.0:
                    continue
                r = daily_ret(panel[s], i)
                if r is None:
                    r = 0.0
                day_gross += w * r
            out_dates.append(dte)
            gross_rets.append(day_gross)
            net_rets.append(day_gross)  # cost applied separately at rebal day below

        # 2) rebalance at month-end close -> sets weights effective tomorrow
        if i in me and i >= look_d:
            sigs: Dict[str, float] = {}
            for s in symbols:
                sg = tsmom_signal(panel[s], i, lookback_m, skip_m)
                if sg is not None:
                    sigs[s] = sg
            in_trend = [s for s, v in sigs.items() if v > 0.0]
            new_w: Dict[str, float] = {s: 0.0 for s in symbols}
            if in_trend:
                if weighting == "ew":
                    w = 1.0 / len(in_trend)
                    for s in in_trend:
                        new_w[s] = w
                elif weighting == "invvol":
                    inv = {}
                    for s in in_trend:
                        v = trailing_vol(panel[s], i)
                        if v and v > 0:
                            inv[s] = 1.0 / v
                    tot = sum(inv.values())
                    if tot > 0:
                        for s, x in inv.items():
                            new_w[s] = x / tot
                    else:
                        w = 1.0 / len(in_trend)
                        for s in in_trend:
                            new_w[s] = w
            # turnover = sum |Δw|; cost = turnover * one_way_bps (each side of the
            # change crosses the spread once)
            turn = sum(abs(new_w[s] - cur_w[s]) for s in symbols)
            cost = turn * (one_way_bps / 1e4)
            if started and net_rets:
                net_rets[-1] -= cost   # debit today's net return for the rebalance
            turnover_events.append(turn)
            n_intrend_hist.append(len(in_trend))
            weights_hist.append((dte, dict(new_w)))
            cur_w = new_w
            if not started and (start_date is None or dte >= start_date):
                started = True
            elif not started and start_date is not None and dte >= start_date:
                started = True

        # allow starting accrual once we are past warmup and past start_date even
        # between rebalances (first started flips at first rebal >= warmup)
        if not started and i >= look_d and (start_date is None or dte >= start_date):
            # only start AFTER a rebalance has set weights; if first rebal hasn't
            # happened yet, weights are all zero -> starting now just yields 0s.
            # We flip started at the first rebal instead (above). So do nothing.
            pass

    return {
        "symbols": symbols,
        "lookback_m": lookback_m,
        "skip_m": skip_m,
        "weighting": weighting,
        "dates": out_dates,
        "gross": gross_rets,
        "net": net_rets,
        "turnover_events": turnover_events,
        "n_intrend_hist": n_intrend_hist,
        "weights_hist": weights_hist,
        "panel_dates": dates,
        "panel": panel,
    }


def spy_buyhold_on_path(out_dates: List[str]) -> List[float]:
    """Buy-hold SPY daily returns aligned to the sleeve's out_dates path."""
    bars = dbc.get_daily("SPY")
    px = {b["date"]: b["adjclose"] for b in bars}
    # build forward-filled adjclose for the union of out_dates
    series = []
    last = None
    # need prev day too; map each out_date to its adjclose, ffill
    alld = sorted(px.keys())
    pos = {d: k for k, d in enumerate(alld)}
    vals = []
    for d in out_dates:
        # find adjclose at or before d
        if d in px:
            last = px[d]
        else:
            # binary-ish: walk back (out_dates are trading days, almost always present)
            last = last
        vals.append(last)
    rets = []
    prev = None
    for v in vals:
        if prev is not None and prev > 0 and v is not None:
            rets.append(v / prev - 1.0)
        else:
            rets.append(0.0)
        prev = v
    return rets


def max_drawdown(rets: List[float]) -> float:
    """Max drawdown (fraction, negative) from a daily return series."""
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        eq *= (1.0 + r)
        if eq > peak:
            peak = eq
        dd = eq / peak - 1.0
        if dd < mdd:
            mdd = dd
    return mdd


def total_return(rets: List[float]) -> float:
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    return eq - 1.0


def corr(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    a = a[:n]; b = b[:n]
    if n < 2:
        return 0.0
    ma = sum(a) / n; mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return cov / math.sqrt(va * vb)


def stats_block(rets: List[float], dates: List[str], label: str) -> Dict[str, float]:
    shp = sharpe_from_returns(rets, BPY)
    cg = lane_honesty.cagr(rets, TRADING_DAYS)
    tr = total_return(rets)
    mdd = max_drawdown(rets)
    return {
        "label": label,
        "n": len(rets),
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "sharpe": shp,
        "cagr_pct": cg,
        "total_return": tr,
        "maxdd": mdd,
    }
