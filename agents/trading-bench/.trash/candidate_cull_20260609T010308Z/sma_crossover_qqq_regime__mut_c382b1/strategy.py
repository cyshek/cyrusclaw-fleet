"""SMA crossover on QQQ 1h bars with a SPY-regime ENTRY gate plus a new
REGIME-CONDITIONAL hard stop-loss on EXITS.

Parent (`sma_crossover_qqq_regime`) opens on a bullish SMA(fast)>SMA(slow)
cross, gated so new longs only open when SPY is above its 50d SMA, and
closes on the bearish cross. The parent has NO protective stop — it rides a
position until the slow cross flips, eating the full per-trade drawdown.

This mutation adds a regime-conditional hard stop on the OPEN position:
  - BEAR/CHOP (SPY below its 50d SMA): TIGHT stop of 0.60%. The parent's
    per-trade max-drawdown distribution is p75 -0.48% / median -0.76%, so a
    0.60% stop sits between p75 and the median — it fires on a meaningful
    chunk (well under half, but more than a quarter) of historical trades,
    cutting losers fast in the regime where the parent bleeds, while staying
    inside the empirical distribution (not inert).
  - BULL (SPY at/above its 50d SMA): LOOSE stop of 1.30%, right at the p25
    deeper-tail drawdown (-1.32%). In uptrends winners frequently dip 0.5-1%
    before resuming (median runup +1.34% vs median drawdown -0.76%), so the
    loose stop only triggers on the worst ~25% tail and otherwise lets trends
    breathe — essentially "no stop" for normal bull noise.

Thesis: the parent's edge is undone by deep drawdowns taken in down/chop
regimes; a regime-aware stop should clip the bear tail without strangling
bull trends. EXIT signal = parent bearish cross OR the regime-conditional
stop. ENTRY signal unchanged (bullish cross + SPY-uptrend gate). Edge: same
entry edge as parent, with the left tail of the bear-regime trade
distribution truncated.

CRITICAL: the stop is EXIT logic and runs in the close section, BEFORE the
entry gate, and it NEVER blocks the parent's own bearish-cross close. If a
position is open it is always closeable; the regime gate only restricts new
entries. Regime read from `market_state["regime"]`
({"spy_closes": [...], "spy_last": float}, or None); None => loose-stop /
parent-fallthrough behavior.
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


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "QQQ")
    fast_p = int(params.get("fast", 10))
    slow_p = int(params.get("slow", 30))
    notional = float(params.get("notional_usd", 100.0))
    regime_period = int(params.get("regime_period", 50))
    # Grounded in parent profile: p75 dd -0.48%, median -0.76%, p25 -1.32%.
    stop_bear_pct = float(params.get("stop_bear_pct", 0.0060))  # 0.60%
    stop_bull_pct = float(params.get("stop_bull_pct", 0.0130))  # 1.30%

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Not-enough-bars guard (need slow_p closes for the slow SMA).
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # ----- CLOSE LOGIC ALWAYS RUNS FIRST (regime gate must never trap us long) -----
    # 1) Parent's own bearish-cross close. Honored unconditionally — the stop
    #    additions below must never pre-empt or block this exit.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2) Regime-conditional hard stop-loss on the OPEN position. Only when we
    #    can measure drawdown from a known entry price; otherwise skip (never
    #    blocks an exit, only adds one).
    if holding > 0 and cs:
        entry = pos.get("avg_entry_price")
        if entry is None:
            entry = pos.get("entry_price")
        try:
            entry = float(entry) if entry is not None else 0.0
        except (TypeError, ValueError):
            entry = 0.0
        if entry > 0:
            last = cs[-1]
            dd = (last - entry) / entry  # negative when underwater
            regime = market_state.get("regime")
            # Permissive default: treat unknown regime as bull (loose stop),
            # matching parent's "absence of bearish signal => behave normally".
            in_bear = False
            if regime:
                in_bear = not regime_uptrend(regime.get("spy_closes") or [],
                                             period=regime_period)
            stop_pct = stop_bear_pct if in_bear else stop_bull_pct
            if dd <= -stop_pct:
                tag = "bear" if in_bear else "bull"
                return Action("close", symbol,
                              reason=f"stop {tag} dd={dd*100:.2f}% "
                                     f"<= -{stop_pct*100:.2f}% "
                                     f"(entry={entry:.2f}, last={last:.2f})")

    # ----- ENTRY GATE (respect regime filter only when entering new positions) -----
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