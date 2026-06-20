"""Donchian breakout on XLK 1h bars, gated by a SPY-trend regime filter.

Mutation of `breakout_xlk_regime`: same logic, but the Donchian lookback
is shortened from 20 to 12 bars. A tighter channel fires more often and
reacts faster to fresh highs/lows; the hypothesis is that on XLK 1h, the
20-bar window is slow enough to enter near the top of moves and exit late.
A 12-bar Donchian should capture earlier breakouts while still being long
enough to filter intrabar noise.

Regime gate is unchanged: blocks NEW entries when SPY is below its
`regime_period`-day SMA, never blocks exits. Already-open positions are
always closeable on a Donchian-low break.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 12))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — the regime gate must never trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry gate: respect regime filter only when entering new positions.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")
    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")