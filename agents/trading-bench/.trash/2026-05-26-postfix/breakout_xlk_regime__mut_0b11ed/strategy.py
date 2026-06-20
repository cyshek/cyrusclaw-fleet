"""Donchian breakout on XLK 1h bars + SPY regime gate + take-profit overlay.

Parent (`breakout_xlk_regime`) gives back gains on winners by holding until
price breaks the 20-bar low. Empirically, median per-trade max runup is
+2.60% but trades often round-trip back through entry before the Donchian
exit fires. Hypothesis: skimming winners at a fixed % above entry locks in
a meaningful chunk of the median winner without being so tight it clips
the small/normal winners.

Take-profit threshold = 1.60%. Rationale grounded in parent's distribution:
- p25 runup is +0.71%, median is +2.60%. 1.60% sits between p25 and median,
  so it would have fired on more than half of historical winners (which
  matches the "lock in winners" intent) while still letting small grinds
  finish on their own. Crucially it's well below the p75 (+4.07%) so it
  isn't inert, and well below the median so it isn't a tiny rounding-error
  threshold either.

Ordering rules (preserved from parent):
- Close-on-Donchian-low ALWAYS runs first; take-profit only triggers when
  the parent would otherwise hold a position.
- Regime gate blocks NEW ENTRIES ONLY; existing positions remain closeable.

Entry price tracking: stored in position_state[symbol]["entry_price"] when
we buy. If a position pre-exists without a tracked entry (cold start /
externally opened), we fall back to position_state[symbol].get("avg_price")
and finally skip TP if neither is available — never block on missing data.
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
    take_profit_pct = float(params.get("take_profit_pct", 0.016))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1) Parent close logic ALWAYS runs first.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) Take-profit overlay: only when parent would otherwise hold.
    if holding > 0:
        entry_price = pos.get("entry_price")
        if entry_price is None:
            entry_price = pos.get("avg_price")
        if entry_price is not None:
            entry_price = float(entry_price)
            if entry_price > 0:
                gain = (last - entry_price) / entry_price
                if gain >= take_profit_pct:
                    return Action(
                        "close", symbol,
                        reason=(f"take-profit {gain*100:.2f}% >= "
                                f"{take_profit_pct*100:.2f}% "
                                f"(entry={entry_price:.2f}, last={last:.2f})")
                    )

    # 3) Entry gate: respect regime filter only when entering new positions.
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