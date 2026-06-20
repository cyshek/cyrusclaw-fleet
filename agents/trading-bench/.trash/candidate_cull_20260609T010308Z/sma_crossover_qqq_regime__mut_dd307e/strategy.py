"""SMA crossover on QQQ 1h bars, regime-gated AND restricted to the US regular
session (14:30-20:00 UTC) for NEW entries only.

Variant of `sma_crossover_qqq_regime`. Same edge thesis as the parent: a
fast/slow SMA crossover has a small positive edge in bull/chop windows that a
SPY-trend regime gate protects by refusing new longs in downtrends. This
mutation adds a second, orthogonal entry filter: only OPEN new positions during
the US regular cash session, 14:30-20:00 UTC. Rationale: the parent trades QQQ
(a cash-equity ETF) on 1Hour bars; crossover signals that first appear in thin
pre/post-market hours are lower-quality (wider spreads, gappy prints, lower
participation) than signals confirmed during regular-session liquidity. Gating
entries to regular hours should drop the noisiest fills while keeping the bulk
of the parent's 42-trade history (median hold 26.5 bars, so most positions span
multiple sessions and are unaffected — only the entry instant is filtered).

Entry signal: fast SMA > slow SMA, AND SPY in uptrend (regime), AND the current
bar's timestamp falls inside 14:30-20:00 UTC.
Exit signal: fast SMA < slow SMA (bearish cross) — fires AT ANY TIME OF DAY.

CRITICAL: both the regime gate and the time-of-day gate block NEW ENTRIES ONLY.
Close logic runs FIRST and unconditionally, so an open position is always
exitable regardless of regime or clock. The time filter must never trap a long
overnight / outside regular hours.

Regime data: read from `market_state["regime"]` (set by runner/backtester to
{"spy_closes": [...], "spy_last": float}, or None). When None, regime gate is a
no-op. Timestamp: read from each bar's "t" (ISO8601 UTC, e.g.
"2026-06-07T14:30:00Z"); parsed by string slicing only (no datetime import,
which is not on the allowed list). If a bar has no parseable "t", the time gate
fails OPEN (permissive) so a malformed feed never silently halts entries.
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


def _minute_of_day_utc(t: object) -> Optional[int]:
    """Extract UTC minute-of-day (0..1439) from an ISO8601 timestamp string.

    Expects the Alpaca/UTC shape "YYYY-MM-DDTHH:MM:SS..." where the 'T' is at
    index 10, hours at 11:13, minutes at 14:16. Returns None if the string is
    missing/short/non-numeric so the caller can fail open. No datetime import
    (not on the allowed list) — pure string slicing + int().
    """
    if not isinstance(t, str) or len(t) < 16 or t[10] != "T":
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


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    # US regular session in UTC minutes-of-day: 14:30 -> 870, 20:00 -> 1200.
    sess_open = int(params.get("session_open_min", 870))
    sess_close = int(params.get("session_close_min", 1200))

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

    # Entry path: bullish cross while flat.
    if fast > slow and holding == 0:
        # Gate 1: regime (skip when regime data unavailable).
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        # Gate 2: time-of-day. Fail OPEN if timestamp is unparseable.
        last_t = bars[-1].get("t") if bars else None
        mod = _minute_of_day_utc(last_t)
        if mod is not None and not (sess_open <= mod <= sess_close):
            return Action("hold", symbol,
                          reason=f"off-session entry blocked "
                                 f"(utc_min={mod}, window {sess_open}-{sess_close})")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")