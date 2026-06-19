"""SPY-relative performance helpers for walk-forward candidate reporting.

This module makes the "beat passive SPX risk-adjusted" comparison a
FIRST-CLASS, mechanical metric instead of an ad-hoc calculation hand-rolled
inside throwaway drivers. Given a strategy's per-period (per-bar) return
series and the aligned SPY buy-and-hold per-period return series over the
SAME dates, it computes:

  - excess_return_annualized = strategy_ann_return − spy_ann_return
        (geometric/compounded annualization of each side's per-period
         returns, using the harness's `bars_per_year` convention)
  - information_ratio = mean(excess_per_period) / std(excess_per_period)
                        * sqrt(periods_per_year)
        (tracking-error-based IR, annualized — the risk-adjusted measure of
         how reliably the strategy out-/under-performs SPY)

DESIGN NOTES
- Annualization convention is the SAME one the harness already uses for
  Sharpe: `bars_per_year(timeframe, is_crypto)` imported from
  runner.backtest. We do NOT hardcode sqrt(252) — intraday timeframes and
  crypto would be mis-annualized.
- The IR uses the SAMPLE standard deviation (ddof=1) of the per-period
  excess series, matching the harness's Sharpe convention (see
  backtest.py: var divides by len-1). This keeps IR and Sharpe on the same
  statistical footing.
- Edge cases:
    * zero / near-zero tracking error  -> IR is undefined; return None
      (NEVER divide by zero / inf).
    * empty or length-mismatched series -> raise ValueError (caller bug;
      fail loudly rather than silently return garbage).
    * < 2 periods                       -> sample std undefined; IR is None.
- Alignment is the CALLER's responsibility for the core math (both series
  must already be aligned index-for-index by date). `align_returns_by_date`
  is provided as a convenience to align two (date -> return) mappings onto
  their common dates in chronological order, with NO lookahead.

This module is REPORTING-ONLY. It does not gate, rank, or alter any
pass/fail decision. It only surfaces numbers.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

# Use the harness's own annualization convention. Do NOT hardcode sqrt(252).
from .backtest import bars_per_year  # noqa: E402

# Tracking error below this (annualized-input scale, i.e. per-period stdev)
# is treated as "effectively zero" -> IR undefined. 1e-12 is far below any
# real per-period return noise but guards against pure floating-point dust.
_ZERO_TE_EPS = 1e-12


def _validate_pair(strategy_returns: Sequence[float],
                   spy_returns: Sequence[float]) -> None:
    """Raise ValueError if the two per-period series are unusable."""
    if strategy_returns is None or spy_returns is None:
        raise ValueError("return series must not be None")
    n_s = len(strategy_returns)
    n_b = len(spy_returns)
    if n_s == 0 or n_b == 0:
        raise ValueError(
            f"empty return series (strategy={n_s}, spy={n_b}); "
            "cannot compute SPY-relative metrics"
        )
    if n_s != n_b:
        raise ValueError(
            f"length mismatch: strategy has {n_s} periods, spy has {n_b}; "
            "series must be aligned by date before computing SPY-relative metrics"
        )


def annualized_return(per_period_returns: Sequence[float],
                      bars_per_yr: float) -> float:
    """Geometric (compounded) annualized return from a per-period return series.

    growth = prod(1 + r_i); total over `n` periods. Annualize by raising the
    per-period geometric mean growth to `bars_per_yr`:

        ann = (prod(1+r))**(bars_per_yr / n) - 1

    This matches how a buy-and-hold or compounding strategy actually grows.
    Empty series -> 0.0 (no periods, no return). A growth factor that goes
    non-positive (a -100%+ wipeout, only possible with leverage/cost bugs)
    is clamped so we don't take a root of a negative number; in that case we
    report -100% (total loss), which is the economically correct floor.
    """
    n = len(per_period_returns)
    if n == 0:
        return 0.0
    growth = 1.0
    for r in per_period_returns:
        growth *= (1.0 + r)
    if growth <= 0.0:
        return -1.0  # total (or worse) loss; floor at -100%
    return growth ** (bars_per_yr / n) - 1.0


def information_ratio(strategy_returns: Sequence[float],
                      spy_returns: Sequence[float],
                      bars_per_yr: float) -> Optional[float]:
    """Annualized, tracking-error-based information ratio.

        excess_i = strategy_i − spy_i               (per period)
        IR = mean(excess) / stdev_sample(excess) * sqrt(bars_per_yr)

    Returns None when IR is undefined:
      - fewer than 2 aligned periods (sample stdev needs ≥2), OR
      - tracking error (stdev of excess) is ~0 (strategy tracks SPY exactly,
        or any constant-excess series -> zero TE -> infinite/undefined IR).

    Raises ValueError on empty / length-mismatched input (caller bug).
    """
    _validate_pair(strategy_returns, spy_returns)
    n = len(strategy_returns)
    excess = [s - b for s, b in zip(strategy_returns, spy_returns)]
    if n < 2:
        return None  # sample stdev undefined
    mean_excess = sum(excess) / n
    var = sum((e - mean_excess) ** 2 for e in excess) / (n - 1)
    te = math.sqrt(var)
    if te <= _ZERO_TE_EPS:
        return None  # zero tracking error -> IR undefined (no divide-by-zero)
    return (mean_excess / te) * math.sqrt(bars_per_yr)


def spy_relative_metrics(strategy_returns: Sequence[float],
                         spy_returns: Sequence[float],
                         *,
                         timeframe: str,
                         is_crypto: bool = False) -> Dict[str, Optional[float]]:
    """Full SPY-relative report for one candidate window.

    Args:
        strategy_returns: per-period (per-bar) returns of the strategy's
            EQUITY, aligned index-for-index with `spy_returns` by date.
        spy_returns: per-period SPY buy-and-hold (close-to-close) returns
            over the SAME dates.
        timeframe: harness timeframe string (e.g. '1Day', '1Hour') — drives
            `bars_per_year` annualization. Same convention as Sharpe.
        is_crypto: pass-through to `bars_per_year` (only affects '1Day').

    Returns dict:
        {
          "strategy_ann_return": float,
          "spy_ann_return": float,
          "excess_return_annualized": float,   # strategy − spy
          "information_ratio": float | None,   # None if undefined
          "n_periods": int,
        }

    Raises ValueError on empty / length-mismatched series.
    """
    _validate_pair(strategy_returns, spy_returns)
    bpy = bars_per_year(timeframe, is_crypto)
    strat_ann = annualized_return(strategy_returns, bpy)
    spy_ann = annualized_return(spy_returns, bpy)
    ir = information_ratio(strategy_returns, spy_returns, bpy)
    return {
        "strategy_ann_return": strat_ann,
        "spy_ann_return": spy_ann,
        "excess_return_annualized": strat_ann - spy_ann,
        "information_ratio": ir,
        "n_periods": len(strategy_returns),
    }


def returns_from_closes(closes: Sequence[float]) -> List[float]:
    """Close-to-close simple returns from a price series.

    Used to build the SPY buy-and-hold per-period return series from SPY
    close prices. A series of `m` closes yields `m-1` returns. Skips any
    non-positive previous price (defensive; real bars are positive).
    """
    out: List[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev > 0:
            out.append((closes[i] - prev) / prev)
    return out


def align_returns_by_date(
    strategy_by_date: Dict[str, float],
    spy_by_date: Dict[str, float],
) -> Tuple[List[float], List[float], List[str]]:
    """Align two date->return maps onto their common dates, chronologically.

    Returns (strategy_aligned, spy_aligned, common_dates_sorted). Only dates
    present in BOTH maps are kept; the result is sorted ascending by date
    string (ISO-8601 sorts chronologically). NO lookahead: this is pure set
    intersection over already-realized per-period returns — no future data
    is borrowed.

    Raises ValueError if there are no common dates (nothing to compare).
    """
    common = sorted(set(strategy_by_date) & set(spy_by_date))
    if not common:
        raise ValueError(
            "no overlapping dates between strategy and SPY return series; "
            "cannot align for SPY-relative metrics"
        )
    strat = [strategy_by_date[d] for d in common]
    spy = [spy_by_date[d] for d in common]
    return strat, spy, common
