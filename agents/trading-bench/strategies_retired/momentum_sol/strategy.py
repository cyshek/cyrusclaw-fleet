"""Momentum on SOL/USD 4h bars.

12-bar return > +2% and flat -> buy.
12-bar return < -1% and holding -> close.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, pct_change


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "SOL/USD")
    lookback = int(params.get("lookback", 12))
    buy_th = float(params.get("buy_threshold", 0.02))
    exit_th = float(params.get("exit_threshold", -0.01))
    notional = float(params.get("notional_usd", 100.0))

    cs = closes(market_state.get("bars") or [])
    ch = pct_change(cs, lookback)
    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if ch is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    if ch > buy_th and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"{lookback}-bar return {ch:.2%} > {buy_th:.2%}")
    if ch < exit_th and holding > 0:
        return Action("close", symbol,
                      reason=f"{lookback}-bar return {ch:.2%} < {exit_th:.2%}")
    return Action("hold", symbol,
                  reason=f"return={ch:.2%}, holding={holding}")
