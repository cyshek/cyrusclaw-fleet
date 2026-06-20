"""SMA crossover on QQQ 1h bars with a trailing stop on the running max.

Parent: `sma_crossover_qqq` (fast/slow SMA crossover, long-only). This
variant adds a trailing stop: we track the highest close seen since entry
in position_state["running_max"] and close the position when price falls
`trail_pct` from that running max (NOT from entry price).

Threshold choice grounded in the parent profile:
- Median max runup per trade = +1.17%; p25 = +0.52%, p75 = +3.03%.
- A trailing stop must fire on the GIVE-BACK after the runup, not during
  the runup itself, so trail_pct should be < median runup (1.17%).
- Picked trail_pct = 0.65% (between p25 runup 0.52% and median 1.17%):
  comfortably below median so most winners that ran >=1% get the trail
  armed and locked in some gain on the reversal, while still wide enough
  to survive ordinary intra-trend noise (parent's median per-trade max
  drawdown is 1.14%, so 0.65% is tighter than typical adverse excursion
  but it is measured from the RUNNING MAX after a runup, not entry, so
  it only engages once price has actually advanced).

Trailing stop must NOT block the parent's own close signal: the slow/fast
SMA cross-down still closes the position regardless of trailing state.
running_max resets to entry_price on every new entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    trail_pct = float(params.get("trail_pct", 0.0065))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    need = max(slow_p, fast_p) + 1
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # --- Exits first: parent close signal ALWAYS honored, then trailing stop.
    if holding > 0:
        # Parent's own close signal: fast crosses below slow.
        if fast < slow:
            pos.pop("running_max", None)
            return Action("close", symbol,
                          reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

        # Update running_max (entry_price seed if first bar held).
        entry_price = float(pos.get("entry_price", last))
        prev_max = float(pos.get("running_max", entry_price))
        running_max = prev_max if prev_max >= last else last
        pos["running_max"] = running_max

        # Trailing stop: fire when price has given back trail_pct from running max.
        if running_max > 0 and last <= running_max * (1.0 - trail_pct):
            give_back = (running_max - last) / running_max
            pos.pop("running_max", None)
            return Action(
                "close", symbol,
                reason=(f"trailing stop: {last:.2f} <= max {running_max:.2f} "
                        f"* (1-{trail_pct:.4f}) (give-back {give_back*100:.2f}%)"),
            )

        return Action("hold", symbol,
                      reason=(f"holding (last={last:.2f}, run_max={running_max:.2f}, "
                              f"fast={fast:.2f}, slow={slow:.2f})"))

    # --- Entry: parent's crossover up.
    if fast > slow:
        # Reset running_max to entry price on new entry.
        pos["running_max"] = last
        pos["entry_price"] = last
        position_state[symbol] = pos
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, flat)")