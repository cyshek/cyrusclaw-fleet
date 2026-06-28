"""UUP SMA-trend OR'd with a VOLUME-CONFIRMED breakout (daily bars).

PAPER ONLY. No real money. Mutation child of `trend_follow_uup`.

THESIS: The parent is a fast UUP (US-dollar bullish ETF) SMA(50) trend
follower — long when close > SMA(50), flat when below. On a thin, slow
dollar-trend that signal alone is starved (the parent closed only 3 trades
across 8 walk-forward windows), so we ADD a second independent entry: a
VOLUME-CONFIRMED breakout borrowed from volume_breakout_qqq. The breakout
leg fires only when UUP closes above its N-bar high AND that bar's volume
exceeds vol_mult x the N-bar average volume — the volume confirmation
(price-AND-volume) is INTERNAL to the breakout leg, filtering out hollow
breakouts on no participation.

WHY OR (not AND): the two legs answer different questions. The SMA-trend leg
captures slow, established dollar uptrends; the volume-confirmed-breakout leg
captures fresh, high-conviction range expansions that the slow SMA hasn't yet
turned up on. ANDing them would intersect to almost nothing (a breakout above
an N-bar high while ALSO already above SMA(50) is rare and redundant) and would
keep the thin parent starved. ORing them is purely ADDITIVE — we enter when
(SMA-trend up) OR (a volume-confirmed breakout fires) — so the dollar-trend
GAINS entries rather than losing them, which is the explicit mutation goal.

EXIT: close < SMA(period) OR close < the N-bar low. Exits are evaluated FIRST
and are NEVER gated by volume, so an already-open position is always closeable
even when volume data is missing/zero or the breakout machinery is dormant.

EDGE: a real dollar uptrend should show up either as a sustained SMA regime or
as a volume-backed breakout; capturing both widens participation in genuine
dollar strength while the dual exit (trend-loss OR range-break) cuts losers.

BAR SHAPE: live gate path feeds Alpaca-shape bars {c,h,l,o,t,v,vw}. Close is
read via 'c' (falling back to 'close'/'adjclose'); volume via 'v'. Bars with
missing/zero/unparseable volume gracefully DISABLE only the volume-breakout
leg — the SMA-trend leg and all exits still run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _bar_close(b: dict) -> Optional[float]:
    """Close from an Alpaca-shape bar ('c') or cache-shape ('close'/'adjclose')."""
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


def _bar_vol(b: dict) -> Optional[float]:
    """Volume from an Alpaca-shape bar ('v'), falling back to 'volume'.
    Returns None when missing/unparseable; 0.0 is preserved (treated as no
    participation by callers)."""
    v = b.get("v")
    if v is None:
        v = b.get("volume")
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f < 0:
        return None
    return f


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
    breakout_lookback = int(params.get("breakout_lookback", 20))
    vol_mult = float(params.get("vol_mult", 1.5))
    notional = float(params.get("notional_usd", 1000.0))

    bars = market_state.get("bars") or []
    cs = _closes(bars)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Need enough bars for BOTH legs: SMA(period) and an N-bar breakout window
    # (N prior bars to form the high/low, +1 for the current bar).
    need = max(period, breakout_lookback + 1)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)}<{need})")

    sma = sum(cs[-period:]) / period
    last = cs[-1]

    # N-bar high/low computed over the PRIOR N bars (exclude current bar).
    window = cs[-(breakout_lookback + 1):-1]
    hi = max(window)
    lo = min(window)

    # ---- EXITS FIRST (never gated by volume; always reachable) ----
    if holding > 0:
        if last < sma:
            return Action("close", symbol,
                          reason=f"close {last:.4f} < SMA{period} {sma:.4f}")
        if last < lo:
            return Action("close", symbol,
                          reason=f"close {last:.4f} < {breakout_lookback}-bar low {lo:.4f}")

    # ---- ENTRY: SMA-trend leg OR volume-confirmed-breakout leg ----
    if holding == 0:
        trend_up = last > sma

        # Volume-confirmed breakout leg (volume confirmation is INTERNAL here).
        breakout_fires = False
        vols: List[float] = []
        # Align volume to the same prior-N window used for the price high/low.
        for b in bars[-(breakout_lookback + 1):-1]:
            vv = _bar_vol(b)
            if vv is not None:
                vols.append(vv)
        cur_vol = _bar_vol(bars[-1]) if bars else None

        price_breaks = last > hi
        # Gracefully skip the volume leg if volume is missing/zero/insufficient.
        vol_avg = (sum(vols) / len(vols)) if vols else 0.0
        if (price_breaks and cur_vol is not None and cur_vol > 0.0
                and vol_avg > 0.0 and cur_vol > vol_mult * vol_avg):
            breakout_fires = True

        if trend_up or breakout_fires:
            if breakout_fires and not trend_up:
                reason = (f"vol-confirmed breakout: close {last:.4f} > "
                          f"{breakout_lookback}-bar high {hi:.4f}, "
                          f"vol {cur_vol:.0f} > {vol_mult:g}x avg {vol_avg:.0f}")
            elif trend_up and breakout_fires:
                reason = (f"close {last:.4f} > SMA{period} {sma:.4f} "
                          f"AND vol-confirmed breakout > {hi:.4f}")
            else:
                reason = f"close {last:.4f} > SMA{period} {sma:.4f}"
            return Action("buy", symbol, notional_usd=notional, reason=reason)

    return Action("hold", symbol,
                  reason=(f"no entry (last={last:.4f}, SMA{period}={sma:.4f}, "
                          f"hi={hi:.4f}, lo={lo:.4f}, holding={holding:g})"))