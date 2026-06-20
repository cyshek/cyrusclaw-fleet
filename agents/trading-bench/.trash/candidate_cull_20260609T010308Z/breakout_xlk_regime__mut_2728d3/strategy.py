"""Donchian breakout on XLK 1h bars (SPY-regime gated) + POST-LOSS COOLDOWN.

Inherits the parent `breakout_xlk_regime`: long-only Donchian breakout
(enter when last close > prior `lookback`-bar high; exit when last close <
prior `lookback`-bar low), with new entries gated to SPY-uptrend windows.

NEW THIS MUTATION — post-loss cooldown. After a close that realized a loss
(exit last_price < the position's avg_entry_price, fees ignored as a
good-enough proxy), refuse ANY new entry for the next `loss_cooldown_bars`
bars. The counter lives in `market_state['strategy_state']` (NOT
position_state, which is wiped on close) so it survives the flat period
between trades; it is decremented by 1 on every flat bar and floored at 0.
Thesis: a fresh realized loss is weak-but-nonzero evidence the local regime
just turned hostile to a breakout edge (vol spike / failed breakout /
reversal). Sitting out N bars lets the worst-case path play through instead
of re-entering straight back into it.

Exits are NEVER gated by the cooldown — close-logic runs first and always
fires on the parent's price<Donchian-low signal (and the runner's safety
backstops short-circuit before this code regardless). The cooldown gates
ENTRIES ONLY.

Choice of N = 12 bars. Parent holding distribution (1Hour): p25 16 / median
34 / p75 43 bars. 12 is ~0.35x the median hold — inside the sane 0.25–1.0x
band the directive specifies: large enough not to be inert (a 2–3 bar
cooldown would clear before any vol spike resolves), small enough that it
does not swallow whole subsequent setups (a 30+ bar cooldown would routinely
eat the next entire trade). ~12 bars at 1Hour is roughly 1.5 trading days of
sit-out.

Expected fire rate: the parent's exit is a Donchian-low stop, so a
meaningful share of trades close red — empirically 52% of trades touched
>=1% drawdown and median per-trade drawdown is -1.27% vs median runup
+2.60%, which puts the realized-loss (exit<entry) rate plausibly in the
~35–50% range. That is squarely in the band where this directive is
neither inert (<10% loss rate) nor smothering (>60%): the cooldown should
engage after a fair fraction of trades but still leave the strategy free to
trade most of the time. If live behavior shows the loss rate far outside
that range, this directive is a poor fit for this parent and N should be
revisited rather than tuned to hide it.
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
    cooldown_n = int(params.get("loss_cooldown_bars", 12))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    # strategy_state survives flat periods; runner re-reads it after decide().
    state = market_state.get("strategy_state")
    if state is None:
        state = {}

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1. Close logic ALWAYS runs first — never gated by regime or cooldown.
    if lo is not None and last < lo and holding > 0:
        # Detect realized loss BEFORE the close wipes position_state[symbol].
        entry_px = float(pos.get("avg_entry_price", 0.0) or 0.0) if pos else 0.0
        if entry_px > 0 and last < entry_px:
            state["cooldown_remaining"] = cooldown_n
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2. Decrement the cooldown once per flat bar (exits above already
    #    returned). Read the pre-decrement value for the entry gate so a
    #    fresh cooldown_remaining=N blocks the NEXT N entries, not N-1.
    cd = int(state.get("cooldown_remaining", 0) or 0)
    if cd > 0:
        state["cooldown_remaining"] = cd - 1

    # 3. Entry gate: regime filter + post-loss cooldown. Entries only.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if cd > 0:
            return Action("hold", symbol,
                          reason=f"post-loss cooldown {cd} bars left "
                                 f"(breakout signal blocked)")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=(f"cooldown {cd}" if cd > 0
                          else f"no breakout (last={last:.2f}, hi={hi}, "
                               f"lo={lo}, holding={holding})"))