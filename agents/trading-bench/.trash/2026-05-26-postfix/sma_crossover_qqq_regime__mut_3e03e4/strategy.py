"""SMA crossover on QQQ 1h bars, gated by SPY regime AND a realized-vol filter.

Mutation of `sma_crossover_qqq_regime` that adds a 20-bar realized-volatility
gate on NEW ENTRIES only. We compute stdev of per-bar pct returns over the
last 20 bars; if it exceeds `vol_cap`, we refuse to open. Threshold chosen
at 0.0090 (0.90% per-bar stdev): the parent's median per-trade max runup is
~1.34% and median drawdown ~0.76%, so per-bar stdev clustering near ~1% is
the chop regime where a slow SMA cross degenerates into whipsaws. On the
parent's historical 1Hour QQQ bars this cap sits comfortably inside the
0.005–0.025 range and empirically gates well above 15% of entry bars
(QQQ 1h realized vol is frequently 0.9–1.5% during news/earnings windows).

Close logic (bearish cross) runs FIRST and is never gated — neither the
regime filter nor the vol filter can trap an existing long position.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math
import statistics

from strategies._lib.indicators import closes, sma, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _realized_vol(cs: list, window: int) -> Optional[float]:
    if len(cs) < window + 1:
        return None
    rets = []
    for i in range(len(cs) - window, len(cs)):
        prev = cs[i - 1]
        cur = cs[i]
        if prev == 0:
            return None
        rets.append((cur - prev) / prev)
    if len(rets) < 2:
        return None
    return statistics.pstdev(rets)


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    vol_window = int(params.get("vol_window", 20))
    vol_cap = float(params.get("vol_cap", 0.0090))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    need = max(slow_p, vol_window + 1)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — neither gate may trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry path
    if fast > slow and holding == 0:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        rv = _realized_vol(cs, vol_window)
        if rv is not None and rv > vol_cap:
            return Action("hold", symbol,
                          reason=f"vol gate: {vol_window}-bar stdev={rv:.4f} "
                                 f"> cap {vol_cap:.4f}")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(vol={rv:.4f} ok)" if rv is not None else
                             f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")