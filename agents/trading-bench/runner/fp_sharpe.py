"""Canonical full-period continuous-span Sharpe — the LOAD-BEARING ruler.

GATE clause (a) binds on the full-period CONTINUOUS-SPAN Sharpe: concatenate
every walk-forward window's per-tick equity returns into ONE series and
annualize. This is materially different from (and generally LOWER than) the
median-of-windows Sharpe that the walk-forward aggregates report. The
median-of-windows number is a MIRAGE — it has already caused one bad
promotion (xsec_momentum_xa) and nearly two more. Clause (a) does NOT bind
on it.

Until now this computation lived re-implemented ad-hoc in 3+ throwaway driver
scripts:
  - reports/_lowturn_fpsharpe.py        (fp_sharpe)
  - reports/_ss_momentum_driver.py      (fp_continuous_sharpe)
  - reports/_dispersed_universe_driver.py / _eval_tsmom_xa.py (inline copies)
Each copy hand-rolled the same concatenate-returns-and-annualize logic with a
hardcoded sqrt(252). That is exactly the kind of duplicated, untested,
load-bearing number that produces silent ruler drift. This module
CONSOLIDATES it into ONE canonical, TESTED implementation.

Annualization convention (matches runner.backtest.bars_per_year, the corrected
2026-05-31 ruler):
  - equities  : sqrt(252)  (NYSE ~252 sessions/yr)
  - crypto    : sqrt(365)  (24/7)
A basket is crypto only if ALL legs use a "/" symbol (e.g. "BTC/USD"); any
equity leg => equities. This mirrors backtest_xsec's xsec_is_crypto rule.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from .backtest import bars_per_year


def equity_curve_returns(equity_curve: Sequence[float]) -> List[float]:
    """Per-tick simple returns from one equity curve, skipping non-positive
    prior values (guards against div-by-zero / blown-up equity). Pure helper,
    no annualization."""
    rets: List[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            rets.append((equity_curve[i] - prev) / prev)
    return rets


def concat_window_returns(windows: Iterable) -> List[float]:
    """Concatenate per-tick equity returns across every window into ONE
    continuous series.

    `windows` is an iterable of objects each exposing `.backtest.equity_curve`
    (both `WindowResult` and `XSecWindowResult` satisfy this). The windows are
    consumed in their stored order — which is the chronological NAMED_WINDOWS
    order — so the concatenated series is the full-period span. We do NOT
    bridge the seam between windows with a synthetic return (the last tick of
    window i and the first tick of window i+1 are NOT differenced against each
    other); each window contributes only its own internal tick-to-tick
    returns. This matches every throwaway driver this consolidates.
    """
    rets: List[float] = []
    for w in windows:
        ec = getattr(getattr(w, "backtest", None), "equity_curve", None) or []
        rets.extend(equity_curve_returns(ec))
    return rets


def sharpe_from_returns(returns: Sequence[float], bpy: float) -> float:
    """Annualized Sharpe of a return series given bars-per-year `bpy`.

    Sample stdev (ddof=1). Returns 0.0 for <2 points or zero variance. No
    risk-free adjustment (consistent with backtest_xsec.sharpe and every
    driver this consolidates)."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var <= 0:
        return 0.0
    sd = math.sqrt(var)
    return (mean / sd) * math.sqrt(bpy)


def fp_continuous_sharpe(
    windows: Iterable,
    *,
    timeframe: str = "1Day",
    is_crypto: bool = False,
) -> Tuple[float, int]:
    """CANONICAL full-period continuous-span Sharpe.

    Concatenate every window's per-tick equity returns into one series and
    annualize with sqrt(bars_per_year(timeframe, is_crypto)) — sqrt(252) for
    equities, sqrt(365) for crypto.

    Returns (sharpe, n_returns). `n_returns` is the length of the concatenated
    series (useful for sanity-checking the span has enough data).

    This is THE number clause (a) binds on. Do NOT substitute median-of-windows.
    """
    rets = concat_window_returns(windows)
    bpy = bars_per_year(timeframe, is_crypto)
    return sharpe_from_returns(rets, bpy), len(rets)


def basket_is_crypto(symbols: Sequence[str]) -> bool:
    """A basket is crypto only if it is non-empty and EVERY leg is a "/"
    symbol. Mirrors backtest_xsec's `xsec_is_crypto` rule: any equity leg =>
    treat the whole basket as equities (sqrt(252))."""
    return bool(symbols) and all("/" in s for s in symbols)


def fp_continuous_sharpe_for_agg(agg) -> Tuple[float, int]:
    """Convenience: compute the canonical FP-cont Sharpe directly from a
    walk-forward aggregate (single-symbol `WalkForwardAggregate` or
    cross-sectional `XSecWalkForwardAggregate`).

    Infers timeframe + crypto class from the aggregate where possible:
      - xsec aggregates carry `.basket`; crypto iff all legs are "/" symbols.
      - single-symbol aggregates: inferred from the strategy's window symbol
        is not stored on the aggregate, so we default to equities/1Day. Pass
        the explicit `fp_continuous_sharpe(...)` form if you need crypto/
        intraday annualization for a single-symbol strategy.
    The per-window equity curves already encode the timeframe; only the
    annualization constant depends on this classification.
    """
    basket = list(getattr(agg, "basket", []) or [])
    is_crypto = basket_is_crypto(basket)
    # Timeframe is not stored on the aggregate; the windows' equity curves are
    # daily for every strategy in this tournament. Default 1Day. The only
    # effect of timeframe here is selecting the bars_per_year constant.
    timeframe = "1Day"
    return fp_continuous_sharpe(
        getattr(agg, "windows", []), timeframe=timeframe, is_crypto=is_crypto)
