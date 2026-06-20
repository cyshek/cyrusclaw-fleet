"""SMA crossover on QQQ 1h bars with a TIGHT hard stop-loss overlay.

Thesis: the parent (`sma_crossover_qqq`) enters on a fast>slow SMA cross and
only exits on the opposite cross. That exit is structurally slow — median
holding period is 20 bars (1Hour) and the crossover can lag a sharp adverse
move by many bars, so a trade can bleed well past the point where the thesis
is already broken before fast<slow finally fires.

Entry signal: SMA(fast) > SMA(slow) and flat (unchanged from parent).
Exit signal: the PARENT exit (fast < slow) ALWAYS runs first and is never
blocked. ADDITIONALLY, a hard stop-loss closes the position if price falls
more than `stop_loss_pct` below the recorded entry price.

Stop value — grounded in the parent's empirical per-trade drawdown
distribution (68 trades / 8 windows): median max-drawdown is -1.14%, p25
(deeper tail) is -1.67%, and 57% of trades touched >=1% drawdown. The
directive caps the stop at 0.3%-1.0% (tighter than 1.5%+, which would be
inert relative to the p25 tail). I chose 0.8%: it sits BELOW the median
drawdown (1.14%), so it would have triggered on more than half of historical
trades, and it lands inside the dense >=1%-drawdown cluster (57% of trades)
rather than out in the rare p25 tail. The move it targets is the fast,
within-trade reversal that craters the position in a handful of bars — the
kind of drop the lagging crossover exit misses until it has already given
back most of the move. A stop tighter than ~0.6% would start firing on the
shallow-tail (p75 = -0.61%) noise that the trade routinely recovers from;
0.8% stays clear of that band while still firing often enough to be live, not
inert code.

Entry-price tracking: recorded into `position_state[symbol]["entry_price"]`
on the bar we issue the buy, and read back on subsequent bars to evaluate the
stop. If we are holding but have no recorded entry price (e.g. position
pre-existed this strategy), we fall back to seeding it from the current close
so the stop arms from here rather than never arming.
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
    stop_loss_pct = float(params.get("stop_loss_pct", 0.008))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Mandatory not-enough-bars guard: need at least `slow_p` closes for SMA.
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # SMA values are guaranteed non-None here (len(cs) >= slow_p >= fast_p),
    # but coerce defensively in case of degenerate params.
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # ---- CLOSE LOGIC FIRST — never blocked by the stop or any gate. ----
    # 1) Parent exit runs first: fast < slow while long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2) Hard stop-loss: only evaluated while long, only after the parent
    #    exit had its chance. Read recorded entry price; seed it if missing.
    if holding > 0:
        entry_price = pos.get("entry_price")
        if entry_price is not None:
            entry_price = float(entry_price)
            if entry_price > 0:
                drawdown = (last - entry_price) / entry_price
                if drawdown <= -stop_loss_pct:
                    return Action("close", symbol,
                                  reason=(f"stop-loss {drawdown*100:.2f}% <= "
                                          f"-{stop_loss_pct*100:.2f}% "
                                          f"(entry={entry_price:.2f}, "
                                          f"last={last:.2f})"))
        else:
            # Holding with no recorded entry price: arm the stop from here.
            pos["entry_price"] = last
            position_state[symbol] = pos

    # ---- ENTRY GATE — runs only after all close logic. ----
    if fast > slow and holding == 0:
        # Record entry price so the stop can arm on subsequent bars.
        pos["entry_price"] = last
        position_state[symbol] = pos
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")