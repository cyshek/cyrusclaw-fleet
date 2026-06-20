"""Donchian breakout on XLK 1h bars (regime-gated) with a take-profit overlay.

Parent (`breakout_xlk_regime`): long Donchian breakout, enters only when SPY
is above its 50d SMA, exits when price breaks the N-bar low. Thesis of THIS
mutation: the parent gives back gains on its winners by holding all the way
back to the Donchian low before exiting. Its trades touched a median max
runup of +2.60% but the median trade still bled out to a -1.27% max drawdown
before closing — i.e. unrealized profit is routinely surrendered.

Fix: add a take-profit overlay. When price has risen more than `take_profit_pct`
above the recorded entry price AND the parent would otherwise HOLD, close to
lock the gain. X is set to 2.30% — just below the parent's median per-trade
max runup (+2.60%, p25 +0.71% / p75 +4.07%), so it would have fired on more
than half of historical winners that reached that level while staying well
inside the observed runup distribution (not the inert >p75 region, not a
trivial sub-p25 grab). It is intentionally NOT a round number; it is anchored
to the empirical median runup.

Ordering contract (critical): the parent's close signal (price < N-bar low)
is evaluated FIRST and is always honored — the take-profit must never block an
exit, and the regime gate must never trap us long. The take-profit fires ONLY
in the branch where the parent strategy would have returned "hold" while a
position is open. Entry logic (with the regime gate) is unchanged and runs last.

Entry price is read from `position_state[symbol]["avg_entry_price"]` (falling
back to "entry_price"); if neither is present we cannot evaluate the overlay
and simply fall through to the parent's hold, so the overlay degrades safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _entry_price(pos: dict) -> Optional[float]:
    """Best-effort entry price from a position dict; None if unavailable."""
    if not pos:
        return None
    for key in ("avg_entry_price", "entry_price", "avg_price"):
        v = pos.get(key)
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv > 0:
                return fv
    return None


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    take_profit_pct = float(params.get("take_profit_pct", 0.023))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1) Parent close logic ALWAYS runs first. Neither the regime gate nor the
    #    take-profit overlay may ever trap us long or block this exit.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) Take-profit overlay. Fires ONLY when a position is open and the parent
    #    would otherwise HOLD (its close above did not trigger). Locks gains the
    #    parent tends to give back. Never blocks the parent's own exit (above).
    if holding > 0:
        ep = _entry_price(pos)
        if ep is not None and last >= ep * (1.0 + take_profit_pct):
            gain = (last - ep) / ep
            return Action("close", symbol,
                          reason=f"take-profit {gain*100:.2f}% >= "
                                 f"{take_profit_pct*100:.2f}% (entry {ep:.2f}, "
                                 f"last {last:.2f})")

    # 3) Entry gate: respect regime filter only when entering new positions.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")