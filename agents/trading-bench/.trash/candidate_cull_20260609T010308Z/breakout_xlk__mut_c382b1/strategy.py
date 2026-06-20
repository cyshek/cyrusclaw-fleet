"""Donchian breakout on XLK 1h bars with a REGIME-CONDITIONAL hard stop-loss.

Thesis: the parent `breakout_xlk` is long-only and has no stop — it relies
solely on price breaking the Donchian low to exit. That's fine when trends
breathe (bull regime) but it bleeds in bear/chop windows where pullbacks are
deeper and the Donchian low is far away. This mutation adds a stop whose
tightness is CONDITIONAL on the SPY regime: tight when SPY is below its
50-day SMA (cut losers fast in hostile tape), loose/near-inert when SPY is
above it (let winners run; the parent's edge lives in trends).

Entry signal: unchanged from parent — close > prior `lookback`-bar high, flat.
Exit signals (in priority order, all honored regardless of any gate):
  1. Parent close: close < prior `lookback`-bar low.
  2. Regime-conditional stop: trade drawdown vs entry breaches the active stop.
Edge: the stop only changes EXIT behavior (the parent's regime use, if any,
gates entries); it asymmetrically trims the bad-regime left tail while leaving
the good-regime right tail nearly untouched.

Stop thresholds grounded in the PARENT PROFILE (45 trades, 8/8 windows):
  - Per-trade max drawdown distribution: p25 -2.21%, median -1.41%, p75 -0.70%;
    64% of trades touched >=1% drawdown.
  - TIGHT stop = 0.85% (bear regime). Sits between p75 (0.70%) and median
    (1.41%) drawdown, so it would have fired on meaningfully MORE than a
    quarter but fewer than half of historical trades — tight enough to cut the
    bear-regime bleed without firing on every routine wiggle.
  - LOOSE stop = 2.50% (bull regime). Sits just BEYOND p25 (2.21%) drawdown,
    so it is nearly inert in this parent's history — it lets trends breathe and
    only backstops an abnormal bull-regime reversal.

Regime data: read from market_state["regime"] = {"spy_closes":[...],
"spy_last":float}. When regime is None (data unavailable / crypto) we default
to the LOOSE stop ("don't know => behave permissively, parent-like").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _entry_price(position_state: dict, symbol: str) -> Optional[float]:
    pos = position_state.get(symbol)
    if not pos:
        return None
    for key in ("avg_entry_price", "entry_price", "avg_price", "cost_basis"):
        v = pos.get(key)
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv > 0:
                return fv
    return None


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    tight_stop_pct = float(params.get("tight_stop_pct", 0.85))
    loose_stop_pct = float(params.get("loose_stop_pct", 2.50))

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ----- EXIT logic ALWAYS runs first; no gate may trap us long. -----
    if holding > 0:
        # 1) Parent's own close signal — never blocked, never overridden away.
        if lo is not None and last < lo:
            return Action("close", symbol,
                          reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

        # 2) Regime-conditional hard stop on trade drawdown vs entry.
        entry = _entry_price(position_state, symbol)
        if entry is not None and entry > 0:
            regime = market_state.get("regime")
            if regime is None:
                # Unknown regime => permissive (loose), behave parent-like.
                stop_pct = loose_stop_pct
                regime_tag = "regime=unknown"
            elif regime_uptrend(regime.get("spy_closes") or [],
                                period=regime_period):
                stop_pct = loose_stop_pct
                regime_tag = f"SPY>{regime_period}d SMA (bull)"
            else:
                stop_pct = tight_stop_pct
                regime_tag = f"SPY<{regime_period}d SMA (bear)"

            dd_pct = (last - entry) / entry * 100.0
            if dd_pct <= -stop_pct:
                return Action("close", symbol,
                              reason=f"stop {dd_pct:.2f}% <= -{stop_pct:.2f}% "
                                     f"[{regime_tag}]")

    # ----- ENTRY logic (parent, unchanged) — only when flat. -----
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")