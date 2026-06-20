"""SMA crossover on QQQ 1h bars, regime-gated AND confirmed by a recent breakout.

Variant of `sma_crossover_qqq_regime`. The parent enters on a bullish SMA
crossover (fast > slow) when SPY is above its regime SMA. This mutation adds
a SECOND entry condition with AND: the bullish cross must ALSO coincide with
the close being at a fresh `breakout_lookback`-bar high.

Why AND (a filter, not more entries): the parent's trade profile shows 43%
of trades touched >=1% drawdown and a median per-trade max drawdown of
-0.76%. The failure mode I am targeting is the "late / mid-pullback cross":
the fast SMA can drift above the slow SMA while price has already rolled over
off a local high, so the cross fires into immediate weakness and bleeds that
-0.76%+ drawdown before either recovering weakly or hitting the bearish-cross
exit. Requiring the close to simultaneously print a new short-horizon high
demands that momentum is actually present AT the moment of entry, eliminating
crossovers that trigger while price is sagging. We accept fewer entries in
exchange for skipping that specific loser class.

Entry: fast SMA > slow SMA AND close == highest close over the last
`breakout_lookback` bars (inclusive), AND (when known) SPY above its regime
SMA. Exit: bearish cross (fast < slow) — UNCHANGED from the parent. The
breakout/regime filters gate NEW ENTRIES ONLY; an open position is always
closeable on the bearish cross so a filter can never trap us long. Exit is
strictly easier than entry (one condition vs three).

Regime data: read from `market_state["regime"]`
({"spy_closes": [...], "spy_last": float} or None). When None the regime gate
is skipped and only the cross+breakout conditions apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, highest, regime_uptrend


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
    breakout_lookback = int(params.get("breakout_lookback", 10))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Need enough bars for the slowest indicator AND the breakout window.
    need = max(slow_p, breakout_lookback)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — filters must never trap us long.
    # Exit is the parent's bearish cross, unchanged: strictly one condition.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry: require BOTH the bullish cross AND a fresh breakout high.
    last = cs[-1]
    hi = highest(cs, breakout_lookback)  # inclusive of last bar
    bullish_cross = fast > slow
    breakout = hi is not None and last >= hi

    if bullish_cross and breakout and holding == 0:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(cross+breakout blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f}>SMA{slow_p}={slow:.2f} "
                             f"AND {breakout_lookback}b-high breakout "
                             f"({last:.2f}>={hi:.2f})")

    return Action("hold", symbol,
                  reason=f"no entry (cross={bullish_cross}, breakout={breakout}, "
                         f"holding={holding})")