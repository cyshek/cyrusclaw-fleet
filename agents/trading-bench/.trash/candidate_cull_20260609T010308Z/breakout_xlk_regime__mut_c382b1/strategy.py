"""Donchian breakout on XLK 1h bars (SPY-regime entry gate) PLUS a
regime-CONDITIONAL hard stop-loss on exits.

Parent (`breakout_xlk_regime`): long-only Donchian breakout whose regime
filter only gates ENTRIES. This mutation adds what the parent lacks —
regime-conditional EXIT behavior — by attaching a hard stop-loss whose
tightness flips with the broad-market regime:

  - SPY BELOW its 50d SMA (bear/chop): TIGHT stop of 0.60% below entry.
    Grounded between the parent's p75 (-0.52%) and median (-1.27%) per-trade
    drawdown, so in a downtrend the stop bites on a meaningful slice of
    trades (the parent touched >=1% drawdown on 52% of trades) and cuts the
    bear bleed the long-only book suffers.
  - SPY ABOVE its 50d SMA (bull): LOOSE stop of 1.80% below entry, just
    beyond the parent's p25 (-1.66%) deepest-tail drawdown. At/beyond p25 it
    is nearly inert historically (it would have fired on almost no past
    trade), so winning trends are allowed to breathe and only a genuinely
    catastrophic excursion is cut.

Entry signal: close > prior `lookback`-bar high AND (regime up OR unknown).
Exit signals (checked BEFORE the entry gate so a filter can never trap us
long): (a) parent's Donchian close — close < prior `lookback`-bar low — is
always honored; (b) the new regime-conditional hard stop. Edge thesis: keep
the parent's bull/chop breakout edge intact while adding asymmetric
downside protection that is aggressive exactly when the market regime says
losers are most likely to keep losing.

Regime data: `market_state["regime"]` = {"spy_closes": [...], "spy_last": ...}.
When regime is None (crypto / SPY bars unavailable) we fall through: entry
gate is skipped (parent behavior) and the stop defaults to the LOOSE band so
we don't over-tighten on an unknown regime.

Entry price for the stop comes from `position_state[symbol]["avg_entry_price"]`
(fallbacks: "avg_price", "entry_price", "cost_basis"); if no entry price is
recoverable the stop is skipped for that bar — the parent's own close signal
still protects the position.
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


def _entry_price(pos: dict) -> Optional[float]:
    """Best-effort recovery of the position's average entry price."""
    for key in ("avg_entry_price", "avg_price", "entry_price", "cost_basis"):
        v = pos.get(key)
        if v is not None:
            try:
                p = float(v)
            except (TypeError, ValueError):
                continue
            if p > 0:
                return p
    return None


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    # Grounded in PARENT PROFILE per-trade max-drawdown distribution:
    #   tight  -> between p75 (-0.52%) and median (-1.27%)  => 0.60%
    #   loose  -> just beyond p25 deepest tail (-1.66%)     => 1.80%
    tight_stop = float(params.get("tight_stop_pct", 0.0060))
    loose_stop = float(params.get("loose_stop_pct", 0.0180))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ----- CLOSE LOGIC ALWAYS RUNS FIRST. No filter below may block an exit. -----
    if holding > 0:
        # (a) Parent's own Donchian close signal — always honored.
        if lo is not None and last < lo:
            return Action("close", symbol,
                          reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

        # (b) Regime-conditional hard stop-loss.
        regime = market_state.get("regime")
        # Default to LOOSE when regime is unknown (don't over-tighten blind).
        bear = False
        if regime:
            bear = not regime_uptrend(regime.get("spy_closes") or [],
                                      period=regime_period)
        stop_pct = tight_stop if bear else loose_stop

        entry = _entry_price(pos) if pos else None
        if entry is not None:
            stop_price = entry * (1.0 - stop_pct)
            if last <= stop_price:
                band = "tight/bear" if bear else "loose/bull"
                return Action("close", symbol,
                              reason=(f"stop {last:.2f} <= {stop_price:.2f} "
                                      f"({stop_pct*100:.2f}% {band} stop, "
                                      f"entry {entry:.2f})"))

    # ----- ENTRY GATE (entries only; never reached while we should be exiting) -----
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")