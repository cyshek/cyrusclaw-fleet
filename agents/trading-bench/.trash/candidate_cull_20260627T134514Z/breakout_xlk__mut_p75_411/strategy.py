"""Donchian breakout on XLK 1h bars with a one-shot PARTIAL EXIT (scale-out).

Parent (`breakout_xlk`) enters long on a close above the 20-bar Donchian high
and exits the WHOLE position on a close below the 20-bar low. The parent's
winners run up a median of +2.60% before exit, but they give a lot of that
back holding all the way to the Donchian-low close. This mutation locks in
gains early: when an open position first rises >= SCALE_OUT_PCT above its
entry price, we SELL HALF (qty=holding/2) and let the remaining half keep
running on the parent's unchanged close logic.

Why X = +2.60%: the parent's per-trade max-runup distribution is
p25 +1.26% / median +2.60% / p75 +4.11%. The directive says ground X near the
MEDIAN runup so the scale-out fires on ~50% of winners. +2.60% sits exactly at
the median, so historically about half of all trades touched this level and
would have had half their size de-risked, while the other half (smaller-runup
trades) are untouched and exit normally. A trigger below p25 would scale out of
nearly everything (no upside left to run); above p75 (4.11%) it would be inert.

Once-per-trade guarantee: position_state[symbol]['scaled_out'] is set True the
bar we trim, so the partial exit can NEVER fire twice on the same position.
The flag is implicitly reset because a flat -> new entry creates fresh state
(no 'scaled_out' key), so the next trade starts un-scaled. Selling half of a
long is still a long (qty stays > 0), so this can never flip the position; and
the close signal is evaluated FIRST every bar, so the scale-out filter can
never trap us long.
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


def _entry_price(pos: dict) -> Optional[float]:
    """Best-effort read of the position's entry/average price.

    position_state shape varies by runner; probe the common keys and return
    the first positive float found, else None (then we simply skip the
    scale-out this bar rather than acting on a bogus 0.0).
    """
    if not pos:
        return None
    for k in ("avg_entry_price", "entry_price", "avg_price", "cost_basis",
              "price", "entry"):
        v = pos.get(k)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > 0:
            return f
    return None


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    scale_out_pct = float(params.get("scale_out_pct", 2.60))
    scale_out_fraction = float(params.get("scale_out_fraction", 0.5))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # --- 1) Full close ALWAYS runs first: never let any filter trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # --- 2) One-shot partial exit (scale-out) on the open position.
    # Fires at most once per trade (gated by 'scaled_out'). Selling a fraction
    # of a long keeps qty > 0, so it can never flip the position.
    if holding > 0 and pos is not None and not bool(pos.get("scaled_out", False)):
        ep = _entry_price(pos)
        if ep is not None:
            runup = (last - ep) / ep * 100.0
            if runup >= scale_out_pct:
                trim_qty = holding * scale_out_fraction
                if trim_qty > 0:
                    # Persist the one-shot flag so this trade can't trim again.
                    pos["scaled_out"] = True
                    return Action(
                        "sell", symbol, qty=trim_qty,
                        reason=(f"scale-out {scale_out_fraction:.0%} at "
                                f"+{runup:.2f}% >= {scale_out_pct:.2f}% "
                                f"(entry {ep:.2f}, last {last:.2f}); "
                                f"remainder runs to Donchian-low close"))

    # --- 3) Entry: parent's Donchian-high breakout, only when flat.
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=(f"no signal (last={last:.2f}, hi={hi}, lo={lo}, "
                          f"holding={holding})"))