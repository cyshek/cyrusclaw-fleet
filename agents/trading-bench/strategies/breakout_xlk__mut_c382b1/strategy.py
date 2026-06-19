"""Donchian breakout on XLK 1h bars with a REGIME-CONDITIONAL hard stop-loss.

Variant of `breakout_xlk`. The parent is a long-only Donchian breakout whose
only exit is price closing below the N-bar low. This mutation adds a second,
regime-dependent exit: a hard stop measured from the position's entry price,
whose tightness flexes with the broad-market regime (SPY vs its 50d SMA).

Thesis: the parent's per-trade drawdowns are regime-sensitive. In a bull
regime (SPY above its 50d SMA) breakouts that dip should be given room to
recover — chopping them out early forfeits the winners (parent median runup
+2.60%, p75 +4.11%). In a bear/chop regime (SPY below its 50d SMA) the same
dip is far more likely to keep going against us, so we cut fast.

Entry: unchanged from parent — close > prior `lookback`-bar high, flat only.
Exit: (1) parent's Donchian-low close ALWAYS honored first; (2) regime stop —
  - BEAR (SPY < 50d SMA): TIGHT stop at `stop_bear_pct` = -0.80%. Grounded
    between the parent's p75 per-trade drawdown (-0.70%, the shallow tail)
    and the median (-1.41%). Sitting just past p75 means it would have fired
    on a meaningful slice of historical trades — well inside the live
    distribution (64% of trades touched >=1% DD) — without being pure noise.
  - BULL (SPY >= 50d SMA): LOOSE stop at `stop_bull_pct` = -2.30%. Grounded
    just BEYOND the parent's p25 per-trade drawdown (-2.21%, the deep tail).
    Past p25 it is nearly inert in normal bull trades (it almost never fired
    historically) and only catches genuine breakdowns, letting trends breathe.
Edge: keep the parent's bull/chop winners intact while truncating the fat
left tail that only shows up when the market regime has already rolled over.

Stop is an ADDITIONAL exit — it never blocks the parent's own close signal,
and the entry gate runs last so no filter can ever trap an open position.
Regime data: `market_state["regime"]` = {"spy_closes": [...], "spy_last": ...}.
When regime is None (crypto / SPY unavailable) the stop defaults to the LOOSE
threshold (permissive) so behavior degrades gracefully toward the parent.
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
    stop_bear_pct = float(params.get("stop_bear_pct", -0.80))
    stop_bull_pct = float(params.get("stop_bull_pct", -2.30))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # (1) Parent close logic ALWAYS runs first — never blocked by any filter.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # (2) Regime-conditional hard stop on an OPEN position (additional exit).
    if holding > 0:
        entry = pos.get("avg_entry_price", pos.get("entry_price"))
        try:
            entry = float(entry) if entry is not None else 0.0
        except (TypeError, ValueError):
            entry = 0.0
        if entry > 0:
            pnl_pct = (last - entry) / entry * 100.0
            regime = market_state.get("regime")
            # Bear regime => tight stop; bull / unknown => loose stop.
            if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                             period=regime_period):
                stop_pct = stop_bear_pct
                tag = "bear/tight"
            else:
                stop_pct = stop_bull_pct
                tag = "bull/loose"
            if pnl_pct <= stop_pct:
                return Action("close", symbol,
                              reason=f"regime stop [{tag}] {pnl_pct:.2f}% "
                                     f"<= {stop_pct:.2f}% (entry {entry:.2f})")

    # (3) Entry gate runs LAST so it can never trap an open position.
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")