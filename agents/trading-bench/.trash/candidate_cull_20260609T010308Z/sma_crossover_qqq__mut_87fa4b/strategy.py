"""Mean-reversion pullback on IWM 1h bars (contrarian variant of sma_crossover_qqq).

Thesis: small-cap IWM mean-reverts intraday — sharp pullbacks below a recent
price floor tend to snap back toward the local mean rather than continue. So
instead of buying breakouts (parent's trend-following crossover), we BUY the
dip: enter long when the last close prints below the N-bar low band AND RSI is
oversold (momentum exhausted), confirming a stretched-down move rather than a
clean trend-down.

Entry: close < lowest(N-bar) band AND RSI(rsi_period) < rsi_oversold, while flat.
Exit (all checked BEFORE the entry gate so a position is always closeable):
  - take-profit: price recovered +tp_pct from entry (lock the bounce),
  - stop-loss:   price fell another -sl_pct from entry (thesis wrong / breakdown),
  - mean-revert target: price climbed back above the SMA(mid_period) midline,
  - time-stop:   held >= max_hold bars (stale, bounce never came).

Edge: the parent bleeds buying strength near local highs; a contrarian dip-buy
on a genuine mean-reverter harvests the snap-back. Thresholds are grounded in
the parent's empirical trade distribution (median max drawdown 1.14%, median
max runup 1.17%, median hold 20 bars), not round guesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, lowest, sma, rsi


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    band_period = int(params.get("band_period", 20))
    mid_period = int(params.get("mid_period", 20))
    rsi_period = int(params.get("rsi_period", 14))
    rsi_oversold = float(params.get("rsi_oversold", 35.0))
    tp_pct = float(params.get("tp_pct", 0.0115))   # +1.15% ~ parent median max runup
    sl_pct = float(params.get("sl_pct", 0.016))    # -1.6% ~ parent p25 max drawdown
    max_hold = int(params.get("max_hold", 39))     # ~ parent p75 holding period
    notional = float(params.get("notional_usd", 1000.0))

    cs = closes(market_state.get("bars") or [])
    need = max(band_period + 1, mid_period, rsi_period + 1)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    lo = lowest(cs[:-1], band_period)
    mid = sma(cs, mid_period)
    r = rsi(cs, rsi_period)

    pos = position_state.get(symbol) if position_state else None
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_px = float(pos.get("avg_entry_price", 0) or 0) if pos else 0.0
    bars_held = int(pos.get("bars_held", 0) or 0) if pos else 0

    # ---- Close logic ALWAYS runs first: a position must always be closeable. ----
    if holding > 0 and entry_px > 0:
        if last >= entry_px * (1.0 + tp_pct):
            return Action("close", symbol,
                          reason=f"take-profit {last:.2f} >= entry {entry_px:.2f} +{tp_pct:.3%}")
        if last <= entry_px * (1.0 - sl_pct):
            return Action("close", symbol,
                          reason=f"stop-loss {last:.2f} <= entry {entry_px:.2f} -{sl_pct:.3%}")
        if mid is not None and last >= mid:
            return Action("close", symbol,
                          reason=f"mean-revert target: {last:.2f} >= SMA{mid_period} {mid:.2f}")
        if bars_held >= max_hold:
            return Action("close", symbol,
                          reason=f"time-stop: held {bars_held} >= {max_hold} bars")
        return Action("hold", symbol,
                      reason=f"holding (last={last:.2f}, entry={entry_px:.2f}, "
                             f"mid={mid}, bars_held={bars_held})")

    # ---- Entry gate (only when flat): dip below band AND oversold RSI. ----
    if holding == 0 and lo is not None and r is not None and last < lo and r < rsi_oversold:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"pullback {last:.2f} < {band_period}-bar low {lo:.2f} "
                             f"& RSI{rsi_period}={r:.1f} < {rsi_oversold:.0f}")

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, lo={lo}, "
                         f"rsi={None if r is None else round(r,1)}, holding={holding})")