"""Donchian-band mean reversion on IWM 1h bars (contrarian flip of breakout_xlk).

Thesis: small-cap index IWM tends to mean-revert intraday/swing — sharp
pullbacks to a Donchian lower band are statistically more likely to bounce
than to keep trending, the opposite of the parent's breakout edge. So we BUY
the pullback (close below the N-bar low) instead of the breakout, and harvest
the reversion back toward the band's mid.

Entry: flat AND close < N-bar lowest low (a fresh down-extreme). We fade it.
Exit (whichever first, all checked BEFORE the entry gate so a position is
always closeable):
  - take-profit: unrealized >= tp_pct (reversion captured),
  - stop-loss:   unrealized <= -sl_pct (the dip kept going — cut it),
  - mean-revert target: close climbs back above the Donchian MID (hi+lo)/2,
  - time-stop: held >= max_hold_bars without resolving (dead trade).

Edge rationale: the parent's own trade distribution shows median per-trade
runup +2.60% and median drawdown -1.41%; a mean-reverter entering at the
lower extreme should see a similar bounce magnitude, so tp/sl are sized inside
that empirical band rather than guessed. There is no regime gate on entries
here by design — but if one were added it must not block exits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    tp_pct = float(params.get("tp_pct", 2.0))
    sl_pct = float(params.get("sl_pct", 2.0))
    max_hold_bars = int(params.get("max_hold_bars", 43))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)
    mid = (hi + lo) / 2.0 if (hi is not None and lo is not None) else None

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_px = float(pos.get("avg_entry_price", 0) or 0) if pos else 0.0
    bars_held = int(pos.get("bars_held", 0) or 0) if pos else 0

    # ---- CLOSE LOGIC FIRST: an open position must always be exitable. ----
    if holding > 0:
        if entry_px > 0:
            unreal = (last - entry_px) / entry_px * 100.0
            if unreal >= tp_pct:
                return Action("close", symbol,
                              reason=f"take-profit {unreal:.2f}% >= {tp_pct:.2f}%")
            if unreal <= -sl_pct:
                return Action("close", symbol,
                              reason=f"stop-loss {unreal:.2f}% <= -{sl_pct:.2f}%")
        if mid is not None and last >= mid:
            return Action("close", symbol,
                          reason=f"reverted to mid {mid:.2f} (last={last:.2f})")
        if bars_held >= max_hold_bars:
            return Action("close", symbol,
                          reason=f"time-stop {bars_held} >= {max_hold_bars} bars")
        return Action("hold", symbol,
                      reason=f"holding, awaiting reversion (last={last:.2f}, mid={mid})")

    # ---- ENTRY GATE: fade the down-extreme. ----
    if lo is not None and last < lo:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"pullback: close {last:.2f} < {lookback}-bar low {lo:.2f}")
    return Action("hold", symbol,
                  reason=f"no pullback (last={last:.2f}, lo={lo}, mid={mid})")