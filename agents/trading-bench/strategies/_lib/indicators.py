"""Small, dependency-free indicator helpers shared by strategies.

All functions take a list of OHLCV bar dicts (Alpaca shape: {t,o,h,l,c,v})
and return either a float or a list of floats aligned to the input bars.
"""

from __future__ import annotations

from typing import List, Optional


def closes(bars: List[dict]) -> List[float]:
    return [float(b["c"]) for b in bars]


def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) <= period:
        return None
    gains = 0.0
    losses = 0.0
    # seed average over first `period` deltas
    for i in range(1, period + 1):
        ch = values[i] - values[i - 1]
        if ch >= 0:
            gains += ch
        else:
            losses -= ch
    avg_gain = gains / period
    avg_loss = losses / period
    # Wilder smoothing on the rest
    for i in range(period + 1, len(values)):
        ch = values[i] - values[i - 1]
        gain = ch if ch > 0 else 0.0
        loss = -ch if ch < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def highest(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return max(values[-period:])


def lowest(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return min(values[-period:])


def pct_change(values: List[float], lookback: int) -> Optional[float]:
    if len(values) <= lookback or lookback <= 0:
        return None
    a = values[-1 - lookback]
    b = values[-1]
    if a == 0:
        return None
    return (b - a) / a


# ---------------------------------------------------------------------------
# Regime filter (global, market-wide). Takes SPY closes specifically — the
# regime signal is meant to gate per-symbol strategies on broad-market state,
# so all callers should agree on the same reference series.
#
# Strategies opt in by reading `market_state["regime"]`, which the runner /
# backtester pre-populates with {"spy_closes": [...], "spy_last": float}.
# When regime is None (e.g. crypto or SPY bars unavailable), the gate is a
# no-op — strategies treat it as "don't know, behave normally".
# ---------------------------------------------------------------------------

def regime_uptrend(spy_closes: List[float], period: int = 50) -> bool:
    """True iff SPY's last close > SPY's SMA(period).

    Simple, standard 50-day-SMA regime filter. Returns True when we can't
    determine the regime (insufficient bars) — "absence of bearish signal"
    defaults to permissive so strategies can warm up.
    """
    if not spy_closes:
        return True
    s = sma(spy_closes, period)
    if s is None:
        return True
    return spy_closes[-1] > s


def regime_score(spy_closes: List[float], period: int = 50) -> float:
    """Graded regime signal: (last - sma) / sma. Positive => uptrend,
    negative => downtrend, magnitude is the % above/below the MA.

    Returns 0.0 when undeterminable (no bars / too few bars). Designed for
    strategies that want to size position by regime strength rather than
    just gate on/off.
    """
    if not spy_closes:
        return 0.0
    s = sma(spy_closes, period)
    if s is None or s == 0:
        return 0.0
    return (spy_closes[-1] - s) / s
