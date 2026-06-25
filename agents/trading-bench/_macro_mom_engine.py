"""MACRO MOMENTUM pre-flight engine (cross-sectional rank head-to-head).

Decisive question: does a MACRO-FUNDAMENTAL tilt add return content BEYOND the
known-dead price-only cross-sectional momentum baseline (~0.87 Sharpe, K=2,
6-asset)? Fair head-to-head on the SAME window.

Constructions (all monthly rebalance, long top-K=2 EW unless noted):
  - PRICE-only  : 12-1 price momentum rank, long top-2 EW  (reproduces the dead baseline)
  - MACRO-only  : per-asset macro regime score, long top-2 EW  (+ a L/S variant)
  - COMBINED    : z(price_rank) + z(macro_score) blended rank, long top-2 EW
  - SPY buy&hold: benchmark

Anti-lookahead:
  * Price signal at rebalance index i uses prices through i; weights take effect
    on i+1's return (1-day signal lag). Standard, leak-free.
  * Macro series are PIT-lagged:
      - monthly revised series (INDPRO, CPIAUCSL, PAYEMS, UNRATE): a month-M
        datapoint is published ~mid-(M+1). At a month-end rebalance on date D we
        only use the most-recent macro obs whose DATA MONTH is <= (D's month - 2).
        i.e. >=2 full calendar months stale. Conservative; no release-date leak.
      - daily market series (T10Y2Y, DGS10, BAA10Y, DTWEXBGS): market quotes,
        effectively unrevised; lag 1 trading day (use last obs strictly before D).
  All macro trends are formed from these lagged values only.
"""
from __future__ import annotations

import math
import datetime as dt
from typing import List, Dict, Optional, Tuple

from runner import daily_bars_cache as dbc
from runner import fred_cache
from runner.fp_sharpe import sharpe_from_returns

BPY = 252.0
TRADING_DAYS = 252

# ---- documented 6-asset cross-asset basket (matches the dead baseline) ----
BASKET = ["SPY", "EFA", "TLT", "GLD", "DBC", "VNQ"]
TOP_K = 2

# Asset -> which macro regime makes it attractive (transparent rules map).
# Each asset accrues +1 for each favourable regime, -1 for each unfavourable.
# Regimes (all from PIT-lagged macro series):
#   GROWTH_UP   : INDPRO 12m trend > 0  (industrial production rising)
#   INFL_UP     : CPI 12m trend rising AND above its own 12m-ago pace (accelerating)
#   CURVE_STEEP : T10Y2Y rising over 3m (bull-steepening => bond tailwind early)
#   CREDIT_TIGHT: BAA10Y spread falling over 3m (risk-on)
#   USD_UP      : DTWEXBGS rising over 3m (dollar trend up)
#
# Mapping (Brooks-2017 economic-trend intuition):
#   SPY/EFA/VNQ (risk assets) : long when GROWTH_UP and CREDIT_TIGHT; hurt by INFL_UP (cost push) and USD_UP for EFA
#   TLT (long bonds)          : long when GROWTH_DOWN (flight) OR CURVE_STEEP early; hurt by INFL_UP
#   GLD (gold)                : long when INFL_UP and/or USD_DOWN
#   DBC (commodities)         : long when INFL_UP and GROWTH_UP (demand); hurt by USD_UP


def _to_map(rows: List[dict]) -> List[Tuple[str, float]]:
    return [(r["date"], r["value"]) for r in rows if r.get("value") is not None]


def load_macro(start: str = "2004-01-01", end: str = "2026-06-24") -> Dict[str, List[Tuple[str, float]]]:
    out: Dict[str, List[Tuple[str, float]]] = {}
    for sid in ["INDPRO", "CPIAUCSL", "T10Y2Y", "DGS10", "BAA10Y", "DTWEXBGS"]:
        out[sid] = _to_map(fred_cache.get_series(sid, start, end, vintage="latest"))
    return out


def asof_value_lagged_daily(series: List[Tuple[str, float]], date: str) -> Optional[float]:
    """Most-recent daily-series value STRICTLY before `date` (1-day market lag)."""
    val = None
    for d, v in series:
        if d < date:
            val = v
        else:
            break
    return val


def asof_value_monthly_pit(series: List[Tuple[str, float]], date: str,
                           min_month_lag: int = 2) -> Optional[Tuple[str, float]]:
    """Most-recent MONTHLY obs whose data-month <= (date's month - min_month_lag).
    Returns (obs_date, value) or None. Conservative release-lag guard."""
    y, m = int(date[:4]), int(date[5:7])
    # cutoff month = current month minus min_month_lag
    cm = m - min_month_lag
    cy = y
    while cm <= 0:
        cm += 12
        cy -= 1
    cutoff = f"{cy:04d}-{cm:02d}-31"  # any obs with date <= cutoff is allowed
    res = None
    for d, v in series:
        if d <= cutoff:
            res = (d, v)
        else:
            break
    return res


def monthly_trend(series: List[Tuple[str, float]], date: str, lookback_m: int,
                  min_month_lag: int = 2) -> Optional[float]:
    """12m-style change of a MONTHLY series using PIT-lagged obs: value_now /
    value_(lookback_m ago) - 1, both taken from the PIT-allowed obs set."""
    now = asof_value_monthly_pit(series, date, min_month_lag)
    if now is None:
        return None
    now_date, now_val = now
    # find obs ~lookback_m months before now_date
    yy, mm = int(now_date[:4]), int(now_date[5:7])
    tm = mm - lookback_m
    ty = yy
    while tm <= 0:
        tm += 12
        ty -= 1
    target = f"{ty:04d}-{tm:02d}-31"
    old_val = None
    for d, v in series:
        if d <= target:
            old_val = v
        else:
            break
    if old_val is None or old_val == 0:
        return None
    return now_val / old_val - 1.0


def daily_change_over(series: List[Tuple[str, float]], date: str, lookback_d: int) -> Optional[float]:
    """Change in a daily series over ~lookback_d calendar-ish days, both values
    strictly-before-date (1-day lag). Uses the value `lookback_d` business-ish
    days earlier by walking the list."""
    # collect (d,v) strictly before date
    hist = [(d, v) for d, v in series if d < date]
    if len(hist) < lookback_d + 1:
        return None
    cur = hist[-1][1]
    prev = hist[-1 - lookback_d][1]
    if cur is None or prev is None:
        return None
    return cur - prev


def macro_score(asset: str, date: str, macro: Dict[str, List[Tuple[str, float]]]) -> Optional[float]:
    """Transparent +1/-1 economic-regime score for `asset` at rebalance `date`.
    Returns None if insufficient macro history (skip asset that month)."""
    growth = monthly_trend(macro["INDPRO"], date, 12)      # INDPRO 12m % change
    infl12 = monthly_trend(macro["CPIAUCSL"], date, 12)    # CPI 12m % change (YoY inflation)
    infl12_prev = monthly_trend_prev(macro["CPIAUCSL"], date, 12)  # YoY 1m ago, for acceleration
    curve_ch = daily_change_over(macro["T10Y2Y"], date, 63)  # 3m change in slope
    credit_ch = daily_change_over(macro["BAA10Y"], date, 63)  # 3m change in Baa spread
    usd_ch = daily_change_over(macro["DTWEXBGS"], date, 63)   # 3m change in broad dollar

    # require the core set; if missing, bail
    if growth is None or infl12 is None or curve_ch is None or credit_ch is None or usd_ch is None:
        return None

    GROWTH_UP = growth > 0.0
    INFL_ACC = (infl12_prev is not None) and (infl12 > infl12_prev) and (infl12 > 0.0)
    INFL_UP = infl12 > 0.025  # YoY inflation running hot (>2.5%)
    CURVE_STEEP = curve_ch > 0.0
    CREDIT_TIGHT = credit_ch < 0.0   # spread falling = risk-on
    USD_UP = usd_ch > 0.0

    s = 0.0
    if asset in ("SPY", "EFA", "VNQ"):
        s += 1.0 if GROWTH_UP else -1.0
        s += 1.0 if CREDIT_TIGHT else -1.0
        s += -1.0 if (INFL_UP or INFL_ACC) else 0.0   # cost-push headwind
        if asset == "EFA":
            s += -1.0 if USD_UP else 1.0               # strong USD hurts intl
    elif asset == "TLT":
        s += -1.0 if GROWTH_UP else 1.0                # bonds love weak growth
        s += 1.0 if CURVE_STEEP else -1.0
        s += -1.0 if (INFL_UP or INFL_ACC) else 1.0    # inflation kills bonds
    elif asset == "GLD":
        s += 1.0 if (INFL_UP or INFL_ACC) else -0.5
        s += -1.0 if USD_UP else 1.0                   # gold inverse USD
    elif asset == "DBC":
        s += 1.0 if (INFL_UP or INFL_ACC) else -1.0
        s += 1.0 if GROWTH_UP else -1.0                # commodities need demand
        s += -1.0 if USD_UP else 1.0
    return s


def monthly_trend_prev(series: List[Tuple[str, float]], date: str, lookback_m: int,
                       min_month_lag: int = 2) -> Optional[float]:
    """Same as monthly_trend but evaluated one month earlier (for acceleration)."""
    # shift the as-of date back ~1 month then call monthly_trend with extra lag
    return monthly_trend(series, date, lookback_m, min_month_lag=min_month_lag + 1)


# ---------------- backtest harness (cross-sectional) ----------------

def build_index():
    dates_set = set()
    series: Dict[str, Dict[str, float]] = {}
    first: Dict[str, str] = {}
    for s in BASKET + ["SPY"]:
        bars = dbc.get_daily(s)
        d = {b["date"]: b["adjclose"] for b in bars if b["adjclose"] is not None}
        series[s] = d
        first[s] = min(d.keys())
        dates_set.update(d.keys())
    dates = sorted(dates_set)
    # forward-fill per symbol
    panel: Dict[str, List[Optional[float]]] = {}
    for s in series:
        d = series[s]
        fd = first[s]
        out = []
        last = None
        for dte in dates:
            if dte in d:
                last = d[dte]
            out.append(last if dte >= fd else None)
        panel[s] = out
    return dates, panel


def month_end_idx(dates: List[str]) -> List[int]:
    out = []
    for i in range(len(dates)):
        cur = dates[i][:7]
        nxt = dates[i + 1][:7] if i + 1 < len(dates) else None
        if nxt != cur:
            out.append(i)
    return out


def price_mom(panel, sym, i, look_d=252, skip_d=21) -> Optional[float]:
    p = panel[sym]
    if i - look_d < 0:
        return None
    a = p[i - skip_d]
    b = p[i - look_d]
    if a is None or b is None or b == 0:
        return None
    return a / b - 1.0


def dret(p: List[Optional[float]], j: int) -> float:
    if j <= 0:
        return 0.0
    a, b = p[j], p[j - 1]
    if a is None or b is None or b == 0:
        return 0.0
    return a / b - 1.0


def zscores(d: Dict[str, float]) -> Dict[str, float]:
    if not d:
        return {}
    vals = list(d.values())
    m = sum(vals) / len(vals)
    var = sum((x - m) ** 2 for x in vals) / len(vals)
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd == 0:
        return {k: 0.0 for k in d}
    return {k: (v - m) / sd for k, v in d.items()}


def run_strategy(mode: str, macro, start_date: str, end_date: str,
                 one_way_bps: float = 2.0, top_k: int = TOP_K, ls: bool = False):
    """mode in {price, macro, combined}. Long top_k EW; if ls=True also short
    bottom_k EW (dollar-neutral-ish). Monthly rebalance, 1-day signal lag,
    turnover-costed."""
    dates, panel = build_index()
    me = set(month_end_idx(dates))
    look_d = 252
    cur_w: Dict[str, float] = {s: 0.0 for s in BASKET}
    out_dates, net = [], []
    started = False
    weights_log = []
    n_sel_hist = []

    for i in range(len(dates)):
        dte = dates[i]
        if end_date and dte > end_date:
            break
        if started:
            g = 0.0
            for s in BASKET:
                w = cur_w[s]
                if w != 0.0:
                    g += w * dret(panel[s], i)
            out_dates.append(dte)
            net.append(g)
        if i in me and i >= look_d and (start_date is None or dte >= start_date):
            # build scores
            pm = {}
            for s in BASKET:
                v = price_mom(panel, s, i)
                if v is not None:
                    pm[s] = v
            mm = {}
            for s in BASKET:
                v = macro_score(s, dte, macro)
                if v is not None:
                    mm[s] = v
            rank_in: Dict[str, float] = {}
            if mode == "price":
                rank_in = pm
            elif mode == "macro":
                rank_in = mm
            elif mode == "combined":
                zp = zscores(pm)
                zm = zscores(mm)
                common = set(zp) & set(zm)
                rank_in = {s: zp[s] + zm[s] for s in common}
            new_w = {s: 0.0 for s in BASKET}
            if rank_in:
                ordered = sorted(rank_in.keys(), key=lambda s: rank_in[s], reverse=True)
                longs = ordered[:top_k]
                lw = 1.0 / len(longs) if longs else 0.0
                for s in longs:
                    new_w[s] += lw
                if ls and len(ordered) >= 2 * top_k:
                    shorts = ordered[-top_k:]
                    sw = 1.0 / len(shorts)
                    for s in shorts:
                        new_w[s] -= sw
            turn = sum(abs(new_w[s] - cur_w[s]) for s in BASKET)
            cost = turn * (one_way_bps / 1e4)
            if started and net:
                net[-1] -= cost
            weights_log.append((dte, dict(new_w)))
            n_sel_hist.append(sum(1 for s in BASKET if new_w[s] != 0))
            cur_w = new_w
            if not started:
                started = True
    return {"dates": out_dates, "net": net, "weights": weights_log,
            "panel": panel, "panel_dates": dates}


# ---- stats ----

def max_drawdown(rets):
    eq = peak = 1.0
    mdd = 0.0
    for r in rets:
        eq *= (1 + r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    return mdd


def total_return(rets):
    eq = 1.0
    for r in rets:
        eq *= (1 + r)
    return eq - 1


def cagr(rets, n_per_year=252):
    if not rets:
        return 0.0
    tr = total_return(rets)
    yrs = len(rets) / n_per_year
    if yrs <= 0:
        return 0.0
    return ((1 + tr) ** (1 / yrs) - 1) * 100


def corr(a, b):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return cov / math.sqrt(va * vb)


def spy_path(panel, panel_dates, out_dates):
    didx = {d: k for k, d in enumerate(panel_dates)}
    p = panel["SPY"]
    rets = []
    for d in out_dates:
        k = didx[d]
        rets.append(dret(p, k))
    return rets


def window_return(out_dates, rets, lo, hi):
    eq = 1.0
    n = 0
    for d, r in zip(out_dates, rets):
        if lo <= d <= hi:
            eq *= (1 + r)
            n += 1
    return (eq - 1) * 100, n
