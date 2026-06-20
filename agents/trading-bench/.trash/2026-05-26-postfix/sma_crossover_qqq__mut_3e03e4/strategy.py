"""SMA crossover on QQQ 1h bars with a 20-bar realized-volatility entry filter.

Parent: sma_crossover_qqq. Entry signal is fast SMA crossing above slow SMA;
exit is the reverse cross. This mutation adds a volatility gate: new entries
are blocked when the stdev of the last 20 per-bar pct returns exceeds
`vol_threshold`. Threshold default = 0.011 (per-bar stdev, ~1.1%), chosen
near the parent's median per-trade max runup (1.17%) so that the choppiest
~15-20% of historical bars — where signal-to-noise on a crossover is worst —
get skipped while normal-vol regimes pass through. Closes are never gated:
an already-open position will always honor the bearish cross.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
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
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    vol_period = int(params.get("vol_period", 20))
    vol_threshold = float(params.get("vol_threshold", 0.011))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    needed = max(slow_p, vol_period + 1)
    if len(cs) < needed:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {needed})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # Close logic ALWAYS runs first — volatility gate must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry signal + volatility gate.
    if fast > slow and holding == 0:
        rets = []
        for i in range(len(cs) - vol_period, len(cs)):
            prev = cs[i - 1]
            if prev == 0:
                continue
            rets.append((cs[i] - prev) / prev)
        vol = pstdev(rets) if len(rets) >= 2 else 0.0
        if vol > vol_threshold:
            return Action("hold", symbol,
                          reason=f"vol gate: stdev{vol_period}={vol:.4f} > {vol_threshold:.4f}")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(vol{vol_period}={vol:.4f})")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")