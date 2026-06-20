"""Donchian breakout on XLK 1h bars with a longer lookback window.

Mutation of `breakout_xlk`: lookback raised from 20 to 40 bars. Hypothesis:
a wider Donchian channel filters out noise-level breakouts and only fires
on more decisive moves, which should reduce whipsaw entries at the cost
of later entries. Entry: close above the prior 40-bar high (and flat).
Exit: close below the prior 40-bar low (and long). Logic otherwise
identical to the parent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 40))
    notional = float(params.get("notional_usd", 100.0))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")
    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")