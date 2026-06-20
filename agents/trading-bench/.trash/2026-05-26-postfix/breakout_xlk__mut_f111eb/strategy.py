"""Donchian breakout on XLK 1h bars with a TRAILING STOP on the running max.

Parent: `breakout_xlk` (Donchian 20-bar breakout, long-only). This variant
adds a trailing stop that tracks the highest close seen since entry
(`running_max` in position_state) and closes the position when price falls
`trail_pct` from that running max — NOT from entry price. Hypothesis: a
trail-from-peak lets winners run during sustained trends (the parent's
median runup is +2.60%, p75 +4.11%, so winners do extend) while still
cutting them on a real give-back, capturing more upside than a fixed
from-entry stop would.

Choice of `trail_pct = 1.40%`: grounded in the parent profile. Median max
runup per trade is +2.60% and median max drawdown is -1.41%. A trail of
1.40% sits just under the median runup, so a typical winner that extends
to +2.60% gives back ~1.40% off the peak before we exit — locking in
roughly half the median runup. It is comfortably wider than typical
intra-trade noise on winners (whose drawdowns from entry are smaller than
1.41% in the upper half of the distribution) and is NOT inert: it sits
well inside the runup distribution (below p75 = 4.11%) so it will fire on
real reversals rather than wait for the full Donchian-low exit.

Exit ordering (mandatory): the parent's Donchian-low close ALWAYS runs
first. The trailing stop is an additional, never-blocking exit — it can
only ADD exits, never suppress them. New entries reset `running_max` to
the entry close price.
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
    trail_pct = float(params.get("trail_pct", 0.014))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1) Parent's close signal ALWAYS runs first — trailing stop never blocks it.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) Trailing stop: track running max since entry, exit on give-back.
    if holding > 0:
        running_max = float(pos.get("running_max", 0.0) or 0.0)
        if running_max <= 0:
            # First bar after entry where we see state — seed with current price.
            running_max = last
        if last > running_max:
            running_max = last
        pos["running_max"] = running_max
        position_state[symbol] = pos
        if running_max > 0 and last <= running_max * (1.0 - trail_pct):
            give_back = (running_max - last) / running_max
            return Action("close", symbol,
                          reason=f"trailing stop: {give_back*100:.2f}% off peak "
                                 f"{running_max:.2f} (trail={trail_pct*100:.2f}%)")

    # 3) Entry: Donchian breakout. Reset running_max to entry price on new entry.
    if hi is not None and last > hi and holding == 0:
        pos["running_max"] = last
        position_state[symbol] = pos
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")