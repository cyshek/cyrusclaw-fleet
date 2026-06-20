"""Donchian breakout on XLK 1h bars, gated by a SPY-trend regime filter AND a
US-regular-session time-of-day filter.

Variant of `breakout_xlk_regime`. Same core edge: open a long only when price
closes above the prior `lookback`-bar Donchian high, and only while SPY trades
above its `regime_period`-day SMA. This mutation ADDS a session filter: new
entries are allowed ONLY during the US regular cash session, 14:30-20:00 UTC.
Bars carry an ISO8601-UTC timestamp in `t`; we read the hour:minute of the most
recent bar and convert to minute-of-day to test the window [870, 1200) minutes.

Thesis: the parent's breakout signal fires on any bar, including thin
pre-/post-market and overnight 1h bars where a single print can poke above the
Donchian high on low participation and then mean-revert. Restricting NEW entries
to regular trading hours should keep only breakouts that occur with real session
liquidity, trimming low-quality fakeouts while leaving the proven bull/chop edge
intact.

Exit discipline is UNCHANGED and UNGATED: a close (price < Donchian low) fires
at ANY time, in ANY session, regardless of regime or time-of-day. Neither the
regime gate nor the session gate may ever trap an open position long — close
logic runs first, before any entry filter is consulted. If `t` is missing or
unparseable the session gate fails OPEN (permissive) so the strategy degrades to
the parent's behavior rather than silently refusing to trade.

Regime data: read from `market_state["regime"]` ({"spy_closes": [...]}). When
None (crypto / SPY unavailable) the regime gate is skipped, matching the parent.
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


# US regular cash session in UTC minutes-of-day: 14:30 -> 20:00.
# 14*60+30 = 870 (inclusive) .. 20*60 = 1200 (exclusive).
_SESSION_OPEN_MIN = 870
_SESSION_CLOSE_MIN = 1200


def _utc_minute_of_day(ts: object) -> Optional[int]:
    """Extract minute-of-day (UTC) from an ISO8601 timestamp string like
    '2026-06-09T14:30:00Z' or '2026-06-09T14:30:00+00:00'. Returns None if the
    value is absent or cannot be parsed (caller treats None as 'unknown' and
    fails the session gate OPEN so exits/parent-behavior are never blocked).

    Pure string parsing only (no datetime import, which is not on the allowed
    list). Bars are documented as UTC, so we read the wall-clock HH:MM directly.
    """
    if not isinstance(ts, str):
        return None
    # Find the time component after the 'T' (or space) separator.
    sep = ts.find("T")
    if sep == -1:
        sep = ts.find(" ")
    if sep == -1 or sep + 1 >= len(ts):
        return None
    time_part = ts[sep + 1:]
    # time_part looks like 'HH:MM:SS...' possibly with 'Z'/'+00:00' suffix.
    pieces = time_part.split(":")
    if len(pieces) < 2:
        return None
    try:
        hh = int(pieces[0])
        mm = int(pieces[1][:2])
    except (ValueError, IndexError):
        return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return hh * 60 + mm


def _in_session(bars: list, open_min: int, close_min: int) -> bool:
    """True iff the most recent bar's UTC minute-of-day is in [open_min, close_min).
    Fails OPEN (returns True) when the timestamp is missing/unparseable so the
    session filter can never silently trap a position or hard-block the parent
    behavior on malformed data.
    """
    if not bars:
        return True
    mod = _utc_minute_of_day(bars[-1].get("t") if isinstance(bars[-1], dict) else None)
    if mod is None:
        return True
    return open_min <= mod < close_min


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    session_open_min = int(params.get("session_open_min", _SESSION_OPEN_MIN))
    session_close_min = int(params.get("session_close_min", _SESSION_CLOSE_MIN))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — neither the regime gate nor the session
    # gate may ever trap us long. Exits fire in any session, at any time.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry path: breakout above prior Donchian high while flat.
    if hi is not None and last > hi and holding == 0:
        # Session gate: only enter during US regular hours (14:30-20:00 UTC).
        if not _in_session(bars, session_open_min, session_close_min):
            return Action("hold", symbol,
                          reason=f"session: outside 14:30-20:00 UTC "
                                 f"(entry blocked, t={bars[-1].get('t') if isinstance(bars[-1], dict) else '?'})")
        # Regime gate: only enter when SPY is above its regime SMA.
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")