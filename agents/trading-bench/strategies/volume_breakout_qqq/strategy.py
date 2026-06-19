"""Volume-Confirmed Breakout on QQQ 1h bars.

Signal family: volume-confirmed price breakout (distinct from pure price
breakout like breakout_xlk which has no volume filter, and from SMA crossover).

Enter long when:
  - price closes above the lookback-bar high (Donchian breakout), AND
  - volume on that bar exceeds volume_mult × the lookback-bar average volume

Exit when price closes below the exit_lookback-bar low.

This double gate (price + volume confirmation) filters out low-conviction
breakouts that are statistically more likely to be false.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from strategies._lib.indicators import closes, highest, lowest


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _volumes(bars: List[dict]) -> List[float]:
    """Extract volume series from bars."""
    return [float(b.get("v", 0)) for b in bars]


def _avg_volume(vols: List[float], period: int) -> Optional[float]:
    """Average volume over last `period` bars."""
    if len(vols) < period or period <= 0:
        return None
    return sum(vols[-period:]) / period


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    lookback = int(params.get("lookback", 20))
    exit_lookback = int(params.get("exit_lookback", 10))
    volume_mult = float(params.get("volume_mult", 1.5))
    notional = float(params.get("notional_usd", 100.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    vs = _volumes(bars)

    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last_close = cs[-1]
    last_vol = vs[-1]

    # Compute breakout level using all bars EXCEPT the last (no lookahead)
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], exit_lookback)
    avg_vol = _avg_volume(vs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if hi is None or avg_vol is None:
        return Action("hold", symbol, reason="insufficient history for breakout")

    if holding == 0:
        # Entry: price breaks above lookback high AND volume spike confirms
        vol_threshold = avg_vol * volume_mult
        if last_close > hi and last_vol > vol_threshold:
            return Action("buy", symbol, notional_usd=notional,
                          reason=(f"close {last_close:.2f} > {lookback}-bar high {hi:.2f} "
                                  f"AND vol {last_vol:.0f} > {volume_mult}x avg {avg_vol:.0f}"))
        return Action("hold", symbol,
                      reason=(f"no vol-breakout (close={last_close:.2f}, hi={hi:.2f}, "
                               f"vol={last_vol:.0f}, avg_vol={avg_vol:.0f}, "
                               f"thresh={avg_vol * volume_mult:.0f})"))

    if holding > 0:
        # Exit: price falls below exit_lookback low
        if lo is not None and last_close < lo:
            return Action("close", symbol,
                          reason=f"close {last_close:.2f} < {exit_lookback}-bar low {lo:.2f}")
        return Action("hold", symbol,
                      reason=f"holding, last={last_close:.2f}, lo={lo}")

    return Action("hold", symbol, reason="fallthrough")
