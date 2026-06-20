"""Bollinger-style mean-reversion on IWM 1h bars, gated by SPY regime.

Contrarian mutation of the SMA-crossover parent: instead of chasing
trend continuation, this strategy fades short-term dislocations on IWM
(small-caps, which mean-revert more reliably than QQQ momentum names).

Entry: close drops below the lower band (SMA(period) - k * stdev) — a
statistically stretched pullback inside an otherwise-healthy tape. The
SPY regime gate still applies to ENTRIES ONLY: we only fade pullbacks
when the broad market is above its 50d SMA, so we're buying dips in an
uptrend rather than catching falling knives in a bear.

Exit: close back through the middle band (SMA(period)) — the mean-revert
thesis has played out. A hard stop at `stop_pct` below entry caps the
downside on trades where mean-reversion fails. Stop and middle-band exits
ignore the regime gate so an open position is always closeable.

Thresholds are grounded in the parent's per-trade distribution: median
runup +1.34% (target ~middle band, typically ~1% move), median drawdown
-0.76% (stop set just past p25 at 1.20% so it fires on the deeper-tail
trades without being inert). Holding-period median ~26 bars matches the
20-bar band lookback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import statistics

from strategies._lib.indicators import closes, sma, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    period = int(params.get("period", 20))
    k = float(params.get("k_stdev", 2.0))
    stop_pct = float(params.get("stop_pct", 0.012))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < period + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    mid = sma(cs, period)
    if mid is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    window = cs[-period:]
    sd = statistics.pstdev(window)
    lower = mid - k * sd
    upper = mid + k * sd

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0) or 0)
    entry_px = float(pos.get("avg_entry_price", 0) or 0)

    # --- EXITS FIRST (never gated) ---
    if holding > 0:
        # Hard stop: cap losses when mean-reversion fails.
        if entry_px > 0 and last <= entry_px * (1.0 - stop_pct):
            return Action("close", symbol,
                          reason=f"stop {last:.2f} <= entry {entry_px:.2f} * "
                                 f"(1-{stop_pct:.4f})")
        # Mean-revert target: close back through middle band.
        if last >= mid:
            return Action("close", symbol,
                          reason=f"revert {last:.2f} >= SMA{period}={mid:.2f}")

    # --- ENTRY (regime-gated) ---
    if holding == 0 and last < lower:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(pullback entry blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"pullback {last:.2f} < lower {lower:.2f} "
                             f"(mid={mid:.2f}, sd={sd:.4f})")

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, lower={lower:.2f}, "
                         f"upper={upper:.2f}, holding={holding})")