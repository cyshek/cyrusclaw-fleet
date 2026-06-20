"""SMA(10/30) crossover on QQQ 1h bars with a POST-LOSS COOLDOWN entry gate.

Thesis: identical entry/exit logic to the parent `sma_crossover_qqq` (long when
fast SMA > slow SMA, flat when fast < slow), but after any trade that closes at
a realized loss (last_price < avg_entry_price at the moment of close) we refuse
ALL new entries for the next `loss_cooldown_bars` bars. A fresh realized loss is
weak-but-nonzero evidence that the local regime just turned hostile to a trend-
following crossover (vol spike, whipsaw, reversal); sitting out a few bars lets
the worst of that path resolve before we re-arm. Exits are NEVER gated — an open
position always closes on the parent's fast<slow signal, and the runner's safety
backstops still short-circuit before this code runs.

Entry signal: fast SMA(10) > slow SMA(30) AND flat AND cooldown_remaining == 0.
Exit signal:  fast SMA(10) < slow SMA(30) while holding (always honored).
Edge (if any): the parent's losing trades cluster in choppy/reversal regimes; a
brief loss-triggered pause should skip the immediate re-entry that would otherwise
get chopped again, trimming the left tail without touching the winning runs.

Chosen N = 7 bars. Parent median holding is 20 bars (p25=11, p75=39), so 7 bars is
~0.35x median holding and ~0.64x the p25 — inside the suggested 0.25-1.0x band,
comfortably above "inert" yet well short of eating a full typical trade's worth of
opportunity. Expected firing frequency: the parent touched >=1% per-trade drawdown
on 57% of trades, so a meaningful share of closes are at/near a loss and the
cooldown will engage on a substantial minority-to-majority of trades — frequent
enough to actually matter, not so universal that it smothers the strategy (it would
need a >90% or <10% loss rate to be degenerate, and 57% is squarely in the useful
middle). If anything the risk is mild over-firing, not inertness; if walk-forward
shows it trimming winners as much as losers, N should come down toward 4-5.
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
    cooldown_n = int(params.get("loss_cooldown_bars", 7))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # MANDATORY not-enough-bars guard: need slow_p closes to form the slow SMA.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = float(market_state.get("last_price", cs[-1]))
    state = market_state.get("strategy_state")
    if state is None:
        # Defensive: if the runner didn't supply a state dict, fall back to a
        # local one (cooldown won't persist, but decide() still behaves safely).
        state = {}

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0) or 0.0)

    entry_signal = fast > slow
    exit_signal = fast < slow

    # 1. EXIT FIRST — never gated by the cooldown. Arm the cooldown on a
    #    realized loss BEFORE returning, while avg_entry_price is still visible
    #    (position_state[symbol] is cleared on the next bar after close).
    if holding > 0 and exit_signal:
        entry_px = float(pos.get("avg_entry_price", 0.0) or 0.0)
        if entry_px > 0 and last < entry_px:
            state["cooldown_remaining"] = cooldown_n
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2. Decrement the cooldown once per (flat) bar. Floor at 0; never negative.
    cd = int(state.get("cooldown_remaining", 0) or 0)
    if cd > 0:
        state["cooldown_remaining"] = cd - 1

    # 3. ENTRY — gated by the PRE-decrement cooldown value so a fresh
    #    cooldown_remaining=N blocks the next N entry opportunities.
    if holding == 0 and entry_signal and cd == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(no cooldown)")

    if cd > 0:
        return Action("hold", symbol,
                      reason=f"cooldown {cd} (entry blocked after loss)")
    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"holding={holding})")