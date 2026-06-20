"""Donchian breakout on XLK 1h bars with a take-profit overlay.

Parent (`breakout_xlk`) goes long on a `lookback`-bar Donchian high break and
exits only when price falls below the `lookback`-bar Donchian low. Thesis of
this mutation: the parent gives back gains on its winners by waiting for the
Donchian low to roll over, so a fast-moving winner can round-trip a large
runup before the exit triggers. We add a take-profit that closes the position
once price has risen TAKE_PROFIT_PCT above the entry price.

Take-profit threshold (2.30%): the parent's empirical per-trade max-runup
distribution is p25 +1.26% / median +2.60% / p75 +4.11%. A target at 2.30%
sits just below the median runup, so it would have locked in more than half
of historical winners while still letting a typical winner breathe past the
+1.26% p25 (a tighter target would clip too many ordinary moves). It is well
inside the distribution — a target above the p75 (+4.11%) would be inert.

Ordering (critical): the parent's own close signal (price < Donchian low)
runs FIRST and is always honored. The take-profit only fires when the parent
would otherwise HOLD an open position — it never blocks an exit, and the
entry gate runs last so a filter can never trap us long.

Entry signal: close > prior `lookback`-bar high while flat.
Exit signals: (1) close < prior `lookback`-bar low [parent], or
              (2) price >= entry * (1 + TAKE_PROFIT_PCT) [overlay].
Edge: harvest the right tail of winners the parent gives back, without
touching its loss-side behavior.
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
    take_profit_pct = float(params.get("take_profit_pct", 0.023))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ---- Close logic ALWAYS runs first so no overlay/gate can trap us long ----
    # (1) Parent exit: Donchian-low breakdown. Runs before the take-profit so
    #     the parent's own close signal is never pre-empted or blocked.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # (2) Take-profit overlay: only fires when the parent would otherwise HOLD
    #     an open position. Reads entry price from position_state; if it's
    #     unavailable we simply skip the overlay (parent behavior unchanged).
    if holding > 0:
        entry_price = 0.0
        if pos:
            for k in ("avg_entry_price", "entry_price", "avg_price", "cost_basis"):
                v = pos.get(k)
                if v is not None:
                    try:
                        entry_price = float(v)
                    except (TypeError, ValueError):
                        entry_price = 0.0
                    break
        if entry_price > 0:
            target = entry_price * (1.0 + take_profit_pct)
            if last >= target:
                gain = (last / entry_price - 1.0) * 100.0
                return Action("close", symbol,
                              reason=(f"take-profit: {last:.2f} >= entry "
                                      f"{entry_price:.2f} * (1+{take_profit_pct:.3f}) "
                                      f"=> +{gain:.2f}% (>= {take_profit_pct*100:.2f}%)"))

    # ---- Entry gate runs LAST; only opens new positions when flat ----
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")