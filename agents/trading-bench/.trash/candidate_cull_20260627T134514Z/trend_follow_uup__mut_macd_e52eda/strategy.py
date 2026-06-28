"""UUP dollar-trend carrier WIDENED with a MACD-momentum entry (OR-combined).

PAPER ONLY. No real money.

THESIS: The parent (trend_follow_uup) is a thin SMA(50) trend on the US-dollar
ETF UUP. On its own it fires rarely (3 closed trades across the walk-forward
panel) because a single slow MA crossover on a low-vol dollar series produces
few signals. This child ADDS a second, faster entry channel: MACD momentum on
UUP's OWN daily closes (MACD = EMA12 - EMA26; signal = EMA9 of MACD). We go long
when EITHER the slow trend is up (close > SMA(period)) OR a fresh bullish MACD
cross fires (MACD crosses above its signal line while MACD > 0).

WHY OR, NOT AND: an earlier AND-combo made UUP effectively inert — requiring BOTH
a slow-trend AND a momentum cross on an already-thin dollar series almost never
co-occurs, so it traded ~never. OR is the correct combinator here because the two
signals are complementary, not confirmatory: SMA(50) captures the slow persistent
dollar regime, the MACD cross captures faster momentum bursts the slow MA misses.
ORing them ADDS entries (the explicit mutation goal — give the thin dollar-trend
MORE entries) while each remains a legitimate long-trend signal in its own right.

EXIT (also OR-combined, always reachable): close when close < SMA(period) OR the
MACD line crosses back below its signal line. Either deterioration — losing the
slow trend OR losing momentum — flattens us. Exits are evaluated BEFORE any entry
logic so a held position is always closeable regardless of entry conditions.

EMA is not in strategies/_lib.indicators, so it's implemented locally below using
only `math`/`statistics`-class arithmetic (a plain iterative EMA recurrence) per
the allowed-imports rule.

BAR SHAPE: the live gate path feeds Alpaca-shape bars {c,h,l,o,t,v,vw}. This reads
close via 'c' (falling back to 'close'/'adjclose') so it works in both the gate
harness and any cache shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _bar_close(b: dict) -> Optional[float]:
    """Close from an Alpaca-shape bar ('c') or a cache-shape bar
    ('close'/'adjclose'). Returns None if unparseable."""
    v = b.get("c")
    if v is None:
        v = b.get("close")
    if v is None:
        v = b.get("adjclose")
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _closes(bars: List[dict]) -> List[float]:
    out: List[float] = []
    for b in bars or []:
        c = _bar_close(b)
        if c is not None:
            out.append(c)
    return out


def _ema_series(values: List[float], period: int) -> List[float]:
    """Iterative EMA over `values`, returned aligned to the input (same length).

    Seeds with the first value (standard recursive EMA). Uses only plain
    arithmetic — no external libs. Caller must ensure period >= 1.
    """
    if period <= 0:
        period = 1
    k = 2.0 / (period + 1.0)
    out: List[float] = []
    prev: Optional[float] = None
    for v in values:
        if prev is None:
            prev = v
        else:
            prev = v * k + prev * (1.0 - k)
        out.append(prev)
    return out


def _macd_lines(values: List[float], fast: int, slow: int, signal: int):
    """Return (macd_series, signal_series) aligned to `values`.

    macd = EMA(fast) - EMA(slow); signal = EMA(signal) of the macd series.
    """
    ema_fast = _ema_series(values, fast)
    ema_slow = _ema_series(values, slow)
    macd = [f - s for f, s in zip(ema_fast, ema_slow)]
    sig = _ema_series(macd, signal)
    return macd, sig


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "UUP")
    period = int(params.get("period", 50))
    fast = int(params.get("macd_fast", 12))
    slow = int(params.get("macd_slow", 26))
    signal = int(params.get("macd_signal", 9))
    notional = float(params.get("notional_usd", 1000.0))

    cs = _closes(market_state.get("bars") or [])

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Need enough bars for BOTH the SMA and a stable MACD with one prior bar
    # (so we can detect a cross). slow+signal warms the MACD; +1 gives a
    # previous bar for the crossover comparison.
    need = max(period, slow + signal) + 1
    if len(cs) < need:
        return Action("hold", symbol,
                      reason=f"not enough bars ({len(cs)}<{need})")

    sma = sum(cs[-period:]) / period
    last = cs[-1]

    macd, sig = _macd_lines(cs, fast, slow, signal)
    macd_now, macd_prev = macd[-1], macd[-2]
    sig_now, sig_prev = sig[-1], sig[-2]

    trend_up = last > sma
    cross_up = (macd_prev <= sig_prev) and (macd_now > sig_now) and (macd_now > 0)
    cross_down = (macd_prev >= sig_prev) and (macd_now < sig_now)

    # --- EXITS FIRST (always reachable): lose the trend OR lose momentum. ---
    if holding > 0 and ((last < sma) or cross_down):
        why = []
        if last < sma:
            why.append(f"close {last:.4f} < SMA{period} {sma:.4f}")
        if cross_down:
            why.append(f"MACD {macd_now:.4f} crossed below signal {sig_now:.4f}")
        return Action("close", symbol, reason="exit: " + " AND ".join(why))

    # --- ENTRIES (OR-combined): slow trend up OR fresh bullish MACD cross. ---
    if holding == 0 and (trend_up or cross_up):
        why = []
        if trend_up:
            why.append(f"close {last:.4f} > SMA{period} {sma:.4f}")
        if cross_up:
            why.append(f"MACD {macd_now:.4f} crossed above signal "
                        f"{sig_now:.4f} (MACD>0)")
        return Action("buy", symbol, notional_usd=notional,
                      reason="entry (OR): " + " OR ".join(why))

    return Action("hold", symbol,
                  reason=(f"close {last:.4f}, SMA{period} {sma:.4f}, "
                          f"MACD {macd_now:.4f}/{sig_now:.4f}, holding={holding:g}"))