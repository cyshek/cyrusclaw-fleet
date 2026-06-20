"""Contrarian Donchian-pullback mean-reversion on IWM 1h bars, regime-gated.

Mirror-image of the trend-following parent `breakout_xlk_regime`. Instead of
buying strength (close above the N-bar high), this BUYS WEAKNESS: it enters
long when price prints a fresh `lookback`-bar LOW (a pullback / washout) on a
mean-reverting instrument (IWM small-caps, which whip around their range far
more than a momentum sector ETF like XLK). Thesis: in an up-regime, sharp dips
to the lower Donchian band are noise that tends to revert; fading them
captures the bounce.

Entry signal: close < lookback-bar low AND we are flat AND SPY is in an
uptrend (regime gate, so we only fade dips inside a healthy broad market —
buying the dip in a downtrend is just catching a falling knife).

Exit signal (any one, checked BEFORE the entry gate so a filter can never
trap us in a losing trade):
  - Mean reversion target: price recovers to the lookback-bar high  -> take profit.
  - Take-profit: unrealized gain >= tp_pct (locks the bounce even mid-range).
  - Stop-loss: unrealized loss >= sl_pct (the dip kept going / no reversion).
  - Time-stop: held >= max_hold bars without reverting -> the thesis expired.

Edge rationale: small-cap index pullbacks inside an uptrend mean-revert more
often than they continue; the parent's own trade distribution shows dips of
~1.3% (median per-trade drawdown) are routine and ~2.6% bounces (median
per-trade runup) are common, so a tight stop just inside the typical drawdown
plus a target just inside the typical runup harvests the asymmetry. Thresholds
are taken directly from the parent profile, not guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, highest, lowest, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    lookback = int(params.get("lookback", 20))
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))
    # Thresholds grounded in parent profile (median trade dd 1.27%, runup 2.60%):
    sl_pct = float(params.get("sl_pct", 0.0120))   # stop just inside median drawdown
    tp_pct = float(params.get("tp_pct", 0.0240))   # target just inside median runup
    max_hold = int(params.get("max_hold", 43))     # p75 holding period at 1Hour

    cs = closes(market_state.get("bars") or [])
    if len(cs) < lookback + 1:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    last = cs[-1]
    hi = highest(cs[:-1], lookback)
    lo = lowest(cs[:-1], lookback)

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_px = float(pos.get("avg_entry_price", 0) or 0) if pos else 0.0
    bars_held = int(pos.get("bars_held", 0) or 0) if pos else 0

    # ---- CLOSE LOGIC ALWAYS RUNS FIRST: no filter may trap an open position ----
    if holding > 0:
        # 1) Mean-reversion target reached: price climbed back to the upper band.
        if hi is not None and last >= hi:
            return Action("close", symbol,
                          reason=f"reverted to {lookback}-bar high {hi:.2f} (target)")
        if entry_px > 0:
            chg = (last - entry_px) / entry_px
            # 2) Take-profit on unrealized gain.
            if chg >= tp_pct:
                return Action("close", symbol,
                              reason=f"take-profit +{chg*100:.2f}% >= {tp_pct*100:.2f}%")
            # 3) Stop-loss: the dip never reverted.
            if chg <= -sl_pct:
                return Action("close", symbol,
                              reason=f"stop-loss {chg*100:.2f}% <= -{sl_pct*100:.2f}%")
        # 4) Time-stop: thesis (a quick bounce) has expired.
        if bars_held >= max_hold:
            return Action("close", symbol,
                          reason=f"time-stop {bars_held} >= {max_hold} bars (no reversion)")
        return Action("hold", symbol,
                      reason=f"holding, awaiting reversion (last={last:.2f}, entry={entry_px:.2f})")

    # ---- ENTRY GATE (only reached when flat) ----
    # Contrarian entry: buy a fresh lower-band pullback, but ONLY in an up-regime.
    if lo is not None and last < lo:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(pullback-buy blocked — no knife-catching)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"pullback {last:.2f} < {lookback}-bar low {lo:.2f}")

    return Action("hold", symbol,
                  reason=f"no pullback (last={last:.2f}, hi={hi}, lo={lo}, holding={holding})")