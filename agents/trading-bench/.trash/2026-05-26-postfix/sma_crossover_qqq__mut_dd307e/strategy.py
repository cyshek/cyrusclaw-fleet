"""SMA crossover on QQQ 1h bars, with US regular-session entry filter.

Variant of `sma_crossover_qqq` that only opens new long positions when the
current bar's timestamp falls within 14:30-20:00 UTC (US regular trading
session). Hypothesis: SMA crossover signals fired during illiquid overnight
or pre/post-market hours on QQQ tend to be noisier — wider spreads, thinner
volume, and gap risk distort the cross. Restricting entries to RTH should
preserve the signal's edge while filtering out the lowest-quality bars.

The time-of-day gate blocks NEW ENTRIES ONLY. If a position is already open
when the fast SMA crosses back under the slow SMA outside RTH, the close
signal is still honored — we never trap an existing long position.
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

    Parses without external libs. Expected shape: 'YYYY-MM-DDTHH:MM:SS[...]Z'
    or with offset. We only need HH:MM in UTC; bars are tagged UTC per spec.
    Returns False on any parse failure (fail-closed for entries — exits are
    unaffected because they don't consult this gate).
    """
    if not ts or not isinstance(ts, str):
        return False
    # Find the 'T' separator
    t_idx = ts.find("T")
    if t_idx < 0 or len(ts) < t_idx + 6:
        return False
    hh_str = ts[t_idx + 1:t_idx + 3]
    mm_str = ts[t_idx + 4:t_idx + 6]
    if not (hh_str.isdigit() and mm_str.isdigit()):
        return False
    hh = int(hh_str)
    mm = int(mm_str)
    minutes = hh * 60 + mm
    # 14:30 UTC = 870 min; 20:00 UTC = 1200 min. Inclusive-exclusive.
    return 870 <= minutes < 1200


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

    # Entry gate: only enter new positions during US RTH (14:30-20:00 UTC).
    if fast > slow and holding == 0:
        last_ts = bars[-1].get("t") if bars else None
        if not _in_rth(str(last_ts) if last_ts is not None else ""):
            return Action("hold", symbol,
                          reason=f"outside RTH 14:30-20:00 UTC (ts={last_ts}); "
                                 f"crossover entry blocked")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")