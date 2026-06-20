"""Donchian breakout on XLK 1h bars with a POST-LOSS COOLDOWN gate.

Variant of `breakout_xlk`. Entry/exit logic is the parent's unchanged
Donchian channel: go long when the last close prints above the prior
`lookback`-bar high; close when it prints below the prior `lookback`-bar
low. The mutation adds one rule: when a position is closed at a realized
loss (exit price < average entry price), refuse to take ANY new entry for
the next `loss_cooldown_bars` bars. Already-open positions are NEVER gated
by the cooldown — the parent's close signal always fires.

Thesis (edge): a fresh realized loss is weak but non-zero evidence that the
local regime has turned hostile to a long-only breakout — a volatility
spike, a failed-breakout chop pocket, or a trend reversal. Re-entering
immediately after a stop-out tends to walk straight back into that same
hostile path. Sitting out a handful of bars lets the worst-case continuation
play through before the strategy is allowed to commit capital again.

Chosen N = 10 bars. Grounding: the parent's holding-period distribution is
p25=14, median=34, p75=43 bars (1Hour). The sane cooldown band the directive
specifies is ~0.25–1.0x median = ~8–34 bars. N=10 sits at the LOW end of
that band (~0.3x median): long enough to step over a typical short reversal
leg, short enough that it does not routinely eat the next genuine breakout
(median time between trades is well above 10 bars given median holding alone).

Expected fire rate: the cooldown arms only on exits where last_price <
avg_entry_price. This parent exits on a downside Donchian break, so a
non-trivial share of exits are below entry. The per-trade max-drawdown
profile (64% of trades touch >=1% drawdown; median trade drawdown -1.41%)
implies a meaningful minority-to-majority of closes realize a loss at the
exit bar — I expect the cooldown to engage on roughly 40-60% of exits. That
puts it in the "active but not smothering" zone: frequent enough that the
directive is NOT inert, infrequent enough that it does not flat-line the
strategy. Honest caveat: if realized-loss exits run toward the high end of
that range, the cooldown will be active a large fraction of the time and
could trim total trade count noticeably — the walk-forward fitness gate, not
this docstring, is the arbiter of whether that trade-off pays.

Cooldown state lives in `market_state['strategy_state']` (survives flat
periods), NOT in `position_state` (cleared on close). The loss is detected
on the close bar by reading `position_state[symbol]['avg_entry_price']`
BEFORE returning the close action, while it is still populated.
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
    cooldown_n = int(params.get("loss_cooldown_bars", 10))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    # strategy_state survives across flat periods; the runner re-reads it
    # after decide() returns, so in-place mutation is sufficient.
    state = market_state.get("strategy_state")
    if state is None:
        state = {}

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0) or 0.0)

    # 1. EXITS ALWAYS RUN FIRST and are NEVER gated by the cooldown.
    #    Detect a realized loss BEFORE the close clears position_state, and
    #    arm the cooldown in the same call that emits the close.
    if lo is not None and last < lo and holding > 0:
        entry_px = float(pos.get("avg_entry_price", 0.0) or 0.0)
        if entry_px > 0 and last < entry_px:
            state["cooldown_remaining"] = cooldown_n
            return Action("close", symbol,
                          reason=f"close {last:.2f} < {lookback}-bar low "
                                 f"{lo:.2f} (loss; cooldown armed {cooldown_n})")
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2. Decrement the cooldown once per bar (only reached when not exiting).
    #    Use the PRE-decrement value to gate entries below so a fresh
    #    cooldown_remaining=N blocks the next N entry opportunities, not N-1.
    cd = int(state.get("cooldown_remaining", 0) or 0)
    if cd > 0:
        state["cooldown_remaining"] = cd - 1

    # 3. ENTRIES: parent breakout signal, gated by the cooldown.
    if hi is not None and last > hi and holding == 0:
        if cd > 0:
            return Action("hold", symbol,
                          reason=f"breakout blocked: post-loss cooldown {cd}")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=(f"cooldown {cd}" if cd > 0
                          else f"no breakout (last={last:.2f}, hi={hi}, "
                               f"lo={lo}, holding={holding})"))