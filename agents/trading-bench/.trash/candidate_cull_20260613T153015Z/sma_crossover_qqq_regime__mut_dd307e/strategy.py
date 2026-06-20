"""SMA crossover on QQQ 1h bars, regime-gated and restricted to the US RTH window.

Variant of `sma_crossover_qqq_regime` that adds a time-of-day entry filter on
top of the existing SPY-trend regime gate. New long positions may ONLY open
when the current bar timestamp falls inside 14:30-20:00 UTC (US regular cash
session). Hypothesis: the parent's bullish crossover signals fired in thin
pre/post-market and overnight hours carry wider spreads and noisier fills than
RTH signals; confining entries to the liquid cash session should drop the
lowest-quality entries without giving up the bulk of the edge. With a parent
median hold of ~26 bars (1h) and 43% of trades touching >=1% drawdown, the
filter is a quality gate on entry timing, not a stop.

Entry: fast SMA crosses above slow SMA, AND SPY is above its regime SMA, AND
the bar time is within 14:30-20:00 UTC.
Exit: fast SMA falls below slow SMA (bearish cross) — fires at ANY time of day.

CRITICAL: both the regime gate and the time-of-day gate block NEW ENTRIES
ONLY. Close logic runs first and unconditionally, so neither filter can ever
trap an already-open long position outside RTH or in a downturn. Bars carry an
ISO8601 UTC timestamp under key 't'; if it's missing or unparseable the time
gate fails OPEN (permissive) so a malformed feed never silently halts entries.
Regime is read from market_state["regime"]; None falls through to parent behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _minutes_utc(ts: object) -> Optional[int]:
    """Parse minutes-since-UTC-midnight from an ISO8601 'YYYY-MM-DDTHH:MM...'
    string. Returns None if it can't be parsed — caller treats None as
    'unknown time' and lets the entry through (fail open)."""
    if not isinstance(ts, str):
        return None
    t_idx = ts.find("T")
    if t_idx < 0 or len(ts) < t_idx + 6:
        return None
    hh = ts[t_idx + 1:t_idx + 3]
    mm = ts[t_idx + 4:t_idx + 6]
    if not (hh.isdigit() and mm.isdigit()):
        return None
    h = int(hh)
    m = int(mm)
    if h > 23 or m > 59:
        return None
    return h * 60 + m


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    # US regular cash session in UTC minutes: 14:30 = 870, 20:00 = 1200.
    rth_start = int(params.get("rth_start_min", 870))
    rth_end = int(params.get("rth_end_min", 1200))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # Close logic ALWAYS runs first — neither the regime gate nor the
    # time-of-day gate may ever trap an open long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry path: bullish cross while flat. Apply regime gate, then time gate.
    if fast > slow and holding == 0:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        last_t = bars[-1].get("t") if bars else None
        mins = _minutes_utc(last_t)
        if mins is not None and not (rth_start <= mins <= rth_end):
            return Action("hold", symbol,
                          reason=f"outside RTH ({mins} min UTC not in "
                                 f"[{rth_start},{rth_end}]); entry blocked")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")