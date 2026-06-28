"""SMA crossover on QQQ 1h bars. Port of sma_crossover_btc.

Period-sweep mutation of the parent: the entry signal is a fast SMA crossing
ABOVE a slow SMA (go long), and the exit signal is the fast SMA crossing
BACK BELOW the slow SMA (close). The only change from the parent is the
lookback pair — fast=20 / slow=50 instead of 10/30 — to capture slower,
more persistent trends and filter out shorter-lived crossovers that whipsaw.
Edge thesis: a wider, slower MA pair trades less often but each signal sits
on a more durable trend, trimming the whipsaw losses the tighter 10/30 pair
takes in choppy regimes while still riding sustained QQQ uptrends.
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
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 20))
    slow_p = int(params.get("slow", 50))
    notional = float(params.get("notional_usd", 100.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")
    if fast > slow and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")
    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")