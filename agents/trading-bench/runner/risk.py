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

Intraday-aware per-day cap (added 2026-06-25, audit §3):
    The legacy cap of 4/UTC-day encodes a once-or-twice-a-day decision book.
    An intraday strategy that legitimately enters/exits several times per
    session would be silently truncated after trade #4 (each later trade logs
    skip_risk and is dropped, biasing the backtest toward early-session fills).

    `resolve_trades_per_day(params, timeframe=...)` now resolves the cap with
    an explicit precedence (highest wins):
        1. explicit `max_trades_per_day: N` param (clamped to
           [1, MAX_TRADES_PER_DAY_CEILING]) -- honored at ANY timeframe;
        2. INTRADAY default (INTRADAY_TRADES_PER_DAY_DEFAULT) when timeframe is
           sub-daily and no explicit override -- never below the basket bump;
        3. xsec-basket bump max(MAX_TRADES_PER_DAY, 2*K);
        4. legacy MAX_TRADES_PER_DAY (4).
    `timeframe` defaults to None == EXACT pre-2026-06-25 behavior, so daily /
    single-arg callers are unchanged (still 4 / basket-bumped). No live
    params.json was changed; the resolver is just capable + documented.
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

# Hard safety ceiling for the per-day trade cap from ANY source other than the
# xsec-basket bump (explicit `max_trades_per_day` override OR the intraday
# default). Mirrors the MAX_XSEC_BASKET_SIZE clamp pattern: a typo'd
# `max_trades_per_day: 100000` in a params.json can never authorize runaway
# turnover -- it is clamped to this. 50 round-trips-ish in a single session is
# already far beyond any strategy we intend to run on paper; it exists purely
# as the runaway floor, not as a target.
MAX_TRADES_PER_DAY_CEILING = 50

# Per-day trade cap for INTRADAY timeframes when a strategy does NOT specify an
# explicit `max_trades_per_day`. The daily book decides once or twice a day
# (cap 4); an intraday strategy may legitimately enter/exit several times per
# session, and the legacy 4 would silently truncate it after the 4th trade
# (every later trade logs skip_risk and is dropped, biasing the backtest toward
# early-session fills -- audit §3). We do NOT scale this to the raw bar count
# (510 bars/day at 1Min would invite runaway turnover and the IEX-only feed
# makes minute fills optimistic anyway); instead we pick a single defensible
# intraday ceiling -- 20 trades/UTC day (~10 round trips) -- high enough to let
# a real multi-entry intraday strategy breathe, low enough to stay a runaway
# rail. A strategy that genuinely needs more must opt in explicitly via
# `max_trades_per_day` (still clamped to MAX_TRADES_PER_DAY_CEILING).
INTRADAY_TRADES_PER_DAY_DEFAULT = 20

# Timeframes treated as intraday for the per-day cap (anything finer than 1Day).
_INTRADAY_TIMEFRAMES = frozenset({
    "1Min", "5Min", "15Min", "30Min",
    "1Hour", "2Hour", "4Hour", "6Hour", "12Hour",
})


def _is_intraday_tf(timeframe: Optional[str]) -> bool:
    """True iff `timeframe` is a recognized sub-daily timeframe.

    None or "1Day" (or anything unrecognized) -> False, so the daily/legacy
    path is the safe default for any caller that passes no timeframe.
    """
    return isinstance(timeframe, str) and timeframe in _INTRADAY_TIMEFRAMES


@dataclass
class RiskCheck:
    ok: bool
    reason: Optional[str] = None


def _explicit_trades_override(params: Optional[dict]) -> Optional[int]:
    """Read an explicit `max_trades_per_day` override from params, defensively.

    Mirrors the xsec_basket_size handling style:
      - key absent -> None (no override).
      - parseable int >= 1 -> clamped to [1, MAX_TRADES_PER_DAY_CEILING].
      - malformed / < 1 -> None (safe fallback; caller uses next tier).
    Never raises.
    """
    if not params:
        return None
    raw = params.get("max_trades_per_day")
    if raw is None:
        return None
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    if v < 1:
        return None
    return min(v, MAX_TRADES_PER_DAY_CEILING)


def _xsec_basket_bump(params: Optional[dict]) -> Optional[int]:
    """The basket-aware bump max(MAX_TRADES_PER_DAY, 2*K), or None if N/A.

    Malformed / out-of-range K -> None (caller falls through to the legacy 4).
    """
    if not params:
        return None
    raw = params.get("xsec_basket_size")
    if raw is None:
        return None
    try:
        k = int(raw)
    except (TypeError, ValueError):
        return None
    if k < 1 or k > MAX_XSEC_BASKET_SIZE:
        return None
    return max(MAX_TRADES_PER_DAY, 2 * k)


def resolve_trades_per_day(params: Optional[dict],
                           timeframe: Optional[str] = None) -> int:
    """Compute the per-day trade cap for a strategy, given its params dict.

    Precedence (highest wins):
      1. EXPLICIT override -- `max_trades_per_day: N` in params, clamped to
         [1, MAX_TRADES_PER_DAY_CEILING]. Honored at ANY timeframe.
      2. INTRADAY default -- when `timeframe` is a sub-daily timeframe and no
         explicit override is given: INTRADAY_TRADES_PER_DAY_DEFAULT (20),
         BUT never below the xsec-basket bump (a big intraday basket still
         gets max(intraday_default, 2*K), clamped to the ceiling).
      3. XSEC-basket bump -- `xsec_basket_size: K` (1<=K<=MAX_XSEC_BASKET_SIZE)
         -> max(MAX_TRADES_PER_DAY, 2*K). Applies at daily timeframe (or when
         no timeframe is passed).
      4. LEGACY default -- MAX_TRADES_PER_DAY (4).

    Backward compatibility: `timeframe` defaults to None, which means EXACTLY
    the pre-2026-06-25 behavior -- single-arg callers (and daily callers) are
    unchanged. None and "1Day" both take the daily/legacy path. Malformed /
    out-of-range params fall back safely; this fn never raises.

    Examples (daily / legacy -- UNCHANGED):
        resolve_trades_per_day(None) -> 4
        resolve_trades_per_day({}) -> 4
        resolve_trades_per_day({"xsec_basket_size": 2}) -> 4 (max(4, 4))
        resolve_trades_per_day({"xsec_basket_size": 3}) -> 6
        resolve_trades_per_day({"xsec_basket_size": 6}) -> 12
        resolve_trades_per_day({"xsec_basket_size": 50}) -> 4 (clamped/invalid)
        resolve_trades_per_day({"xsec_basket_size": "banana"}) -> 4
        resolve_trades_per_day({}, timeframe="1Day") -> 4

    Examples (intraday / explicit -- NEW):
        resolve_trades_per_day({}, timeframe="1Min") -> 20
        resolve_trades_per_day({}, timeframe="1Hour") -> 20
        resolve_trades_per_day({"max_trades_per_day": 8}) -> 8
        resolve_trades_per_day({"max_trades_per_day": 8}, timeframe="1Min") -> 8
        resolve_trades_per_day({"max_trades_per_day": 999}) -> 50 (ceiling)
        resolve_trades_per_day({"max_trades_per_day": 0}, timeframe="1Min") -> 20
        resolve_trades_per_day({"xsec_basket_size": 12}, timeframe="1Min") -> 24
    """
    # Tier 1: explicit override wins everywhere.
    explicit = _explicit_trades_override(params)
    if explicit is not None:
        return explicit

    basket = _xsec_basket_bump(params)

    # Tier 2: intraday default (never below the basket bump), clamped.
    if _is_intraday_tf(timeframe):
        floor = INTRADAY_TRADES_PER_DAY_DEFAULT
        if basket is not None:
            floor = max(floor, basket)
        return min(floor, MAX_TRADES_PER_DAY_CEILING)

    # Tier 3: xsec-basket bump (daily / no-timeframe path).
    if basket is not None:
        return basket

    # Tier 4: legacy default.
    return MAX_TRADES_PER_DAY


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
