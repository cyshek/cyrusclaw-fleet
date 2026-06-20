"""Donchian breakout on XLK 1h bars with a HARD TIME-STOP exit.

Thesis: this is `breakout_xlk` (long when close > 20-bar Donchian high, exit
when close < 20-bar Donchian low) plus a hard time-stop. The parent's trades
have a long right tail of holding periods (p25=14, median=34, p75=43 bars).
The hypothesis is that a breakout that hasn't resolved within the parent's
typical holding window is dead money: the momentum thesis has decayed, the
position is tying up capital, and the longer it churns the more likely it
mean-reverts back through the entry. So after N bars we force-close
regardless of the Donchian exit signal.

Entry signal: close > prior 20-bar high AND flat (unchanged from parent).
Exit signals (either fires): (a) parent's Donchian close (close < 20-bar
low), or (b) TIME-STOP after N bars held.

N = 43, the parent profile's p75 holding-bars value. Grounding rationale:
the parent already closes ~75% of trades within 43 bars on its own signal,
so a 43-bar time-stop is deliberately near-inert on the fast/normal majority
and only bites the slowest ~25% of trades — the ones the directive targets as
"dead money." A tighter N (e.g. the median 34) would amputate the normal
right half of the holding distribution and likely cut winners that simply
take a while to run; 43 surgically removes only the stragglers.

Which bucket did the slow trades fall into? In a breakout system the edge is
front-loaded: the parent profile shows median max-runup +2.60% but p75
drawdown only -0.70%, i.e. trades that work tend to run early. Trades still
open past p75 holding are disproportionately the ones that never ran (no
clean exit because price chopped sideways near entry), so on average the
time-stopped cohort skews toward the parent's UNPROFITABLE / break-even
bucket — exactly the dead-money the time-stop is meant to recycle. The
time-stop therefore aims to free capital from non-performing churn rather
than to clip winners.

Time-stop is a HARD exit, evaluated alongside (and after) the parent's close
signal, in the same defensive slot a stop-loss would occupy: it can never be
gated by an entry filter, so an open position is always closeable.

Entry-bar tracking: on the bar we open, position_state has no recorded entry
index yet, so we stamp `entry_bar_index` = current bar count. On subsequent
bars we read it back and force-close once (current_bar_index - entry) >= N.
If the runner doesn't persist the stamp (entry_bar_index missing while
holding), we fall back to honoring only the parent's Donchian exit rather
than guessing an age — never trap the position, but don't force a spurious
time-stop on bar 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest


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
    notional = float(params.get("notional_usd", 1000.0))
    max_hold_bars = int(params.get("max_hold_bars", 43))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    # Current bar index = number of bars seen so far (monotonic within a run).
    current_bar_index = len(cs)

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # ----- EXITS FIRST (never gated; both hard exits live here) -----
    if holding > 0:
        # (a) Parent's Donchian close signal.
        if lo is not None and last < lo:
            return Action("close", symbol,
                          reason=f"close {last:.2f} < {lookback}-bar low {lo:.2f}")
        # (b) TIME-STOP: force-close once held >= max_hold_bars.
        entry_idx = pos.get("entry_bar_index")
        if entry_idx is not None:
            try:
                held = current_bar_index - int(entry_idx)
            except (TypeError, ValueError):
                held = None
            if held is not None and held >= max_hold_bars:
                return Action("close", symbol,
                              reason=f"time-stop: held {held} bars >= "
                                     f"{max_hold_bars} (p75 holding)")

    # ----- ENTRY (only when flat) -----
    if hi is not None and last > hi and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      qty=None,
                      reason=f"close {last:.2f} > {lookback}-bar high {hi:.2f} "
                             f"(entry_bar_index={current_bar_index})")

    return Action("hold", symbol,
                  reason=f"no signal (last={last:.2f}, hi={hi}, lo={lo}, "
                         f"holding={holding})")