"""SMA crossover on QQQ 1h bars with regime gate + half-position scale-out.

Mutation of `sma_crossover_qqq_regime`: when an open long has risen by
`scale_out_pct` above entry, sell HALF the position once, then let the
parent's bearish-cross close signal handle the remaining half. Hypothesis:
parent winners often run up then give it back before the slow SMA catches
down; locking in half near the median runup de-risks the trade while
preserving upside on the runners.

Threshold grounding (from parent profile, 42 trades, 8 windows):
- Median max runup per trade: +1.34%
- p25 runup: +0.70%, p75 runup: +3.33%
- 64% of trades touched >=1% runup
We set `scale_out_pct = 0.0134` (median) so the partial exit fires on
~50% of winners by construction — neither too eager (above p25 would
trigger on most noise) nor inert (above p75 would barely fire).

Entry signal: fast SMA crosses above slow SMA AND SPY regime is up.
Exits: (1) partial — half sold once when runup >= 1.34% from entry;
       (2) full — parent's bearish cross (fast < slow) closes remainder.
The `scaled_out` flag in position_state ensures the partial only fires
ONCE per trade. Regime gate blocks entries only, never exits.
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
    scale_out_pct = float(params.get("scale_out_pct", 0.0134))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_price = float(pos.get("avg_entry_price", 0.0) or pos.get("entry_price", 0.0) or 0.0)
    scaled_out = bool(pos.get("scaled_out", False))

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]

    # Close logic ALWAYS runs first — regime gate must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Partial exit: fire ONCE per trade when runup >= scale_out_pct.
    if holding > 0 and not scaled_out and entry_price > 0:
        runup = (last - entry_price) / entry_price
        if runup >= scale_out_pct:
            return Action("sell", symbol,
                          qty=holding / 2.0,
                          reason=f"scale-out: runup {runup*100:.2f}% >= "
                                 f"{scale_out_pct*100:.2f}% (half off, "
                                 f"remainder rides parent exit)")

    # Entry gate: respect regime filter only when entering new positions.
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
                         f"holding={holding}, scaled_out={scaled_out})")