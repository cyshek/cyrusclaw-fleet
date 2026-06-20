"""SMA crossover on QQQ 1h bars (SPY-regime gated) + a 3-bar entry-confirmation delay.

Mutation of `sma_crossover_qqq_regime`. The parent enters the instant
fast SMA crosses above slow SMA (`fast > slow`). Many of those crossovers
are single-bar noise: the fast line pokes above the slow line for one bar
and flips back, producing a whipsaw entry that the next-bar bearish cross
immediately closes for a small loss. This variant requires the bullish-cross
condition (`fast > slow`) to hold TRUE for `entry_confirm_bars` CONSECUTIVE
bars before buying; any single bar where the condition is false resets the
counter to 0. The consecutive count lives in `market_state['strategy_state']`
so it survives flat periods between trades.

Entry signal: `fast > slow` true for N=3 consecutive bars, regime permitting.
Exit signal: parent's own bearish cross `fast < slow` (NEVER gated by the
counter or the regime — already-open positions are always closeable).
Edge thesis: filtering one- and two-bar crossover spikes should drop the
worst of the immediate-reversal whipsaws (the parent has 43% of trades touch
>=1% drawdown, consistent with a chunk of bad early entries) while only
entering 3 bars late on real trends.

Choice of N=3: the parent's holding distribution is p25=17.0, median=26.5,
p75=48.8 bars. N=3 is ~11% of the median hold and ~18% of the p25 hold — a
small fraction, so the 3-bar lag eats only a sliver of a typical move rather
than a large chunk. N=3 (vs N=2) also rejects the two-bar pokes, not just the
one-bar ones. Expected filtering: SMA-crossover signals that survive >=3
consecutive bars are a meaningful minority of all crossover events — I expect
this to suppress roughly 15-35% of the parent's entries (the flips that don't
persist 3 bars), which sits inside the directive's healthy 5%-50% band: low
enough to stay active, high enough to actually cut whipsaws.
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


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    n_confirm = int(params.get("entry_confirm_bars", 3))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # strategy_state survives flats so the consecutive-bar counter persists
    # naturally across trades. Runner re-reads it after decide() returns, so
    # mutating in place is sufficient.
    state = market_state.get("strategy_state")
    if state is None:
        state = {}
        market_state["strategy_state"] = state

    if fast is None or slow is None:
        # Not enough bars to evaluate the cross; do not advance the counter.
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    bull_cross = fast > slow
    bear_cross = fast < slow

    # Close logic ALWAYS runs first — neither the regime gate nor the
    # confirmation counter may ever trap us long.
    if bear_cross and holding > 0:
        state["confirm_count"] = 0  # reset on exit too
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Advance / reset the consecutive-bar confirmation counter on EVERY bar.
    # Any bar where the bullish-cross condition is false resets to 0.
    if bull_cross:
        state["confirm_count"] = int(state.get("confirm_count", 0)) + 1
    else:
        state["confirm_count"] = 0

    # Entry: requires N consecutive confirmed bars AND a permissive regime.
    if bull_cross and holding == 0 and int(state.get("confirm_count", 0)) >= n_confirm:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            # Regime blocks the entry, but keep the confirmation intact so a
            # still-valid signal can fire the moment the regime turns up.
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(confirmed cross blocked)")
        state["confirm_count"] = 0  # consume the confirmation on a real buy
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"confirmed {n_confirm} bars")

    return Action("hold", symbol,
                  reason=f"no entry (fast={fast:.2f}, slow={slow:.2f}, "
                         f"confirm={int(state.get('confirm_count', 0))}/{n_confirm}, "
                         f"holding={holding})")