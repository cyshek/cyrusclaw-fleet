"""SMA crossover on QQQ 1h bars with a trailing stop layered on the parent exit.

Thesis: the parent (`sma_crossover_qqq`) enters on a fast>slow SMA cross and
only exits when the cross reverts (fast<slow). That exit lags — by the time
the slow SMA rolls over, a winner has often given back a chunk of its runup.
A trailing stop tracks the highest price seen SINCE ENTRY (running max, stored
in position_state) and closes the position when price falls X% below that
running max. This lets winners keep running during a sustained trend (the
running max ratchets up with them) but cuts them the moment a real reversal
starts giving back, capturing more of the parent's upside than a fixed-from-
entry stop ever could.

Entry: fast SMA > slow SMA and flat (unchanged from parent).
Exit:  (a) trailing stop — price <= running_max * (1 - X), OR
       (b) parent's own close — fast SMA < slow SMA.
Either exit fires independently; the trailing stop NEVER blocks the parent's
close signal (both are checked before the entry gate, parent-close as a
fallback when the trail hasn't tripped).

Choice of X = 0.61%. Grounded in the parent trade profile: median max-runup
per trade is +1.17% and p25 runup is +0.52%. The directive requires X < median
runup so the trail fires on the give-back phase, not the run-up phase. 0.61%
sits just above the p25 runup (0.52%) and well below the median (1.17%): a
trade that has run to at least its median outcome can give back 0.61% from its
peak before we exit — small enough to protect realized gains on the typical
winner, large enough not to be shaken out by the ~0.61% (p75 drawdown) of
ordinary intra-trade noise. It is NOT a round number; it is the p75 drawdown
magnitude from this exact parent's empirical distribution.

running_max is reset to entry_price on every NEW entry (handled below by
detecting the flat->long transition: when we emit a buy we also recompute the
trail baseline from the current price on the next bar, and we re-seed if the
stored running_max is missing/stale relative to the live position).
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
    trail_pct = float(params.get("trail_pct", 0.0061))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    need = slow_p + 1
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ----- CLOSE LOGIC FIRST: never let the trailing-stop bookkeeping or any
    # gate trap an open position. Both the trailing stop and the parent's own
    # SMA-cross close are evaluated before the entry gate. -----
    if holding > 0:
        # Seed/advance the running max. On a fresh entry the running_max is
        # absent -> baseline it to entry_price (directive: reset to entry on
        # every new entry). Thereafter ratchet it up with new highs.
        entry_price = float(pos.get("entry_price", last) or last)
        running_max = pos.get("running_max")
        if running_max is None:
            running_max = entry_price
        running_max = float(running_max)
        if last > running_max:
            running_max = last
        # Persist the ratchet so the runner carries it to the next bar.
        pos["running_max"] = running_max
        position_state[symbol] = pos

        stop_level = running_max * (1.0 - trail_pct)
        if last <= stop_level:
            return Action(
                "close", symbol,
                reason=(f"trailing stop: {last:.2f} <= "
                        f"max {running_max:.2f} * (1-{trail_pct:.4f}) "
                        f"= {stop_level:.2f}"))

        # Parent's own close signal is still honored (trail did not trip).
        if fast < slow:
            return Action(
                "close", symbol,
                reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

        return Action(
            "hold", symbol,
            reason=(f"hold long (last={last:.2f}, max={running_max:.2f}, "
                    f"stop={stop_level:.2f}, fast={fast:.2f}, slow={slow:.2f})"))

    # ----- ENTRY GATE (flat only). -----
    if fast > slow:
        # New entry: reset the trail baseline to entry_price (== current price).
        pos = position_state.get(symbol) or {}
        pos["entry_price"] = last
        pos["running_max"] = last
        position_state[symbol] = pos
        return Action(
            "buy", symbol, notional_usd=notional,
            reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action(
        "hold", symbol,
        reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")