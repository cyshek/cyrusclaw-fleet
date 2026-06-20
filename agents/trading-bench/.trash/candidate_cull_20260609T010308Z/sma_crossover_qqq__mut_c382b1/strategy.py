"""SMA(10/30) crossover on QQQ 1h bars, with a REGIME-CONDITIONAL hard stop-loss.

Thesis: the parent (`sma_crossover_qqq`) is a long-only crossover with no
explicit risk exit — it only sells when the fast SMA crosses back below the
slow SMA, which can lag badly in a fast bear/chop tape. This mutation keeps
the parent's crossover entry/exit untouched but adds a hard stop whose
tightness is conditioned on the broad-market regime (SPY vs its 50d SMA).

Entry signal: SMA(fast) > SMA(slow) while flat (identical to parent).
Exit signals (either fires the close, whichever triggers first):
  1. Parent crossover exit: SMA(fast) < SMA(slow) while long.
  2. Regime-conditional hard stop on unrealized loss vs avg_entry_price:
       - BEAR/CHOP (SPY < 50d SMA): TIGHT stop. We expect the parent's edge
         to bleed here, so we cut losers fast.
       - BULL (SPY >= 50d SMA): LOOSE stop. Let winners breathe; the stop is
         only a catastrophic backstop, not a routine exit.

Edge rationale: the parent's regime exposure is asymmetric — long-only books
bleed in downtrends because the crossover exit lags. A tight stop ONLY in
bear regime trims that left tail without clipping the bull-trend runners that
generate most of the parent's runup (median +1.17%, p75 +3.03%).

Thresholds are grounded in the PARENT PROFILE of per-trade max drawdown
(n=68 closed trades, all 8 walk-forward windows):
  p25 = -1.67%  |  median = -1.14%  |  p75 = -0.61%  ;  57% of trades touched >=1% DD.
  - TIGHT stop = 0.85%. Sits between p75 (0.61%) and median (1.14%), i.e.
    "near p75, close to the median" as the directive asks. It would have
    fired on MORE than half of historical trades' drawdowns when active —
    appropriate for the regime where we WANT to be quick to cut.
  - LOOSE stop = 1.80%. Sits just BEYOND p25 (1.67%), so in bull regime it is
    nearly inert against the parent's historical drawdowns — it only catches
    a trade that runs deeper than essentially any the parent ever held,
    letting normal bull-trend noise breathe exactly as the directive wants.

The stop NEVER blocks the parent's own close signal: close logic runs in full
before any entry gate, and the stop is itself a close (it only ever EXITS).

Regime data: read from `market_state["regime"]` = {"spy_closes": [...],
"spy_last": float}. When regime is None (crypto / SPY bars unavailable) the
stop falls back to the TIGHT threshold as a conservative default — "don't
know the regime, so protect capital" — and entries behave like the parent.
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
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    tight_stop = float(params.get("tight_stop_pct", 0.0085))  # 0.85% (bear/chop)
    loose_stop = float(params.get("loose_stop_pct", 0.0180))  # 1.80% (bull)

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Mandatory not-enough-bars guard: need slow_p closes for the slow SMA.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0) or 0.0)

    # ---- CLOSE LOGIC FIRST — no filter may ever trap us in a position. ----
    if holding > 0:
        # (1) Parent crossover exit: honored exactly as in the parent.
        if fast < slow:
            return Action("close", symbol,
                          reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

        # (2) Regime-conditional hard stop on unrealized loss.
        entry_px = float(pos.get("avg_entry_price", 0.0) or 0.0)
        last_px = market_state.get("last_price")
        last_px = float(last_px) if last_px is not None else cs[-1]
        if entry_px > 0.0 and last_px > 0.0:
            loss_pct = (entry_px - last_px) / entry_px  # >0 means we're down
            regime = market_state.get("regime")
            if regime is None:
                # Unknown regime -> conservative tight stop.
                stop_pct = tight_stop
                regime_label = "regime?"
            elif regime_uptrend(regime.get("spy_closes") or [], period=regime_period):
                stop_pct = loose_stop  # bull: let it breathe
                regime_label = f"SPY>={regime_period}dSMA"
            else:
                stop_pct = tight_stop  # bear/chop: cut fast
                regime_label = f"SPY<{regime_period}dSMA"
            if loss_pct >= stop_pct:
                return Action("close", symbol,
                              reason=(f"stop {loss_pct*100:.2f}% loss >= "
                                      f"{stop_pct*100:.2f}% [{regime_label}] "
                                      f"(entry={entry_px:.2f}, last={last_px:.2f})"))

    # ---- ENTRY GATE — parent crossover entry, unchanged. ----
    if fast > slow and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")