"""RSI Oversold / Mean-Reversion on SPY 1h bars.

Signal family: mean-reversion (distinct from trend/breakout/SMA crossover).

Enter long when RSI(14) crosses BELOW oversold_threshold (e.g. 30).
Exit when RSI crosses ABOVE exit_rsi (e.g. 60) OR a hard time-stop fires
after time_stop_bars bars from entry.

Stateless except for position_state carrying {entry_bar_idx: int} for the
time-stop. bar_idx is incremented on every tick by reading the bar count
so we can compute bars-held without storing wall-clock time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, rsi


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "SPY")
    rsi_period = int(params.get("rsi_period", 14))
    oversold = float(params.get("oversold_threshold", 30))
    exit_rsi = float(params.get("exit_rsi", 60))
    time_stop = int(params.get("time_stop_bars", 8))
    notional = float(params.get("notional_usd", 100.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    r = rsi(cs, rsi_period)
    n_bars = len(cs)  # total bars visible this tick

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if r is None:
        return Action("hold", symbol, reason=f"not enough bars ({n_bars})")

    # ---- If flat: check for entry ----
    if holding == 0:
        if r < oversold:
            # Record entry bar index in position_state so we can count bars held
            # (position_state is mutable; runner/backtest persists it across ticks)
            position_state["_rsi_spy_entry_bar"] = n_bars
            return Action("buy", symbol, notional_usd=notional,
                          reason=f"RSI={r:.1f} < oversold {oversold}")
        return Action("hold", symbol, reason=f"RSI={r:.1f} (flat, waiting for oversold)")

    # ---- If holding: check exits ----
    entry_bar = position_state.get("_rsi_spy_entry_bar", n_bars)
    bars_held = n_bars - entry_bar

    if r > exit_rsi:
        position_state.pop("_rsi_spy_entry_bar", None)
        return Action("close", symbol,
                      reason=f"RSI={r:.1f} > exit threshold {exit_rsi}")

    if bars_held >= time_stop:
        position_state.pop("_rsi_spy_entry_bar", None)
        return Action("close", symbol,
                      reason=f"time-stop: held {bars_held} bars >= {time_stop}")

    return Action("hold", symbol,
                  reason=f"RSI={r:.1f}, bars_held={bars_held}/{time_stop}")
