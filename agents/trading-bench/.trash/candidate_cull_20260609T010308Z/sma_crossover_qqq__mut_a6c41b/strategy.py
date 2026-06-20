"""SMA(10/30) crossover on QQQ 1h bars, gated by a GRADED SPY-regime score.

Thesis: the parent `sma_crossover_qqq` is a long-only fast/slow SMA crossover.
Its edge comes from riding QQQ momentum, but a crossover can fire in a weak or
deteriorating broad market and bleed. Instead of a binary "SPY above its 50d
SMA" on/off gate, this mutation requires the market to be MEANINGFULLY in an
uptrend: it only opens new longs when `regime_score(spy_closes, 50) > 0.02`,
i.e. SPY is at least 2% above its 50-day SMA. That is a strictly stricter
regime filter than the binary version (which fires at any positive distance),
so it should skip the marginal "barely-above-the-line" entries that tend to
chop.

Entry: fast SMA(10) > slow SMA(30) AND flat AND regime_score > 0.02.
Exit:  fast SMA(10) < slow SMA(30) while holding. The regime gate blocks
NEW ENTRIES ONLY — the crossover-down close ALWAYS runs first so a turning
market can never trap us long. When regime data is unavailable (None, e.g.
SPY bars missing) the gate is skipped and behavior matches the parent.

Edge: same momentum capture as the parent, but the +2% regime floor filters
out entries taken in tepid markets, where long-only crossover signals are
least reliable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, regime_score


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
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    regime_floor = float(params.get("regime_floor", 0.02))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Not-enough-bars guard: need slow_p closes for the slow SMA.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — the regime gate must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry gate: crossover up + flat, then the stricter graded regime floor.
    if fast > slow and holding == 0:
        regime = market_state.get("regime")
        if regime is not None:
            score = regime_score(regime.get("spy_closes") or [], period=regime_period)
            if score <= regime_floor:
                return Action("hold", symbol,
                              reason=(f"regime_score {score:.4f} <= floor "
                                      f"{regime_floor:.4f} (SPY not >2% above "
                                      f"{regime_period}d SMA; entry blocked)"))
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")