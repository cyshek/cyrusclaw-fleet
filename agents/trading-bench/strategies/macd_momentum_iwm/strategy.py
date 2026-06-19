"""MACD Momentum on IWM 1h bars.

Signal family: momentum via MACD oscillator (distinct from RSI mean-reversion,
price/volume breakout, and SMA crossover).

Enter long when:
  - MACD line (EMA_fast − EMA_slow) crosses ABOVE the signal line (EMA_signal of MACD), AND
  - MACD > 0 (above zero line, confirming broad uptrend)

Exit when MACD line crosses BELOW the signal line.

Uses Wilder-style EMA (exponential moving average) consistent with the
existing indicators.py style but implemented locally because EMA isn't in
the shared _lib yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from strategies._lib.indicators import closes


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _ema_series(values: List[float], period: int) -> List[float]:
    """Compute EMA series for all values. Returns empty list if insufficient data.

    Uses the standard EMA formula: EMA_i = alpha * val_i + (1 - alpha) * EMA_{i-1}
    where alpha = 2 / (period + 1). Seeded with the SMA of the first `period` values.
    """
    if len(values) < period:
        return []
    alpha = 2.0 / (period + 1.0)
    ema = [sum(values[:period]) / period]
    for val in values[period:]:
        ema.append(alpha * val + (1.0 - alpha) * ema[-1])
    return ema


def _macd(values: List[float], fast: int, slow: int,
          signal: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Compute current MACD line, signal line, and histogram.

    Returns (macd_val, signal_val, histogram) or (None, None, None) if
    insufficient data.

    macd_line  = EMA(fast) - EMA(slow)
    signal_line = EMA(signal) of macd_line series
    histogram  = macd_line - signal_line
    """
    if len(values) < slow + signal:
        return (None, None, None)

    # Build full EMA series (both start from their respective warmup lengths)
    ema_fast_series = _ema_series(values, fast)
    ema_slow_series = _ema_series(values, slow)

    if not ema_fast_series or not ema_slow_series:
        return (None, None, None)

    # Align: EMA_fast has len(values)-fast+1 values, EMA_slow has len(values)-slow+1.
    # MACD = EMA_fast - EMA_slow for the OVERLAPPING tail.
    n_fast = len(ema_fast_series)
    n_slow = len(ema_slow_series)
    min_n = min(n_fast, n_slow)
    macd_line_series = [
        ema_fast_series[n_fast - min_n + i] - ema_slow_series[n_slow - min_n + i]
        for i in range(min_n)
    ]

    if len(macd_line_series) < signal:
        return (None, None, None)

    signal_series = _ema_series(macd_line_series, signal)
    if not signal_series:
        return (None, None, None)

    macd_val = macd_line_series[-1]
    signal_val = signal_series[-1]
    histogram = macd_val - signal_val
    return (macd_val, signal_val, histogram)


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal = int(params.get("signal", 9))
    notional = float(params.get("notional_usd", 100.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    macd_val, signal_val, histogram = _macd(cs, fast, slow, signal)

    if macd_val is None:
        return Action("hold", symbol, reason=f"not enough bars for MACD ({len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    prev_macd = position_state.get("_macd_prev_macd")
    prev_signal = position_state.get("_macd_prev_signal")

    # Update stored prev values BEFORE return so next tick sees them
    position_state["_macd_prev_macd"] = macd_val
    position_state["_macd_prev_signal"] = signal_val

    if holding == 0:
        # Entry: MACD crosses ABOVE signal AND MACD > 0 (uptrend confirmed)
        crossed_above = (prev_macd is not None and prev_signal is not None
                         and prev_macd <= prev_signal  # was at or below
                         and macd_val > signal_val)     # now above
        if crossed_above and macd_val > 0:
            return Action("buy", symbol, notional_usd=notional,
                          reason=(f"MACD={macd_val:.4f} crossed above signal={signal_val:.4f} "
                                  f"and MACD>0 (momentum bullish)"))
        return Action("hold", symbol,
                      reason=(f"MACD={macd_val:.4f}, signal={signal_val:.4f}, "
                               f"hist={histogram:.4f}, flat"))

    if holding > 0:
        # Exit: MACD crosses BELOW signal line
        crossed_below = (prev_macd is not None and prev_signal is not None
                         and prev_macd >= prev_signal  # was at or above
                         and macd_val < signal_val)     # now below
        if crossed_below:
            return Action("close", symbol,
                          reason=(f"MACD={macd_val:.4f} crossed below signal={signal_val:.4f}"))
        return Action("hold", symbol,
                      reason=(f"MACD={macd_val:.4f}, signal={signal_val:.4f}, holding"))

    return Action("hold", symbol, reason="fallthrough")
