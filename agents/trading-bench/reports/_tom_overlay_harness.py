"""TOM OVERLAY — full honest harness (cross-index, two implementations, DD, OOS x2, canary).

Assigned by parent (trading-bench main) as the verdict harness for the
"Turn-of-Month leverage-concentration overlay" lead.

CONSTRUCT UNDER TEST
--------------------
The DEAD version (do NOT pursue): flat-elsewhere TOM (long only in the TOM
window, flat the rest of the month) loses to buy & hold on raw return over 33yr
because it forfeits market beta. CONFIRMED dead by parent; not retested here.

The LIVE construct: an OVERLAY. Base exposure = 1.0x the index EVERY day (so we
never give up beta); during the TOM window we add EXTRA exposure `tilt`. The
thesis (well-documented "turn-of-the-month effect"): a disproportionate share of
the equity premium accrues in the last few + first few trading days of the month,
so concentrating *extra* leverage there should add raw return.

  exposure(day) = 1.0 + (tilt if in_TOM(day) else 0.0)
  TOM window    = last `pre` trading days of month + first `post` of next month
                  (a PURE function of the calendar date axis — NO price lookahead)

TWO HONEST IMPLEMENTATIONS OF THE "EXTRA EXPOSURE"
--------------------------------------------------
(i)  EXPLICIT MARGIN: borrow the `tilt` portion at a financing APY; charge daily
     financing on the >1.0 exposure. Sweep financing ∈ {0,3,5,7,10}%/yr to find
     the BREAK-EVEN rate where the raw-return edge over B&H dies.

(ii) LEVERAGED-ETF TILT (the actually-tradeable form on our paper account):
     hold the 1x index normally; during the TOM window ADDITIONALLY hold a
     notional `w` of a leveraged ETF (SSO=2x / UPRO=3x for S&P; QLD=2x / TQQQ=3x
     for Nasdaq). A 2x ETF position of weight w delivers ~2w extra index exposure;
     to target an extra `tilt` index exposure we set w = tilt / (mult-1)... no:
     the ETF itself already includes the 1x, so to get +tilt EXTRA index beta from
     a kx ETF we hold the ETF in place of (tilt) of base AND let its leverage do
     the rest. We model it the clean tradeable way: during TOM, move `w_etf` of
     the book FROM the 1x index INTO the kx ETF. Net exposure during TOM =
     (1 - w_etf)*1x  +  w_etf*kx  = 1 + w_etf*(k-1).  So extra exposure
     delta = w_etf*(k-1); to hit a target `tilt` set w_etf = tilt/(k-1).
     CRUCIALLY we use the ETF's REAL realized adjclose return, which already bakes
     in its volatility decay + expense ratio + embedded financing. Fully honest;
     no idealized leverage. Shorter span (SSO/QLD 2006+, UPRO/TQQQ 2010+) — stated.

HONEST TESTS APPLIED TO EVERY PROMOTABLE VARIANT
------------------------------------------------
- maxDrawdown: true peak-to-trough on the compounded equity curve (leverage
  amplifies DD — we quantify the cost, not just the upside).
- OOS split #1: IS < 2013 / OOS >= 2013.  OOS split #2: IS < 2018 / OOS >= 2018.
  Edge must survive BOTH cuts (robustness to the split date).
- +1bar CANARY: shift the TOM mask forward 1 trading day (tilt on the WRONG days).
  A real calendar effect must DEGRADE; if it survives/improves under the lag it
  was same-bar alignment noise, not a timing edge.
- COST: 2bps one-way on every exposure CHANGE (entering/leaving the window, and
  the intra-book rotation into/out of the ETF in impl (ii)).

NOT A PROMOTION. Verdict harness. Mission bar = RAW RETURN vs buy & hold; the
Sharpe gate is suspended but still reported.
"""
from __future__ import annotations

import datetime as dt
import statistics as st
from typing import List, Tuple, Optional

from runner import daily_bars_cache as dbc

COST_BPS = 2.0
TRADING_DAYS = 252.0


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def load(sym: str) -> List[Tuple[dt.date, float]]:
    """Ascending [(date, adjclose)]; adjclose = split+div adjusted (correct for
    cumulative-return compounding, mandatory for leveraged ETFs)."""
    out: List[Tuple[dt.date, float]] = []
    for rec in dbc.get_daily(sym):
        d = rec.get("date")
        px = rec.get("adjclose")
        if px is None:
            px = rec.get("close")
        if px is None:
            continue
        if isinstance(d, str):
            d = dt.date.fromisoformat(d[:10])
        elif isinstance(d, dt.datetime):
            d = d.date()
        out.append((d, float(px)))
    out.sort(key=lambda r: r[0])
    return out


def daily_returns(series: List[Tuple[dt.date, float]]) -> List[Tuple[dt.date, float]]:
    """[(date_i, close_i/close_{i-1} - 1)] for i>=1."""
    rets: List[Tuple[dt.date, float]] = []
    for i in range(1, len(series)):
        p0 = series[i - 1][1]
        p1 = series[i][1]
        if p0 > 0:
            rets.append((series[i][0], p1 / p0 - 1.0))
    return rets


def align_returns(base_dates: List[dt.date], etf_series: List[Tuple[dt.date, float]]
                  ) -> dict:
    """Map date -> ETF daily return, keyed by the ETF's own consecutive bars.
    Returns a dict {date: ret}. Only dates where the ETF has a *consecutive*
    prior bar get a return (no synthetic gap-filling)."""
    d2r = {}
    for i in range(1, len(etf_series)):
        p0 = etf_series[i - 1][1]
        p1 = etf_series[i][1]
        if p0 > 0:
            d2r[etf_series[i][0]] = p1 / p0 - 1.0
    return d2r


# --------------------------------------------------------------------------- #
# TOM mask (pure date function; optional +shift for the canary)
# --------------------------------------------------------------------------- #
def tom_mask(dates: List[dt.date], pre: int, post: int, shift: int = 0) -> List[bool]:
    n = len(dates)
    base = [False] * n
    for idx in range(n):
        d = dates[idx]
        in_pre = False
        for k in range(1, pre + 1):
            j = idx + k
            if j >= n or dates[j].month != d.month:
                in_pre = True
                break
        in_post = False
        for k in range(0, post):
            j = idx - k
            if j <= 0:
                continue
            if dates[j - 1].month != dates[j].month:
                if 0 <= idx - j < post:
                    in_post = True
                break
        base[idx] = in_pre or in_post
    if shift == 0:
        return base
    shifted = [False] * n
    for i in range(n):
        src = i - shift
        if 0 <= src < n:
            shifted[i] = base[src]
    return shifted


# --------------------------------------------------------------------------- #
# Stats + drawdown
# --------------------------------------------------------------------------- #
def equity_curve(rets: List[Tuple[dt.date, float]]) -> List[float]:
    eq = [1.0]
    for _, r in rets:
        eq.append(eq[-1] * (1.0 + r))
    return eq


def max_drawdown(rets: List[Tuple[dt.date, float]]) -> float:
    """True peak-to-trough max drawdown on the compounded equity curve (>=0)."""
    eq = equity_curve(rets)
    peak = eq[0]
    mdd = 0.0
    for v in eq:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd
    return mdd


def stats(rets: List[Tuple[dt.date, float]]) -> Tuple[float, float, float, float]:
    """(ann_ret, sharpe, cum_ret, max_drawdown). Sharpe = excess-of-zero / vol,
    annualized by sqrt(252) — matches the probes (rf=0 for comparability)."""
    vals = [r for _, r in rets]
    if not vals:
        return 0.0, 0.0, 0.0, 0.0
    mean = sum(vals) / len(vals)
    sd = st.pstdev(vals) if len(vals) > 1 else 0.0
    ann = (1.0 + mean) ** TRADING_DAYS - 1.0
    sh = (mean / sd * (TRADING_DAYS ** 0.5)) if sd > 0 else 0.0
    cum = 1.0
    for v in vals:
        cum *= (1.0 + v)
    return ann, sh, cum - 1.0, max_drawdown(rets)


# --------------------------------------------------------------------------- #
# Overlay implementations
# --------------------------------------------------------------------------- #
def overlay_margin(dates, rets, mask, tilt, fin_apy) -> List[Tuple[dt.date, float]]:
    """(i) EXPLICIT MARGIN: base 1.0x + `tilt` borrowed during TOM, financed at
    fin_apy on the borrowed portion. Cost on exposure changes."""
    fin_daily = fin_apy / TRADING_DAYS
    out = []
    prev_exp = 1.0
    for k in range(1, len(dates)):
        exp = 1.0 + (tilt if mask[k] else 0.0)
        r = exp * rets[k - 1][1]
        borrowed = max(0.0, exp - 1.0)
        r -= borrowed * fin_daily
        if exp != prev_exp:
            r -= abs(exp - prev_exp) * COST_BPS / 10000.0
        prev_exp = exp
        out.append((dates[k], r))
    return out


def overlay_etf(dates, rets, mask, tilt, etf_d2r, k_mult) -> List[Tuple[dt.date, float]]:
    """(ii) LEVERAGED-ETF TILT: hold 1x index normally; during TOM rotate
    w_etf = tilt/(k-1) of the book from the 1x index into the kx ETF, so net
    exposure during TOM = 1 + w_etf*(k-1) = 1 + tilt. Uses the ETF's REAL daily
    return (decay + fees + embedded financing baked in). 2bps on the rotation.

    If the ETF has no return for a TOM date (missing bar), that day falls back to
    pure 1x (degraded but honest — never invents an ETF return)."""
    w_etf = tilt / (k_mult - 1.0)
    out = []
    prev_in = False
    for k in range(1, len(dates)):
        d = dates[k]
        idx_ret = rets[k - 1][1]
        in_win = mask[k]
        if in_win:
            er = etf_d2r.get(d)
            if er is None:
                # no consecutive ETF bar -> can't hold the ETF leg today; 1x only
                r = idx_ret
                eff_in = False
            else:
                r = (1.0 - w_etf) * idx_ret + w_etf * er
                eff_in = True
        else:
            r = idx_ret
            eff_in = False
        if eff_in != prev_in:
            # rotation turnover = w_etf moved in/out; cost on that notional
            r -= w_etf * COST_BPS / 10000.0
        prev_in = eff_in
        out.append((d, r))
    return out


# --------------------------------------------------------------------------- #
# Reporting helpers
# --------------------------------------------------------------------------- #
def split2(rets, cut: dt.date):
    is_r = [(d, r) for d, r in rets if d < cut]
    oos_r = [(d, r) for d, r in rets if d >= cut]
    return is_r, oos_r


def line(label, rr) -> str:
    ar, sh, cum, mdd = stats(rr)
    return (f"{label:>26}: cum {cum*100:>10.1f}%  ann {ar*100:>6.2f}%  "
            f"Sharpe {sh:>5.3f}  maxDD {mdd*100:>5.1f}%")


def section(title: str) -> str:
    return f"\n{'='*78}\n{title}\n{'='*78}"


__all__ = [
    "load", "daily_returns", "align_returns", "tom_mask", "stats",
    "max_drawdown", "overlay_margin", "overlay_etf", "split2", "line", "section",
]
