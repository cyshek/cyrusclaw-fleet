"""Donchian breakout on XLK 1h bars, gated by a GRADED SPY-regime score.

Mutation of `breakout_xlk_regime`: instead of the binary "SPY above its
50d SMA" gate, this variant uses the graded `regime_score(spy_closes, 50)`
= (last - sma50) / sma50 and only opens new longs when that score exceeds
+0.02 — i.e. SPY must be at least 2% ABOVE its 50-day SMA, not merely
fractionally above it. Thesis: the parent's binary gate still lets entries
through in marginal regimes where SPY is barely above the MA (score ~0),
which are the regimes most likely to whipsaw back into a downtrend and
hand the long-only breakout its worst bars. Demanding a 2% buffer keeps
only the more decisively-bullish regimes, trading a few entries away for a
cleaner regime backdrop.

Entry: close breaks above the prior `lookback`-bar Donchian high AND the
SPY regime_score > entry_regime_score (default 0.02). Exit: close falls
below the prior `lookback`-bar Donchian low.

Important: the regime gate blocks NEW ENTRIES ONLY. Close logic runs first
and unconditionally, so an already-open position can always exit on the
Donchian-low signal even when the regime has decayed below the entry
threshold — otherwise the filter would trap us long through the very
downturn it's meant to avoid. When regime data is absent (None, e.g.
crypto / SPY bars unavailable), regime_score returns 0.0; since 0.0 is not
> 0.02 the gate would block all entries, so we explicitly treat missing
regime as "don't know -> permissive" and skip the gate, matching the
parent's None-handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_score


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
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    entry_regime_score = float(params.get("entry_regime_score", 0.02))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first - the regime gate must never trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry gate: graded regime score must clear the entry threshold.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        spy_closes = (regime.get("spy_closes") or []) if regime else []
        # Missing/empty regime -> permissive (don't know), matching parent.
        if spy_closes:
            score = regime_score(spy_closes, period=regime_period)
            if score <= entry_regime_score:
                return Action("hold", symbol,
                              reason=f"regime score {score:.4f} <= "
                                     f"{entry_regime_score:.4f} "
                                     f"(SPY not >{entry_regime_score:.0%} above "
                                     f"{regime_period}d SMA; breakout blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")
    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")