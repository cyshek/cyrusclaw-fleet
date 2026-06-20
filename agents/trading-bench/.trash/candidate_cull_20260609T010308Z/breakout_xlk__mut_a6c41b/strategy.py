"""Donchian breakout on XLK 1h bars, gated by a GRADED SPY-trend regime score.

Variant of `breakout_xlk` that replaces the parent's binary regime gate
(SPY above/below its 50d SMA) with a stricter graded threshold: it only
opens new longs when `regime_score(spy_closes, 50) > 0.02`, i.e. SPY is at
least 2% ABOVE its 50-day SMA — not merely above it. Thesis: the parent's
long-only breakout edge is strongest in confirmed, well-established uptrends;
shallow regimes where SPY hovers just above its MA (0% to +2%) are exactly
the chop where breakouts whipsaw, so demanding a 2% cushion filters out the
weakest entry regime while keeping the strong-trend entries.

Entry signal: close > prior `lookback`-bar Donchian high AND regime_score > 0.02.
Exit signal: close < prior `lookback`-bar Donchian low (UNGATED — see below).
Edge: same breakout momentum as the parent, but the regime cushion trims the
marginal, downtrend-adjacent entries that bleed in bear/early-recovery windows.

Important: the regime gate blocks NEW ENTRIES ONLY. Close logic runs FIRST and
is never gated, so an already-open position is always exitable on the Donchian
low even when the regime score has collapsed below the entry threshold.

Regime data: read from `market_state["regime"]` = {"spy_closes": [...],
"spy_last": float}, pre-populated by the runner/backtester for stocks. When
regime is None (data unavailable / crypto), the entry gate is skipped and
behavior falls through to the parent breakout logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_score


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
    regime_min = float(params.get("regime_min_score", 0.02))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — the regime gate must never trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry gate: graded regime score must clear the 2% cushion threshold.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime is not None:
            score = regime_score(regime.get("spy_closes") or [],
                                 period=regime_period)
            if score <= regime_min:
                return Action("hold", symbol,
                              reason=f"regime score {score:.4f} <= {regime_min:.4f} "
                                     f"(SPY not >{regime_min*100:.0f}% above "
                                     f"{regime_period}d SMA; breakout blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")
    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")