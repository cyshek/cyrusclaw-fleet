"""SMA crossover on QQQ 1h bars with a HARD TIME-STOP exit.

Parent: `sma_crossover_qqq` (fast SMA(10) crosses slow SMA(30); long-only;
exit when fast < slow). Thesis of this mutation: trades that have not been
resolved by the parent's crossover exit within their *typical* holding
window are mostly dead money — capital pinned in a position that is neither
trending out as a winner nor getting cut, just drifting sideways. Forcing
those slow trades out frees capital and trims the right tail of holding
time without touching the parent's normal entry/exit logic.

Entry: unchanged from parent — buy when SMA(fast) > SMA(slow) and flat.
Exit:  (1) parent crossover exit (SMA(fast) < SMA(slow)), OR
       (2) HARD time-stop — force-close once the position has been held for
           >= TIME_STOP_BARS bars, regardless of the crossover state. The
           time-stop fires AFTER the parent close check, exactly like a
           stop-loss: it is an additional hard exit, never an entry filter,
           so it can never trap us in or block a normal exit.

Grounding for TIME_STOP_BARS (default 39): the parent's empirical holding
distribution over 68 closed trades across 8 walk-forward windows is
p25=11, median=20, p75=39 bars (1Hour). The directive asks to force out the
slow ~25% of trades, so N is set at the p75 value of 39 bars — a trade that
reaches 39 bars open has outlasted 75% of the parent's historical trades and
is, by this thesis, overstaying. N is intentionally NOT a round number; it
is the measured p75 of this exact parent's holding profile.

Which bucket did the slow trades fall in? Inference from the parent profile:
median per-trade runup is only +1.17% while p75 runup jumps to +3.03% — the
real winners are the minority that trend far and tend to resolve on the
crossover. Trades that linger toward the p75 holding tail without the fast/
slow lines re-crossing skew toward the flat-to-losing ("dead money") bucket
rather than the big-winner bucket, so cutting them at 39 bars should remove
more marginal/unprofitable holding time than it sacrifices in upside. This is
an inference from the holding-vs-runup shape, not a measured per-trade
correlation, and the walk-forward will adjudicate whether it actually helps.

Entry-bar tracking: on the first bar we observe an open position without a
recorded entry index, we stamp position_state[symbol]["entry_bar_index"]
with the current bar count (len(closes)). The backtester/runner preserves
custom position_state keys across bars while a position is open and clears
them on close (flat -> pop), so the stamp self-resets per trade. bars_held =
current_bar_count - entry_bar_index.
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
    # p75 of the parent's holding-bars distribution (force out slow 25%).
    time_stop_bars = int(params.get("time_stop_bars", 39))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Not-enough-bars guard: we need at least slow_p closes to form SMA(slow).
    if len(cs) < slow_p:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0
    bar_count = len(cs)  # monotonic bar index: bars are market_state["bars"][:i+1]

    # ----- CLOSE LOGIC ALWAYS RUNS FIRST (no exit may ever be blocked) -----
    if holding > 0:
        # (1) Parent crossover exit.
        if fast < slow:
            return Action("close", symbol,
                          reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

        # (2) HARD time-stop. Stamp entry bar on first sight of this position,
        #     then force-close once held >= time_stop_bars.
        entry_idx = pos.get("entry_bar_index") if pos else None
        if entry_idx is None:
            # First bar we see this open position without a stamp: record it.
            # (Covers the entry bar and any position opened before this logic
            # ran.) No close yet on the stamping bar.
            pos["entry_bar_index"] = bar_count
            return Action("hold", symbol,
                          reason=f"holding (entry stamped @bar {bar_count}, "
                                 f"fast={fast:.2f}, slow={slow:.2f})")
        bars_held = bar_count - int(entry_idx)
        if bars_held >= time_stop_bars:
            return Action("close", symbol,
                          reason=f"time-stop: held {bars_held} >= "
                                 f"{time_stop_bars} bars (p75 holding)")
        # Holding, not yet timed out, no crossover exit.
        return Action("hold", symbol,
                      reason=f"holding {bars_held}/{time_stop_bars} bars "
                             f"(fast={fast:.2f}, slow={slow:.2f})")

    # ----- ENTRY (only reached when flat) -----
    if fast > slow and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")