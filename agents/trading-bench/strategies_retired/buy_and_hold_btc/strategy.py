"""buy_and_hold_btc: the dumbest strategy in the tournament.

Logic:
    - If we hold no BTC/USD position, buy `notional_usd` worth.
    - Otherwise, hold.

That's it. Real point is to exercise the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Action:
    action: str            # 'buy' | 'sell' | 'hold'
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "BTC/USD")
    notional = float(params.get("notional_usd", 100.0))

    pos = position_state.get(symbol)
    holding_qty = float(pos.get("qty", 0)) if pos else 0.0

    if holding_qty > 0:
        return Action(
            action="hold",
            symbol=symbol,
            reason=f"already holding {holding_qty} {symbol}",
        )

    return Action(
        action="buy",
        symbol=symbol,
        notional_usd=notional,
        reason=f"no position; opening ${notional:.2f} buy-and-hold",
    )
