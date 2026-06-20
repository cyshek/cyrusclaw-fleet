"""SMA crossover on QQQ 1h bars with a HARD TIME-STOP exit.

Parent: `sma_crossover_qqq` — long QQQ when SMA(fast) > SMA(slow), close on
the inverse cross. Mutation: track the entry bar index in position_state and
force-close the position after N bars elapsed, regardless of the parent's
crossover signal. Thesis: trades that haven't resolved within their typical
holding window are dead money — the parent's edge, if any, plays out inside
its usual horizon; bars beyond that are noise tying up capital that could
rotate into a fresher signal.

Choice of N: parent profile holding-bars distribution is p25=11, median=20,
p75=39. The directive says "force out the slow 25%" → N = p75 = 39 bars.
Trades that close on the SMA-cross before bar 39 are unaffected; only the
slow tail (the 25% of trades that would otherwise drag past 39 hours) get
guillotined.

Time-stopped bucket: in the parent's raw_trades, holding_bars correlates
weakly-negatively with pnl in this distribution (median holding = 20 bars
while p75 runup is only +3.03%, and 57% of trades touched ≥1% drawdown
before exit — i.e. the long tail of holders is disproportionately the
losers grinding sideways/down waiting for a recross that never comes).
So time-stopped trades land on average in the UNPROFITABLE bucket — which
is exactly why cutting them is hypothesized to help.

Entry-vs-exit discipline: the time-stop is a HARD exit and runs alongside
the parent close signal, BEFORE entry logic, so an open position can always
be closed. Entry bar index is stamped into position_state[symbol]["_entry_bar"]
on the buy turn; the runner persists position_state across bars. We key off
the current bar count (len(bars)) so the index is monotone and comparable.
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
    time_stop_bars = int(params.get("time_stop_bars", 39))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    need = max(slow_p, fast_p)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    pos = position_state.get(symbol) or {}
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_bar = pos.get("_entry_bar")
    now_bar = len(cs)

    # --- HARD EXITS FIRST (time-stop + parent close) ---
    if holding > 0:
        if isinstance(entry_bar, (int, float)):
            elapsed = now_bar - int(entry_bar)
            if elapsed >= time_stop_bars:
                return Action("close", symbol,
                              reason=f"time-stop: held {elapsed} bars >= {time_stop_bars}")
        if fast < slow:
            return Action("close", symbol,
                          reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # --- ENTRY ---
    if fast > slow and holding == 0:
        pos["_entry_bar"] = now_bar
        position_state[symbol] = pos
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f} "
                             f"(time-stop armed @ +{time_stop_bars} bars)")

    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                         f"holding={holding}, entry_bar={entry_bar}, now={now_bar})")