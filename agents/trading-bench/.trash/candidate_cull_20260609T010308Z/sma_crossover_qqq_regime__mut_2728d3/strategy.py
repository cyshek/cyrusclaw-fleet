"""SMA crossover on QQQ 1h bars (SPY-regime gated) with a POST-LOSS COOLDOWN.

Parent: `sma_crossover_qqq_regime`. Same entry/exit core — go long on a
bullish SMA cross (fast > slow) when SPY is above its regime SMA, close on
the bearish cross (fast < slow). This mutation adds one filter: after any
close that realized a LOSS (exit price < average entry price), refuse to
open a new long for the next `loss_cooldown_bars` bars.

Thesis: a fresh realized loss is weak-but-nonzero evidence the local regime
just turned hostile to a trend-following cross (a volatility spike, a whipsaw
reversal, or a news shock that the SMA pair will keep getting chopped by).
Sitting out a handful of bars lets that worst-case path drain before we
re-arm, instead of immediately buying back into the same chop that just cost
us. The cooldown gates ENTRIES ONLY — an already-open position is always
closeable on the parent's normal bearish-cross signal, and the runner's
safety backstops short-circuit before this code runs.

Chosen N = 8 bars. Parent median holding is 26.5 bars (p25 17.0, p75 48.8),
so 8 is ~0.30x median — inside the sane 0.25-1.0x band, toward the lower end.
Rationale for the low end: this is QQQ at 1Hour, ~6-7 bars per session, so
8 bars is roughly one trading day of sit-out — long enough to let a single
hostile session play through, short enough that it does not eat the multi-day
bull/chop re-entries that carry the parent's edge. A much smaller N (3-4)
would be inert (a whipsaw resolves slower than that); a much larger N (15-20)
would skip too many legitimate re-entries given the parent only holds ~26
bars per trade on average.

Expected firing rate: the parent exits purely on the bearish cross, which in
chop frequently unwinds slightly below entry, so realized-loss exits are
common-but-not-dominant — order of ~40-55% of trades (consistent with the
43% of trades that touched >=1% drawdown in the parent profile). That puts
the cooldown in a healthy middle band: it engages often enough to matter, but
the parent is NOT a <10% loss-rate strategy (where this would be inert) nor a
>60% loss-rate strategy (where it would smother). So the directive is a
reasonable fit for this parent rather than a no-op or a muzzle.

Cooldown state lives in `market_state['strategy_state']` (survives flats),
NOT position_state (cleared on close). The realized loss is detected on the
closing bar by reading `position_state[symbol]['avg_entry_price']` BEFORE the
close clears it.

Regime data: read from `market_state["regime"]` ({"spy_closes": [...]}) or
None when unavailable; when None the regime gate is a no-op (parent behavior).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from strategies._lib.indicators import closes, sma, regime_uptrend


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
    cooldown_n = int(params.get("loss_cooldown_bars", 8))

    bars = market_state.get("bars") or []
    cs = closes(bars)
    fast = sma(cs, fast_p)
    slow = sma(cs, slow_p)

    # strategy_state survives flat periods, so the cooldown counter persists
    # naturally between trades. Mutating it in place is sufficient.
    state = market_state.get("strategy_state")
    if state is None:
        state = {}

    pos = position_state.get(symbol)
    holding = float(pos.get("qty", 0)) if pos else 0.0

    # Not-enough-bars guard (need slow_p closes for the slow SMA).
    if fast is None or slow is None:
        return Action("hold", symbol, reason=f"not enough bars ({len(cs)})")

    # 1. CLOSE LOGIC ALWAYS RUNS FIRST — never gated by cooldown or regime.
    #    On a loss-exit, ARM the cooldown by reading avg_entry_price BEFORE
    #    the close clears position_state.
    if fast < slow and holding > 0:
        last = float(market_state.get("last_price", cs[-1]))
        entry_px = float((pos or {}).get("avg_entry_price", 0.0) or 0.0)
        if entry_px > 0 and last < entry_px:
            state["cooldown_remaining"] = cooldown_n
        return Action("close", symbol,
                      reason=f"SMA{fast_p}={fast:.2f} < SMA{slow_p}={slow:.2f}")

    # 2. Decrement cooldown once per bar (only reached when flat or no exit).
    #    Floor at 0; never negative.
    cd = int(state.get("cooldown_remaining", 0) or 0)
    if cd > 0:
        state["cooldown_remaining"] = cd - 1

    # 3. Entry gate: bullish cross + flat + regime ok + no active cooldown.
    #    Use the PRE-decrement value (cd) so a fresh cooldown_remaining=N
    #    blocks the next N entry opportunities, not N-1.
    if fast > slow and holding == 0:
        if cd > 0:
            return Action("hold", symbol,
                          reason=f"post-loss cooldown {cd} bar(s) remaining")
        regime = market_state.get("regime")
        if regime and not regime_uptrend(regime.get("spy_closes") or [],
                                         period=regime_period):
            return Action("hold", symbol,
                          reason=f"regime: SPY below {regime_period}d SMA "
                                 f"(bullish cross blocked)")
        return Action("buy", symbol, notional_usd=notional,
                      reason=f"SMA{fast_p}={fast:.2f} > SMA{slow_p}={slow:.2f}")

    return Action("hold", symbol,
                  reason=(f"post-loss cooldown {cd} bar(s) remaining" if cd > 0
                          else f"no signal (fast={fast:.2f}, slow={slow:.2f}, "
                               f"holding={holding})"))