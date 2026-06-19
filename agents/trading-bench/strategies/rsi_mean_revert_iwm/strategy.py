"""RSI mean-reversion on IWM 1h bars. Port of rsi_mean_revert_eth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, rsi


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    period = int(params.get("rsi_period", 14))
    buy_below = float(params.get("buy_below", 30))
    exit_above = float(params.get("exit_above", 55))
    notional = float(params.get("notional_usd", 100.0))

    cs = closes(market_state.get("bars") or [])
    r = rsi(cs, period)
    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if r is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")
    if r < buy_below and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"RSI={r:.1f} < {buy_below}")
    if r > exit_above and holding > 0:
        return Action("close", symbol, reason=f"RSI={r:.1f} > {exit_above}")
    return Action("hold", symbol, reason=f"RSI={r:.1f}, holding={holding}")
