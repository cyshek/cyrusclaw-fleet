"""SMA crossover on QQQ 1h bars, gated by a US-regular-session time-of-day filter.

Variant of `sma_crossover_qqq` that only OPENS new long positions during the
US regular cash session, 14:30-20:00 UTC. Thesis: the parent's SMA(10/30)
crossover edge is an equity-index signal, and index intraday trend is
cleanest while the underlying cash market is open and liquid; crossovers that
trigger in the thin pre/post-market and overnight bars are noisier and more
prone to whipsaw. Restricting ENTRIES to the regular session should keep the
real-session crossovers while skipping the low-quality off-hours ones.

Entry signal: fast SMA(10) > slow SMA(30) AND the current bar's UTC time is
within 14:30-20:00, AND we are flat. Exit signal: fast SMA(10) < slow SMA(30)
while long. Edge: filters entry noise by liquidity/session without changing
the underlying crossover thesis.

CRITICAL: the time-of-day filter blocks NEW ENTRIES ONLY. The close signal
(fast < slow) is evaluated FIRST and is always honored regardless of the
time of day, so an existing long is never trapped by the session window.

Bars carry an ISO8601 UTC timestamp in b['t'] (e.g. "2026-06-05T14:30:00Z").
We read the HH:MM directly off that string (chars 11:16) rather than parsing
a datetime, to stay inside the allowed-import contract. Bars whose timestamp
is missing/malformed are treated as out-of-window for entry (conservative:
no entry rather than an entry on an unknown time) but still allow closes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


# US regular cash session in UTC, expressed as minutes-since-midnight.
# 14:30 UTC = 870 ; 20:00 UTC = 1200. Half-open-ish inclusive window.
_SESSION_OPEN_MIN = 14 * 60 + 30   # 870
_SESSION_CLOSE_MIN = 20 * 60       # 1200


def _bar_minute_of_day_utc(bar: dict) -> Optional[int]:
    """Extract minutes-since-UTC-midnight from an ISO8601 't' field.

    Expects 't' like '2026-06-05T14:30:00Z' (or with offset/fraction). Reads
    the HH:MM at fixed offsets 11:13 and 14:16. Returns None when the field is
    absent or doesn't look like a parseable timestamp, so callers can treat
    'unknown time' as out-of-window for entries.
    """
    t = bar.get("t")
    if not isinstance(t, str) or len(t) < 16:
        return None
    if t[10] not in ("T", " ") or t[13] != ":":
        return None
    hh = t[11:13]
    mm = t[14:16]
    if not (hh.isdigit() and mm.isdigit()):
        return None
    h = int(hh)
    m = int(mm)
    if h > 23 or m > 59:
        return None
    return h * 60 + m


def _in_session(bar: dict) -> bool:
    mod = _bar_minute_of_day_utc(bar)
    if mod is None:
        return False
    return _SESSION_OPEN_MIN <= mod <= _SESSION_CLOSE_MIN


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    need = slow_p + 1
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ---- Close logic ALWAYS runs first; the session filter must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # ---- Entry gate: crossover up AND inside the US regular session AND flat.
    if fast > slow and holding == 0:
        last_bar = bars[-1] if bars else {}
        if not _in_session(last_bar):
            return Action("hold", symbol,
                          reason="session: outside 14:30-20:00 UTC "
                                 "(entry blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(in session)")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"holding={holding})")