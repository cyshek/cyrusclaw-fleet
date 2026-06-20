"""SMA crossover ported from QQQ to SMH (semiconductor ETF, same tech asset class).

Thesis: the parent `sma_crossover_qqq` rides intermediate-term tech momentum by
going long when the fast SMA crosses above the slow SMA and flattening when it
crosses back below. Semiconductors (SMH) are a higher-beta expression of the same
broad-tech trend that drives QQQ, so the identical crossover logic should capture
the same momentum regimes with more amplitude per move.

Entry: fast SMA(10) > slow SMA(30) and currently flat -> go long.
Exit:  fast SMA(10) < slow SMA(30) while long -> close. The close test is
evaluated BEFORE the entry test so no filter can ever trap an open position.

Edge: trend-following on a liquid, high-beta tech proxy. The crossover params
(fast=10, slow=30) and bar_limit are carried over unchanged from the parent,
whose 68-trade walk-forward profile (median per-trade runup +1.17%, median
drawdown -1.14%, median hold 20 bars at 1Hour) is the empirical basis for
trusting this symbol port without re-tuning the periods.
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
    symbol = params.get("symbol", "SMH")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 1000.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Mandatory not-enough-bars guard: need at least `slow_p` closes for SMA(slow).
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # Close logic FIRST so an exit signal is never blocked by any gate.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry second.
    if fast > slow and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")