"""Donchian breakout on SMH (semiconductor ETF) 1h bars, SPY-regime gated, with
empirically-grounded stop-loss and take-profit overlays.

Port of `breakout_xlk_regime` from XLK to SMH — same tech asset class, same
breakout-plus-regime logic. SMH is semiconductor-concentrated (a higher-beta
slice of the tech complex than the broad XLK), so the same Donchian-breakout
edge should be present but expressed with larger per-trade swings.

Thesis: a 20-bar Donchian breakout captures momentum continuation in trending
tech; gating new entries on SPY > 50d SMA preserves the bull/chop edge while
refusing to enter long into broad-market downtrends (the parent's bear bleed).

Entry: last close > prior 20-bar high AND SPY in uptrend AND flat.
Exit (any one, evaluated BEFORE the entry gate so a filter can never trap us):
  (1) price < prior 20-bar Donchian low  — the parent's native exit;
  (2) drawdown from entry <= -stop_loss_pct — caps the loss tail;
  (3) runup from entry >= take_profit_pct — banks the winner.
Stop/TP are grounded in the parent's empirical per-trade distribution (median
max drawdown -1.27%, median max runup +2.60%): stop at -1.2% would have fired
on ~half of historical trades (and sits inside the p25 -1.66% tail so it is not
inert); TP at +2.5% sits at/below the +2.60% median runup so it locks in at
least half the winners while staying below the +4.07% p75 (not inert).

Edge: same breakout-momentum + regime-protection edge as the parent, now with
an explicit risk-symmetry overlay tuned to where this family of trades actually
moves, on a higher-beta tech vehicle.
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
    symbol = params.get("symbol", "SMH")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    # Grounded in parent profile: median max drawdown -1.27% (p25 -1.66%),
    # median max runup +2.60% (p75 +4.07%).
    stop_loss_pct = float(params.get("stop_loss_pct", 0.012))
    take_profit_pct = float(params.get("take_profit_pct", 0.025))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_px = float(pos.get("avg_entry_price", 0.0)) if pos else 0.0

    # --- Close logic ALWAYS runs first: no filter may trap an open position. ---
    if holding > 0:
        # (1) native Donchian-low exit
        if lo is not None and last < lo:
            return Action("close", symbol,
                          reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")
        # (2)/(3) stop-loss / take-profit relative to entry, when we know entry
        if entry_px > 0:
            chg = (last - entry_px) / entry_px
            if chg <= -stop_loss_pct:
                return Action("close", symbol,
                              reason=f"stop-loss {chg*100:.2f}% <= -{stop_loss_pct*100:.2f}%")
            if chg >= take_profit_pct:
                return Action("close", symbol,
                              reason=f"take-profit {chg*100:.2f}% >= {take_profit_pct*100:.2f}%")

    # --- Entry gate: regime filter applies to NEW entries only. ---
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