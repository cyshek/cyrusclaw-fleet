"""Donchian breakout on SOXX 1h bars, gated by a SPY-trend regime filter.

Port of `breakout_xlk_regime` to SOXX (iShares Semiconductor ETF). Same
asset class (US tech sector ETF) as the XLK parent, but concentrated in
semiconductors — historically higher beta than broad tech, which may give
the Donchian breakout signal more room to run when it works (and more
room to bleed when it doesn't, hence the regime gate matters more here).

Entry: close breaks above the prior `lookback`-bar high AND SPY is above
its `regime_period`-day SMA. Exit: close breaks below the prior
`lookback`-bar low (always honored, regardless of regime). Edge hypothesis
is identical to parent: trend-following on a liquid sector ETF, with the
SPY regime filter cutting bear-market false breakouts that bleed a
long-only system.

Regime data: read from `market_state["regime"]`. If None (data unavailable),
the gate is skipped and behavior matches the un-gated parent.
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
    symbol = params.get("symbol", "SOXX")
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