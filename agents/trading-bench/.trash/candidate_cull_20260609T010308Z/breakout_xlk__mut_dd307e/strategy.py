"""Donchian breakout on XLK 1h bars, gated to US regular-session entries only.

Variant of `breakout_xlk` that opens new long positions ONLY when the most
recent bar's timestamp falls inside the US regular session, 14:30-20:00 UTC.
Thesis: the parent's breakout signal is long-only and fires on any bar it
gets, including thin pre/post-market 1h bars where a "breakout" is more often
a low-liquidity spike that mean-reverts. Restricting new entries to regular
trading hours should keep the genuine intraday-momentum breakouts (which
form during liquid RTH) while skipping the off-hours noise that tends to
reverse — the parent's distribution shows 64% of trades touch >=1% drawdown,
consistent with some entries being poor-quality off-hours pokes.

Entry: last close > prior `lookback`-bar high AND last bar time in
[14:30, 20:00) UTC AND flat. Exit: last close < prior `lookback`-bar low
(fired ANY time of day, off-hours included). Edge: time-of-day liquidity
filter on entries without ever trapping an open position.

The session gate blocks NEW ENTRIES ONLY. Close logic runs first and is
honored at all hours, so an open position is never stuck waiting for RTH to
exit. If a bar timestamp is missing or unparseable, the gate fails OPEN
(treats the bar as in-session) so a data hiccup degrades to parent behavior
rather than silently halting all entries.
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


def _minutes_of_day_utc(t: object) -> Optional[int]:
    """Parse an ISO8601 UTC timestamp string and return minutes-since-midnight
    UTC (0-1439), or None if it can't be parsed. Pure string slicing — no
    datetime import. Expects 't' like '2026-06-07T14:30:00Z' or
    '2026-06-07T14:30:00+00:00'. Bars are documented as UTC, so we read the
    wall-clock HH:MM directly and ignore any trailing offset (which is +00:00
    for this data set)."""
    if not isinstance(t, str):
        return None
    sep = None
    if "T" in t:
        sep = "T"
    elif " " in t:
        sep = " "
    if sep is None:
        return None
    time_part = t.split(sep, 1)[1]
    if len(time_part) < 5:
        return None
    hh = time_part[0:2]
    mm = time_part[3:5]
    if not (hh.isdigit() and mm.isdigit()):
        return None
    if time_part[2:3] != ":":
        return None
    hour = int(hh)
    minute = int(mm)
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    # Session window in minutes-since-midnight UTC: 14:30 = 870, 20:00 = 1200.
    session_start = int(params.get("session_start_min_utc", 870))
    session_end = int(params.get("session_end_min_utc", 1200))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — the session gate must never trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry gate: breakout AND inside the RTH session window.
    if hi is not None and last > hi and holding == 0:
        mod = _minutes_of_day_utc(bars[-1].get("t"))
        in_session = (mod is None) or (session_start <= mod < session_end)
        if not in_session:
            return Action("hold", symbol,
                          reason=f"breakout blocked: bar {mod}min UTC outside "
                                 f"session [{session_start},{session_end})")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f} "
                             f"in-session")
    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")