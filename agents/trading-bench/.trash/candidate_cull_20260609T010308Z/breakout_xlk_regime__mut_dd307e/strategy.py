"""Donchian breakout on XLK 1h bars, gated by SPY-trend regime AND a US-session time-of-day filter.

Variant of `breakout_xlk_regime`. It keeps the parent's two ideas — Donchian
breakout entries and a SPY-above-50d-SMA regime gate — and adds a third gate:
new long entries are only allowed during the US regular session, 14:30-20:00
UTC. Hypothesis: breakout signals that fire outside regular trading hours (in
thin pre/post-market 1h bars) are lower-quality and more prone to whipsaw;
restricting entries to the liquid regular session should keep the genuine
intraday-momentum breakouts while dropping the noisy off-session ones.

Entry signal: last close > prior `lookback`-bar Donchian high, AND SPY is in
an uptrend (regime gate), AND the current bar's UTC timestamp falls inside the
14:30-20:00 session window. Exit signal: last close < prior `lookback`-bar
Donchian low — fired ANY time, no gate. Edge: trades only the part of the day
where institutional flow makes breakouts stick, while never trapping an open
position (closes are ungated).

Both the regime gate and the time gate block NEW ENTRIES ONLY. An already-open
position is always closeable. If regime data is None (crypto / SPY bars
unavailable) the regime gate is skipped; if the bar timestamp is missing or
unparseable the time gate is skipped (permissive default — "don't know, behave
like the parent"), matching the regime-None convention.

Regime data: read from `market_state["regime"]` = {"spy_closes": [...],
"spy_last": float}, pre-populated by the runner/backtester for stocks.
Timestamps: each bar dict carries 't' as an ISO8601 UTC string (e.g.
"2026-06-05T14:30:00Z"); the session window is checked on the LAST bar only.
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


def _minute_of_day_utc(t: Optional[str]) -> Optional[int]:
    """Extract minutes-since-UTC-midnight from an ISO8601 timestamp string.

    Returns None when the timestamp is missing or cannot be parsed, so the
    caller can treat "unknown time" as permissive (skip the gate). No I/O,
    no imports — pure string slicing of the fixed "...THH:MM..." shape.
    """
    if not t or not isinstance(t, str):
        return None
    sep = "T"
    if sep not in t:
        return None
    time_part = t.split(sep, 1)[1]
    # time_part looks like "HH:MM:SS..." possibly with trailing Z/offset.
    if len(time_part) < 5 or time_part[2] != ":":
        return None
    hh = time_part[0:2]
    mm = time_part[3:5]
    if not (hh.isdigit() and mm.isdigit()):
        return None
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    # Session window in minutes-since-UTC-midnight: 14:30 UTC = 870, 20:00 UTC = 1200.
    session_start = int(params.get("session_start_min", 870))
    session_end = int(params.get("session_end_min", 1200))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — neither the regime gate nor the time
    # gate may ever trap an open position long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry path: all gates below apply ONLY when opening a new position.
    if hi is not None and last > hi and holding == 0:
        # Regime gate (entries only).
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        # Time-of-day gate (entries only). Permissive when timestamp unknown.
        last_bar = bars[-1] if bars else {}
        mod = _minute_of_day_utc(last_bar.get("t") if isinstance(last_bar, dict) else None)
        if mod is not None and not (session_start <= mod < session_end):
            return Action("hold", symbol,
                          reason=f"off-session: bar at {mod // 60:02d}:{mod % 60:02d} UTC "
                                 f"outside {session_start // 60:02d}:{session_start % 60:02d}-"
                                 f"{session_end // 60:02d}:{session_end % 60:02d} "
                                 f"(breakout entry blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")