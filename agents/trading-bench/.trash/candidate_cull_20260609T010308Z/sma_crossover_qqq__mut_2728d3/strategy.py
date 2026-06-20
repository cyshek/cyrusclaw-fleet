"""SMA crossover on QQQ 1h bars with a POST-LOSS COOLDOWN entry filter.

Parent: `sma_crossover_qqq`. Entry signal = fast SMA(10) crosses ABOVE
slow SMA(30); exit signal = fast SMA(10) crosses BELOW slow SMA(30). The
mutation adds one gate on ENTRIES ONLY: when we close a trade whose exit
price is below the parent's average entry price (a realized loss, fees
ignored as a good-enough proxy), we arm a cooldown of `loss_cooldown_bars`
bars and refuse ANY new entry until it decays to zero. Exits are never
gated — an open position always closes on the parent's normal cross-down.

Thesis: a fresh realized loss is weak-but-nonzero evidence the local regime
has turned hostile to a trend-follower (vol spike, whipsaw, reversal). The
SMA cross is slow to re-confirm and tends to re-fire prematurely into the
same chop that just stopped us out; sitting out a handful of bars lets the
worst-case path resolve before we risk capital on the next cross-up.

Chosen N = 6 bars. The parent's holding distribution is p25=11 / median=20 /
p75=39 bars at 1Hour, so 6 ≈ 0.30× median holding — squarely inside the
directive's sane 0.25–1.0× band, toward the short end. Rationale for the
short end: this is a slow MA-cross system, not a fast mean-reverter; a
6-bar pause covers the typical re-test window of a freshly broken cross
without idling through a third of an average trade's worth of opportunity.

Expected firing frequency: the parent's per-trade max-drawdown median is
-1.14% against a per-trade max-runup median of +1.17% — a roughly balanced
excursion profile, so realized losses (exit<entry) should land in the
moderate ~40–50% range of the 68 sampled trades, NOT the <10% (inert) or
>60% (smothering) extremes. So the cooldown will engage on a meaningful
minority of closes and genuinely change behavior without dominating it —
this directive is a reasonable fit for this parent.
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


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 1000.0))
    cooldown_n = int(params.get("loss_cooldown_bars", 6))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Not-enough-bars guard: need slow_p closes for the slow SMA.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = float(market_state.get("last_price", cs[-1]))
    state = market_state.get("strategy_state")
    if state is None:
        state = {}

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0) or 0.0)

    exit_signal = fast < slow
    entry_signal = fast > slow

    # 1. Exits ALWAYS run first and are NEVER gated by the cooldown.
    if holding > 0 and exit_signal:
        # Arm the cooldown if this close realizes a loss. Read avg_entry_price
        # NOW, before the close clears position_state[symbol] next bar.
        entry_px = float(pos.get("avg_entry_price", 0.0) or 0.0)
        if entry_px > 0 and last < entry_px:
            state["cooldown_remaining"] = cooldown_n
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2. Decrement the cooldown once per bar while flat (exits above already
    #    returned). Capture the pre-decrement value to gate entries on.
    cd = int(state.get("cooldown_remaining", 0) or 0)
    if cd > 0:
        state["cooldown_remaining"] = cd - 1

    # 3. Entry gate: only when flat, signal up, AND no cooldown was active
    #    this bar (pre-decrement cd == 0 so a fresh N blocks the NEXT N
    #    entry opportunities, not N-1).
    if holding == 0 and entry_signal:
        if cd > 0:
            return Action("hold", symbol,
                          reason=f"post-loss cooldown ({cd} bars left), "
                                 f"entry blocked")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(no cooldown)")

    return Action("hold", symbol,
                  reason=(f"cooldown {cd}" if cd > 0
                          else f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                               f"holding={holding})"))