"""Donchian breakout on XLK 1h bars, gated by a SPY-trend regime filter.

Variant of `breakout_xlk` that only opens new long positions when SPY is
trading above its `regime_period`-day SMA (default 50). Hypothesis: the
parent strategy's edge is consistent in bull/chop windows but bleeds in
bear windows because it's long-only; refusing to enter during downtrends
should preserve the bull/chop edge while cutting the bear bleed.

Important: the regime gate blocks NEW ENTRIES ONLY. If a position is
already open when the regime turns down, the close signal (price < Donchian
low) is still honored. Otherwise we'd be stuck holding through the very
downturn the filter is supposed to protect us from.

Regime data: read from `market_state["regime"]`, which the runner/backtester
pre-populates with {"spy_closes": [...], "spy_last": float}. If regime is
None (data unavailable / crypto), the gate is skipped and behavior matches
the parent strategy.
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
    lookback = int(params.get("lookback", 20))
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

    # Close logic ALWAYS runs first \u2014 the regime gate must never trap us long.
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
