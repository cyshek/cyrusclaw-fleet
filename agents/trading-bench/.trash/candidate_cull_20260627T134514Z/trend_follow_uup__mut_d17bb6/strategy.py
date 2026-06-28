"""Fast cross-asset TREND carrier on UUP — SMA(20) crossover single-name `decide()`.

PAPER ONLY. No real money.

PURPOSE: inject genuine CROSS-ASSET trend DNA into the single-name mutation gene
pool (GATE_PASSING_PARENTS), on the US-DOLLAR leg (UUP), as a deliberate
de-correlator parent (exactly how `trend_follow_gld` injects gold-trend DNA).
UUP was chosen empirically as the MOST equity-orthogonal non-equity leg
(monthly trend-return corr to SPY -0.415, to GLD -0.344) — a dollar-trend signal
is NEGATIVELY correlated to the equity-heavy pool and distinct from the existing
gold parent.

MUTATION vs PARENT: this child sweeps the trend LOOKBACK from the parent's
SMA(50) down to SMA(20) — a meaningfully faster medium-term trend. A shorter
window reacts sooner to dollar-trend reversals (the parent's median hold was
~1 bar, so it already trades fast turns); SMA(20) tests whether a quicker
crossover captures the same orthogonal dollar-trend DNA with earlier entries
and exits. All other logic is identical to the parent.

THE RULE (single leg, fast trend)
---------------------------------
SMA crossover on daily closes: BUY when close > SMA(period) and flat; CLOSE when
close < SMA(period) and long. Default leg is UUP (most equity-orthogonal cleanly
-profiling non-equity asset); override via params.

BAR SHAPE: the live gate path feeds Alpaca-shape bars {c,h,l,o,t,v,vw} (NO
adjclose / NO 'close' / NO 'date'). This reads close via 'c' (falling back to
'close'/'adjclose') so it works in BOTH the gate harness and any cache shape.
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
    period = int(params.get("period", 20))
    notional = float(params.get("notional_usd", 100.0))

    cs = _closes(market_state.get("bars") or [])
    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if len(cs) < period:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)}<{period})")

    sma = sum(cs[-period:]) / period
    last = cs[-1]

    if last > sma and holding == 0:
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"close {last:.4f} > SMA{period} {sma:.4f}")
    if last < sma and holding > 0:
        return Action("close", symbol,
                      reason=f"close {last:.4f} < SMA{period} {sma:.4f}")
    return Action("hold", symbol,
                  reason=f"close {last:.4f}, SMA{period} {sma:.4f}, holding={holding:g}")