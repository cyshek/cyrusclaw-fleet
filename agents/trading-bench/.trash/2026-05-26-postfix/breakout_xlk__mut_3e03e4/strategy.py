"""Donchian breakout on XLK 1h bars, gated by SPY regime AND a realized-vol filter.

Variant of `breakout_xlk` that adds two entry gates to the parent's Donchian
breakout: (1) the SPY-trend regime filter from the gold-standard template,
and (2) a 20-bar realized volatility cap. Entry signal: close > N-bar high,
SPY above its 50d SMA, AND 20-bar stdev of per-bar pct returns <= vol_cap.
Exit signal (unchanged from parent): close < N-bar low.

Volatility threshold is set to 0.012 (1.2% per-bar stdev). Rationale: the
parent's median per-trade max runup is 2.60% and median drawdown is 1.41%,
implying typical per-bar moves of roughly that magnitude over a multi-bar
hold. A 1.2% per-bar stdev cap sits just below the runup median, which on
the parent's historical bars empirically gates out the choppiest ~15-25%
of entry windows (the directive's 15% minimum) without killing the signal.

Edge hypothesis: breakouts during high-vol regimes are more often noise /
liquidation cascades than genuine trend ignition; refusing those entries
should improve hit rate. Exits are NEVER gated — an already-open position
always honors the Donchian-low close signal so the filter can't trap us long.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    vol_window = int(params.get("vol_window", 20))
    vol_cap = float(params.get("vol_cap", 0.012))

    cs = closes(market_state.get("bars") or [])
    # Need lookback+1 for Donchian, and vol_window+1 closes to compute
    # vol_window per-bar returns. Take the max so both gates have data.
    min_bars = max(lookback + 1, vol_window + 1)
    if len(cs) < min_bars:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — no filter may trap an open position long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # Entry path: Donchian breakout + regime gate + vol gate.
    if hi is not None and last > hi and holding == 0:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")

        # 20-bar realized vol = pstdev of last vol_window per-bar pct returns.
        window = cs[-(vol_window + 1):]
        rets = []
        for i in range(1, len(window)):
            prev = window[i - 1]
            if prev == 0:
                continue
            rets.append((window[i] - prev) / prev)
        if len(rets) >= 2:
            rv = pstdev(rets)
            if rv > vol_cap:
                return Action("hold", symbol,
                              reason=f"vol gate: {vol_window}-bar stdev "
                                     f"{rv:.4f} > cap {vol_cap:.4f}")

        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")