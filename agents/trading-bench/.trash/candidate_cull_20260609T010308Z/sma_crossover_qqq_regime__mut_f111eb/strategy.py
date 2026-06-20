"""SMA crossover on QQQ 1h bars (SPY-regime gated) + a price TRAILING STOP.

Thesis: the parent (`sma_crossover_qqq_regime`) exits only on the bearish
SMA cross (fast < slow), which is a lagging signal — by the time the fast
SMA rolls under the slow, a winner has often already handed back most of
its runup. This mutation adds a give-back trailing stop: it tracks the
highest price seen since entry (running_max in position_state) and closes
when price falls X% BELOW that running max (not below entry). The goal is
to let winners run during sustained trends but bank the trade once a real
reversal eats into the runup, capturing more of the parent's upside than a
fixed-from-entry stop would.

Entry: unchanged from parent — bullish cross (fast > slow) while flat, gated
by the SPY regime filter (SPY > regime_period-day SMA). Regime blocks NEW
ENTRIES ONLY.

Exit: whichever fires first — (a) the parent's bearish-cross close, or
(b) the trailing stop: last <= running_max * (1 - trail_pct). Both close
paths run BEFORE the entry gate so a filter can never trap an open position.

Grounding X (trail_pct = 0.0070 = 0.70%): from the parent trade profile the
max-runup distribution is p25 +0.70%, median +1.34%, p75 +3.33%, and the
median per-trade max drawdown is 0.76%. The directive requires X smaller
than the median runup (1.34%) so the stop fires on the give-back phase, not
the run-up phase. I chose 0.70% — equal to the p25 runup and just under the
0.76% median drawdown — so it sits firmly inside the observed give-back
range (a live, non-inert level: it is shallower than the p25 drawdown of
1.32%, so it would actually have fired, not been a no-op) while still being
loose enough that a normal winner gets to run past 0.70% of runup before any
0.70% pullback from its peak can trigger. Edge: trades the lagging-cross exit
for a peak-relative exit, which should recover runup the parent currently
gives back between the price top and the delayed cross.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, regime_uptrend


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
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    trail_pct = float(params.get("trail_pct", 0.0070))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]

    # ---- CLOSE LOGIC ALWAYS RUNS FIRST (no filter may trap an open position) ----
    if holding > 0:
        # Maintain the running max of price seen since entry. On a fresh entry
        # the runner seeds position_state; if running_max is missing/zero we
        # reset it to entry_price (fallback: current price). It only ratchets up.
        entry_price = float(pos.get("entry_price", last)) if pos else last
        running_max = float(pos.get("running_max", 0.0)) if pos else 0.0
        if running_max <= 0.0:
            running_max = entry_price
        if last > running_max:
            running_max = last
        # persist back so subsequent bars keep ratcheting
        if pos is not None:
            pos["running_max"] = running_max

        # (a) trailing give-back stop relative to the peak since entry
        trail_level = running_max * (1.0 - trail_pct)
        if last <= trail_level:
            return Action("close", symbol,
                          reason=f"trail stop: {last:.2f} <= peak {running_max:.2f} "
                                 f"* (1-{trail_pct:.4f}) = {trail_level:.2f}")

        # (b) parent's bearish-cross close
        if fast < slow:
            return Action("close", symbol,
                          reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # ---- ENTRY GATE (regime filter applies to NEW ENTRIES ONLY) ----
    regime = market_state.get("regime")
    if fast > slow and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(trail {trail_pct:.4f} armed on entry)")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")