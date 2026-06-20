"""Donchian breakout on XLK 1h bars with a regime-conditional hard stop-loss.

Entry: classic Donchian breakout — buy when last close exceeds the prior
`lookback`-bar high. Exit: original Donchian exit (close < `lookback`-bar low)
PLUS a regime-conditional hard stop-loss measured against the entry price
stored in `position_state[symbol]["avg_entry_price"]`.

Stop-loss thresholds are grounded in the parent's empirical per-trade
drawdown distribution (n=45):
  - p75 (shallow tail) = -0.70%, median = -1.41%, p25 (deep tail) = -2.21%.
When SPY is BELOW its 50d SMA (bear/chop), we use a TIGHT stop at 0.80%,
just outside p75 — close to the median, so it would have fired on roughly
half of historical trades, cutting bleed in unfavorable regimes. When SPY
is ABOVE its 50d SMA (bull), we use a LOOSE stop at 2.20%, essentially at
p25 — only the deepest historical drawdowns would have tripped it, letting
trends breathe. When regime data is unavailable (None), default to the
loose stop so we don't over-trim crypto/warmup cases.

The hard stop NEVER blocks the parent's Donchian close signal; close-logic
runs first and the stop is an additional exit path layered on top.
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
    stop_tight_pct = float(params.get("stop_tight_pct", 0.008))   # 0.80%, bear/chop
    stop_loose_pct = float(params.get("stop_loose_pct", 0.022))   # 2.20%, bull

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # 1) Parent's Donchian close signal ALWAYS runs first — never blocked.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) Regime-conditional hard stop-loss (only when long).
    if holding > 0:
        entry = float(pos.get("avg_entry_price", 0.0) or 0.0)
        if entry > 0:
            regime = market_state.get("regime")
            if regime is None:
                bull = True  # unknown regime -> loose stop, parent-like behavior
            else:
                bull = regime_uptrend(regime.get("spy_closes") or [],
                                      period=regime_period)
            stop_pct = stop_loose_pct if bull else stop_tight_pct
            drawdown = (last - entry) / entry
            if drawdown <= -stop_pct:
                tag = "bull/loose" if bull else "bear/tight"
                return Action("close", symbol,
                              reason=f"stop-loss ({tag} {stop_pct*100:.2f}%): "
                                     f"dd={drawdown*100:.2f}% "
                                     f"(entry={entry:.2f}, last={last:.2f})")

    # 3) Entry: parent breakout signal, no regime gate (parent had none).
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")