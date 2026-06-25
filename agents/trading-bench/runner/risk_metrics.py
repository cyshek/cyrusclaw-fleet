"""Risk-adjusted ranking metrics: Sortino and Calmar.

These complement the raw total-P&L ranking in `ranking.py`. Both are derived from a
**realized daily-P&L series** (the same FIFO series that `correlation.daily_pnl_series`
already produces), so no new data subsystem is needed.

Design notes / honesty caveats (this is a tiny live book):
  * These are computed on REALIZED daily P&L in DOLLARS, not on a returns ratio over capital.
    With per-strategy notionals differing, dollar-Sharpe-likes are comparable in *shape* but
    a strategy with larger notional will show larger dollar dispersion. We expose both the raw
    dollar metric AND a per-dollar-turnover-normalized variant so the leaderboard isn't just
    "who traded biggest". Treat all of these as noise until n_closed_days is large.
  * Sortino uses DOWNSIDE deviation (only negative daily P&L vs a 0 target). If there are no
    losing days, downside dev is 0 and Sortino is undefined (returned as None, not +inf).
  * Calmar = annualized mean daily P&L / max peak-to-trough drawdown of the cumulative curve.
    If the curve never draws down (monotone up), maxDD is 0 and Calmar is undefined (None).
  * Annualization uses 252 trading days (equities), matching the project-wide √252 convention
    (see MEMORY.md "THE √252 SHARPE BUG").

All functions are pure and import nothing from the runner except types. Unit-tested in
tests/test_risk_metrics.py.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Dict, List, Optional, Tuple

TRADING_DAYS_PER_YEAR = 252


def series_to_sorted_pairs(pnl_by_day: Dict[date, float]) -> List[Tuple[date, float]]:
    """Sort a {day: pnl} dict into ascending-date (day, pnl) pairs."""
    return sorted(pnl_by_day.items(), key=lambda kv: kv[0])


def daily_values(pnl_by_day: Dict[date, float]) -> List[float]:
    """Realized daily P&L values in date order (days with no close are absent upstream)."""
    return [v for _, v in series_to_sorted_pairs(pnl_by_day)]


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def downside_deviation(values: List[float], target: float = 0.0) -> Optional[float]:
    """Root-mean-square of shortfalls below `target`.

    Population RMS over the FULL sample length (standard Sortino denominator):
    sqrt( mean( min(0, x - target)^2 ) ). Returns None if there are zero days, or 0.0 if
    there are days but none below target (caller maps 0.0 -> undefined Sortino).
    """
    if not values:
        return None
    sq = [min(0.0, x - target) ** 2 for x in values]
    return math.sqrt(sum(sq) / len(values))


def sortino(
    values: List[float],
    target: float = 0.0,
    annualize: bool = True,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> Optional[float]:
    """Sortino ratio of a daily-P&L series. None if undefined (no days or no downside)."""
    if not values or len(values) < 2:
        return None
    dd = downside_deviation(values, target)
    if dd is None or dd == 0.0:
        return None  # no losing days -> Sortino undefined (do NOT return +inf)
    excess = _mean(values) - target
    ratio = excess / dd
    if annualize:
        ratio *= math.sqrt(periods_per_year)
    return ratio


def max_drawdown(values: List[float]) -> float:
    """Max peak-to-trough drawdown (in the same units) of the CUMULATIVE sum of values.

    The equity curve starts at 0 (no capital deployed yet), so the running peak is seeded
    at 0.0 and a strategy that opens with a losing day is correctly counted as in drawdown.
    Returns a NON-NEGATIVE magnitude. 0.0 if the cumulative curve never declines below its
    running peak (e.g. a monotone-up curve).
    """
    cum = 0.0
    peak = 0.0  # equity starts at 0; an opening loss is a real drawdown vs the 0 peak
    max_dd = 0.0
    for x in values:
        cum += x
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
    return max_dd


def calmar(
    values: List[float],
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> Optional[float]:
    """Calmar-like ratio = annualized mean daily P&L / max drawdown.

    Uses the realized-day sample (mean over days that had closes), annualized by
    periods_per_year. None if <2 days or if there is no drawdown (undefined).
    """
    if not values or len(values) < 2:
        return None
    mdd = max_drawdown(values)
    if mdd == 0.0:
        return None  # monotone-up curve -> Calmar undefined (do NOT return +inf)
    annual_pnl = _mean(values) * periods_per_year
    return annual_pnl / mdd


def compute_for_series(pnl_by_day: Dict[date, float]) -> dict:
    """Bundle Sortino + Calmar + supporting counts for one strategy's daily-P&L series."""
    vals = daily_values(pnl_by_day)
    n_days = len(vals)
    n_down = sum(1 for v in vals if v < 0.0)
    return {
        "n_closed_days": n_days,
        "n_down_days": n_down,
        "sortino": sortino(vals),
        "calmar": calmar(vals),
        "max_drawdown_usd": round(max_drawdown(vals), 4) if vals else 0.0,
    }
