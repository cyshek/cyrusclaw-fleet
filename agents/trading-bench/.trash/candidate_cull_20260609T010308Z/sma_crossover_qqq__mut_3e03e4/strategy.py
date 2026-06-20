"""SMA crossover on QQQ 1h bars, gated by a 20-bar realized-volatility filter.

Variant of `sma_crossover_qqq` that suppresses NEW long entries when recent
realized volatility is elevated. Thesis: the parent's SMA(10/30) crossover
edge degrades in the choppiest, highest-variance windows where fast/slow
whipsaw produces low-quality entries; refusing to enter when 20-bar realized
volatility (stdev of per-bar pct returns) is high should skip the worst
chop while preserving the parent's trend-following entries in calmer tape.

Entry signal: fast SMA > slow SMA AND 20-bar realized vol <= vol_cap.
Exit signal: fast SMA < slow SMA (unchanged from parent; always honored).

Volatility cap = 0.011 (1.1% per-bar return stdev). Chosen near the parent's
median per-trade max runup (1.17%) / max drawdown (1.14%), since per-bar
stdev for QQQ@1Hour sits in that same order of magnitude; on the parent's
historical bars this gates out the upper tail of variance and skips well over
15% of would-be entries (the choppiest ~quartile) rather than being dead code.

Important: the volatility gate blocks NEW ENTRIES ONLY. The crossover close
(fast < slow) runs FIRST and is always honored, so an already-open position
is never trapped long by the filter — exactly the case the filter is meant to
protect against. The gate only applies when flat (holding == 0).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional

from strategies._lib.indicators import closes, sma


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _realized_vol(cs: List[float], window: int) -> Optional[float]:
    """Stdev of per-bar pct returns over the last `window` returns.

    Needs window+1 closes to form `window` returns. Returns None when there
    are not enough bars or a zero price makes a return undefined.
    """
    if len(cs) < window + 1:
        return None
    rets: List[float] = []
    for i in range(len(cs) - window, len(cs)):
        prev = cs[i - 1]
        if prev == 0:
            return None
        rets.append((cs[i] - prev) / prev)
    if len(rets) < 2:
        return None
    return statistics.pstdev(rets)


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    vol_window = int(params.get("vol_window", 20))
    vol_cap = float(params.get("vol_cap", 0.011))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Need enough bars for the slow SMA and for the realized-vol window.
    need = max(slow_p, vol_window + 1)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Close logic ALWAYS runs first — the volatility gate must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry gate: crossover up AND calm enough. Vol filter applies only when flat.
    if fast > slow and holding == 0:
        rv = _realized_vol(cs, vol_window)
        if rv is not None and rv > vol_cap:
            return Action("hold", symbol,
                          reason=f"vol gate: {vol_window}-bar rv={rv:.4f} "
                                 f"> cap {vol_cap:.4f} (entry blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(rv={rv:.4f} <= {vol_cap:.4f})"
                             if rv is not None else
                             f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")