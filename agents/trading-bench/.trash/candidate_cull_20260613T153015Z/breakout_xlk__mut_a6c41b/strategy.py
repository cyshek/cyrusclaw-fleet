"""Donchian breakout on XLK 1h bars, gated by a GRADED SPY-regime score.

Variant of `breakout_xlk` that replaces the parent's binary regime gate
(SPY above/below its 50d SMA) with a graded `regime_score` threshold. New
long entries are only opened when SPY is trading at least 2% above its
50-day SMA (regime_score > 0.02). This is a STRICTER version of the regime
filter: instead of merely requiring SPY to be above its MA, it demands a
meaningful trend cushion, so marginal "barely-above-the-line" regimes (the
ones most likely to whipsaw back into a downtrend) no longer admit new
breakout entries.

Thesis: the parent breakout edge is long-only and bleeds when the broad
market is weak or just-barely-positive. A binary above/below-SMA gate still
lets us enter when SPY is fractionally above its MA — exactly the fragile
regime where breakouts fail. Requiring a 2% cushion concentrates entries in
clearly-confirmed uptrends, where momentum breakouts have historically held.

Entry: close > 20-bar Donchian high AND flat AND regime_score(SPY,50) > 0.02.
Exit:  close < 20-bar Donchian low while holding (ALWAYS honored — the regime
       gate blocks NEW ENTRIES ONLY and must never trap an open position).

Regime data: read from `market_state["regime"]` ({"spy_closes": [...],
"spy_last": float}), pre-populated by the runner/backtester for stocks. When
regime is None (data unavailable / crypto), the gate is skipped and behavior
matches the parent strategy ("don't know -> behave normally").
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
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    regime_min_score = float(params.get("regime_min_score", 0.02))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first -- the regime gate must never trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry gate: graded regime score must clear the cushion to admit a NEW long.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime is not None:
            score = regime_score(regime.get("spy_closes") or [],
                                 period=regime_period)
            if score <= regime_min_score:
                return Action("hold", symbol,
                              reason=f"regime score {score:.4f} <= "
                                     f"{regime_min_score:.4f} "
                                     f"(SPY trend cushion too thin)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")
    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")