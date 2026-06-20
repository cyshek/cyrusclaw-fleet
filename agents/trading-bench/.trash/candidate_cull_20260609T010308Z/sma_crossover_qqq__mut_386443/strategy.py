"""SMA crossover on QQQ 1h bars with an entry-confirmation delay.

Thesis: the parent (`sma_crossover_qqq`) buys the instant fast SMA(10)
crosses above slow SMA(30) and closes when it crosses back. Many of those
crossovers are single-bar whipsaws — the fast line pokes above the slow line
for one bar and reverts, generating a false entry that the parent immediately
has to close at a small loss. This mutation requires the bullish crossover
(fast > slow) to hold for N CONSECUTIVE bars before buying. Any bar where the
condition is false resets the counter to 0, so only crossovers that persist
get traded; one-bar pokes are filtered out.

Entry signal: fast SMA(10) > slow SMA(30) for `entry_confirm_bars` consecutive
bars, then buy (and consume the confirmation).
Exit signal: parent's own close — fast SMA(10) < slow SMA(30) — fires
immediately and is NEVER gated by the confirmation counter. Already-open
positions are always closeable.
Edge: filtering 1-2 bar whipsaws should cut the cluster of tiny losing trades
the parent takes on noise crossovers, at the cost of entering N bars late on
genuine trends.

Choice of N = 3. The parent's holding-period distribution is p25=11 /
median=20 / p75=39 bars. N=3 is ~15% of the median hold — a small fraction,
so on a true trend the 3-bar lag costs only a modest slice of a 20-bar move,
and even the shortest typical trades (p25=11 bars) still have ~8 bars of
runway left after the delay. N=2 would barely move the needle (it only kills
strictly single-bar pokes); N>=4 starts eating meaningfully into the p25
holds. I expect N=3 to filter on the order of ~15-30% of the parent's
entries (the whipsaw tail of crossovers that don't survive 3 bars) — inside
the 5-50% "not inert" band the directive calls for.

State: the consecutive-bar counter lives in `market_state['strategy_state']`
(survives flat periods between trades), NOT `position_state` (cleared on
close). Mutating that dict in place is sufficient; the runner re-reads it
after decide() returns.
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
    n_confirm = int(params.get("entry_confirm_bars", 3))
    notional = float(params.get("notional_usd", 1000.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Not-enough-bars guard: slow SMA needs `slow_p` closes.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    state = market_state.get("strategy_state")
    if state is None:
        state = {}
        market_state["strategy_state"] = state

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    entry_signal = fast > slow
    exit_signal = fast < slow

    # Exits ALWAYS run first and are never gated by the confirmation counter.
    if holding > 0 and exit_signal:
        state["confirm_count"] = 0  # reset on exit too
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Confirmation counter — only meaningful when flat.
    if entry_signal:
        state["confirm_count"] = int(state.get("confirm_count", 0)) + 1
    else:
        state["confirm_count"] = 0  # ANY false bar resets immediately

    if holding == 0 and int(state.get("confirm_count", 0)) >= n_confirm:
        state["confirm_count"] = 0  # consume the confirmation
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}>{slow_p} held {n_confirm} bars "
                             f"({fast:.2f}>{slow:.2f})")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"confirm={state.get('confirm_count', 0)}/{n_confirm}, "
                         f"holding={holding})")