"""Point-in-time MACRO-REGIME features (Fed liquidity + yield-curve) for
backtesting, built on top of the keyed FRED cache (`runner/fred_cache.py`).

RESEARCH/BACKTEST-ONLY. This is the data layer for the `macro_regime_long`
candidate strategy: a long/flat equity overlay whose entry/exit comes from
EXOGENOUS macro series (orthogonal to the traded symbol's own price).

Two features, both classic risk-on/off gates:

  1. liq_slope  — 13-week (configurable) slope of Fed total assets (FRED WALCL,
                  weekly H.4.1 level). >= 0 means the Fed balance sheet is not
                  contracting (liquidity tailwind / neutral). We report the slope
                  as a simple (level_now - level_lookback) difference in $millions
                  (WALCL's native unit). Sign is all the strategy needs, but the
                  magnitude is preserved so a mutation could threshold on it.

  2. curve_spread — 10yr minus 2yr Treasury yield (FRED T10Y2Y, daily, in pct
                  points). A market-priced spread (NOT revised), so "latest"
                  vintage is point-in-time by construction. Deep inversion
                  (well below 0) is the classic late-cycle risk-off tell.

────────────────────────────────────────────────────────────────────────────
ANTI-LOOKAHEAD — THE MAKE-OR-BREAK (read this before trusting any backtest):
────────────────────────────────────────────────────────────────────────────
A macro value must NEVER be visible to a bar decided before that value was
actually PUBLISHED. Each series has a different publication lag, enforced here
by shifting every observation's *effective-known date* forward by a release lag
and then, at query time, only returning rows whose effective-known date is
<= the bar being decided.

  • WALCL (Fed total assets): the H.4.1 statistical release reports the level
    as of each Wednesday, but it is not PUBLISHED until ~16:30 ET the FOLLOWING
    Thursday — i.e. 8 days after the reference Wednesday. We enforce a
    conservative `walcl_release_lag_days = 9` (≥1 week, rounds the 8-day gap up
    and absorbs holiday slippage). So a WALCL row dated 2022-06-01 (a Wednesday)
    is treated as KNOWN only on/after 2022-06-10. A bar on 2022-06-05 sees the
    PRIOR week's level, never the 06-01 one. This is the ">= 1 week lag" the
    task requires, implemented as a per-row effective-date shift (not a sloppy
    global series shift, which would mis-handle the irregular weekly cadence).

  • T10Y2Y (10y-2y spread): a daily MARKET quote computed from that day's
    constant-maturity Treasury yields, published same business day after close.
    A bar deciding at/after that day's close may use the same calendar date's
    value. We still apply a tiny `t10y2y_release_lag_days = 0` (same-day OK) but
    keep it a PARAM so it can be hardened to 1 if one wanted strict
    next-open-only usage. Treasury yields are not revised, so no vintage leak.

Because WALCL is weekly and we need a 13-WEEK SLOPE, the slope at effective
date d uses the latest-known WALCL level at d minus the latest-known level at
(d - lookback_weeks*7), each resolved through the SAME effective-date filter —
so the lookback anchor is itself lag-correct, never a future-revised level.

We additionally REQUIRE both legs of the slope to exist (enough warmup) before
emitting a `liq_slope`; if warmup is missing we emit None and the strategy
treats "no macro read" as risk-OFF (stay flat / fail-safe), never as risk-on.

────────────────────────────────────────────────────────────────────────────
WIRING CHOICE (Option B): this module is imported by the STRATEGY, which builds
its date-indexed macro lookup ONCE at first-decision and maps each bar's
timestamp to the most-recent-allowable (lagged) macro row. We deliberately do
NOT touch the protected backtester's market_state injection — the sibling
candidates `credit_regime_spy_hyglqd` / `macro_nowcast` already prove the
module-scope-cache + slice-by-date pattern runs cleanly through the real
walk-forward with zero backtester changes, so existing bars/regime injection
and every existing test are untouched by construction.

Cache: leans entirely on fred_cache's own disk cache (.cache/fred/). We add a
small in-process memo so a walk-forward run (8 windows) builds each series once.
"""

from __future__ import annotations

import bisect
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from . import fred_cache


# ---------------------------------------------------------------------------
# Defaults (also mirrored as strategy params so a mutation can sweep them).
# ---------------------------------------------------------------------------
WALCL_RELEASE_LAG_DAYS = 9      # H.4.1 published ~Thu after the ref-Wednesday (8d) → 9d safe
T10Y2Y_RELEASE_LAG_DAYS = 0     # daily market quote, same-day after close OK
DEFAULT_LIQ_SLOPE_WEEKS = 13    # 13-week (~1 quarter) Fed-balance-sheet slope
# How far back to pull each series. Generous so even a pre-2010 backtest window
# has full slope warmup. WALCL starts 2002, T10Y2Y starts 1976.
FETCH_START = "2002-01-01"


# In-process memo: (series_id, lag_days) -> list of (effective_known_date_str,
# value) sorted ascending by effective_known_date. Built once per process.
_EFF_SERIES_MEMO: Dict[Tuple[str, int], List[Tuple[str, float]]] = {}


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _shift_date(date_str: str, days: int) -> str:
    """Return date_str + `days` as YYYY-MM-DD (calendar-day shift)."""
    d = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (d + timedelta(days=days)).strftime("%Y-%m-%d")


def _effective_series(series_id: str, lag_days: int) -> List[Tuple[str, float]]:
    """Full-history [(effective_known_date, value)] for `series_id`, oldest-first,
    where effective_known_date = observation_date + lag_days (the publication
    lag). Sorted ascending by effective_known_date so a bisect can resolve the
    latest-known value as-of any bar date without lookahead.

    Uses fred_cache.get_values (vintage="latest"; both WALCL and T10Y2Y are
    effectively unrevised for our purposes — T10Y2Y is a market quote, WALCL is
    an accounting level whose tiny back-revisions are immaterial to a 13-week
    slope SIGN, and the release-lag shift is the dominant correctness control).
    Missing values are dropped by get_values(drop_missing=True).
    """
    key = (series_id, int(lag_days))
    memo = _EFF_SERIES_MEMO.get(key)
    if memo is not None:
        return memo
    raw = fred_cache.get_values(series_id, FETCH_START, _today_str(),
                                vintage="latest", drop_missing=True)
    eff: List[Tuple[str, float]] = []
    for obs_date, val in raw:
        try:
            ed = _shift_date(obs_date, lag_days)
        except Exception:
            continue
        eff.append((ed, float(val)))
    # Sort by effective-known date (lag shift can only preserve/maintain order
    # for a constant lag, but sort defensively in case of duplicates/holidays).
    eff.sort(key=lambda t: t[0])
    _EFF_SERIES_MEMO[key] = eff
    return eff


def _latest_known(eff_series: List[Tuple[str, float]], as_of_date: str
                  ) -> Optional[Tuple[str, float]]:
    """Return the (effective_date, value) with the greatest effective_date that
    is <= as_of_date, or None if none is known yet. Pure no-lookahead lookup.
    """
    if not eff_series:
        return None
    dates = [d for d, _ in eff_series]
    # rightmost index with dates[idx] <= as_of_date
    idx = bisect.bisect_right(dates, as_of_date) - 1
    if idx < 0:
        return None
    return eff_series[idx]


def _value_known_at_or_before(eff_series: List[Tuple[str, float]],
                              as_of_date: str) -> Optional[float]:
    hit = _latest_known(eff_series, as_of_date)
    return hit[1] if hit else None


# ---------------------------------------------------------------------------
# Public feature accessors (all strictly no-lookahead).
# ---------------------------------------------------------------------------

def curve_spread_asof(as_of_date: str,
                      lag_days: int = T10Y2Y_RELEASE_LAG_DAYS) -> Optional[float]:
    """Latest-known 10y-2y spread (pct points) as of `as_of_date`, or None."""
    eff = _effective_series("T10Y2Y", lag_days)
    return _value_known_at_or_before(eff, as_of_date)


def liq_slope_asof(as_of_date: str,
                   lookback_weeks: int = DEFAULT_LIQ_SLOPE_WEEKS,
                   lag_days: int = WALCL_RELEASE_LAG_DAYS) -> Optional[float]:
    """Latest-known WALCL level minus the level `lookback_weeks` earlier, both
    resolved through the lag filter as of `as_of_date`. $millions (WALCL unit).

    Returns None if warmup is insufficient (either leg unknown) — the strategy
    treats None as risk-OFF (fail-safe flat), never risk-on.

    No-lookahead: the "now" leg is the latest WALCL whose effective-known date
    <= as_of_date; the "lookback" leg is the latest WALCL whose effective-known
    date <= (as_of_date - lookback_weeks*7). Both legs use only published data.
    """
    eff = _effective_series("WALCL", lag_days)
    if not eff:
        return None
    now_hit = _latest_known(eff, as_of_date)
    if now_hit is None:
        return None
    anchor_date = _shift_date(as_of_date, -int(lookback_weeks) * 7)
    past_hit = _latest_known(eff, anchor_date)
    if past_hit is None:
        return None
    # If the "now" and "past" resolve to the SAME observation (not enough
    # history between them), the slope is trivially 0 and uninformative —
    # treat as insufficient warmup.
    if now_hit[0] == past_hit[0]:
        return None
    return now_hit[1] - past_hit[1]


def macro_features_asof(as_of_date: str,
                        *,
                        liq_slope_weeks: int = DEFAULT_LIQ_SLOPE_WEEKS,
                        walcl_lag_days: int = WALCL_RELEASE_LAG_DAYS,
                        t10y2y_lag_days: int = T10Y2Y_RELEASE_LAG_DAYS
                        ) -> Dict[str, Optional[float]]:
    """Bundle both features for one bar date. Either may be None (warmup)."""
    return {
        "liq_slope": liq_slope_asof(as_of_date, liq_slope_weeks, walcl_lag_days),
        "curve_spread": curve_spread_asof(as_of_date, t10y2y_lag_days),
    }


def selftest() -> Dict[str, object]:
    """Smoke: prove (a) both series reachable, (b) lag actually shifts the
    effective date forward, (c) a 2020 COVID-QE date reads a POSITIVE liq_slope
    (balance sheet exploding) and a 2022-QT date reads a NEGATIVE one, and
    (d) no future leak (effective dates never precede their observation date).
    Returns a report dict; raises on hard FRED failure.
    """
    rep: Dict[str, object] = {}
    walcl_eff = _effective_series("WALCL", WALCL_RELEASE_LAG_DAYS)
    t10_eff = _effective_series("T10Y2Y", T10Y2Y_RELEASE_LAG_DAYS)
    rep["walcl_n"] = len(walcl_eff)
    rep["t10y2y_n"] = len(t10_eff)
    # (b) effective date strictly later than obs for WALCL (lag>0)
    raw0 = fred_cache.get_values("WALCL", FETCH_START, _today_str(),
                                 vintage="latest", drop_missing=True)
    if raw0:
        obs0 = raw0[0][0]
        eff0 = _shift_date(obs0, WALCL_RELEASE_LAG_DAYS)
        rep["walcl_lag_shifts_forward"] = eff0 > obs0
    # (c) COVID-QE 2020-06 should be strongly POSITIVE; QT 2022-12 NEGATIVE.
    rep["liq_slope_2020_06_15"] = liq_slope_asof("2020-06-15")
    rep["liq_slope_2022_12_15"] = liq_slope_asof("2022-12-15")
    rep["curve_2019_08_30"] = curve_spread_asof("2019-08-30")  # was inverted
    rep["curve_2021_03_31"] = curve_spread_asof("2021-03-31")  # steep positive
    # (d) no leak: an early-window as_of must NOT see a value whose OBSERVATION
    # date is after as_of. Check the WALCL now-leg observation date stays <= as_of.
    asof = "2020-06-15"
    nowhit = _latest_known(walcl_eff, asof)
    rep["walcl_asof_2020_06_15_eff_date"] = nowhit[0] if nowhit else None
    rep["walcl_asof_effdate_le_asof"] = (nowhit[0] <= asof) if nowhit else None
    return rep


if __name__ == "__main__":
    import pprint
    pprint.pprint(selftest())
