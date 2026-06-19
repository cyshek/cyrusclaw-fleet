"""buy_and_hold_spy: passive-baseline equivalent of buy_and_hold_btc, ported to SPY.

Logic: flat -> buy `notional_usd` of SPY. Else hold. Same as the crypto version
with the symbol swapped; symbol-format detection in the runner picks the right
bar/price/TIF (stocks use TIF=day).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "SPY")
    notional = float(params.get("notional_usd", 100.0))
    pos = position_state.get(symbol)
    holding_qty = float(pos.get("qty", 0)) if pos else 0.0
    if holding_qty > 0:
        return Action("hold", symbol, reason=f"already holding {holding_qty} {symbol}")
    return Action("buy", symbol, notional_usd=notional,
                  reason=f"no position; opening ${notional:.2f} buy-and-hold")
