"""VIX-complex regime / carry signals — point-in-time, no-lookahead.

RESEARCH/BACKTEST-ONLY. Built on `cboe_cache` (the keyless CBOE VIX-complex
ingest) and `bars_cache` (Alpaca SPY daily bars for the realized-vol leg).
Implements the standard VIX-complex risk-on/off + carry signals used by a
Natenberg-style "regime overlay on a long-SPX core" (NATENBERG_SYNTHESIS #2):

  - VIX level            : raw 30d implied vol level.
  - VIX percentile       : trailing-window rank of VIX (regime extremity).
  - VIX z-score          : trailing standardized VIX.
  - term-structure slope : VIX3M - VIX (and ratio VIX/VIX3M). Contango
                           (VIX < VIX3M, slope > 0) = calm/risk-on; backwardation
                           (VIX > VIX3M, slope < 0 / ratio > 1) = stress/risk-off.
                           This is the CORE risk-on/off gate.
  - SKEW level/percentile: CBOE SKEW (index put-skew / tail-risk demand).
  - VVIX level/percentile: vol-of-VIX (vol-market stress).
  - VRP proxy            : VIX - trailing realized vol of SPY (annualized).
                           Implied-minus-realized variance/vol risk premium.
                           Positive = vol sellers paid (calm carry); a collapse
                           toward / below 0 flags a stress transition.

EVERY signal here is POINT-IN-TIME. All VIX-complex inputs come through
`cboe_cache.asof / history_asof` (strictly-before-decision-date) and the SPY
realized-vol leg uses only SPY closes strictly before the decision date. There
is NO use of date D's own data in a signal evaluated for a decision on date D.

This module is signal-COMPUTATION only. It does not place trades or gate
anything; the backtest driver (`vix_overlay_backtest.py`) consumes it.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence

from . import cboe_cache


# Default trailing windows (trading days). Tunable by the driver.
DEFAULT_PCT_WINDOW = 252          # ~1yr percentile/z-score window for VIX/SKEW/VVIX
DEFAULT_REALIZED_WINDOW = 21      # ~1mo realized vol (matches VIX's ~30 calendar / 21 trading days)
TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Small stats helpers (pure stdlib; no numpy on this box)
# ---------------------------------------------------------------------------

def _percentile_rank(window: Sequence[float], value: float) -> Optional[float]:
    """Fraction of `window` values <= `value`, in [0,1]. None if window empty.

    This is the classic 'where does today sit in its trailing distribution'
    percentile (a VIX at its 95th percentile => 0.95 => historically extreme).
    """
    if not window:
        return None
    n = len(window)
    le = sum(1 for x in window if x <= value)
    return le / n


def _zscore(window: Sequence[float], value: float) -> Optional[float]:
    """(value - mean(window)) / sample_std(window). None if <2 points or std~0."""
    n = len(window)
    if n < 2:
        return None
    mean = sum(window) / n
    var = sum((x - mean) ** 2 for x in window) / (n - 1)
    sd = math.sqrt(var)
    if sd <= 1e-12:
        return None
    return (value - mean) / sd


def realized_vol_annualized(closes: Sequence[float]) -> Optional[float]:
    """Annualized realized vol (%) from a series of daily closes.

    Uses close-to-close log returns, sample std, * sqrt(252), * 100 to put it on
    the SAME scale as VIX (which is an annualized vol in percentage points).
    Needs >= 3 closes (>=2 returns). None otherwise.
    """
    if closes is None or len(closes) < 3:
        return None
    rets: List[float] = []
    for i in range(1, len(closes)):
        p0 = closes[i - 1]
        p1 = closes[i]
        if p0 and p0 > 0 and p1 and p1 > 0:
            rets.append(math.log(p1 / p0))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(var)
    return sd * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0


# ---------------------------------------------------------------------------
# SPY realized-vol leg (point-in-time)
# ---------------------------------------------------------------------------

def _spy_closes_before(spy_bars: Sequence[dict], asof_iso: str,
                       window: int) -> List[float]:
    """The last `window` SPY closes with bar-date STRICTLY BEFORE asof_iso.

    `spy_bars` is an oldest-first list of Alpaca bars ({t,o,h,l,c,v}). We slice
    to bars dated < asof (no lookahead: date D's own close is not used for a
    decision on date D) and take the trailing `window`+1 closes so the caller
    gets `window` returns.
    """
    out: List[float] = []
    for b in spy_bars:
        d = str(b.get("t", ""))[:10]
        if d and d < asof_iso:
            try:
                out.append(float(b["c"]))
            except (TypeError, ValueError, KeyError):
                continue
        elif d >= asof_iso:
            break  # bars are sorted; nothing later qualifies
    # need window+1 closes to make `window` returns
    return out[-(window + 1):] if out else []


# ---------------------------------------------------------------------------
# The signal bundle
# ---------------------------------------------------------------------------

def signals_asof(asof_date,
                 spy_bars: Optional[Sequence[dict]] = None,
                 *,
                 pct_window: int = DEFAULT_PCT_WINDOW,
                 realized_window: int = DEFAULT_REALIZED_WINDOW,
                 use_cache: bool = True) -> Dict[str, Optional[float]]:
    """Compute the full VIX-complex regime/carry signal bundle as-of a date.

    POINT-IN-TIME: every input is strictly before `asof_date`. Returns a dict of
    named signals (any of which may be None when the underlying data isn't yet
    available — e.g. VIX3M before 2009-09, or VVIX before 2006-03). Callers must
    treat None as 'signal unavailable, fall back to default risk-on'.

    Keys:
        vix, vix3m, vvix, skew                 : raw levels (close, strictly prior)
        vix_pct, vvix_pct, skew_pct            : trailing percentile rank [0,1]
        vix_z                                  : trailing z-score
        ts_slope   = vix3m - vix               : >0 contango (calm), <0 backwardation
        ts_ratio   = vix / vix3m               : >1 backwardation (stress)
        realized_vol                           : trailing annualized SPY realized vol (%)
        vrp        = vix - realized_vol        : implied-minus-realized risk premium
        asof                                   : the decision date (echo)
    """
    asof_iso = cboe_cache._as_iso(asof_date)
    out: Dict[str, Optional[float]] = {"asof": asof_iso}

    # --- Raw levels (strictly-before) ---
    vix = cboe_cache.level_asof("VIX", asof_iso, use_cache=use_cache)
    vix3m = cboe_cache.level_asof("VIX3M", asof_iso, use_cache=use_cache)
    vvix = cboe_cache.level_asof("VVIX", asof_iso, use_cache=use_cache)
    skew = cboe_cache.level_asof("SKEW", asof_iso, use_cache=use_cache)
    out["vix"] = vix
    out["vix3m"] = vix3m
    out["vvix"] = vvix
    out["skew"] = skew

    # --- Trailing percentile / z (point-in-time windows) ---
    def _pct_and_z(idx: str, value: Optional[float]):
        if value is None:
            return None, None
        hist = cboe_cache.history_asof(idx, asof_iso, lookback=pct_window,
                                       use_cache=use_cache)
        window = [r["close"] for r in hist if r.get("close") is not None]
        return _percentile_rank(window, value), _zscore(window, value)

    vix_pct, vix_z = _pct_and_z("VIX", vix)
    vvix_pct, _ = _pct_and_z("VVIX", vvix)
    skew_pct, _ = _pct_and_z("SKEW", skew)
    out["vix_pct"] = vix_pct
    out["vix_z"] = vix_z
    out["vvix_pct"] = vvix_pct
    out["skew_pct"] = skew_pct

    # --- Term-structure slope / ratio (the core risk-on/off) ---
    if vix is not None and vix3m is not None and vix3m > 0:
        out["ts_slope"] = vix3m - vix          # >0 contango (calm), <0 backwardation
        out["ts_ratio"] = vix / vix3m          # >1 backwardation (stress)
    else:
        out["ts_slope"] = None
        out["ts_ratio"] = None

    # --- VRP proxy: VIX minus trailing realized vol of SPY ---
    rv: Optional[float] = None
    if spy_bars:
        closes = _spy_closes_before(spy_bars, asof_iso, realized_window)
        rv = realized_vol_annualized(closes)
    out["realized_vol"] = rv
    out["vrp"] = (vix - rv) if (vix is not None and rv is not None) else None

    return out


# ---------------------------------------------------------------------------
# Self-check: spans + a couple of known regime points
# ---------------------------------------------------------------------------

def selftest(spy_bars: Optional[Sequence[dict]] = None) -> Dict[str, object]:
    """Smoke: compute signals at a calm and a stressed historical date and show
    the term-structure sign flips. Pure-CBOE legs run with no SPY bars; the VRP
    leg only populates if spy_bars is passed."""
    report: Dict[str, object] = {}
    # 2017-10-02: famously calm, deep contango, low VIX.
    report["calm_2017-10-02"] = signals_asof("2017-10-02", spy_bars)
    # 2020-03-18: COVID crash, VIX ~80, backwardation.
    report["stress_2020-03-18"] = signals_asof("2020-03-18", spy_bars)
    return report


if __name__ == "__main__":
    import pprint
    pprint.pprint(selftest())
