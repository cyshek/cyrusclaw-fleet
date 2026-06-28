"""Contrarian Donchian *fade* on IWM 1h bars — the mean-reversion inversion of `breakout_xlk`.

Where the parent BUYS strength (close above the N-bar high) and SELLS weakness
(close below the N-bar low), this variant does the OPPOSITE: it FADES the move.
Entry signal: go LONG when price breaks *below* the lower Donchian band
(close < N-bar low) — an oversold flush in a range-bound small-cap index that
statistically tends to snap back. Exit signal: take profit when price reverts
back UP to the opposite (upper) Donchian band OR a +reversion target is hit;
cut the trade on a stop if the flush keeps going, or on a time-stop if the
bounce never comes. Edge thesis: IWM (Russell 2000) mean-reverts intraday/over
a few days far more than it trends, so the breakout signal the parent chases is
usually noise that gets bought back — we harvest that reversion instead of
paying for the parent's trend continuation that often fails on this symbol.

Thresholds are grounded in `breakout_xlk`'s empirical trade distribution
(median max-runup +2.60%, p25 max-drawdown -2.21%, p75 hold 43 bars): the
reversion take-profit (+2.0%) sits just below the median runup so it would have
locked in at least half of comparable winners; the stop (-2.0%) sits between the
median (-1.41%) and p25 (-2.21%) drawdown so it actually fires on adverse trades
without whipsawing the median; the time-stop (45 bars) tracks the p75 holding
period so a dead trade is never trapped.

Safety: exit logic (take-profit / stop / time-stop / band-reversion) ALWAYS runs
before the entry signal, so no filter can ever trap an open position.
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
    symbol = params.get("symbol", "IWM")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    take_profit_pct = float(params.get("take_profit_pct", 2.0))
    stop_loss_pct = float(params.get("stop_loss_pct", 2.0))
    max_hold_bars = int(params.get("max_hold_bars", 45))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)   # upper band = mean-reversion profit target zone
    lo = lowest(cs[:-1], lookback)    # lower band = oversold flush = our ENTRY trigger

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ----------------------------------------------------------------------
    # EXIT LOGIC FIRST — must never be blocked by the entry filter, so an
    # open position is always closeable (never trapped).
    # ----------------------------------------------------------------------
    if holding > 0:
        entry_px = 0.0
        if pos:
            entry_px = float(pos.get("avg_entry_price", pos.get("entry_price", 0)) or 0.0)
        bars_held = int(pos.get("bars_held", 0)) if pos else 0

        # 1) Profit-take on % reversion bounce off the flush.
        if entry_px > 0:
            change_pct = (last - entry_px) / entry_px * 100.0
            if change_pct >= take_profit_pct:
                return Action("close", symbol,
                              reason=f"take-profit: +{change_pct:.2f}% reversion "
                                     f">= {take_profit_pct:.2f}%")
            # 2) Stop-loss: flush kept going against us.
            if change_pct <= -stop_loss_pct:
                return Action("close", symbol,
                              reason=f"stop-loss: {change_pct:.2f}% "
                                     f"<= -{stop_loss_pct:.2f}%")

        # 3) Band reversion: price snapped all the way back to the upper band
        #    (the move the parent would chase) — fully mean-reverted, take it.
        if hi is not None and last >= hi:
            return Action("close", symbol,
                          reason=f"reverted to upper band: close {last:.2f} "
                                 f">= {lookback}-bar high {hi:.2f}")

        # 4) Time-stop: bounce never materialized within the p75 holding window.
        if max_hold_bars > 0 and bars_held >= max_hold_bars:
            return Action("close", symbol,
                          reason=f"time-stop: held {bars_held} >= {max_hold_bars} bars, "
                                 f"reversion thesis stale")

    # ----------------------------------------------------------------------
    # ENTRY LOGIC — CONTRARIAN: fade the breakdown, buy the oversold flush.
    # (Inverse of parent: parent buys close > high; we buy close < low.)
    # ----------------------------------------------------------------------
    if lo is not None and last < lo and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"fade flush: close {last:.2f} < {lookback}-bar low "
                             f"{lo:.2f} (mean-reversion long)")

    return Action("hold", symbol,
                  reason=f"no flush (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")