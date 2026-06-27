"""INDEX-LEVEL TS-VALUE vs MOMENTUM-BOOK correlation probe.

PAPER RESEARCH / FEASIBILITY GATE. Read-only on all caches. Writes nothing
outside reports/. Does NOT modify strategies/runner/crontab/db.

GATING QUESTION: is an index-level time-series VALUE signal reliably but
IMPERFECTLY negatively correlated to our momentum book, with its own standalone
expectancy -- or is it just relabeled inverse-momentum?

DISCRIMINATION TEST (the crux): a -1x-momentum book has corr-to-mom = -1.0 by
construction. A genuine value premium must be DISTINGUISHABLE from that: corr to
mom should be in (-0.6, ~0] (imperfect), and corr to (-mom) should be well below
+1.0. If value's return stream ~ -mom (corr-to-mom approx -0.9, corr-to-(-mom)
approx +0.9), it is NOT a distinct premium -> lane DEAD.

HARNESS DISCIPLINE: lookahead-safe (z-scores/means use only data <= D), +1-day
signal lag, 2bps/side, FP-continuous Sharpe sqrt(252), OOS 2018-01-01 split,
1-day-lag canary on any 'it works'.
"""
from __future__ import annotations

import json
import math
import datetime as dt
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import sys
sys.path.insert(0, ".")

from runner import daily_bars_cache as dbc
from runner.fred_cache import get_series
from runner.fp_sharpe import sharpe_from_returns
from runner.backtest import bars_per_year

BPY = bars_per_year("1Day", is_crypto=False)  # 252.0
TRADING_DAYS = 252
ONE_WAY_BPS = 2.0
OOS_START = "2018-01-01"
SAMPLE_START = "2008-01-01"   # common usable start once warmups satisfied

# ------------------------------------------------------------------ utils
def _to_iso(d) -> str:
    return str(d)[:10]


def daily_ret(prices: List[Optional[float]], j: int) -> Optional[float]:
    if j <= 0:
        return None
    a, b = prices[j - 1], prices[j]
    if a is None or b is None or a <= 0:
        return None
    return b / a - 1.0


def trailing_vol(prices: List[Optional[float]], idx: int, window_d: int = 63) -> Optional[float]:
    rets = []
    for j in range(idx - window_d + 1, idx + 1):
        r = daily_ret(prices, j)
        if r is not None:
            rets.append(r)
    if len(rets) < 5:
        return None
    m = sum(rets) / len(rets)
    v = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(v) * math.sqrt(BPY) if v > 0 else None


def max_drawdown(rets: List[float]) -> float:
    eq = 1.0; peak = 1.0; mdd = 0.0
    for r in rets:
        eq *= (1.0 + r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)
    return mdd


def total_return(rets: List[float]) -> float:
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    return eq - 1.0


def corr(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a = a[:n]; b = b[:n]
    ma = sum(a) / n; mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return cov / math.sqrt(va * vb)


def cagr(rets: List[float], n_per_year: int = TRADING_DAYS) -> float:
    if not rets:
        return 0.0
    eq = 1.0
    for r in rets:
        eq *= (1.0 + r)
    if eq <= 0:
        return -1.0
    yrs = len(rets) / n_per_year
    if yrs <= 0:
        return 0.0
    return eq ** (1.0 / yrs) - 1.0


# ------------------------------------------------------------------ trading calendar
def build_calendar(ref_symbol: str = "SPY") -> List[str]:
    """Use SPY's trading dates as the master daily calendar."""
    bars = dbc.get_daily(ref_symbol)
    return [b["date"] for b in bars]


def adjclose_on(symbol: str, dates: List[str]) -> List[Optional[float]]:
    """adjclose forward-filled onto `dates` (never looks ahead: <= D)."""
    return dbc.adjclose_series(symbol, dates)


# ------------------------------------------------------------------ FRED series onto daily calendar
def fred_on_calendar(series_id: str, dates: List[str], start="1990-01-01",
                     end="2026-06-27") -> List[Optional[float]]:
    """Forward-fill a FRED series onto the daily `dates` calendar. PIT-safe:
    for date D we use the most-recent observation with obs_date <= D. (These
    market-quoted series -- real yields, spreads -- are effectively unrevised.)"""
    rows = get_series(series_id, start, end, vintage="latest")
    obs = [(r["date"], r["value"]) for r in rows if r["value"] is not None]
    obs.sort()
    out: List[Optional[float]] = []
    j = 0
    last = None
    n = len(obs)
    for d in dates:
        while j < n and obs[j][0] <= d:
            last = obs[j][1]
            j += 1
        out.append(last)
    return out


# ------------------------------------------------------------------ MOMENTUM BOOK proxy
def tsmom_book_returns(dates: List[str], symbols=("QQQ", "SPY"),
                       lookback_m: int = 12, skip_m: int = 1,
                       vol_target: float = 0.15, lag_days: int = 1,
                       one_way_bps: float = ONE_WAY_BPS,
                       start: str = SAMPLE_START) -> Dict:
    """Reconstruct the 'our momentum book' return stream: 12-1 TSMOM, long/flat,
    vol-targeted, monthly rebalance, +`lag_days` signal lag, 2bps/side.

    Returns daily net return aligned to a date axis (the subset of `dates` we
    actually trade). Equal-weight across in-trend symbols, vol-target the blend.
    Also returns the per-day SIGNED momentum SIGNAL (sum of in-trend indicators,
    +1 per in-trend leg, vol-scaled) so we can build a -1x mirror for the
    discrimination test."""
    panel = {s: adjclose_on(s, dates) for s in symbols}
    me = _month_end_idx(dates)
    look_d = lookback_m * 21
    skip_d = skip_m * 21

    cur_w = {s: 0.0 for s in symbols}
    cur_scale = 0.0
    out_dates: List[str] = []
    net: List[float] = []
    sig_dir: List[float] = []   # +1 if book net-long, 0 if flat (the 'momentum signal' sign)
    started = False
    me_set = set(me)

    for i in range(len(dates)):
        d = dates[i]
        if d < start:
            # still rebalance to warm weights, but don't accrue
            pass
        # accrue today's return using yesterday's weights*scale
        if started:
            g = 0.0
            for s in symbols:
                w = cur_w[s]
                if w == 0.0:
                    continue
                r = daily_ret(panel[s], i)
                g += w * (r if r is not None else 0.0)
            net.append(cur_scale * g)
            out_dates.append(d)
            sig_dir.append(1.0 if cur_scale > 0 and any(cur_w[s] > 0 for s in symbols) else 0.0)

        if i in me_set and i >= look_d + lag_days:
            # signal computed from prices through index i-lag_days (lookahead-safe)
            si = i - lag_days
            sigs = {}
            for s in symbols:
                pr = panel[s]
                i_rec = si - skip_d
                i_old = si - look_d
                if i_old < 0 or pr[i_rec] is None or pr[i_old] is None or pr[i_old] <= 0:
                    continue
                sigs[s] = pr[i_rec] / pr[i_old] - 1.0
            in_trend = [s for s, v in sigs.items() if v > 0]
            new_w = {s: 0.0 for s in symbols}
            if in_trend:
                w = 1.0 / len(in_trend)
                for s in in_trend:
                    new_w[s] = w
            # vol-target the equal-weight blend using trailing vol at si
            blend_rets = []
            for j in range(si - 63 + 1, si + 1):
                if j <= 0:
                    continue
                gg = 0.0; cnt = 0
                for s in in_trend:
                    r = daily_ret(panel[s], j)
                    if r is not None:
                        gg += r; cnt += 1
                if cnt > 0:
                    blend_rets.append(gg / cnt)
            scale = 0.0
            if in_trend and len(blend_rets) >= 20:
                m = sum(blend_rets) / len(blend_rets)
                v = sum((r - m) ** 2 for r in blend_rets) / (len(blend_rets) - 1)
                rv = math.sqrt(v) * math.sqrt(BPY) if v > 0 else None
                if rv and rv > 0:
                    scale = min(vol_target / rv, 1.5)   # cap leverage 1.5x
            # turnover cost on weight*scale change
            old_eff = {s: cur_w[s] * cur_scale for s in symbols}
            new_eff = {s: new_w[s] * scale for s in symbols}
            turn = sum(abs(new_eff[s] - old_eff[s]) for s in symbols)
            cost = turn * (one_way_bps / 1e4)
            if started and net:
                net[-1] -= cost
            cur_w = new_w
            cur_scale = scale
            if not started and d >= start:
                started = True

    return {"dates": out_dates, "net": net, "sig_dir": sig_dir,
            "symbols": list(symbols), "lookback_m": lookback_m,
            "vol_target": vol_target}


def _month_end_idx(dates: List[str]) -> List[int]:
    out = []
    for i in range(len(dates)):
        cur = dates[i][:7]
        nxt = dates[i + 1][:7] if i + 1 < len(dates) else None
        if nxt != cur:
            out.append(i)
    return out


# ------------------------------------------------------------------ VALUE SIGNALS (index-level TS)
def zscore_trailing(series: List[Optional[float]], idx: int, win_d: int) -> Optional[float]:
    """z-score of series[idx] vs trailing window [idx-win_d+1 .. idx] INCLUSIVE.
    Lookahead-safe: uses only data <= idx. Returns None if insufficient data."""
    lo = idx - win_d + 1
    if lo < 0:
        return None
    vals = [series[k] for k in range(lo, idx + 1) if series[k] is not None]
    if len(vals) < max(20, win_d // 4):
        return None
    m = sum(vals) / len(vals)
    v = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    sd = math.sqrt(v) if v > 0 else 0.0
    if sd == 0:
        return 0.0
    cur = series[idx]
    if cur is None:
        return None
    return (cur - m) / sd


def value_signal_returns(dates: List[str], asset_symbol: str,
                         value_level: List[Optional[float]],
                         cheap_is_high: bool, z_win_d: int,
                         vol_target: float = 0.15, lag_days: int = 1,
                         one_way_bps: float = ONE_WAY_BPS,
                         start: str = SAMPLE_START,
                         long_flat_only: bool = False,
                         rebal: str = "month") -> Dict:
    """Build a TS-VALUE return stream on ONE asset.

    value_level: the raw valuation level on the daily calendar (e.g. real yield,
      or asset-price/5yr-avg). cheap_is_high: True if a HIGH level means cheap
      (=> long tilt). We z-score `value_level` (or its sign-flipped version so
      that high z = cheap = long), lookahead-safe, then map z -> target position
      in [-1, +1] (or [0, 1] if long_flat_only), vol-target the asset.

    The TRADED ASSET is `asset_symbol` (the thing whose return value harvests).
    Position sign = cheap->long. Vol-target to `vol_target`. +lag_days lag.
    """
    px = adjclose_on(asset_symbol, dates)
    me_set = set(_month_end_idx(dates))
    cur_pos = 0.0   # signed target * scale
    out_dates: List[str] = []
    net: List[float] = []
    pos_hist: List[float] = []
    started = False

    for i in range(len(dates)):
        d = dates[i]
        if started:
            r = daily_ret(px, i)
            net.append(cur_pos * (r if r is not None else 0.0))
            out_dates.append(d)
            pos_hist.append(cur_pos)

        do_rebal = (i in me_set) if rebal == "month" else True
        if do_rebal and i >= lag_days:
            si = i - lag_days
            lvl = value_level[si]
            z = zscore_trailing(value_level, si, z_win_d) if lvl is not None else None
            if z is None:
                target = cur_pos  # hold
            else:
                signed_z = z if cheap_is_high else -z
                # map to [-1,1] via clip at +-2 sigma
                raw = max(-1.0, min(1.0, signed_z / 2.0))
                if long_flat_only:
                    raw = max(0.0, raw)
                # vol-target the asset
                rv = trailing_vol(px, si, 63)
                scale = (vol_target / rv) if (rv and rv > 0) else 0.0
                scale = min(scale, 1.5)
                target = raw * scale
            old = cur_pos
            turn = abs(target - old)
            cost = turn * (one_way_bps / 1e4)
            if started and net:
                net[-1] -= cost
            cur_pos = target
            if not started and d >= start:
                started = True

    return {"dates": out_dates, "net": net, "pos_hist": pos_hist,
            "asset": asset_symbol, "cheap_is_high": cheap_is_high,
            "z_win_d": z_win_d, "long_flat_only": long_flat_only}


# ------------------------------------------------------------------ alignment + probe stats
def align(a_dates, a_vals, b_dates, b_vals) -> Tuple[List[float], List[float], List[str]]:
    """Inner-join two daily return streams on date."""
    bm = {d: v for d, v in zip(b_dates, b_vals)}
    ra, rb, dd = [], [], []
    for d, v in zip(a_dates, a_vals):
        if d in bm:
            ra.append(v); rb.append(bm[d]); dd.append(d)
    return ra, rb, dd


def rolling_corr(a: List[float], b: List[float], dd: List[str], win_d: int = 504) -> List[float]:
    out = []
    for i in range(win_d, len(a) + 1):
        out.append(corr(a[i - win_d:i], b[i - win_d:i]))
    return out


def stats(rets: List[float], dd: List[str], label: str) -> Dict:
    si = next((k for k, d in enumerate(dd) if d >= OOS_START), len(dd))
    return {
        "label": label,
        "n": len(rets),
        "span": [dd[0], dd[-1]] if dd else [None, None],
        "fp_sharpe": round(sharpe_from_returns(rets, BPY), 4),
        "fp_cagr": round(cagr(rets) * 100, 3),
        "fp_total_ret": round(total_return(rets), 4),
        "fp_maxdd": round(max_drawdown(rets), 4),
        "is_sharpe": round(sharpe_from_returns(rets[:si], BPY), 4),
        "oos_sharpe": round(sharpe_from_returns(rets[si:], BPY), 4),
        "oos_total_ret": round(total_return(rets[si:]), 4),
        "oos_cagr": round(cagr(rets[si:]) * 100, 3),
    }
