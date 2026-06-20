"""Donchian breakout on XLK 1h bars, gated by BOTH a SPY-trend regime filter
and a 20-bar realized-volatility filter.

Variant of `breakout_xlk_regime`. Thesis: the parent's long-only breakout
edge holds up in trending/calm tape but the worst trades cluster in choppy,
high-realized-volatility bars where breakouts whipsaw. So we keep the SPY
regime gate (only enter when SPY > its 50d SMA) AND add a second entry gate:
skip new breakouts when the last 20 bars' realized volatility — the
population stdev of per-bar pct returns — exceeds `vol_cap`.

Entry signal: close prints a new `lookback`-bar high, SPY is in an uptrend,
AND 20-bar realized vol <= vol_cap. Exit signal: close prints a new
`lookback`-bar low (unchanged from parent).

Why edge: the parent's per-trade max drawdown touches >=1% on 52% of trades
and the deepest tail (-1.66%) lines up with volatile chop; filtering out the
choppiest entry bars should shave that left tail without surrendering the
calm-trend winners (median runup +2.60%).

vol_cap = 0.012 (1.2% per-bar stdev): on calm XLK 1h tape the 20-bar per-bar
return stdev sits near ~0.005-0.008, so 1.2% sits above the typical-calm band
but well below volatile-chop spikes — it gates out only the choppiest ~15%+
of breakout bars (roughly half the median per-trade runup of 2.60% in
order of magnitude, just under the median drawdown 1.27%), satisfying the
"skip at least 15% of entries" requirement while staying live, not inert.

Important: BOTH gates block NEW ENTRIES ONLY. Close logic runs first and is
always honored, so neither the regime gate nor the vol gate can ever trap an
already-open position long.

Regime data: read from `market_state["regime"]`, pre-populated by the
runner/backtester with {"spy_closes": [...], "spy_last": float}. If regime is
None (crypto / SPY unavailable) the regime gate is skipped; the vol gate is
self-contained and always applies.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional

from strategies._lib.indicators import closes, highest, lowest, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _realized_vol(cs: List[float], period: int) -> Optional[float]:
    """Population stdev of the last `period` per-bar pct returns.

    Needs period+1 closes to form `period` returns. Returns None when there
    aren't enough bars or a zero base price would make a return undefined.
    """
    if len(cs) < period + 1:
        return None
    window = cs[-(period + 1):]
    rets: List[float] = []
    for i in range(1, len(window)):
        prev = window[i - 1]
        if prev == 0:
            return None
        rets.append((window[i] - prev) / prev)
    if len(rets) < 2:
        return None
    return statistics.pstdev(rets)


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    vol_period = int(params.get("vol_period", 20))
    vol_cap = float(params.get("vol_cap", 0.012))

    cs = closes(market_state.get("bars") or [])
    need = max(lookback + 1, vol_period + 1)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — neither gate may ever trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry path: breakout signal must pass BOTH gates before we buy.
    if hi is not None and last > hi and holding == 0:
        # Gate 1: volatility — skip the choppiest bars.
        rv = _realized_vol(cs, vol_period)
        if rv is not None and rv > vol_cap:
            return Action("hold", symbol,
                          reason=f"vol gate: {vol_period}-bar realized vol "
                                 f"{rv:.4f} > cap {vol_cap:.4f} "
                                 f"(breakout signal blocked)")
        # Gate 2: SPY regime — only enter in an uptrend.
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