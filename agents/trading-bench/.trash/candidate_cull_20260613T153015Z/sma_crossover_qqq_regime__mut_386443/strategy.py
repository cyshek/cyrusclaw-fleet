"""SMA crossover on QQQ 1h bars, regime-gated, with a 3-bar entry-confirmation delay.

Mutation of `sma_crossover_qqq_regime`. The parent buys the instant the fast
SMA crosses above the slow SMA (while SPY is in an uptrend). Thesis: a chunk of
those bullish crosses are single-bar whipsaws — fast pokes above slow for one
bar then recrosses back down — and the parent eats a small loss on each. Because
SMAs are smooth and persistent, on a TRUE trend the `fast > slow` condition
holds for many consecutive bars, whereas a whipsaw flips back within a bar or
two. So we require the parent's bullish-cross condition to stay TRUE for N=3
consecutive bars before actually buying; any single false bar resets the counter
to 0. Exit is unchanged (bearish cross fast < slow) and is NEVER gated.

Entry signal: fast SMA > slow SMA held for 3 consecutive bars (regime permitting).
Exit signal:  fast SMA < slow SMA (parent's own close, fires immediately).
Edge: filters the cross-then-recross whipsaw cohort while entering true trends
only ~3 bars late.

Choice of N=3: parent's median holding period is 26.5 bars (p25 17.0), so a
3-bar confirmation is ~11% of the median hold — a small fraction, well below
even the p25 holding period, so the lag eats only a sliver of the move. Because
a sustained crossover stays true for many bars, the only entries this filters
are the short-lived whipsaw crosses; I expect this to drop roughly 15-25% of the
parent's raw entry signals (the cohort that recrosses within 1-2 bars), which
sits inside the 5-50% "doing something but not inert" band.

The confirmation counter lives in `market_state['strategy_state']`, which
survives across flat periods (unlike position_state, which is cleared on close),
so the count persists naturally between trades. The runner re-reads
strategy_state after decide() returns, so mutating it in place is sufficient.

Regime data: read from `market_state["regime"]` ({"spy_closes": [...]} or None).
When None (crypto / SPY unavailable) the gate is a no-op and behavior matches
the parent.
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

    state = market_state.setdefault("strategy_state", {})  # survives flat periods

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    entry_signal = fast > slow
    exit_signal = fast < slow

    # Close logic ALWAYS runs first — neither the regime gate nor the
    # confirmation counter may ever block an exit.
    if exit_signal and holding > 0:
        state["confirm_count"] = 0  # reset confirmation on exit
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Confirmation counter: count consecutive bars the bullish cross holds.
    # ANY false bar resets it to 0 immediately.
    if entry_signal:
        state["confirm_count"] = state.get("confirm_count", 0) + 1
    else:
        state["confirm_count"] = 0

    # Entry: bullish cross must have held n_confirm bars, regime must permit.
    if entry_signal and holding == 0 and state.get("confirm_count", 0) >= n_confirm:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(confirmed cross blocked)")
        state["confirm_count"] = 0  # consume the confirmation
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}>{slow_p} confirmed {n_confirm} bars "
                             f"(fast={fast:.2f}, slow={slow:.2f})")

    return Action("hold", symbol,
                  reason=f"no entry (fast={fast:.2f}, slow={slow:.2f}, "
                         f"confirm={state.get('confirm_count', 0)}/{n_confirm}, "
                         f"holding={holding})")