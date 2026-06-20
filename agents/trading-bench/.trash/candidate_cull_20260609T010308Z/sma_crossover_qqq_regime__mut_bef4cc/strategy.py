"""SMA crossover on QQQ 1h bars (SPY-regime gated) + a TIGHT hard stop-loss.

Variant of `sma_crossover_qqq_regime`. The parent opens long on a bullish
SMA cross (fast>slow) when SPY is above its 50-day SMA, and closes on the
bearish cross (fast<slow). Hypothesis for this mutation: the parent's exit
is structurally LATE on sharp adverse moves — it only fires once the fast
SMA has fallen back under the slow SMA, which takes several bars of decline
to confirm. A trade can therefore bleed through a fast intra-trade reversal
before the cross-exit ever triggers. A tight per-trade stop catches that
specific failure: a quick drop that the lagging cross hasn't yet registered.

Stop threshold = 0.60% below entry. Grounding (parent's 42-trade profile):
median per-trade max drawdown was -0.76% and p75 was -0.48%, with 43% of
trades touching >=1%. A 0.60% stop sits BETWEEN p75 and the median, so it
would have fired on more than half of historical trades (the median trade
drew down past it) while staying shallow enough not to be inert like a
1.3%+ stop (which is below the p25 tail and would essentially never fire).
The stop is meant to amputate the fat-left-tail trades early rather than
ride them down to the eventual cross-exit.

The stop NEVER blocks the parent's own close signal: close-logic (cross
exit, then stop) runs entirely before the entry gate, so an open position
is always exitable regardless of regime. Entry price is tracked in
position_state[symbol]["avg_entry_price"] (runner-populated); we fall back
to "entry_price"/"price" keys and skip the stop gracefully if none exist.

Regime data: read from market_state["regime"] = {"spy_closes":[...]} or
None (crypto / unavailable), in which case the entry gate is a no-op.
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


def _entry_price(pos: dict) -> Optional[float]:
    """Best-effort entry price from position_state; None if unknown."""
    if not pos:
        return None
    for key in ("avg_entry_price", "entry_price", "avg_price", "price"):
        v = pos.get(key)
        if v is not None:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if f > 0:
                return f
    return None


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    stop_pct = float(params.get("stop_loss_pct", 0.006))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]

    # ----- CLOSE LOGIC (always first; never gated) -----
    # 1) Parent's own exit takes priority: bearish cross closes the position.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2) Hard stop-loss: only if the parent's exit did NOT already fire.
    if holding > 0:
        ep = _entry_price(pos)
        if ep is not None and last <= ep * (1.0 - stop_pct):
            dd = (last - ep) / ep
            return Action("close", symbol,
                          reason=f"stop-loss {dd*100:.2f}% <= -{stop_pct*100:.2f}% "
                                 f"(last={last:.2f}, entry={ep:.2f})")

    # ----- ENTRY GATE (regime-filtered) -----
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