"""Donchian breakout on XLK 1h bars (SPY-regime-gated) + post-loss cooldown.

Thesis: identical edge to the parent `breakout_xlk_regime` (long-only
Donchian breakout, enter on close > 20-bar high, exit on close < 20-bar
low, new entries gated to SPY-uptrend regimes), with one addition: after a
trade closes at a realized LOSS (exit price < average entry price), refuse
any NEW entry for the next `loss_cooldown_bars` bars. A fresh realized loss
is weak-but-nonzero evidence the local regime is briefly hostile to this
breakout edge (a volatility spike or failed breakout / reversal); sitting
out a handful of bars lets that worst-case path play through instead of
re-entering straight back into it. Exits are NEVER gated — an already-open
position is always closeable on the parent's own low-breakout signal, and
the runner's safety backstops continue to short-circuit before this code.

Entry signal: close > prior 20-bar high AND SPY > 50d SMA AND no cooldown.
Exit signal:  close < prior 20-bar low (always honored).
Edge: breakout momentum capture, with the regime gate cutting bear-window
bleed and the cooldown skipping the immediate post-loss bars.

Choice of N (loss_cooldown_bars = 10), grounded in the parent profile:
median holding is 34 bars (p25=16, p75=43), so 10 bars is ~0.29x median
holding — inside the sane 0.25-1.0x band, deliberately at the LOW end. It
is shorter than even the quickest-quartile trade (16 bars), so it skips the
immediate hostile bars without structurally blocking re-entry once a fresh
breakout sets up. A much smaller N (3-4) is essentially inert against this
parent's long holds; a much larger N (toward 20+) would eat into the p25
holding window and smother re-entries, so 10 is the conservative middle.

How often it fires: this is a classic low-win-rate breakout (median per-trade
max runup +2.60% vs median max drawdown -1.27%; 52% of trades touched >=1%
drawdown). Realized losses at exit are common but not dominant for this shape
— a reasonable expectation is that roughly 40-55% of the 29 historical trades
close below entry, so the cooldown engages on a meaningful minority of trades
without being active "most of the time." That sits comfortably between the
inert (<10% loss rate) and smothering (>60% loss rate) extremes the directive
warns about, so the directive is a sound fit for this parent rather than a
no-op or a muzzle. (If live loss rate drifts toward either extreme, N should
be revisited — flagged here honestly rather than tuned to hide it.)
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
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    cooldown_n = int(params.get("loss_cooldown_bars", 10))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    # strategy_state survives flat periods, so the cooldown counter persists
    # between trades. Mutating it in place is sufficient (runner re-reads it).
    state = market_state.get("strategy_state")
    if state is None:
        state = {}

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1. Close logic ALWAYS runs first — never gated by cooldown or regime.
    if lo is not None and last < lo and holding > 0:
        # Detect a realized loss BEFORE the close clears position_state, and
        # arm the cooldown in the same call that emits the close.
        entry_px = float(pos.get("avg_entry_price", 0.0) or 0.0)
        if entry_px > 0 and last < entry_px:
            state["cooldown_remaining"] = cooldown_n
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2. Decrement the cooldown once per bar (we only reach here when no exit
    #    fired this bar). Floor at 0; never negative.
    cd = int(state.get("cooldown_remaining", 0) or 0)
    if cd > 0:
        state["cooldown_remaining"] = cd - 1

    # 3. Entry gate: breakout + regime + cooldown. Use the PRE-decrement cd so
    #    a fresh cooldown_remaining=N blocks the next N entry opportunities.
    if hi is not None and last > hi and holding == 0:
        if cd > 0:
            return Action("hold", symbol,
                          reason=f"post-loss cooldown active ({cd} bars left); "
                                 f"breakout signal blocked")
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=(f"cooldown {cd}" if cd > 0 else
                          f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, "
                          f"holding={holding})"))