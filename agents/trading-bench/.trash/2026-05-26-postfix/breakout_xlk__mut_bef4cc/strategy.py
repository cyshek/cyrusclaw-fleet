"""Donchian breakout on XLK 1h bars with a tight hard stop-loss.

Variant of `breakout_xlk` that adds an intra-trade hard stop. The parent
exits only when price breaks the N-bar Donchian low, which on 1h XLK bars
can lag a sharp adverse move by many hours — the parent's own trade
distribution shows 64% of trades touched a >=1% drawdown and the median
trade saw a 1.41% max drawdown before the Donchian-low exit fired.

Entry signal: close > prior `lookback`-bar high (same as parent).
Exit signals (parent's close runs FIRST, then stop):
  1. Parent: close < prior `lookback`-bar low.
  2. Stop:   last price <= entry_price * (1 - stop_pct).

Stop choice: stop_pct = 0.012 (1.2%). Why this value?
  - The parent's median per-trade max drawdown is 1.41%, and 64% of trades
    touched >=1% drawdown. A 1.2% stop sits just below the median, so it
    would have fired on roughly half of historical trades — well inside
    the empirical distribution, NOT inert.
  - p25 drawdown is 2.21%; anything above ~2% would only catch the
    worst-quartile trades and leave the bulk of mid-tier losers running
    until the slow Donchian-low exit. 1.2% is meaningfully tighter than
    that tail.
  - The thesis: catch the fast 1-3 bar adverse spikes that turn a small
    losing breakout into a multi-percent drawdown before the Donchian
    low finally rolls over. Median runup is 2.60%, so a 1.2% stop also
    keeps the realized R-multiple reasonable on winners that don't
    immediately go our way.

Entry price tracking: stored in position_state[symbol]["entry_price"] when
we issue the buy. If the runner doesn't persist that field across bars (or
if we inherit a pre-existing position), we fall back to position_state's
own `avg_entry_price` if present, else skip the stop check that bar (the
parent's exit will still protect us).
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
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 100.0))
    stop_pct = float(params.get("stop_pct", 0.012))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1. Parent exit ALWAYS runs first \u2014 stop must not block the Donchian close.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2. Hard stop-loss check (only if we have a usable entry price).
    if holding > 0:
        entry_price = pos.get("entry_price")
        if entry_price is None:
            entry_price = pos.get("avg_entry_price")
        if entry_price is not None:
            try:
                ep = float(entry_price)
            except (TypeError, ValueError):
                ep = 0.0
            if ep > 0:
                stop_level = ep * (1.0 - stop_pct)
                if last <= stop_level:
                    drawdown = (last - ep) / ep
                    return Action("close", symbol,
                                  reason=f"stop-loss: last {last:.2f} <= "
                                         f"{stop_level:.2f} "
                                         f"(entry {ep:.2f}, dd {drawdown*100:.2f}%, "
                                         f"stop {stop_pct*100:.2f}%)")

    # 3. Entry signal (parent breakout).
    if hi is not None and last > hi and holding == 0:
        # Record entry price so future bars can evaluate the stop.
        position_state[symbol] = {
            **pos,
            "entry_price": last,
        }
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f} "
                             f"(stop @ -{stop_pct*100:.2f}%)")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")