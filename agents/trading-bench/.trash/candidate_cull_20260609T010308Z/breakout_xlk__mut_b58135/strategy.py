"""Donchian breakout OR SMA-crossover momentum entry on XLK 1h bars.

Parent (`breakout_xlk`) is a pure Donchian breakout: it ONLY enters when the
last close pierces the 20-bar high. That single trigger misses a whole class
of profitable continuation moves where XLK is already in a clean short-term
uptrend (fast SMA above slow SMA) and grinding higher, but hasn't printed a
fresh 20-bar high on the current bar to fire the breakout. Those are missed
OPPORTUNITIES, not losers to filter out — so this mutation widens entries via
an OR, adding a momentum-crossover trigger alongside the parent breakout.

ENTRY (OR — either suffices, when flat):
  (A) parent breakout: last close > prior 20-bar high, OR
  (B) momentum crossover: fast SMA(8) > slow SMA(34) AND last close is at or
      above the fast SMA (confirming the bar is participating in the up-move,
      not a stale crossover left over from an earlier leg).

EXIT (OR — either parent exit suffices; a position is never harder to close
than to open):
  (A) parent exit: last close < prior 20-bar low, OR
  (B) momentum break: fast SMA(8) < slow SMA(34) (the crossover that justified
      the momentum entry has flipped), OR
  (C) take-profit at +2.60% vs entry — the parent's MEDIAN per-trade max runup,
      so it would have locked in at least half the historical winners (a target
      above the +4.11% p75 would be inert).

Edge thesis: the parent's breakout edge is real but its trigger is narrow and
long-only; adding a grounded momentum-continuation entry should increase the
number of participating up-trend trades without loosening the exit discipline.
Periods are grounded in the parent's holding distribution (median 34 bars):
slow SMA(34) ~ one median holding period, fast SMA(8) ~ a quarter of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, sma


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
    fast_period = int(params.get("fast_period", 8))
    slow_period = int(params.get("slow_period", 34))
    take_profit_pct = float(params.get("take_profit_pct", 2.60))
    notional = float(params.get("notional_usd", 1000.0))

    cs = closes(market_state.get("bars") or [])
    # Need enough bars for the slow SMA plus the Donchian lookback (+1 for the
    # prior-bar window used by highest/lowest).
    need = max(lookback + 1, slow_period)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)
    fast = sma(cs, fast_period)
    slow = sma(cs, slow_period)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_price = float(pos.get("avg_entry_price", 0) or 0) if pos else 0.0

    # -----------------------------------------------------------------
    # CLOSE LOGIC FIRST — a position must never be harder to close than to
    # open. Any of the parent/momentum exits, plus take-profit, can fire.
    # -----------------------------------------------------------------
    if holding > 0:
        if lo is not None and last < lo:
            return Action("close", symbol,
                          reason=f"exit: close {last:.2f} < {lookback}-bar low {lo:.2f}")
        if fast is not None and slow is not None and fast < slow:
            return Action("close", symbol,
                          reason=f"exit: momentum break SMA{fast_period} {fast:.2f} "
                                 f"< SMA{slow_period} {slow:.2f}")
        if entry_price > 0 and take_profit_pct > 0:
            gain_pct = (last - entry_price) / entry_price * 100.0
            if gain_pct >= take_profit_pct:
                return Action("close", symbol,
                              reason=f"take-profit: +{gain_pct:.2f}% >= {take_profit_pct:.2f}%")

    # -----------------------------------------------------------------
    # ENTRY LOGIC (only when flat) — OR of breakout and momentum crossover.
    # -----------------------------------------------------------------
    if holding == 0:
        breakout = hi is not None and last > hi
        momentum = (fast is not None and slow is not None
                    and fast > slow and last >= fast)
        if breakout or momentum:
            if breakout:
                why = f"breakout: close {last:.2f} > {lookback}-bar high {hi:.2f}"
            else:
                why = (f"momentum: SMA{fast_period} {fast:.2f} > SMA{slow_period} "
                       f"{slow:.2f} and close {last:.2f} >= fast")
            return Action("buy", symbol, notional_usd=notional, reason=why)

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, hi={hi}, lo={lo}, "
                         f"fast={fast}, slow={slow}, holding={holding})")