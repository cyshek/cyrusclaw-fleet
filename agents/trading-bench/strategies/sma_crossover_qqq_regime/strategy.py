"""SMA crossover on QQQ 1h bars, gated by a SPY-trend regime filter.

Variant of `sma_crossover_qqq` that only opens new long positions when SPY
is above its `regime_period`-day SMA (default 50). Hypothesis: the parent
strategy's small positive edge in bull/chop windows is partially undone by
losses in bear windows; a regime gate should reduce the bear bleed without
giving up much of the bull/chop edge.

Important: the regime gate blocks NEW ENTRIES ONLY. If a position is
already open when the regime turns down, the bearish-cross close signal
(fast < slow) is still honored. The gate must never trap us long.

Regime data: read from `market_state["regime"]` (set by runner/backtester
to {"spy_closes": [...], "spy_last": float}, or None when unavailable).
When None, behavior falls through to parent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # Close logic ALWAYS runs first \u2014 the regime gate must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry gate: respect regime filter only when entering new positions.
    regime = market_state.get("regime")
    if fast > slow and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")
    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")
