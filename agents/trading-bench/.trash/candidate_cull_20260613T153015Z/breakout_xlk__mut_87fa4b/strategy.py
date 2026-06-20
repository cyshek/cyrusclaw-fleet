"""Donchian-pullback mean reversion on GLD 1h bars (contrarian flip of breakout_xlk).

Thesis: GLD is a range-bound, mean-reverting instrument far more often than it
trends; the parent (breakout_xlk) BUYS strength (close above the N-bar high),
but on a mean-reverter that buys the top and gets chopped. This variant inverts
the signal: it BUYS WEAKNESS — a close BELOW the N-bar low (an oversold pullback
flushing into the bottom of the range) — and bets on snap-back toward the range.

Entry: flat AND close < lowest(N-bar) low  -> buy (catch the pullback).
Exit (any one, close-logic runs first so a filter never traps us long):
  1. close > highest(N-bar) high  -> reversion completed, exit at range top.
  2. price has fallen >= stop_loss_pct from entry -> the pullback kept going,
     cut it. Grounded at -1.40% (parent's MEDIAN per-trade max drawdown -1.41%,
     so this stop would have fired on ~half of historical adverse excursions —
     deeper than that = inert vs the parent's own distribution).
  3. price has risen >= take_profit_pct from entry -> lock the bounce. Grounded
     at +2.50% (just under the parent's MEDIAN per-trade max runup +2.60%, so it
     would have captured at least half the winners; a target above p75 +4.11%
     would be inert).

Edge hypothesis: on a mean-reverting symbol, fading the breakdown harvests the
reversion premium the trend-following parent leaves on the table, while the
profile-grounded stop bounds the left tail when a "pullback" is actually a
regime break.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "GLD")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    stop_loss_pct = float(params.get("stop_loss_pct", -1.40))
    take_profit_pct = float(params.get("take_profit_pct", 2.50))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_px = float(pos.get("avg_entry_price", 0) or 0) if pos else 0.0

    # ---- CLOSE LOGIC FIRST (never let any gate trap an open position) ----
    if holding > 0:
        # 1. profit-taking / stop based on move from entry
        if entry_px > 0:
            chg_pct = (last - entry_px) / entry_px * 100.0
            if chg_pct <= stop_loss_pct:
                return Action("close", symbol,
                              reason=f"stop {chg_pct:.2f}% <= {stop_loss_pct:.2f}% "
                                     f"(entry {entry_px:.2f} -> {last:.2f})")
            if chg_pct >= take_profit_pct:
                return Action("close", symbol,
                              reason=f"take-profit {chg_pct:.2f}% >= {take_profit_pct:.2f}% "
                                     f"(entry {entry_px:.2f} -> {last:.2f})")
        # 2. mean-reversion completed: close back above the N-bar high
        if hi is not None and last > hi:
            return Action("close", symbol,
                          reason=f"reverted: close {last:.2f} > {lookback}-bar high {hi:.2f}")

    # ---- ENTRY: fade the breakdown (buy the pullback below the N-bar low) ----
    if lo is not None and last < lo and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"pullback: close {last:.2f} < {lookback}-bar low {lo:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")