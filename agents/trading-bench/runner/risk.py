"""Hard risk caps. Enforced in the runner, NEVER in strategy code.

Caps (paper bump 2026-05-31, Cyrus):
    MAX_NOTIONAL          = $1000 per single trade  (was $100 Session 1)
    MAX_POSITION          = $1000 total position size per symbol  (was $100)
    MAX_TRADES_PER_DAY    = 4   per strategy, per UTC day (default)

    PAPER ONLY. Real-money start stays $100 max (GATE.md Bar E, per-request
    Cyrus approval). The paper sandbox is bigger so cross-sectional baskets
    are runnable; it is NOT a real-capital commitment.

A risk rejection logs a 'skip_risk' decision and returns False; the strategy
gets no second chance for that tick.

Basket-aware per-day cap (added 2026-05-30, Tessera):
    A cross-sectional / basket strategy with K legs may need up to 2*K trades
    on a rebalance day (close all, open all). Hard-coding cap=4 forced the
    xsec harness to silently drop legs after trade #4, biasing backtests and
    blocking any K>2 basket from rebalancing cleanly live.

    Resolution: a strategy that declares `xsec_basket_size: K` in params.json
    gets `max_trades_per_day = max(MAX_TRADES_PER_DAY, 2*K)`. Strategies that
    don't declare it keep the legacy cap of 4. The runaway-protection invariant
    holds: a strategy can't trade more than its declared basket size requires.
    A buggy basket strategy is still bounded by 2*K, just at a higher K.

    Use `resolve_trades_per_day(params)` to compute the cap once at tick start
    and pass into `check_trade(..., max_trades_per_day=...)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import db


# Defaults; overridable per-strategy via params.json if we ever want to.
# Per-strategy caps. PAPER notional bumped $100 -> $1000 (Cyrus, 2026-05-31):
# notional per trade and total open position are both $1000, so a strategy can
# hold one full $1000 position OR be flat. Trades per day stays at 4 (room for
# enter/exit/re-enter without runaway turnover).
#
# IMPORTANT — PAPER ONLY. This $1000 is the paper sandbox size. Real-money
# graduation start is UNCHANGED at $100 max, explicit per-request Cyrus
# approval (north star / GATE.md Bar E). Do NOT read this $1000 as license to
# fund $1000 of real capital. The bigger sandbox exists so single-stock
# cross-sectional baskets (~10 names @ ~$100 each) become runnable; at $100
# total they degenerate to $10/name noise. See memory/2026-05-31.md.
MAX_NOTIONAL = 1000.0
MAX_POSITION = 1000.0
MAX_TRADES_PER_DAY = 4
# Hard ceiling on basket-aware per-day cap. Any strategy claiming
# xsec_basket_size > MAX_XSEC_BASKET_SIZE is clamped here as a safety floor
# (prevents a typo'd params.json from authorizing 1000 trades/day).
MAX_XSEC_BASKET_SIZE = 12


@dataclass
class RiskCheck:
    ok: bool
    reason: Optional[str] = None


def resolve_trades_per_day(params: Optional[dict]) -> int:
    """Compute the per-day trade cap for a strategy, given its params dict.

    - No params or no `xsec_basket_size` key -> MAX_TRADES_PER_DAY (legacy).
    - `xsec_basket_size: K` present and 1 <= K <= MAX_XSEC_BASKET_SIZE ->
      max(MAX_TRADES_PER_DAY, 2*K).
    - Malformed/out-of-range K -> MAX_TRADES_PER_DAY (safe fallback) and
      caller is responsible for whatever observability they want; this fn
      does not raise.

    Examples:
        resolve_trades_per_day(None) -> 4
        resolve_trades_per_day({}) -> 4
        resolve_trades_per_day({"xsec_basket_size": 2}) -> 4 (max(4, 4))
        resolve_trades_per_day({"xsec_basket_size": 3}) -> 6
        resolve_trades_per_day({"xsec_basket_size": 6}) -> 12
        resolve_trades_per_day({"xsec_basket_size": 50}) -> 4 (clamped/invalid)
        resolve_trades_per_day({"xsec_basket_size": "banana"}) -> 4
    """
    if not params:
        return MAX_TRADES_PER_DAY
    raw = params.get("xsec_basket_size")
    if raw is None:
        return MAX_TRADES_PER_DAY
    try:
        k = int(raw)
    except (TypeError, ValueError):
        return MAX_TRADES_PER_DAY
    if k < 1 or k > MAX_XSEC_BASKET_SIZE:
        return MAX_TRADES_PER_DAY
    return max(MAX_TRADES_PER_DAY, 2 * k)


def check_trade(strategy: str,
                symbol: str,
                side: str,
                notional_usd: float,
                current_position_usd: float,
                *,
                max_notional: float = MAX_NOTIONAL,
                max_position: float = MAX_POSITION,
                max_trades_per_day: int = MAX_TRADES_PER_DAY) -> RiskCheck:
    if side == "close":
        # closing a position is always allowed (de-risking); only enforce daily trade cap.
        n_today = db.trades_today(strategy)
        if n_today >= max_trades_per_day:
            return RiskCheck(False,
                             f"already {n_today} trades today; cap {max_trades_per_day}")
        return RiskCheck(True)

    if notional_usd <= 0:
        return RiskCheck(False, f"non-positive notional {notional_usd}")
    if notional_usd > max_notional:
        return RiskCheck(False, f"notional ${notional_usd:.2f} > cap ${max_notional:.2f}")

    if side == "buy":
        projected = current_position_usd + notional_usd
        if projected > max_position:
            return RiskCheck(
                False,
                f"projected position ${projected:.2f} > cap ${max_position:.2f}",
            )

    n_today = db.trades_today(strategy)
    if n_today >= max_trades_per_day:
        return RiskCheck(
            False,
            f"already {n_today} trades today; cap {max_trades_per_day}",
        )

    return RiskCheck(True)
