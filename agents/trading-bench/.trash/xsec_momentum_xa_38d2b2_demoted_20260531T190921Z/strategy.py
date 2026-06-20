"""Cross-sectional momentum (Jegadeesh-Titman 12-1) on a CROSS-ASSET basket.

Archetype #1 from `reports/ARCHETYPE_TRIAGE_20260530T170659Z.md`,
**wave-4 cross-asset variant**. Sister candidate to
`xsec_momentum_236b86` (sector-equity universe, REJECTED in wave 3).

## Why this exists

Wave-3 #1 (sector-equity universe of 11 SPDRs) failed Bar A — REJECT.
The retrospective question: was the failure a property of the
strategy class (momentum doesn't work) or the universe class
(sector-equity is too internally correlated, all SPDRs share 0.7-0.9
SPY beta so the cross-sectional ranking has nowhere to find meaningful
dispersion)?

This candidate isolates the universe variable by re-running the SAME
strategy on a CROSS-ASSET basket spanning 4 asset classes:

  - SPY: US large-cap equity
  - EFA: developed international equity (~0.85 SPY beta but real
         dispersion in regional regimes — Europe / Japan can diverge)
  - TLT: 20+yr US Treasuries (negative SPY beta historically)
  - VNQ: US REITs (~0.7 SPY beta but rate-sensitive)
  - DBC: broad commodity basket (~0 SPY beta, inflation-sensitive)
  - GLD: gold (small/negative SPY beta, crisis hedge)

If this passes Bar A, prior REJECT was universe-class.
If this also rejects, prior REJECT was strategy-class — at least
under bench constraints (monthly cadence, $100 cap, alpaca_stocks
cost model). Either answer is informative.

## Spec

- Universe: 6 ETFs (above). Smaller than 11 SPDRs by design — fewer
  but more independent legs.
- Signal: trailing 12-month (252 trading bars) total return SKIPPING
  the most recent month (~21 trading bars). Canonical "12-1" lookback
  per Jegadeesh & Titman 1993. Computed per symbol independently.
- Allocation: long-only top-K (default K=2 of 6, ~N/3 rule-of-thumb
  for cross-asset). Per-leg notional = MAX_POSITION / K = $50/leg.
  Total exposure capped at MAX_POSITION = $100 by harness
  `_clamp_basket` regardless.
- Rebalance: calendar-month boundaries. First tick whose calendar
  month != stored last_rebalance_month triggers a rebalance.
- Cost model: alpaca_stocks (2 bps spread, 0 fee). All 6 symbols
  trade on US equity venues so the cost model is consistent.
- Optional regime gate: when `params.use_regime_filter` is True, all
  buys are gated on `regime_uptrend(spy_closes, regime_sma_period)`.
  **Per PATTERNS.md #1, this gate is documented as no-go for
  sector-equity baskets but MAY add genuine information on cross-asset
  baskets** because TLT/GLD/DBC have low/negative SPY beta. We report
  both variants honestly; the result here is itself a Pattern #1
  generalization datum.

## Persistent state (cross-flat)

- `last_rebalance_month`: "YYYY-MM" of most recent rebalance, used
  to throttle to monthly cadence.

## Citation

Jegadeesh, N., & Titman, S. (1993). "Returns to Buying Winners and
Selling Losers." *Journal of Finance* 48(1).

Asness, C., Moskowitz, T., & Pedersen, L. H. (2013). "Value and
Momentum Everywhere." *Journal of Finance* 68(3). Canonical
cross-asset extension.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def _month_key(t_iso: str) -> str:
    """Extract 'YYYY-MM' from an ISO timestamp."""
    return t_iso[:7] if t_iso and len(t_iso) >= 7 else ""


def _rank_12_1(bars_by_sym: Dict[str, List[dict]], lookback_bars: int,
               skip_bars: int) -> List:
    """Return [(ret, sym), ...] sorted descending. Symbols without enough
    history are dropped."""
    out = []
    needed = lookback_bars + skip_bars + 1
    for sym, bars in bars_by_sym.items():
        if len(bars) < needed:
            continue
        # 12-1 return: from bar[-(lookback+skip)] to bar[-skip-1].
        end_px = float(bars[-1 - skip_bars]["c"])
        start_px = float(bars[-1 - skip_bars - lookback_bars]["c"])
        if start_px <= 0:
            continue
        out.append(((end_px - start_px) / start_px, sym))
    out.sort(reverse=True)
    return out


def _regime_up(spy_closes, period: int) -> bool:
    """Inline copy of regime_uptrend (close > SMA(period)). Avoids importing
    strategies._lib (sibling-package import quirks under loaders)."""
    if not spy_closes or len(spy_closes) < period + 1:
        return True  # insufficient data => don't gate
    sma = sum(spy_closes[-period:]) / period
    return spy_closes[-1] > sma


def decide_xsec(market_state: dict, position_state: dict, params: dict) -> dict:
    """Top-K cross-asset momentum on a monthly cadence.

    Returns: {symbol: Action} for symbols to act on this tick.
    Absent symbols are implicitly hold.
    """
    actions: Dict[str, Action] = {}
    symbols_view = market_state.get("symbols") or {}
    if not symbols_view:
        return {}

    state = market_state.setdefault("strategy_state", {}) if isinstance(
        market_state.get("strategy_state"), dict) else {}
    market_state["strategy_state"] = state

    clock_t = str(market_state.get("clock_t", ""))
    this_month = _month_key(clock_t)
    last_month = state.get("last_rebalance_month", "")

    # Only rebalance on month change.
    if this_month == last_month or not this_month:
        return {}

    lookback_bars = int(params.get("lookback_bars", 252))
    skip_bars = int(params.get("skip_bars", 21))
    top_k = max(1, int(params.get("top_k", 2)))
    max_notional = float(params.get("max_notional_usd", 100.0))
    per_leg = max_notional / top_k

    bars_by_sym = {sym: sv["bars"] for sym, sv in symbols_view.items()
                   if sv.get("bars")}

    ranks = _rank_12_1(bars_by_sym, lookback_bars, skip_bars)
    if not ranks:
        return {}

    # Regime gate (optional, applied to NEW buys only).
    regime_ok = True
    if params.get("use_regime_filter", False):
        regime = market_state.get("regime") or {}
        spy_closes = regime.get("spy_closes") or []
        period = int(params.get("regime_sma_period", 50))
        regime_ok = _regime_up(spy_closes, period)

    winners = {sym for _, sym in ranks[:top_k]}

    # Close holdings not in new winners set.
    for held in list(position_state.keys()):
        if held not in winners:
            actions[held] = Action(
                action="close", symbol=held,
                reason=f"rotate-out: not in top-{top_k}")

    # If regime is off, close losers and stay flat for the new month.
    if not regime_ok:
        state["last_rebalance_month"] = this_month
        return actions

    # Open new winners we don't currently hold.
    for w in winners:
        if w in position_state:
            continue
        sv = symbols_view.get(w, {})
        if not sv.get("has_bar"):
            continue
        actions[w] = Action(
            action="buy", symbol=w, notional_usd=per_leg,
            reason=f"top-{top_k} 12-1 cross-asset momentum")

    state["last_rebalance_month"] = this_month
    return actions
