"""Donchian breakout on XLK 1h bars with a one-shot 50%% scale-out at the median runup.

Thesis: the parent (`breakout_xlk`) is a long-only Donchian breakout that holds
each winner all the way to the Donchian-low exit. Per the parent's empirical
runup distribution (45 trades, 8/8 walk-forward windows), winners routinely
print a meaningful peak before the exit signal fires — runup p25 +1.26%, MEDIAN
+2.60%, p75 +4.11%, with 78%% of trades touching >=1%% runup — yet many give a
chunk of that back by the time price falls through the Donchian low. By locking
in HALF the position once it has risen +2.60%% above entry (the median max
runup, chosen so the scale-out would have fired on roughly half of historical
trades and sits strictly inside the observed distribution, below the p75 of
+4.11%% so it is not inert), we de-risk the trade while leaving the remaining
half to run on the parent's unchanged Donchian-low exit and capture the right
tail. The +2.60%% level is deliberately NOT a round number and is taken directly
from the parent runup median.

Entry signal (unchanged from parent): close breaks above the prior `lookback`-bar
high while flat -> buy `notional_usd`.

Scale-out (new): while holding and not yet scaled out, if the latest close is
>= entry_price * (1 + scale_out_pct) (scale_out_pct=0.026), sell HALF the held
qty (qty=holding/2) ONCE. This is gated by `scaled_out` in position_state so it
fires at most once per trade; the runner is expected to flip that flag (or it is
reset when the position goes flat). The scale-out is a partial EXIT, so it lives
in the close/exit section and is never blocked by any entry-side filter.

Exit signal (unchanged from parent): close breaks below the prior `lookback`-bar
low while holding -> close the remainder.

Why edge: same breakout edge as the parent, but with realized profit-taking on
the median winner. It cannot block exits, adds no new entry filter, and only
ever reduces (never increases) risk relative to the parent.
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
    notional = float(params.get("notional_usd", 1000.0))
    # Median max runup of the parent (+2.60%%) -> fires the scale-out on ~half of
    # historical winners; inside the parent distribution (p25 +1.26%, p75 +4.11%).
    scale_out_pct = float(params.get("scale_out_pct", 0.026))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    # Entry price for runup measurement; coerce defensively. Several common keys.
    entry_price = pos.get("avg_entry_price", pos.get("entry_price", pos.get("avg_price")))
    try:
        entry_price = float(entry_price) if entry_price is not None else None
    except (TypeError, ValueError):
        entry_price = None
    scaled_out = bool(pos.get("scaled_out", False))

    # -----------------------------------------------------------------
    # EXIT / CLOSE LOGIC FIRST. Nothing below the entry gate may block these.
    # -----------------------------------------------------------------

    # Full close: parent's Donchian-low exit fires the remainder of the position.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Partial scale-out: lock in HALF once, at the median-runup threshold.
    if (holding > 0 and not scaled_out and entry_price is not None
            and entry_price > 0):
        runup = (last - entry_price) / entry_price
        if runup >= scale_out_pct:
            half = holding / 2.0
            if half > 0:
                return Action("sell", symbol, qty=half,
                              reason=(f"scale-out 50%%: runup {runup * 100:.2f}%% "
                                      f">= {scale_out_pct * 100:.2f}%% "
                                      f"(entry {entry_price:.2f}, last {last:.2f})"))

    # -----------------------------------------------------------------
    # ENTRY GATE (after all exits). Parent's breakout entry, unchanged.
    # -----------------------------------------------------------------
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=(f"no signal (last={last:.2f}, hi={hi}, lo={lo}, "
                          f"holding={holding}, scaled_out={scaled_out})"))