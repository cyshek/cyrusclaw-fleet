"""Donchian breakout on XLK 1h bars, gated by a 20-bar realized-volatility filter.

Variant of `breakout_xlk` that blocks NEW long entries when 20-bar realized
volatility (population stdev of bar-to-bar pct returns) exceeds a per-bar cap
of 0.012 (1.2%). Thesis: the parent's Donchian breakout edge degrades in
high-volatility chop, where breakouts above the 20-bar high tend to be
whipsaw fakeouts that immediately retrace; 64% of the parent's trades touched
>=1% drawdown, so the choppiest bars are precisely where its entries bleed.
Gating those entries should preserve the cleaner trend-breakout fills while
skipping the noisy ones.

Threshold rationale: 0.012 sits just below the parent's per-trade median max
drawdown (1.41%) and median max runup (2.60%) on a cumulative basis, but as a
per-bar 20-bar stdev it is high enough that only the most agitated XLK
windows clear it — sized to skip the noisiest >=15% of breakout signals while
leaving normal-regime breakouts untouched (filter must actually fire to earn
its keep, not be inert).

Entry signal: close > prior 20-bar high AND 20-bar realized vol <= 0.012.
Exit signal: close < prior 20-bar low (ALWAYS honored, regardless of vol).
Edge: trend-following breakout, de-noised by refusing entries in the
high-variance regime where the breakout's whipsaw drawdowns concentrate.

Important: the volatility gate blocks NEW ENTRIES ONLY. Close logic runs
first and is never gated — an already-open position must always be able to
exit on the Donchian-low signal, otherwise the filter could trap us long
through exactly the volatile drawdown it is meant to avoid. When fewer than
`vol_lookback`+1 returns are available the vol value is unknown and the gate
is skipped (permissive warm-up), matching the parent's behavior.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional

from strategies._lib.indicators import closes, highest, lowest


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _realized_vol(cs: List[float], lookback: int) -> Optional[float]:
    """Population stdev of the last `lookback` bar-to-bar pct returns.

    Returns None when there aren't enough closes to form `lookback` returns
    (need lookback+1 closes). Skips any bar with a zero prior close to avoid
    division blow-ups; if that leaves < 2 usable returns, returns None.
    """
    if lookback <= 1 or len(cs) < lookback + 1:
        return None
    window = cs[-(lookback + 1):]
    rets: List[float] = []
    for i in range(1, len(window)):
        prev = window[i - 1]
        if prev == 0:
            continue
        rets.append((window[i] - prev) / prev)
    if len(rets) < 2:
        return None
    return statistics.pstdev(rets)


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    vol_lookback = int(params.get("vol_lookback", 20))
    vol_cap = float(params.get("vol_cap", 0.012))
    notional = float(params.get("notional_usd", 1000.0))

    cs = closes(market_state.get("bars") or [])
    # Need lookback+1 closes for the Donchian high/low, and vol_lookback+1 for
    # the realized-vol window. Guard on the larger requirement.
    min_bars = max(lookback, vol_lookback) + 1
    if len(cs) < min_bars:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — the volatility gate must never trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry gate: respect the volatility filter only when entering new positions.
    if hi is not None and last > hi and holding == 0:
        rv = _realized_vol(cs, vol_lookback)
        if rv is not None and rv > vol_cap:
            return Action("hold", symbol,
                          reason=f"vol gate: {vol_lookback}-bar realized vol "
                                 f"{rv:.4f} > cap {vol_cap:.4f} "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}"
                             + (f", vol {rv:.4f} ok" if rv is not None else ""))
    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")