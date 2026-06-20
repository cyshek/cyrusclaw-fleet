"""Donchian breakout on XLK 1h bars (SPY-regime gated) + a TRAILING STOP.

Thesis: the parent `breakout_xlk_regime` exits only on a Donchian-low break,
which can give back a large fraction of an open winner before the low is
violated. Adding a trailing stop that tracks the running max since entry lets
sustained trends keep running while cutting the position the moment a real
give-back begins — capturing more of the parent's upside than a fixed-from-
entry stop (a fixed stop can't ratchet up as the trade gains).

Entry: close > prior `lookback`-bar Donchian high AND SPY in uptrend regime
(blocks NEW entries only). Exits (either one, both honored even when regime
turns down): (1) parent's close = close < prior `lookback`-bar Donchian low;
(2) trailing stop = price falls `trail_pct` from the running max seen since
entry.

Why edge: parent trade profile (29 trades) shows median max-runup +2.60% but
median max-drawdown -1.27% and 52% of trades touching >=1% drawdown — winners
run, then bleed back before the Donchian low triggers. A trailing stop on the
give-back recovers part of that bleed.

Choosing trail_pct = 0.0140 (1.40%): it must be SMALLER than the median runup
(2.60%) so it fires on the give-back phase, not the run-up — a 2.60%+ trail
would sit above half the winners' entire excursion and rarely bind. It must
also clear normal noise: median per-trade max-drawdown is 1.27%, so a trail
tighter than ~1.3% would whipsaw out on routine pullbacks. 1.40% sits just
above the noise floor (1.27%) yet well under the median runup (2.60%) and the
p75 runup (4.07%), so a typical +2.6% winner keeps running to its peak and
only exits after surrendering 1.40% from that peak — the give-back, by design.

running_max resets to entry_price on every NEW entry (tracked in
position_state[symbol]["running_max"]) and ratchets up each bar we hold; it is
never carried across a flat period.

Regime data: read from market_state["regime"] = {"spy_closes":[...],
"spy_last":float}, pre-populated by the runner/backtester for stocks (None for
crypto). When None the gate is skipped and entry behavior matches the parent.
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
    # Trailing-stop give-back fraction from the running max. Grounded in the
    # parent profile: below median runup (2.60%), above median drawdown-noise
    # (1.27%). See module docstring for the full justification.
    trail_pct = float(params.get("trail_pct", 0.0140))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ---- CLOSE LOGIC ALWAYS RUNS FIRST. No filter below may block an exit. ----

    if holding > 0:
        # Maintain the running max since entry. position_state may not yet have
        # running_max (first bar after a fill) -> seed from entry price, else
        # fall back to current price so the trail always has a reference.
        entry_price = float(pos.get("entry_price", last) or last)
        running_max = pos.get("running_max")
        if running_max is None:
            running_max = entry_price
        running_max = max(float(running_max), last)
        # Persist the ratcheted max so the next bar sees it.
        pos["running_max"] = running_max
        position_state[symbol] = pos

        # (1) Parent's own close signal — close < prior Donchian low.
        if lo is not None and last < lo:
            return Action("close", symbol,
                          reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

        # (2) Trailing stop — price fell trail_pct from the running max.
        trail_level = running_max * (1.0 - trail_pct)
        if last <= trail_level:
            give_back = (running_max - last) / running_max if running_max else 0.0
            return Action("close", symbol,
                          reason=(f"trailing stop: {last:.2f} <= "
                                  f"{trail_level:.2f} (max {running_max:.2f}, "
                                  f"give-back {give_back*100:.2f}% >= "
                                  f"{trail_pct*100:.2f}%)"))

    # ---- ENTRY GATE (entries only; never reached when an exit fired above) ----

    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        # New entry: seed running_max at the entry price (this bar's close).
        new_pos = position_state.get(symbol) or {}
        new_pos["entry_price"] = last
        new_pos["running_max"] = last
        position_state[symbol] = new_pos
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")