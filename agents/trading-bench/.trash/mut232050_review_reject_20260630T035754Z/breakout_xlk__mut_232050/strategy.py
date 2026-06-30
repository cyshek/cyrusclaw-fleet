"""Donchian breakout on XLK 1h bars WITH a half-position scale-out overlay.

Parent: `breakout_xlk` (BUY when close > 20-bar high; CLOSE when close <
20-bar low). The parent rides every winner all the way to the Donchian-low
exit, so on trades that run up and then give the gain back before the low
breaks, it surrenders a lot of open profit.

This mutation adds a PARTIAL EXIT (scale-out). When an open position has
risen `scaleout_pct` above its average entry price, we sell HALF the
position once, then let the remaining half ride the parent's normal
Donchian-low exit. Locking in half de-risks the trade while preserving
upside on the runner.

Choosing X from the PARENT PROFILE runup percentiles (max runup per trade,
vs entry): p25 +1.26%, median +2.60%, p75 +4.11%; 78% of trades touch
>=1% runup. We set `scaleout_pct = 0.026` (= the +2.60% MEDIAN runup) so
the scale-out fires on roughly HALF of all winners — the half that reach at
least the median runup — exactly as the directive specifies. A value near
p75 (+4.11%) would be near-inert (fires on only the top quartile); a value
near p25 (+1.26%) would dump half the position on nearly every trade and
strangle the runners. The median is the principled midpoint.

CRITICAL mechanics:
  * `position_state[symbol]['_scaled_out']` is a per-symbol boolean so the
    half-sale fires AT MOST ONCE per trade. It is set True on the scale-out
    bar and reset (cleared) on every fresh entry, so the next trade starts
    clean.
  * The scale-out emits `Action('sell', ..., qty=holding/2)` — a partial
    de-risk that keeps the position long (the runner's trim/sell path
    clamps to held qty and does not flip short).
  * The parent's CLOSE signal (price < Donchian low) ALWAYS runs first and
    fires the full remainder; the scale-out never blocks or delays a close.
    A position is therefore never harder to close than to open.
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
    scaleout_pct = float(params.get("scaleout_pct", 0.026))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ---- Parent CLOSE ALWAYS runs first — never trap a position long. ----
    if lo is not None and last < lo and holding > 0:
        if pos is not None:
            pos.pop("_scaled_out", None)
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # ---- Scale-out: sell HALF once when runup >= scaleout_pct above entry. ----
    if holding > 0 and pos is not None:
        entry_px = float(pos.get("avg_entry_price", 0.0) or 0.0)
        already = bool(pos.get("_scaled_out", False))
        if entry_px > 0 and not already:
            runup = (last - entry_px) / entry_px
            if runup >= scaleout_pct:
                pos["_scaled_out"] = True
                return Action("sell", symbol, qty=holding / 2.0,
                              reason=f"scale-out half: +{runup * 100:.2f}% "
                                     f">= {scaleout_pct * 100:.2f}% median runup")

    # ---- Entry: parent Donchian breakout. ----
    if hi is not None and last > hi and holding == 0:
        position_state.setdefault(symbol, {})["_scaled_out"] = False
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")