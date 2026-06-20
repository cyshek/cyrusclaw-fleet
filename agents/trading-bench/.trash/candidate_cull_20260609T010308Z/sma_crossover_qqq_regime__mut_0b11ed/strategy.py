"""SMA crossover on QQQ 1h bars (SPY-regime gated) with a take-profit overlay.

Variant of `sma_crossover_qqq_regime`. The parent opens long on a bullish
SMA10/30 cross (only when SPY is above its 50d SMA) and closes on the
bearish cross. Thesis for this mutation: the parent gives back gains on
winners by waiting for the slow bearish cross to confirm; by then a chunk
of the runup has already reverted. A modest take-profit locks in winners
before they round-trip.

Entry: SMA(fast) > SMA(slow) AND holding == 0 AND (regime up OR no regime).
Exit (in priority order, exits ALWAYS run before any entry gate):
  1. Parent bearish-cross close: SMA(fast) < SMA(slow) while holding.
  2. Take-profit: price >= entry * (1 + tp_pct), fired ONLY when the parent
     would otherwise hold (i.e. no bearish cross yet).

Take-profit level: tp_pct = 0.011 (1.10%). Grounded in the parent's trade
profile — median per-trade max runup is +1.34% and 64% of trades touched
>=1% runup, so 1.10% sits between the p25 runup (0.70%) and the median,
capturing more than half of historical winners while staying well inside
the distribution (not inert: a target above the +3.33% p75 would almost
never fire). Picking just under the median deliberately harvests the typical
winner a touch early rather than waiting for the full slow-cross reversal.

Edge: same regime-gated trend entry as the parent, but the exit no longer
relies solely on a lagging crossover — it banks gains near the empirical
runup center, which should cut give-back on the winners that the parent
historically let revert.

Regime data: read from `market_state["regime"]` ({"spy_closes": [...]} or
None). When None (crypto / SPY unavailable) the entry gate is skipped and
behavior matches the parent. Take-profit needs a tracked entry price; if
position_state carries no usable entry price we simply skip TP and fall
back to the parent's crossover exit — never trapping the position.
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


def _entry_price(pos: dict) -> Optional[float]:
    """Best-effort entry price from the runner's position_state record.

    Tries the common field names the runner/backtester may populate. Returns
    None when nothing usable is present (then take-profit is skipped).
    """
    if not pos:
        return None
    for key in ("avg_entry_price", "entry_price", "avg_price", "price"):
        v = pos.get(key)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv > 0:
            return fv
    return None


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    tp_pct = float(params.get("tp_pct", 0.011))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Mandatory not-enough-bars guard: need slow_p closes to form the slow SMA.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # --- Close logic ALWAYS runs first; no filter may block an exit. ---

    # 1) Parent bearish-cross exit (unchanged from parent).
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2) Take-profit overlay: only reached when the parent would HOLD
    #    (fast >= slow while holding). Fires when price has risen tp_pct
    #    above the tracked entry. Skipped silently if no entry price known.
    if holding > 0:
        ep = _entry_price(pos)
        if ep is not None and last >= ep * (1.0 + tp_pct):
            gain = (last / ep - 1.0) * 100.0
            return Action("close", symbol,
                          reason=f"take-profit {gain:.2f}% >= "
                                 f"{tp_pct * 100:.2f}% (entry {ep:.2f} -> {last:.2f})")

    # --- Entry gate: regime filter applies to NEW entries only. ---
    regime = market_state.get("regime")
    if fast > slow and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")