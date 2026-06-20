"""Donchian breakout on XLK 1h bars (SPY-regime-gated) with a TIGHT hard stop.

Same core as `breakout_xlk_regime`: go long on a `lookback`-bar Donchian
breakout, but only open when SPY trades above its regime SMA; the Donchian
low is the primary exit. This mutation adds a hard intra-trade stop-loss at
`stop_loss_pct` below the recorded entry price.

Why a stop, and why this value: the parent's only exit is "close below the
20-bar Donchian low", which early in a trade can sit ~1.5-2% under entry, so
a fast adverse reversal can bleed well past 1% before the Donchian exit ever
triggers. The parent's empirical per-trade max-drawdown distribution is
median -1.27%, p75(shallower) -0.52%, and 52% of trades touched >=1% drawdown.
I set the stop at 0.80% — between the p75 shallow tail (0.52%) and the median
(1.27%), so it sits at/below the median adverse excursion and therefore would
have fired on MORE than half of historical trades, while staying inside the
distribution (a stop deeper than the p25 -1.66% would be inert). The stop is
meant to catch the sharp single-bar/2-bar reversal-from-breakout that the
slow Donchian-low exit lets run; it intentionally accepts being shaken out of
some eventual winners (median runup is +2.60%) in exchange for capping the
left tail.

CRITICAL ordering: the parent's own close signals (Donchian-low exit AND this
stop) run BEFORE the regime entry gate, so no filter can ever trap an open
position. Entry price is tracked via `position_state[symbol]["avg_entry_price"]`
(falling back to last price the first bar we see a position, so the stop is
never silently disabled). Regime data read from `market_state["regime"]`;
None => gate skipped (behaves like the ungated parent).
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


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    stop_loss_pct = float(params.get("stop_loss_pct", 0.008))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # --- CLOSE LOGIC ALWAYS RUNS FIRST: no gate may ever trap an open long. ---
    if holding > 0:
        # Parent's primary exit: break of the Donchian low.
        if lo is not None and last < lo:
            return Action("close", symbol,
                          reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")
        # Hard stop-loss: entry price tracked in position_state; fall back to
        # last price so the stop is never silently disabled on the first bar.
        entry = None
        if pos is not None:
            entry = pos.get("avg_entry_price", pos.get("entry_price"))
        entry_price = float(entry) if entry not in (None, 0) else last
        stop_price = entry_price * (1.0 - stop_loss_pct)
        if last <= stop_price:
            return Action("close", symbol,
                          reason=f"stop-loss {last:.2f} <= {stop_price:.2f} "
                                 f"({stop_loss_pct*100:.2f}% below entry {entry_price:.2f})")

    # --- ENTRY GATE: regime filter applies to NEW positions only. ---
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