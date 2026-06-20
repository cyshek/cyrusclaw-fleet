"""Donchian breakout on XLK 1h bars, gated by a strict SPY regime-score filter.

Variant of the regime-gated breakout that replaces the binary
`regime_uptrend` check with a graded `regime_score` threshold. New long
entries are only allowed when SPY trades at least `regime_min_score`
above its 50-bar SMA (default +2%). Hypothesis: requiring a meaningful
cushion above trend (not merely a crossover) filters out fragile regimes
where SPY is hovering at the MA and prone to whipsaws, keeping us long
only in clearly-confirmed uptrends.

Entry signal: close breaks above the prior `lookback`-bar high AND
regime_score(SPY, 50) > regime_min_score. Exit signal: close falls below
the prior `lookback`-bar low — exits ALWAYS run first so the regime gate
never traps an open position. If regime data is unavailable (crypto, or
SPY bars missing) regime_score returns 0.0, which fails the strict
threshold and blocks entries — conservative by design for this mutation.
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
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    regime_min_score = float(params.get("regime_min_score", 0.02))

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

    # Entry gate: graded regime filter must clear the strict threshold.
    if hi is not None and last > hi and holding == 0:
        regime = market_state.get("regime")
        spy_closes = (regime or {}).get("spy_closes") or []
        score = regime_score(spy_closes, period=regime_period)
        if score <= regime_min_score:
            return Action("hold", symbol,
                          reason=f"regime score {score:.4f} <= "
                                 f"{regime_min_score:.4f} (entry blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f} "
                             f"(regime score {score:.4f})")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")