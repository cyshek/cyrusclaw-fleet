"""Donchian breakout on XLK 1h bars, combined (AND) with an SMA trend filter.

Entry signal: BOTH conditions must hold simultaneously:
  1. Close breaks above the prior `lookback`-bar Donchian high (parent signal).
  2. Fast SMA > Slow SMA on the same series (local trend confirmation).

The AND combination is deliberate: pure Donchian breakouts fire in chop and
get whipsawed; requiring the local SMA structure to already be in an uptrend
filters out counter-trend breakout attempts and false breaks from range-bound
regimes. Hypothesis: fewer trades, higher hit rate, better expectancy.

Exit signal: fires on EITHER parent exit (close < `lookback`-bar low). Per
the directive, exits are never harder than entries — we do NOT require the
SMA filter to flip before closing. The SMA filter only gates NEW entries.

Regime: not used here; the SMA-trend filter is itself a local trend gate,
and stacking another global regime would over-restrict an already-narrow
signal. Behavior on crypto / missing SPY data is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, sma


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
    fast_period = int(params.get("fast_period", 10))
    slow_period = int(params.get("slow_period", 30))
    notional = float(params.get("notional_usd", 100.0))

    cs = closes(market_state.get("bars") or [])
    need = max(lookback + 1, slow_period)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)
    fast = sma(cs, fast_period)
    slow = sma(cs, slow_period)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Exit ALWAYS evaluated first — never trap a position behind an entry filter.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry: Donchian breakout AND fast-SMA above slow-SMA (local uptrend).
    if hi is not None and last > hi and holding == 0:
        if fast is None or slow is None:
            return Action("hold", symbol, reason="sma not ready")
        if fast <= slow:
            return Action("hold", symbol,
                          reason=f"breakout but fast SMA {fast:.2f} <= slow SMA {slow:.2f}")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f} "
                             f"AND fast {fast:.2f} > slow {slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, hi={hi}, lo={lo}, "
                         f"fast={fast}, slow={slow}, holding={holding})")