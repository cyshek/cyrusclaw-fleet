"""SMA crossover on QQQ 1h bars with a single partial scale-out.

Thesis: the parent (`sma_crossover_qqq`) holds full size from the 10/30 SMA
up-cross to the down-cross and gives back gains on winners that run up and
then fade before the slow cross catches it. This mutation locks in HALF the
position once a trade has run up to the parent's MEDIAN per-trade max runup,
then lets the other half ride the parent's normal SMA-cross exit.

Entry signal: SMA(10) > SMA(30) while flat -> buy full notional (unchanged
from parent).
Exit signals (in priority order, both honored regardless of any gate):
  1. Full close when SMA(10) < SMA(30) and holding > 0 (parent exit; fires
     the remaining half too).
  2. One-time partial scale-out: when last price has risen >= +1.17% above
     the recorded entry price, sell HALF the current holding (qty/2).
The `scaled_out` flag in position_state is set so the partial fires at most
ONCE per trade.

Why +1.17%: from this parent's 68-trade profile, per-trade max runup has
p25=+0.52%, MEDIAN=+1.17%, p75=+3.03%, and 56% of trades touch >=1% runup.
Setting the scale-out at the median means it would have fired on roughly half
of historical trades — de-risking the runners that actually moved while
leaving the small/flat trades fully on the parent exit. A target above p75
(3.03%) would be inert; the median is the directive-mandated ~50% fire rate.

Edge rationale: half-off at the median runup converts a chunk of unrealized
gain into realized gain before mean-reversion erases it, while the trailing
half preserves the parent's full upside capture on trades that keep trending.
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
    notional = float(params.get("notional_usd", 1000.0))
    # Scale-out trigger = parent's MEDIAN per-trade max runup (+1.17%).
    scale_out_pct = float(params.get("scale_out_pct", 0.0117))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Need slow_p + 1 closes so both SMAs are defined; mandatory guard.
    need = slow_p + 1
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0) or 0)
    entry_px = float(pos.get("entry_price", 0) or 0)
    scaled_out = bool(pos.get("scaled_out", False))

    # ---- CLOSE LOGIC FIRST (never blocked by any gate) ----
    # 1. Parent full-exit on bearish cross — closes the remaining half too.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2. One-time partial scale-out at the parent's median runup.
    if holding > 0 and not scaled_out and entry_px > 0:
        runup = (last - entry_px) / entry_px
        if runup >= scale_out_pct:
            return Action("sell", symbol, qty=holding / 2.0,
                          reason=(f"scale-out half: runup {runup*100:.2f}% "
                                  f">= {scale_out_pct*100:.2f}% "
                                  f"(entry={entry_px:.2f}, last={last:.2f})"))

    # ---- ENTRY GATE (only when flat) ----
    if fast > slow and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=(f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                          f"holding={holding}, scaled_out={scaled_out})"))