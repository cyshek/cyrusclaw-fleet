"""Donchian breakout on XLK 1h with a one-shot partial exit (scale-out).

Parent: `breakout_xlk` — long when close > 20-bar high, exit when close
< 20-bar low. Parent profile shows median per-trade runup of +2.60% with
78% of trades touching at least +1%, so winners reliably reach a
mid-single-digit runup before the Donchian-low exit fires.

Mutation: when an open position's last close is >= entry * (1 + partial_pct),
sell HALF the position (qty/2) once per trade and flag `scaled_out=True`
on position_state[symbol]. The remaining half rides the parent's normal
Donchian-low close. partial_pct defaults to 2.6% — the parent's MEDIAN
runup — so the scale-out should fire on roughly half of historical winners
(it sits between p25=+1.26% and p75=+4.11%, comfortably inside the
distribution and well below the p75 inert zone).

Close logic ALWAYS runs first so no filter can trap us long. The partial
exit is gated by the `scaled_out` flag so it fires at most once per trade;
the runner is expected to clear that flag when the position goes flat.
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
    partial_pct = float(params.get("partial_pct", 0.026))

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

    # 1) Full close ALWAYS first — never let any gate trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) Partial exit (one-shot): half off when runup >= partial_pct.
    if holding > 0 and not scaled_out and entry_price > 0:
        runup = (last - entry_price) / entry_price
        if runup >= partial_pct:
            half = holding / 2.0
            pos["scaled_out"] = True
            position_state[symbol] = pos
            return Action("sell", symbol, qty=half,
                          reason=f"partial exit: runup {runup*100:.2f}% "
                                 f">= {partial_pct*100:.2f}% (sell half)")

    # 3) Entry on breakout when flat.
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, hi={hi}, lo={lo}, "
                         f"holding={holding}, scaled_out={scaled_out})")