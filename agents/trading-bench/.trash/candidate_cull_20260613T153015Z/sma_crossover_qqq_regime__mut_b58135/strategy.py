"""SMA crossover on QQQ 1h bars, AND-confirmed by a short breakout, SPY-regime gated.

Variant of `sma_crossover_qqq_regime`. The parent enters on a bullish SMA
cross (fast > slow) whenever SPY is in an uptrend. Its empirical weakness:
~43% of its 42 historical trades touched >=1% drawdown while only ~half
reached the +1.34% median runup, i.e. a meaningful slice of crossovers fire
on limp, low-momentum drift that crosses the moving averages on noise and
then reverses before going anywhere. That is the failure mode this mutant
tries to ELIMINATE.

Combination: AND (a filter, deliberately). Entry now requires BOTH the
parent's bullish SMA cross AND a confirming breakout — the last close must
exceed the highest close of the prior `breakout_lookback` bars (12, chosen
below the p25 holding period of 17 bars so the breakout is fresh momentum at
entry, not a stale level). AND is chosen over OR on purpose: the goal here is
to KILL the no-momentum whipsaw entries, not to add more trades. Requiring a
breakout means the cross must coincide with price actually making new local
highs — eliminating the dead-drift crossovers.

Exit signal is UNCHANGED from the parent and fires on the bearish SMA cross
(fast < slow) alone — the breakout confirmation gates ENTRIES ONLY and never
makes the position harder to close than to open. Close logic runs before any
entry gate, so neither the regime filter nor the breakout filter can ever
trap us long.

Regime data: read from `market_state["regime"]` (set by runner/backtester to
{"spy_closes": [...], "spy_last": float}, or None when unavailable, e.g.
crypto). When None, the regime gate is skipped and behavior falls through to
the SMA-AND-breakout logic.

Edge thesis: the parent's small positive expectancy is diluted by zero/low-edge
whipsaw trades; demanding a coincident breakout should raise per-trade quality
(fewer, cleaner entries) without ever impairing the exit.
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
    breakout_lookback = int(params.get("breakout_lookback", 12))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Need enough bars for the slowest of: slow SMA, or breakout lookback + 1
    # (breakout compares last close to the highest of the PRIOR lookback bars).
    need = max(slow_p, breakout_lookback + 1)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    prior_hi = highest(cs[:-1], breakout_lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — exits depend on the bearish SMA cross
    # ONLY, identical to the parent. No filter may block this.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry gate: require the bullish SMA cross AND a fresh breakout, AND the
    # SPY regime (when known) to be an uptrend.
    breakout = prior_hi is not None and last > prior_hi
    if fast > slow and breakout and holding == 0:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(SMA+breakout entry blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f}>SMA{slow_p}={slow:.2f} AND "
                             f"close {last:.2f} > {breakout_lookback}-bar high {prior_hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"breakout={breakout}, holding={holding})")