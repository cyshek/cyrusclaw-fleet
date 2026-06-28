"""Fast US-dollar TREND carrier (UUP SMA50 crossover) + a 20-bar VOLATILITY GATE.

PAPER ONLY. No real money. MUTATION CHILD of `trend_follow_uup`.

PARENT THESIS (unchanged): SMA crossover on UUP (US-dollar bullish ETF) daily
closes — BUY when close > SMA(period) and flat; CLOSE when close < SMA(period)
and long. A deliberate DE-CORRELATOR leg: dollar-trend is negatively correlated
to the equity-heavy single-name pool (monthly trend-return corr to SPY -0.415),
so it injects orthogonal cross-asset trend DNA the equity-momentum pool lacks.

MUTATION (this child): add a realized-volatility filter that BLOCKS NEW ENTRIES
when 20-bar realized volatility (sample stdev of the last 20 per-bar pct
returns) exceeds `vol_threshold` (default 0.006). Thesis: a slow dollar
SMA-trend signal is cleanest in low-vol drift regimes; the choppiest 20-bar
windows produce the most whipsaw entries, so refusing to open into them should
trim the worst false breakouts while leaving the calm-trend edge intact.

WHY 0.006 (grounded, not guessed): on UUP's full daily history the 20-bar
realized vol AT the parent's replicated SMA50 entry points has median ~0.0042
and p75 ~0.0058; a 0.006 cap sits just above that median/p75 cluster and would
have skipped ~20% of historical entries (>=15% floor satisfied, and inside the
0.005–0.025 allowed band) — gating out only the genuinely choppiest bars rather
than being inert dead code (any cap >=0.015 never fires for this symbol).

EXITS ARE NEVER GATED: the close signal (close < SMA) runs FIRST, so the
volatility filter can only ever suppress a NEW long — it can never trap an
already-open position. When `market_state` lacks enough bars to compute the
vol window, the gate is skipped (permissive) so warmup/edge cases fall through
to the parent behavior.

BAR SHAPE: the live gate path feeds Alpaca-shape bars {c,h,l,o,t,v,vw} (NO
adjclose / NO 'close' / NO 'date'). This reads close via 'c' (falling back to
'close'/'adjclose') so it works in BOTH the gate harness and any cache shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import stdev
from typing import List, Optional


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


def _realized_vol(cs: List[float], window: int) -> Optional[float]:
    """Sample stdev of the last `window` per-bar pct returns.

    Needs window+1 closes to form `window` returns. Returns None when there
    aren't enough bars (caller treats None as 'unknown' -> gate is permissive).
    """
    if window < 2 or len(cs) < window + 1:
        return None
    seg = cs[-(window + 1):]
    rets: List[float] = []
    for i in range(1, len(seg)):
        prev = seg[i - 1]
        if prev == 0:
            return None
        rets.append((seg[i] - prev) / prev)
    if len(rets) < 2:
        return None
    return stdev(rets)


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "UUP")
    period = int(params.get("period", 50))
    notional = float(params.get("notional_usd", 1000.0))
    vol_window = int(params.get("vol_window", 20))
    vol_threshold = float(params.get("vol_threshold", 0.006))

    cs = _closes(market_state.get("bars") or [])
    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Need at least `period` closes for the SMA; the vol window (window+1
    # closes) is a soft requirement handled inside _realized_vol.
    if len(cs) < period:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)}<{period})")

    sma = sum(cs[-period:]) / period
    last = cs[-1]

    # Close logic ALWAYS runs first — the volatility gate must never trap us long.
    if last < sma and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.4f} < SMA{period} {sma:.4f}")

    # Entry: parent crossover, then apply the volatility gate to NEW longs only.
    if last > sma and holding == 0:
        rv = _realized_vol(cs, vol_window)
        if rv is not None and rv > vol_threshold:
            return Action("hold", symbol,
                          reason=(f"vol gate: {vol_window}-bar realized vol "
                                  f"{rv:.5f} > {vol_threshold:.5f} (entry blocked)"))
        rv_txt = f"{rv:.5f}" if rv is not None else "n/a"
        return Action("buy", symbol, notional_usd=notional,
                      reason=(f"close {last:.4f} > SMA{period} {sma:.4f}; "
                              f"vol {rv_txt} <= {vol_threshold:.5f}"))

    return Action("hold", symbol,
                  reason=f"close {last:.4f}, SMA{period} {sma:.4f}, holding={holding:g}")