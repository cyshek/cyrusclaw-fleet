"""SMA crossover on QQQ 1h bars with a take-profit overlay.

Thesis: the parent `sma_crossover_qqq` exits only on a slow SMA(10)/SMA(30)
cross-down. By the time that lagging signal fires, winners that ran up have
often already given much of the gain back. This variant locks in profit by
closing the position once price has risen more than 1.10% above the recorded
entry price.

Entry signal: unchanged from parent — buy when SMA(fast) > SMA(slow) and flat.
Exit signal: (1) parent's SMA cross-down close ALWAYS runs first; (2) if the
parent would otherwise hold, a take-profit fires when price >= entry * 1.0110.

Why 1.10%? The parent's empirical per-trade max-runup distribution over 68
walk-forward trades has median +1.17% (p25 +0.52%, p75 +3.03%). A target ABOVE
the p75 (3.03%) would be inert; a target at/below the median (1.17%) would have
locked in at least half the winners. 1.10% sits just below the median, so it
fires on slightly more than half of the runup-touching trades while staying
inside the observed distribution (not a round 1%/2% guess) — capturing the
typical winner's high before the lagging cross hands it back.

Entry price is tracked in position_state[symbol]["avg_entry_price"] (with
fallbacks to other common keys); if no entry price is available the overlay
safely no-ops and behavior matches the parent.
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


def _entry_price(pos: dict) -> Optional[float]:
    """Best-effort recovery of the position's entry price from common keys."""
    if not pos:
        return None
    for key in ("avg_entry_price", "entry_price", "avg_price", "cost_basis"):
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
    take_profit_pct = float(params.get("take_profit_pct", 0.0110))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Mandatory not-enough-bars guard: need `slow_p` closes for the slow SMA.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]

    # ---- CLOSE LOGIC FIRST: the parent's exit must never be blocked. ----
    # Parent exit: SMA cross-down while long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Take-profit overlay: only fires when the parent would otherwise HOLD a
    # long (fast >= slow, still holding). Never blocks the parent's own close.
    if holding > 0:
        entry = _entry_price(pos)
        if entry is not None and last >= entry * (1.0 + take_profit_pct):
            gain = (last - entry) / entry
            return Action("close", symbol,
                          reason=(f"take-profit {gain*100:.2f}% >= "
                                  f"{take_profit_pct*100:.2f}% "
                                  f"(entry={entry:.2f}, last={last:.2f})"))

    # ---- ENTRY: unchanged from parent. ----
    if fast > slow and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")