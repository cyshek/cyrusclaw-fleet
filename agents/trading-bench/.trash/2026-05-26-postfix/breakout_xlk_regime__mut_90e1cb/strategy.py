"""Donchian breakout AND SMA-trend confirmation on XLK 1h, SPY-regime gated.

Mutation of `breakout_xlk_regime`: requires BOTH the parent's Donchian
breakout (last close > N-bar high) AND a fast/slow SMA confirmation
(fast SMA > slow SMA) to enter. Logical AND — both must fire on the same
bar. Thesis: raw Donchian breakouts include a lot of chop-noise pokes
above recent highs that immediately fail; requiring the trend structure
(fast MA above slow MA) to already be up filters out counter-trend
breakouts and breakouts that occur during sideways/topping action.

Exit is unchanged from parent: close when last < N-bar low. Per the rules,
exits must never be harder than entries — neither the SMA filter nor the
regime gate can block a close. SPY regime gate still blocks new entries
only when SPY is below its regime SMA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, sma, regime_uptrend


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
    fast_period = int(params.get("fast_period", 10))
    slow_period = int(params.get("slow_period", 30))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))

    cs = closes(market_state.get("bars") or [])
    need = max(lookback + 1, slow_period)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)
    fast = sma(cs, fast_period)
    slow = sma(cs, slow_period)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — no filter may trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry: require Donchian breakout AND fast SMA > slow SMA AND flat.
    if (hi is not None and fast is not None and slow is not None
            and last > hi and fast > slow and holding == 0):
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout+trend signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"breakout {last:.2f}>{hi:.2f} AND "
                             f"fast({fast_period})={fast:.2f}>slow({slow_period})={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no entry (last={last:.2f}, hi={hi}, fast={fast}, "
                         f"slow={slow}, holding={holding})")