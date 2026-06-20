"""SMA crossover on QQQ 1h bars (SPY-regime gated) + a HARD time-stop.

Mutation of `sma_crossover_qqq_regime`: identical entry/exit logic, but a
position is force-closed once it has been held for N bars, regardless of the
parent's bearish-cross exit. Thesis: a trade that has not resolved within its
typical holding window is dead money — it ties up capital while the parent
waits for a fast<slow cross that may be far away. Cutting the slow tail frees
capital and caps the drift of trades that have gone sideways.

Entry signal (unchanged): SMA(fast) crosses above SMA(slow) AND SPY is above
its regime-period SMA (regime gate blocks NEW ENTRIES ONLY).
Exit signal: parent's bearish cross (fast < slow) OR the new time-stop, which
fires after `max_hold_bars` bars in the position. The time-stop is a HARD exit
modeled exactly like a stop-loss: it is evaluated in the close block, BEFORE
the entry gate, so a filter can never trap us long.

Choice of N (max_hold_bars = 49): grounded in the parent trade profile's
holding distribution at 1Hour — p25=17.0, median=26.5, p75=48.8 bars. The
directive targets the p75 (~the slowest 25% of trades), so N = ceil(48.8) = 49.
Trades that have not been closed by the parent's own signal within 49 bars are
the long tail; forcing them out leaves the median (26.5-bar) and faster trades
fully intact while only truncating the slow quartile.

Profitable vs unprofitable bucket: in this parent, max-runup is front-loaded
(median runup +1.34% touched by 64% of trades) while max-drawdown is shallow
(median -0.76%). A trade still open at bar 49 has typically already seen its
runup and is now grinding sideways/down without triggering the bearish cross —
i.e. the slow tail skews toward the UNPROFITABLE / break-even bucket (longer
holding_bars correlate with lower realized pnl as the early runup decays).
So the time-stop should mostly evict dead-money laggards rather than cut
winners short; that is the edge it is intended to harvest.

Regime data: read from `market_state["regime"]` (set by runner/backtester to
{"spy_closes": [...], "spy_last": float}, or None when unavailable). When None,
behavior falls through to the parent (gate is a no-op).
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
    # Time-stop horizon. p75 holding-bars for this parent at 1Hour is 48.8,
    # so 49 bars forces out the slowest ~25% of trades. Not a round number —
    # it is ceil(p75) from the parent profile.
    max_hold_bars = int(params.get("max_hold_bars", 49))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Current bar index (monotonic, runner/backtester supplied). Fall back to
    # the number of bars seen so far when an explicit index is absent.
    bar_index = market_state.get("bar_index")
    if bar_index is None:
        bar_index = len(cs) - 1
    bar_index = int(bar_index)

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # ----- CLOSE LOGIC ALWAYS RUNS FIRST (no filter may block an exit) -----

    if holding > 0:
        # Track the bar at which we entered. position_state is the durable
        # per-symbol dict; the runner persists keys we write here across bars.
        entry_bar = pos.get("entry_bar") if pos else None
        if entry_bar is None:
            # First time we observe this open position without a recorded
            # entry bar: stamp it now so the time-stop has an anchor. We do
            # NOT force-close on this bar (we don't know the true age yet).
            if pos is not None:
                pos["entry_bar"] = bar_index
        else:
            held = bar_index - int(entry_bar)
            if held >= max_hold_bars:
                return Action(
                    "close", symbol,
                    reason=f"time-stop: held {held} bars >= "
                           f"max_hold_bars {max_hold_bars}")

        # Parent's bearish-cross exit (still honored, fires after time-stop in
        # priority but in the same close-before-entry block).
        if fast < slow:
            return Action("close", symbol,
                          reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # ----- ENTRY GATE (regime filter applies to NEW ENTRIES ONLY) -----

    regime = market_state.get("regime")
    if fast > slow and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(entry_bar={bar_index})")
    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")