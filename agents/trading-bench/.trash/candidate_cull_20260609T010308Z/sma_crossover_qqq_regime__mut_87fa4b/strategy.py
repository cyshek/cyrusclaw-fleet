"""Mean-reversion buy-the-dip on IWM 1h bars, gated by a SPY-trend regime filter.

Contrarian mutation of `sma_crossover_qqq_regime`. Where the parent is
trend-following (buy the bullish SMA cross / breakout), this variant fades
short-term pullbacks in a mean-reverting symbol (IWM, small-caps). The thesis:
small-cap intraday selloffs that dip materially below a short SMA tend to snap
back toward the mean, BUT only when the broad market is healthy — so we keep the
parent's SPY-uptrend regime gate to avoid catching falling knives in bear tape.

Entry: when flat AND SPY is in an uptrend AND price has pulled back below the
SMA(`sma_p`) band by at least `band_pct` AND RSI(`rsi_p`) is oversold (< `rsi_buy`),
i.e. a stretched dip inside an uptrend. Exit: revert-to-mean (close back above
the SMA), OR take-profit at `tp_pct` above entry, OR stop-loss at `stop_pct`
below entry, OR a time-stop after `max_hold` bars. Edge: pullback reversion is
the opposite regime to breakout trend-following, so it should be uncorrelated
with the parent and earn on the parent's chop/drawdown bars.

Thresholds are grounded in the parent's empirical trade distribution (QQQ 1h):
median per-trade max drawdown ~0.76% -> stop_pct=0.76% (would have fired on >=half
of historical trades, not inert vs the p25 of 1.32%); median per-trade max runup
~1.34% -> tp_pct=1.34% (locks >=half of winners, not inert vs the p75 of 3.33%);
band_pct=0.70% matches the p25 runup magnitude / per-bar vol scale; max_hold=49
matches the p75 holding period as a backstop.

Important: the regime gate and all entry filters block NEW ENTRIES ONLY. Every
exit (mean-revert / take-profit / stop / time-stop) is evaluated BEFORE the entry
gate so a filter can never trap us in an open position. Regime data is read from
`market_state["regime"]` ({"spy_closes": [...], "spy_last": float}); when None
(data unavailable / crypto) the regime gate is skipped and we fall through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, rsi, regime_uptrend


@dataclass
class Action:
    action: str
    symbol: str
    notional_usd: float = 0.0
    qty: Optional[float] = None
    reason: str = ""


def decide(market_state: dict, position_state: dict, params: dict) -> Action:
    symbol = params.get("symbol", "IWM")
    sma_p = int(params.get("sma_p", 20))
    rsi_p = int(params.get("rsi_p", 14))
    rsi_buy = float(params.get("rsi_buy", 32.0))
    band_pct = float(params.get("band_pct", 0.0070))   # 0.70% below SMA = "pullback"
    tp_pct = float(params.get("tp_pct", 0.0134))        # +1.34% take-profit
    stop_pct = float(params.get("stop_pct", 0.0076))    # -0.76% stop-loss
    max_hold = int(params.get("max_hold", 49))          # bars; p75 holding backstop
    notional = float(params.get("notional_usd", 1000.0))
    regime_period = int(params.get("regime_period", 50))

    bars = market_state.get("bars") or []
    cs = closes(bars)

    # Need enough bars for both the SMA band and the RSI seed (rsi needs rsi_p+1).
    need = max(sma_p, rsi_p + 1)
    if len(cs) < need:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)} < {need})")

    last = cs[-1]
    ma = sma(cs, sma_p)
    r = rsi(cs, rsi_p)
    if ma is None or r is None:
        return Action("hold", symbol, reason=f"indicators warming up (bars={len(cs)})")

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0
    entry_px = float(pos.get("avg_entry_price", 0) or 0) if pos else 0.0
    bars_held = int(pos.get("bars_held", 0) or 0) if pos else 0

    # ---- Close logic ALWAYS runs first; no filter may block an exit. ----
    if holding > 0:
        # Mean reversion achieved: price recovered back to/above the SMA.
        if last >= ma:
            return Action("close", symbol,
                          reason=f"reverted: close {last:.2f} >= SMA{sma_p} {ma:.2f}")
        if entry_px > 0:
            chg = (last - entry_px) / entry_px
            # Take-profit on the bounce.
            if chg >= tp_pct:
                return Action("close", symbol,
                              reason=f"take-profit +{chg*100:.2f}% >= {tp_pct*100:.2f}%")
            # Stop-loss: dip kept going against us.
            if chg <= -stop_pct:
                return Action("close", symbol,
                              reason=f"stop-loss {chg*100:.2f}% <= -{stop_pct*100:.2f}%")
        # Time-stop: reversion didn't materialize in time.
        if bars_held >= max_hold:
            return Action("close", symbol,
                          reason=f"time-stop: held {bars_held} >= {max_hold} bars")
        return Action("hold", symbol,
                      reason=f"in trade (last={last:.2f}, SMA{sma_p}={ma:.2f}, held={bars_held})")

    # ---- Entry gate (flat only). All filters below block ENTRIES only. ----
    lower_band = ma * (1.0 - band_pct)
    dipped = last < lower_band
    oversold = r < rsi_buy

    if dipped and oversold:
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(dip-buy blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"pullback dip: close {last:.2f} < band {lower_band:.2f} "
                             f"({band_pct*100:.2f}% below SMA{sma_p}), RSI {r:.1f} < {rsi_buy:.0f}")

    return Action("hold", symbol,
                  reason=f"no dip (last={last:.2f}, SMA{sma_p}={ma:.2f}, "
                         f"band={lower_band:.2f}, RSI={r:.1f}, holding={holding})")