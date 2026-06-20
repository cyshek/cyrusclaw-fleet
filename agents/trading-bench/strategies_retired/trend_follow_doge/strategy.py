"""Trend-follow on DOGE/USD 1d bars.

Close > SMA(20) and flat -> buy.
Close < SMA(20) and holding -> close.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "DOGE/USD")
    period = int(params.get("period", 20))
    notional = float(params.get("notional_usd", 100.0))

    cs = closes(market_state.get("bars") or [])
    s = sma(cs, period)
    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if s is None or not cs:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    if last > s and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.4f} > SMA{period} {s:.4f}")
    if last < s and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.4f} < SMA{period} {s:.4f}")
    return Action("hold", symbol,
                  reason=f"last={last:.4f}, sma={s:.4f}, holding={holding}")
