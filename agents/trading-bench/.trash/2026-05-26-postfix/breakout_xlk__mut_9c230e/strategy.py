"""Donchian breakout on XLK 1h bars with a hard stop-loss overlay.

Mutation of `breakout_xlk`: same Donchian entry (close > N-bar high) and
same Donchian exit (close < N-bar low), but adds a hard percentage
stop-loss tracked via `position_state[symbol]['entry_price']`. If price
falls more than `stop_loss_pct` below the recorded entry, we close
immediately regardless of the Donchian band.

Hypothesis: the parent's worst trades are breakouts that immediately
reverse and bleed down to the lower band, giving back far more than the
typical winning trade earns. A tight hard stop caps the per-trade loss
and should improve expectancy even if it costs some win rate.

Exit precedence: parent's Donchian close signal runs FIRST so the stop
can never block a legitimate exit; the stop only fires when the parent
would otherwise hold. Entry records the entry price into position_state
so subsequent bars can evaluate the stop.
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
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 100.0))
    stop_loss_pct = float(params.get("stop_loss_pct", 0.015))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Parent's close signal ALWAYS runs first — stop must never preempt it.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Hard stop-loss: only evaluated when parent would otherwise hold/no-exit.
    if holding > 0:
        entry_price = pos.get("entry_price")
        try:
            entry_price = float(entry_price) if entry_price is not None else None
        except (TypeError, ValueError):
            entry_price = None
        if entry_price is not None and entry_price > 0:
            drawdown = (last - entry_price) / entry_price
            if drawdown <= -stop_loss_pct:
                return Action("close", symbol,
                              reason=f"stop-loss: last {last:.2f} vs entry "
                                     f"{entry_price:.2f} ({drawdown*100:.2f}% "
                                     f"<= -{stop_loss_pct*100:.2f}%)")

    # Entry: Donchian breakout. Record entry price for the stop to use later.
    if hi is not None and last > hi and holding == 0:
        position_state.setdefault(symbol, {})["entry_price"] = last
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")