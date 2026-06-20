"""Donchian-breakout-on-XLK (SPY-regime-gated) PLUS a hard time-stop.

Thesis (mutation): inherit the parent `breakout_xlk_regime` entry/exit/regime
logic unchanged, then add a HARD time-stop that force-closes any open position
after it has been held for `time_stop_bars` bars, regardless of the parent's
Donchian-low exit. The directive's hypothesis is that trades which haven't
resolved within their typical holding window are dead money tying up capital.

Entry signal: close breaks above the prior `lookback`-bar Donchian high AND
SPY is above its `regime_period`-day SMA (regime gate, entries only).
Exit signal: parent's close = price < prior `lookback`-bar Donchian low; OR
the new time-stop = held >= `time_stop_bars` bars (whichever fires first).

Grounding N: the parent profile's per-trade holding distribution is
p25=16, median=34, p75=43 bars at 1Hour. Per the directive, N is set near the
p75 value to force out the slow 25% of trades, so `time_stop_bars` default = 43.

Honest edge note (REQUIRED by directive — did time-stopped trades land in the
profitable or unprofitable bucket?): I computed holding_bars vs realized-return
over the parent's 29 raw trades. The correlation is STRONGLY POSITIVE (+0.955):
the 8 trades that held >= 43 bars averaged +5.98% with a 100% win rate, while
the 21 trades that closed in < 43 bars averaged -0.55% with a 38% win rate. So
for THIS parent the time-stopped (slow) trades were the PROFITABLE bucket, not
dead money — the winners are precisely the long holds. The directive's premise
is therefore inverted for this strategy: a p75 time-stop is expected to amputate
the parent's best cohort and HURT performance. This module exists to let the
walk-forward fitness gate measure that swing honestly rather than assert it; if
the gate rejects it, that is the correct, evidence-driven outcome.

Mechanics: entry-bar bookkeeping is tracked in position_state[symbol], which the
backtester/runner preserves across bars while a position is open and clears on
close. `bars_held` is incremented once per bar the position is visible. The
time-stop is a HARD exit and runs AFTER the parent close signal, exactly like a
stop-loss, so no filter ever blocks an exit. Regime is read from
market_state["regime"]; when None (crypto / SPY unavailable) the gate is a no-op.
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
    # Grounded at the parent profile p75 holding-bars value (43) so the stop
    # forces out the slow ~25% of trades, per the mutation directive.
    time_stop_bars = int(params.get("time_stop_bars", 43))

    cs = closes(market_state.get("bars") or [])
    # Need lookback+1 closes to form the prior-window high/low excluding last.
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # --- EXIT LOGIC FIRST: no filter may ever trap us in an open position. ---

    # (a) Parent's Donchian-low close signal — honored regardless of regime.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # (b) HARD time-stop. Track bars-held in position_state[symbol]; the
    #     backtester/runner persists custom keys here while a position is open
    #     and clears them on close, so the counter auto-resets per trade. We
    #     increment each bar the position is visible, then force-close once the
    #     holding window reaches the p75-grounded threshold. This fires AFTER
    #     the parent close, in the same manner as a stop-loss.
    if holding > 0 and pos is not None:
        bars_held = int(pos.get("bars_held", 0)) + 1
        pos["bars_held"] = bars_held
        if bars_held >= time_stop_bars:
            return Action("close", symbol,
                          reason=f"time-stop: held {bars_held} bars "
                                 f">= {time_stop_bars} (p75 holding window)")

    # --- ENTRY GATE SECOND: regime filter applies to NEW entries only. ---
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