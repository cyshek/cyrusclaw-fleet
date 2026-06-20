"""SMA crossover on QQQ 1h bars, gated by a GRADED SPY-trend regime score.

Variant of `sma_crossover_qqq_regime`. The parent used a binary regime gate
(`regime_uptrend`): enter only when SPY > its 50d SMA. This mutation tightens
that gate into a graded one using `regime_score(spy_closes, 50)` — the percent
distance of SPY above/below its 50d SMA — and requires SPY to be at least 2%
ABOVE its 50d SMA (regime_score > 0.02) before any new long is opened.

Thesis: the binary gate fires the instant SPY pokes above its MA, including
shallow, whipsaw-prone reclaims that often roll right back over. Demanding a
2% cushion only enters when the broad-market uptrend has real separation from
the mean, which should filter out the marginal-regime entries that contribute
disproportionately to the parent's bear/chop bleed. The parent's own trade
profile shows 43% of trades touched a >=1% drawdown and the median trade only
ran up +1.34%; trimming the weakest-regime entries should raise the average
quality of the surviving trades.

Entry: fast SMA (10) crosses above slow SMA (30) AND regime_score(SPY,50) > 0.02.
Exit: fast SMA < slow SMA (bearish cross) — honored unconditionally.

Important: the regime gate blocks NEW ENTRIES ONLY. If a position is already
open when the regime weakens, the bearish-cross close signal still fires. The
gate must never trap us long.

Regime data: read from `market_state["regime"]` (set by runner/backtester to
{"spy_closes": [...], "spy_last": float}, or None when unavailable). When the
regime is None or SPY bars are too few, `regime_score` returns 0.0, which is
NOT > 0.02, so entries are blocked rather than taken blind. This is the
intended conservative behavior for a stricter filter: no broad-market
confirmation => no new long.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, regime_score


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
    regime_period = int(params.get("regime_period", 50))
    regime_min = float(params.get("regime_min_score", 0.02))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # Close logic ALWAYS runs first — the regime gate must never trap us long.
    if fast < slow and holding > 0:
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # Entry gate: graded regime filter, applied to NEW entries only.
    if fast > slow and holding == 0:
        regime = market_state.get("regime")
        spy_closes = (regime.get("spy_closes") if regime else None) or []
        score = regime_score(spy_closes, period=regime_period)
        if score <= regime_min:
            return Action("hold", symbol,
                          reason=f"regime: SPY score {score:.4f} <= "
                                 f"{regime_min:.4f} ({regime_period}d) "
                                 f"(bullish cross blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}, "
                             f"regime score {score:.4f} > {regime_min:.4f}")
    return Action("hold", symbol,
                  reason=f"no signal (fast={fast:.2f}, slow={slow:.2f}, holding={holding})")