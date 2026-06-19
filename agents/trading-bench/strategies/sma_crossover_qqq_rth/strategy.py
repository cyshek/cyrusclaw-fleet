"""SMA crossover on QQQ 1h bars with US-regular-session entry filter.

Variant of `sma_crossover_qqq` that only opens NEW long positions when the
current bar's timestamp falls inside 14:30-20:00 UTC (US regular trading
hours). Hypothesis: extended-hours QQQ bars are thinner, wider-spread, and
noisier; restricting entries to RTH should produce cleaner crossover signals
with better fill quality, while crossovers fired during illiquid hours are
disproportionately false signals.

Important: the time-of-day gate blocks ENTRIES ONLY. If a position is
already open when a bearish crossover fires outside RTH, the close signal
is still honored — otherwise the filter could trap us long through a
downtrend that started overnight.
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


def _in_rth(ts: str) -> bool:
    """Return True iff ISO8601 UTC timestamp `ts` is within 14:30-20:00 UTC.

    Parses minimally without importing datetime: expects 'YYYY-MM-DDTHH:MM...'.
    On any parse failure, returns False (fail-closed for entries; exits are
    unaffected because this gate only runs on the entry path).
    """
    if not ts or not isinstance(ts, str):
        return False
    try:
        t_idx = ts.index("T")
        hh = int(ts[t_idx + 1:t_idx + 3])
        mm = int(ts[t_idx + 4:t_idx + 6])
    except (ValueError, IndexError):
        return False
    minutes = hh * 60 + mm
    # 14:30 UTC = 870, 20:00 UTC = 1200
    return 870 <= minutes <= 1200


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # Close logic ALWAYS runs first — the time-of-day gate must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry path: gate on RTH (14:30-20:00 UTC).
    if fast > slow and holding == 0:
        last_ts = bars[-1].get("t", "") if bars else ""
        if not _in_rth(last_ts):
            return Action("hold", symbol,
                          reason=f"outside RTH (bar t={last_ts}); "
                                 f"crossover signal blocked")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")