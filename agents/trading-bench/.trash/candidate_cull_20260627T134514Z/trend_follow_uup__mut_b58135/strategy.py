"""SMA50 trend (parent trend_follow_uup) AND-confirmed by RSI(14) momentum.

PAPER ONLY. No real money. Mutation child of `trend_follow_uup` (UUP @ 1Day).

THESIS / EDGE
-------------
The parent goes long the instant close crosses above SMA(50) and flat when it
crosses back below. Its empirical trade profile is thin and whippy: only 3
closed trades, median per-trade runup just +0.09% while 33% of trades touched
>=1% drawdown and median drawdown bottomed at -0.33%. That shape is the
signature of "marginal" entries — price barely pokes above the 50-day mean with
no real momentum behind it, then immediately reverses, so the trade pays almost
nothing on the upside but eats a drawdown before the SMA exit fires.

SECOND SIGNAL (AND-confirmation): RSI(14) > rsi_min (default 50).
We require BOTH the parent's trend signal (close > SMA(period)) AND positive
short-term momentum (RSI above its midline) before opening. RSI > 50 means
recent average gains exceed recent average losses, i.e. the cross is being
driven by genuine buying pressure rather than noise grinding sideways across the
mean. This is a deliberate FILTER (AND, not OR): the goal is to ELIMINATE the
parent's specific failure mode — momentum-less SMA pokes that pay <0.1% and
risk >1% — not to add more trades. Fewer, better-confirmed entries.

EXIT: the parent's exit is preserved unchanged and fires ALONE — CLOSE when
close < SMA(period) and long. The RSI confirmation gates ENTRIES ONLY; an
already-open long is never made harder to close than it was to open (close
logic runs first, before any entry gate). If RSI is uncomputable (too few
deltas) it is treated as failing the gate for entries only, never trapping a
position.

BAR SHAPE: reads close via 'c' (Alpaca shape), falling back to
'close'/'adjclose', so it works in both the gate harness and any cache shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from strategies._lib.indicators import rsi


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _bar_close(b: dict) -> Optional[float]:
    """Close from an Alpaca-shape bar ('c') or a cache-shape bar
    ('close'/'adjclose'). Returns None if unparseable."""
    v = b.get("c")
    if v is None:
        v = b.get("close")
    if v is None:
        v = b.get("adjclose")
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _closes(bars: List[dict]) -> List[float]:
    out: List[float] = []
    for b in bars or []:
        c = _bar_close(b)
        if c is not None:
            out.append(c)
    return out


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "UUP")
    period = int(params.get("period", 50))
    rsi_period = int(params.get("rsi_period", 14))
    rsi_min = float(params.get("rsi_min", 50.0))
    notional = float(params.get("notional_usd", 1000.0))

    cs = _closes(market_state.get("bars") or [])
    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Need enough bars for the SMA and for RSI(rsi_period) (rsi needs > period
    # deltas, i.e. rsi_period + 1 closes). Use the larger requirement.
    need = max(period, rsi_period + 1)
    if len(cs) < need:
        return Action("hold", symbol,
                      reason=f"not enough bars ({len(cs)}<{need})")

    sma = sum(cs[-period:]) / period
    last = cs[-1]

    # --- Close logic ALWAYS runs first: the RSI gate must never trap us long.
    if last < sma and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.4f} < SMA{period} {sma:.4f}")

    # --- Entry: require parent trend signal AND RSI momentum confirmation.
    if last > sma and holding == 0:
        r = rsi(cs, rsi_period)
        if r is None or r <= rsi_min:
            return Action("hold", symbol,
                          reason=f"trend ok (close {last:.4f} > SMA{period} "
                                 f"{sma:.4f}) but RSI{rsi_period}="
                                 f"{('NA' if r is None else format(r, '.1f'))}"
                                 f" <= {rsi_min:.1f} (entry blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.4f} > SMA{period} {sma:.4f} AND "
                             f"RSI{rsi_period} {r:.1f} > {rsi_min:.1f}")

    return Action("hold", symbol,
                  reason=f"close {last:.4f}, SMA{period} {sma:.4f}, "
                         f"holding={holding:g}")