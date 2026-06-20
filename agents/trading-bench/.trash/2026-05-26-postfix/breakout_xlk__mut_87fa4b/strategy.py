"""Bollinger-style mean-reversion on IWM 1h bars.

Thesis: small-cap ETFs like IWM tend to mean-revert on short horizons —
sharp pullbacks below a lower volatility band on otherwise-trending tape
are often overreactions that snap back to the moving-average mid-line.
This is the contrarian inverse of the parent Donchian breakout: instead
of buying new highs, we buy washouts below an SMA - k*stdev lower band,
and exit when price reverts back to (or above) the SMA mid-line, or when
a hard stop/take-profit fires sized to the parent's empirical trade
distribution.

Entry: flat AND last close < SMA(period) - entry_k * stdev(period).
Exit: holding AND (last close >= SMA(period)              # mean reverted
                   OR drawdown from entry <= -stop_pct    # hard stop
                   OR runup from entry >= take_pct).      # take profit

Stop (1.30%) sits just inside the parent's median per-trade drawdown
(1.41%); take-profit (2.40%) sits just inside the parent's median per-trade
runup (2.60%) — both inside the empirical distribution, neither inert.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    period = int(params.get("period", 20))
    entry_k = float(params.get("entry_k", 2.0))
    stop_pct = float(params.get("stop_pct", 0.0130))
    take_pct = float(params.get("take_pct", 0.0240))
    notional = float(params.get("notional_usd", 100.0))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < period + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)}, need {period + 1})")

    last = cs[-1]
    mid = sma(cs, period)
    if mid is None:
        return Action("hold", symbol, reason="sma unavailable")

    window = cs[-period:]
    try:
        sd = statistics.pstdev(window)
    except statistics.StatisticsError:
        return Action("hold", symbol, reason="stdev unavailable")

    if not math.isfinite(sd) or sd <= 0:
        return Action("hold", symbol, reason=f"degenerate stdev ({sd})")

    lower = mid - entry_k * sd

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_price = float(pos.get("avg_entry_price", 0) or pos.get("entry_price", 0) or 0.0)

    # --- Close logic ALWAYS runs first so no filter can trap us long. ---
    if holding > 0:
        # Mean reversion completed: price reclaimed the mid-line.
        if last >= mid:
            return Action("close", symbol,
                          reason=f"reverted: close {last:.2f} >= sma{period} {mid:.2f}")
        # Hard stop / take-profit, sized to parent's per-trade distribution.
        if entry_price > 0:
            change = (last - entry_price) / entry_price
            if change <= -stop_pct:
                return Action("close", symbol,
                              reason=f"stop: {change*100:.2f}% <= -{stop_pct*100:.2f}%")
            if change >= take_pct:
                return Action("close", symbol,
                              reason=f"take: {change*100:.2f}% >= {take_pct*100:.2f}%")

    # --- Entry: pullback below lower band while flat. ---
    if holding == 0 and last < lower:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"pullback: close {last:.2f} < lower {lower:.2f} "
                             f"(sma{period}={mid:.2f}, sd={sd:.2f}, k={entry_k})")

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, mid={mid:.2f}, "
                         f"lower={lower:.2f}, holding={holding})")