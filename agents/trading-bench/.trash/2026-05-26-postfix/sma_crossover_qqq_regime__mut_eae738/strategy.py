"""SMA crossover on SMH 1h bars, gated by a SPY-trend regime filter.

Port of `sma_crossover_qqq_regime` to SMH (semiconductor ETF), a tech
sub-sector with higher beta than QQQ. Hypothesis: the regime-gated SMA
crossover logic that produced a small positive edge on QQQ should
transfer to SMH, where the larger amplitude of semi moves may give the
crossover signal more room to capture trend without proportionally
worse whipsaw — semis tend to trend hard when tech leads and chop hard
when it doesn't, which is exactly what the SPY regime gate is designed
to filter.

Entry: fast SMA crosses above slow SMA AND SPY > SPY SMA(regime_period).
Exit: fast SMA crosses below slow SMA (regime gate does NOT block exits).
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
    symbol = params.get("symbol", "SMH")
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

    # Close logic ALWAYS runs first — the regime gate must never trap us long.
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