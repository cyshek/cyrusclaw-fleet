"""Donchian breakout on XLK 1h bars (SPY-regime gated) + N-bar entry confirmation.

Variant of `breakout_xlk_regime`. Same long-only Donchian breakout (close >
prior `lookback`-bar high) gated by a SPY-above-50d-SMA regime filter, but
with an ENTRY-CONFIRMATION DELAY: the breakout signal must hold TRUE for
`entry_confirm_bars` consecutive bars before we actually buy. Any single bar
where the signal is false resets the counter to 0. Thesis: a chunk of the
parent's losers are one-bar breakouts that poke above the prior high and
immediately reverse next bar (whipsaws); making the breakout prove itself for
2 bars filters those single-bar spikes out, at the cost of entering 1 bar
later on true trends.

Entry signal: close > prior `lookback`-bar high for `entry_confirm_bars`
CONSECUTIVE bars (counter in `market_state['strategy_state']`, which survives
flat periods), AND SPY in an uptrend (regime gate, entries only).
Exit signal: close < prior `lookback`-bar low (parent's own close, NEVER
gated — already-open positions are always closeable, and the confirm counter
never blocks an exit).
Edge: removes the most fleeting false-positive entries without materially
lagging real moves.

Choice of N: entry_confirm_bars = 2. The parent's median holding period is
34 bars (p25=16, p75=43), so N=2 is ~6% of the median hold — a small fraction,
so the 1-bar entry lag eats only a sliver of the typical move (parent median
runup +2.60%). N is deliberately at the low end of the 2-5 range because the
parent's holds aren't long and I don't want lag to erode the +2.60% median
runup. For a Donchian breakout, requiring 2 consecutive closes above the prior
high is expected to filter out roughly 15-35% of the parent's raw entries —
specifically the single-bar pokes that revert the next bar — which sits inside
the 5-50% "actually does something but isn't inert" band. N=3+ (>=9% of median
hold) was rejected as starting to lag the move for a holding distribution this
short.
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
    n_confirm = int(params.get("entry_confirm_bars", 2))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # strategy_state survives flat periods, so the consecutive-bar counter
    # persists naturally across trades. Runner re-reads it after decide().
    state = market_state.get("strategy_state")
    if state is None:
        state = {}

    # ---- Close logic ALWAYS runs first; NEVER gated by regime or counter. ----
    if lo is not None and last < lo and holding > 0:
        state["confirm_count"] = 0  # reset on exit
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # ---- Breakout signal (parent's own entry condition). ----
    entry_signal = hi is not None and last > hi

    # Consecutive-bar confirmation counter (only meaningful while flat).
    if entry_signal:
        state["confirm_count"] = state.get("confirm_count", 0) + 1
    else:
        state["confirm_count"] = 0  # ANY false bar resets immediately

    # ---- Entry gate: regime filter + N-bar confirmation, entries only. ----
    if holding == 0 and state.get("confirm_count", 0) >= n_confirm:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            # Blocked by regime: keep the counter (signal is still live) so a
            # later in-regime bar can act on a still-confirmed breakout.
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(confirmed breakout blocked)")
        state["confirm_count"] = 0  # consume the confirmation
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"breakout confirmed {n_confirm} bars "
                             f"(last {last:.2f} > {lookback}-bar high {hi:.2f})")

    return Action("hold", symbol,
                  reason=f"no confirmed breakout (last={last:.2f}, hi={hi}, "
                         f"lo={lo}, holding={holding}, "
                         f"count={state.get('confirm_count', 0)}/{n_confirm})")