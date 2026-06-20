"""Donchian breakout on XLK 1h bars with N-bar entry confirmation delay.

Variant of `breakout_xlk` that adds an entry-confirmation filter: the
breakout signal (close > prior `lookback`-bar high) must hold TRUE for
`entry_confirm_bars` consecutive bars before we actually place the buy.
Any false bar resets the counter to 0 immediately. Hypothesis: many
one-bar Donchian "breakouts" are spikes that close back inside the channel
the next bar; requiring persistence filters those head-fakes at the cost
of entering N bars late on real trends.

Chosen N = 2. Justification: parent's median holding is 34 bars (p25=14),
so a 2-bar lag is ~6% of the median hold and ~14% of the p25 hold — small
enough to preserve most of the post-breakout move. With Donchian breakouts
on 1h bars, a meaningful fraction of bars that pierce the high close back
inside on the next bar; I expect this filter to eliminate roughly 20-35%
of historical entries (the single-bar pokes), well inside the "not inert"
band of 5-50%. N=3+ would push the lag past 10% of p25 hold and risk
missing the faster trends entirely.

Exits (close < prior `lookback`-bar low) ALWAYS fire and are never gated
by the confirmation counter — already-open positions must remain closeable.
The confirm counter lives in `market_state['strategy_state']` so it
persists across flat periods between trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest


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
    notional = float(params.get("notional_usd", 100.0))
    n_confirm = int(params.get("entry_confirm_bars", 2))

    state = market_state.get("strategy_state")
    if state is None:
        # Defensive: runner should always provide this, but don't crash if not.
        state = {}
        market_state["strategy_state"] = state

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Exits ALWAYS run first — never gated by the confirmation counter.
    if lo is not None and last < lo and holding > 0:
        state["confirm_count"] = 0  # reset on exit too
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Update confirmation counter based on current bar's entry signal.
    entry_signal = hi is not None and last > hi
    if entry_signal:
        state["confirm_count"] = int(state.get("confirm_count", 0)) + 1
    else:
        state["confirm_count"] = 0  # ANY false bar resets

    cc = int(state.get("confirm_count", 0))

    if holding == 0 and cc >= n_confirm:
        state["confirm_count"] = 0  # consume the confirmation
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"breakout confirmed {n_confirm} bars "
                             f"(last={last:.2f}, hi={hi:.2f})")

    return Action("hold", symbol,
                  reason=f"no entry (last={last:.2f}, hi={hi}, lo={lo}, "
                         f"confirm={cc}/{n_confirm}, holding={holding})")