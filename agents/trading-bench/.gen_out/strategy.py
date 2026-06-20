"""Donchian breakout on XLK 1h bars with a tight hard stop-loss.

Thesis: the parent enters on a 20-bar Donchian high breakout and exits only
when price slips below the 20-bar Donchian low — a slow, lagging exit that can
sit through a sharp adverse 1-2% candle long before the channel low is breached.
This mutation adds a 1.2% hard stop measured from entry price. We chose 1.2%
because the parent's per-trade max-drawdown distribution has a median of 1.41%
and p25 of 2.21%: a 1.2% stop sits just below the median, so it fires on more
than half of historical trades (the ones whose intra-trade dip the lazy
Donchian-low exit would otherwise ride out) while staying well inside the p25
tail so it isn't inert. It catches the fast intra-trade reversal — a one-to-two
bar drop that undercuts entry but recovers before touching the channel low —
that the parent's exit structurally misses. The parent's own Donchian-low close
signal always runs first so an already-triggered exit is never blocked.
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
    stop_loss_pct = float(params.get("stop_loss_pct", 1.2))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) if position_state else None
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1) Parent close signal FIRST: price below Donchian low.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) Hard stop-loss: close if price fell more than stop_loss_pct below entry.
    if holding > 0 and pos:
        entry = pos.get("avg_entry_price")
        if entry is None:
            entry = pos.get("entry_price")
        if entry is not None:
            entry = float(entry)
            if entry > 0:
                drop_pct = (entry - last) / entry * 100.0
                if drop_pct >= stop_loss_pct:
                    return Action("close", symbol,
                                  reason=(f"stop-loss: {last:.2f} is "
                                          f"{drop_pct:.2f}% below entry "
                                          f"{entry:.2f} (>= {stop_loss_pct:.2f}%)"))

    # 3) Entry gate: breakout above Donchian high when flat.
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")
