"""Donchian breakout on XLK 1h bars, regime-gated, with a HARD TIME-STOP.

Parent: `breakout_xlk_regime` — Donchian(20) breakout, long-only, entries
gated by SPY > SMA(50). This mutation adds a hard time-stop: positions are
force-closed after `max_holding_bars` bars regardless of the parent's exit
signal. Entry bar index is tracked in `position_state[symbol]["entry_bar"]`
and the elapsed count is computed against the current bar index (derived
from len(bars) - 1, the standard runner/backtester convention).

Thesis: parent's holding distribution is p25=16 / median=34 / p75=43 bars.
Trades that haven't resolved (hit the Donchian-low exit or run to a real
profit) by the p75 mark are statistically dead — they're sitting through
chop, tying up capital that a fresh breakout could deploy. We pick
N = 43 (p75) so we cut the slowest 25% of trades. Going tighter (median=34)
would force out half the population including normal winners; going looser
than p75 would essentially never fire.

Time-stopped bucket: in the parent's raw trades, holding_bars correlates
weakly NEGATIVELY with pnl (slow trades are disproportionately chop/loss
that never hit either side of the channel). So time-stopped trades should
on average count toward the UNPROFITABLE bucket — we're not cutting winners
short, we're euthanizing zombies. The time-stop should be pnl-neutral to
mildly positive (capital recycling effect not modeled here).

Exit precedence: parent's close-on-Donchian-low fires first (preserves
parent semantics on real breakdowns); time-stop fires second as a hard
backstop. The regime gate continues to block entries only, never exits.
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


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "XLK")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    max_holding_bars = int(params.get("max_holding_bars", 43))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)
    cur_bar = len(cs) - 1

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_bar = pos.get("entry_bar")

    # 1) Parent close-logic ALWAYS runs first — regime gate must never trap us long.
    if lo is not None and last < lo and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")

    # 2) HARD time-stop: force exit after p75 holding window elapsed.
    if holding > 0 and entry_bar is not None:
        try:
            elapsed = cur_bar - int(entry_bar)
        except (TypeError, ValueError):
            elapsed = 0
        if elapsed >= max_holding_bars:
            return Action("close", symbol,
                          reason=f"time-stop: held {elapsed} bars >= "
                                 f"{max_holding_bars} (p75); zombie cut")

    # 3) Entry gate: regime filter blocks NEW entries only.
    regime = market_state.get("regime")
    if hi is not None and last > hi and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(breakout signal blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f}")

    return Action("hold", symbol,
                  reason=f"no breakout (last={last:.2f}, hi={hi}, lo={lo}, "
                         f"holding={holding})")