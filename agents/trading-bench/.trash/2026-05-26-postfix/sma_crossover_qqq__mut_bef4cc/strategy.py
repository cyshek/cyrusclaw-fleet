"""SMA crossover on QQQ 1h bars with a tight hard stop-loss.

Parent: `sma_crossover_qqq` enters long when SMA(fast) crosses above
SMA(slow) and exits on the reverse cross. The crossover exit is lagging —
it only fires after the fast MA bends back below the slow MA, which on 1h
QQQ bars typically takes many bars. Parent trade stats show 57% of trades
touched ≥1% drawdown and the median trade drawdown was -1.14%, so the
crossover exit routinely lets winners give back >1% before flipping.

Entry signal: SMA(fast) > SMA(slow) and flat.
Exit signals (either fires):
  1. Parent crossover exit: SMA(fast) < SMA(slow). Runs FIRST so the stop
     never blocks the parent's own close.
  2. Hard stop-loss: last close <= entry_price * (1 - stop_pct).

Stop threshold: 0.9% — chosen to sit just below the median per-trade max
drawdown (1.14%) so it triggers on roughly the worse half of trades, but
above the noise floor of typical 1h QQQ bar wiggles. The stop is meant to
catch the trade-killers — sharp intrabar reversals where the fast MA is
still nominally above slow but price has already broken down 1%+ from
entry, the kind of move the crossover exit takes 5-10 more bars to
confirm. A looser stop (≥1.5%) would sit past p25 (-1.67%) and almost
never fire, making it inert code rather than risk control.
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


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    stop_pct = float(params.get("stop_pct", 0.009))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_price = pos.get("entry_price")
    try:
        entry_price = float(entry_price) if entry_price is not None else None
    except (TypeError, ValueError):
        entry_price = None

    # 1) Parent exit signal runs FIRST so the stop never blocks the parent close.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2) Hard stop-loss: tight, sized just under the median trade drawdown.
    if holding > 0 and entry_price is not None and entry_price > 0:
        stop_price = entry_price * (1.0 - stop_pct)
        if last <= stop_price:
            drop = (last - entry_price) / entry_price * 100.0
            return Action("close", symbol,
                          reason=f"stop-loss: {last:.2f} <= {stop_price:.2f} "
                                 f"(entry={entry_price:.2f}, {drop:.2f}%)")

    # 3) Entry on bullish cross while flat.
    if fast > slow and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"holding={holding}, entry={entry_price})")