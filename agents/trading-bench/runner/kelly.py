"""Kelly-fraction position sizer.

Computes a Kelly-optimal notional for the next trade given the strategy's
closed-round-trip history in tournament.db. Falls back to flat notional
when history is insufficient or Kelly fraction is negative/zero.

Kelly formula (simplified, win/loss binary framing):
    f = (p * b - q) / b
    where:
        p = win_rate (fraction of closed round-trips with realized PnL > 0)
        q = 1 - p
        b = avg_win / avg_loss  (ratio of avg winning trade $ to avg losing $ in abs terms)

    notional = f * max_notional   (capped to [0, max_notional])

    In practice we use HALF-Kelly (f *= 0.5) to reduce variance and account
    for estimation error.

Minimum history gate:
    - At least MIN_ROUND_TRIPS (20) closed round-trips required.
    - A "round-trip" = at least one buy + one sell leg that produced a
      realized PnL entry.
    - If history < MIN_ROUND_TRIPS: return flat_fallback (params["notional_usd"]).

Negative Kelly:
    - If f <= 0 (edge is negative or zero): return 0.0 (signal to skip).
    - Caller should check: if kelly_notional == 0.0 → skip/hold, don't place order.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from .risk import MAX_NOTIONAL

# Re-exported for tests that want to import from here.
_DEFAULT_MAX_NOTIONAL = MAX_NOTIONAL
MIN_ROUND_TRIPS = 20


# ---------------------------------------------------------------------------
# Internal FIFO-matching helpers
# ---------------------------------------------------------------------------

def _fifo_round_trip_pnls(rows: list) -> list[float]:
    """FIFO-match buy/sell rows into per-round-trip realized PnL values.

    Each row is expected to be a dict-like with keys: side, qty, price, notional_usd.
    Returns a list of floats — one value per closing-sell leg — representing
    the realized PnL of that leg (can be negative).

    Logic mirrors ranking.py / db.strategy_pnl:
        - Buy legs accumulate a cost queue.
        - A sell leg pops from the front of the buy queue (FIFO), computing
          proceeds - cost_released for the matched quantity.
    """
    # Each entry: (qty, cost_per_unit)
    buy_queue: list[tuple[float, float]] = []
    pnls: list[float] = []

    for row in rows:
        side = row["side"] if isinstance(row, dict) else row[0]
        qty_raw = row["qty"] if isinstance(row, dict) else row[1]
        price_raw = row["price"] if isinstance(row, dict) else row[2]
        notional_raw = row["notional_usd"] if isinstance(row, dict) else row[3]

        try:
            q = float(qty_raw or 0)
        except (TypeError, ValueError):
            q = 0.0
        try:
            p = float(price_raw) if price_raw is not None else None
        except (TypeError, ValueError):
            p = None
        try:
            n = float(notional_raw or 0)
        except (TypeError, ValueError):
            n = 0.0

        if q <= 0:
            continue

        cost_per_unit = (n / q) if q > 0 and n > 0 else (p or 0.0)

        if side == "buy":
            buy_queue.append((q, cost_per_unit))

        elif side == "sell":
            remaining_sell = q
            while remaining_sell > 1e-10 and buy_queue:
                buy_qty, buy_cpu = buy_queue[0]
                matched = min(remaining_sell, buy_qty)
                proceeds = matched * (p or 0.0)
                cost = matched * buy_cpu
                pnls.append(proceeds - cost)
                remaining_sell -= matched
                if matched >= buy_qty - 1e-10:
                    buy_queue.pop(0)
                else:
                    buy_queue[0] = (buy_qty - matched, buy_cpu)

    return pnls


def _fetch_trade_rows(strategy: str, db_path: Path) -> list:
    """Query trades for a strategy, ordered by id ASC.

    Returns a list of sqlite3.Row objects with keys:
        side, qty, price, notional_usd
    """
    _OPEN_STATUSES = ("filled", "submitted", "partially_filled")
    placeholders = ",".join("?" * len(_OPEN_STATUSES))
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT side, qty, price, notional_usd FROM trades "
            f"WHERE strategy = ? AND status IN ({placeholders}) "
            f"ORDER BY id ASC",
            (strategy, *_OPEN_STATUSES),
        ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def kelly_notional(
    strategy: str,
    params: dict,
    *,
    max_notional: float = _DEFAULT_MAX_NOTIONAL,
    min_round_trips: int = MIN_ROUND_TRIPS,
    half_kelly: bool = True,
    db_path: Optional[Path] = None,
) -> float:
    """Compute a Kelly-sized notional for the next trade.

    Parameters
    ----------
    strategy : str
        Strategy name (must match the ``strategy`` column in the trades table).
    params : dict
        Strategy params dict (must contain ``"notional_usd"`` for flat fallback).
    max_notional : float
        Hard cap on the returned notional; defaults to risk.MAX_NOTIONAL.
    min_round_trips : int
        Minimum closed round-trips required before Kelly is used; defaults to 20.
    half_kelly : bool
        If True, multiply the raw Kelly fraction by 0.5 (recommended for live use).
    db_path : Path or None
        Path to the SQLite DB file; defaults to db.DB_PATH.

    Returns
    -------
    float
        - Positive float in (0, max_notional]: Kelly-sized notional.
        - 0.0: Kelly fraction ≤ 0 (negative edge) — caller should skip the trade.
        - params["notional_usd"]: flat fallback (insufficient history).
    """
    flat_fallback = float(params.get("notional_usd", 100.0))

    # Resolve DB path lazily to avoid import-time side effects.
    if db_path is None:
        from . import db as _db
        db_path = _db.DB_PATH

    db_path = Path(db_path)

    # --- Fetch trade rows and compute per-round-trip PnL via FIFO matching ---
    try:
        rows = _fetch_trade_rows(strategy, db_path)
    except Exception:  # noqa: BLE001
        # DB not found / unreadable → fall back.
        return flat_fallback

    pnls = _fifo_round_trip_pnls(list(rows))

    if len(pnls) < min_round_trips:
        return flat_fallback

    # --- Compute Kelly inputs ---
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]

    n_total = len(pnls)
    p = len(wins) / n_total          # win rate
    q = 1.0 - p                      # loss rate

    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (abs(sum(losses) / len(losses))) if losses else 0.0  # positive

    # Edge cases:
    # - No losses ever: pure-win history → full Kelly = 1.0 (cap to max).
    # - No wins ever: b = 0 → Kelly < 0 → return 0.0.
    if avg_loss == 0.0:
        if avg_win > 0:
            # All trades were winners; Kelly = 1.0 (max exposure).
            f = 1.0
        else:
            # No wins, no losses (all break-even) → no edge.
            return 0.0
    else:
        b = avg_win / avg_loss   # win/loss ratio
        if b == 0.0:
            # avg_win is 0 but losses exist → definitely negative edge.
            return 0.0
        # f* = (p * b - q) / b
        f = (p * b - q) / b

    if f <= 0:
        return 0.0

    if half_kelly:
        f *= 0.5

    notional = f * max_notional
    return min(notional, max_notional)
