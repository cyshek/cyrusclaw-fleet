"""Donchian breakout on XLK 1h bars (regime-gated) with a one-shot partial exit.

Parent: `breakout_xlk_regime` — long-only Donchian breakout, SPY-SMA regime
gate on entries, exit when close < lookback-bar low. Parent profile shows
72% of trades touch +1% runup and the median trade peaks at +2.60% before
the Donchian-low exit eventually fires (often well after the peak). That's
the classic "winners give back gains" pattern this mutation targets.

Mutation: when an open position's last close is >= `partial_exit_pct` above
entry AND we haven't already scaled out this trade, sell HALF the position
(qty/2) and flag `scaled_out=True` in position_state. The remaining half
keeps running on the parent's normal Donchian-low close. Parent close logic
is unchanged and always runs first so exits are never blocked.

Choice of X = 2.5% (just below parent median runup of 2.60%): by construction
this fires on ~50% of historical winners (those that touch >=2.5% runup),
which is exactly the "median runup" target the directive asks for. A more
aggressive 4% would sit at p75 and only fire on ~25% of trades (too rare to
matter); 1% would fire on ~72% and lock in trivial gains before the trade
has proven anything. 2.5% threads the needle.

Edge hypothesis: parent's expectancy is dragged down by round-trippers — trades
that run to +2-4% then mean-revert all the way to the Donchian-low stop.
Scaling out at the median runup converts half of those round-trippers from
"give it all back" into "locked half the peak," while the surviving half
still captures the right tail when a breakout actually trends.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_uptrend


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
    partial_exit_pct = float(params.get("partial_exit_pct", 0.025))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_price = float(pos.get("avg_entry_price", 0) or pos.get("entry_price", 0) or 0.0)
    scaled_out = bool(pos.get("scaled_out", False))

    # 1) Full-close logic ALWAYS runs first — never let any filter trap us long.
    if lo is not None and last < lo and holding > 0:
        # Reset scaled_out flag for next trade lifecycle.
        pos["scaled_out"] = False
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) Partial exit: one-shot per trade, only if we're holding, have an entry
    #    price, haven't scaled out yet, and last >= entry * (1 + X).
    if (holding > 0 and entry_price > 0 and not scaled_out
            and last >= entry_price * (1.0 + partial_exit_pct)):
        runup_pct = (last - entry_price) / entry_price * 100.0
        pos["scaled_out"] = True
        return Action("sell", symbol, qty=holding / 2.0,
                      reason=f"partial exit: +{runup_pct:.2f}% >= "
                             f"{partial_exit_pct*100:.2f}% (scale out half)")

    # 3) Entry: regime gate applies to NEW positions only.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        # New trade — make sure scaled_out is clean.
        pos["scaled_out"] = False
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, "
                         f"holding={holding}, scaled_out={scaled_out})")