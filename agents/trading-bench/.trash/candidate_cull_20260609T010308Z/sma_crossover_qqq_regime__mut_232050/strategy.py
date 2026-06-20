"""SMA crossover on QQQ 1h bars (SPY-regime gated) with a one-shot partial exit.

Extends `sma_crossover_qqq_regime`: same SMA10/SMA30 crossover entries gated by
the SPY 50d-SMA regime filter, same bearish-cross full-close. NEW: a scale-out
leg. When an open position's last close has risen >= scale_out_pct above the
average entry price, we close HALF the position once, then let the remaining
half ride to the parent's normal bearish-cross exit.

Thesis: the parent's winners give back gains by holding the whole size to the
crossover exit. Locking in half at the median runup de-risks the trade while
preserving upside on the runner. Grounding for scale_out_pct = 1.34%: that is
the parent profile's MEDIAN max-runup per trade (p25 +0.70%, median +1.34%,
p75 +3.33%). Setting the trigger at the median means the scale-out would have
fired on ~50% of historical winners — exactly the "half of winners" target the
directive asks for — and it sits well below the p75 (+3.33%) so it is not inert.

One-shot guard: position_state[symbol]['scaled_out'] is read as a boolean so the
partial exit fires AT MOST ONCE per trade; once a position is flat again the
runner clears that flag with the position. The scale-out is an EXIT, so it is
evaluated BEFORE the entry gate and can never be blocked by the regime filter.
The full bearish-cross close is evaluated first of all and is never blocked.

Regime data: read from market_state['regime'] ({'spy_closes': [...]}, or None
when unavailable, e.g. crypto). When None the regime gate is a no-op and
behavior falls through to the parent.
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
    # Grounded in parent profile: median max-runup per trade = +1.34%.
    scale_out_pct = float(params.get("scale_out_pct", 1.34))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0) or 0.0)

    # Mandatory not-enough-bars guard (need slow_p closes for the slow SMA).
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # --- EXIT LOGIC FIRST (never gated by regime) -------------------------

    # 1) Full close on bearish cross — parent's primary exit. Always honored.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2) One-shot partial scale-out: position up >= scale_out_pct vs entry,
    #    and we have not already scaled out this trade. Sell HALF the holding.
    scaled_out = bool(pos.get("scaled_out", False))
    entry_price = float(pos.get("avg_entry_price", 0) or 0.0)
    if holding > 0 and not scaled_out and entry_price > 0:
        last = cs[-1]
        runup = (last - entry_price) / entry_price * 100.0
        if runup >= scale_out_pct:
            return Action("sell", symbol, qty=holding / 2.0,
                          reason=f"scale-out half: +{runup:.2f}% >= "
                                 f"{scale_out_pct:.2f}% (median runup)")

    # --- ENTRY GATE SECOND (regime filter applies to NEW entries only) -----
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
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"holding={holding})")