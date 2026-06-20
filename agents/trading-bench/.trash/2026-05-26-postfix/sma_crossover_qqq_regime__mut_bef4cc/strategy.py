"""SMA crossover on QQQ 1h bars, regime-gated, with a TIGHT 0.6% stop-loss.

Parent (`sma_crossover_qqq_regime`) exits when fast SMA crosses below slow
SMA — a lagging signal that can take many bars to fire after price has
already rolled over. This mutation adds a hard 0.6% stop-loss measured from
the recorded entry price.

Why 0.6% (and not looser): on QQQ 1h bars, a typical "noise" candle is
~0.2-0.4%; the SMA10/SMA30 cross typically lags a real reversal by 3-6
bars, during which price can drop 1-2% before the parent's exit fires.
A 0.6% stop sits just outside normal intra-bar chop but well inside the
drawdown the lagging SMA cross allows — so it actually triggers on the
sharp gap-down / news-shock candles that the parent sleeps through, while
not getting tapped out by ordinary 1h wiggle. A 1.5%+ stop would almost
never beat the parent's own exit to the punch and would be inert code.

Stop-loss runs AFTER the parent's own close signal (parent exit wins ties),
and entry price is tracked in position_state[symbol]["entry_px"], seeded
on the bar we issue the buy.
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
    stop_pct = float(params.get("stop_loss_pct", 0.006))  # 0.6%

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    last = cs[-1]

    # 1) Parent's own close signal ALWAYS runs first — never block exits.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2) Hard stop-loss: tight 0.6% below entry. Runs after parent's exit
    #    but before any hold — catches sharp drawdowns the lagging SMA misses.
    if holding > 0:
        entry_px = pos.get("entry_px")
        if entry_px is not None:
            entry_px = float(entry_px)
            if entry_px > 0 and last <= entry_px * (1.0 - stop_pct):
                return Action("close", symbol,
                              reason=f"stop-loss: last={last:.2f} <= "
                                     f"entry={entry_px:.2f} * (1-{stop_pct:.4f})")

    # 3) Entry gate: respect regime filter only when entering new positions.
    regime = market_state.get("regime")
    if fast > slow and holding == 0:
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        # Record entry price so the stop-loss has a reference next bar.
        position_state.setdefault(symbol, {})["entry_px"] = last
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"@ {last:.2f} (stop {stop_pct*100:.2f}%)")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"holding={holding}, last={last:.2f})")