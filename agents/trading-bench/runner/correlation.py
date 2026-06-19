"""Per-strategy P&L correlation analysis.

Goal: with many mediocre strategies, find the UNCORRELATED ones — those
actually diversify a portfolio. High pairwise correlation means redundancy.

We compute realized daily P&L per strategy (FIFO closed legs only, same logic
as ranking.compute()) and produce a pairwise Pearson correlation matrix over
the union of trading days. Missing days are filled with 0.0 (a flat day is
real signal, not missing data).

Pure-Python implementation — pandas/scipy NOT required.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import db


def _parse_day(ts_utc: str) -> date:
    # ts is ISO8601 e.g. "2026-05-30T10:06:00+00:00" or "...Z"
    s = ts_utc.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        # fall back: take first 10 chars
        return date.fromisoformat(ts_utc[:10])


def daily_pnl_series(
    strategy_name: str,
    db_path: Optional[Path] = None,
) -> Dict[date, float]:
    """Realized daily P&L for a single strategy via FIFO on closed legs.

    Returns dict keyed by date (the day a sell closed against a prior buy).
    Days with no closes are simply absent (caller decides fill policy).
    """
    path = Path(db_path) if db_path else db.DB_PATH
    with db.connect(path) as c:
        rows = c.execute(
            "SELECT symbol, side, qty, price, ts_utc FROM trades "
            "WHERE strategy=? AND status IN "
            "('submitted','filled','partially_filled','accepted','new','pending_new') "
            "ORDER BY id ASC",
            (strategy_name,),
        ).fetchall()

    lots_by_symbol: Dict[str, deque] = defaultdict(deque)
    pnl_by_day: Dict[date, float] = defaultdict(float)

    for r in rows:
        sym = r["symbol"]
        qty = float(r["qty"] or 0)
        price = float(r["price"] or 0)
        if r["side"] == "buy":
            lots_by_symbol[sym].append({"qty": qty, "price": price})
        else:  # sell
            remaining = qty
            day = _parse_day(r["ts_utc"])
            lots = lots_by_symbol[sym]
            while remaining > 1e-12 and lots:
                lot = lots[0]
                take = min(lot["qty"], remaining)
                pnl_by_day[day] += (price - lot["price"]) * take
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] <= 1e-12:
                    lots.popleft()

    return dict(pnl_by_day)


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    """Pure-python Pearson r. Returns None if undefined (zero variance / n<2)."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx2 = sum((x - mx) ** 2 for x in xs)
    dy2 = sum((y - my) ** 2 for y in ys)
    if dx2 <= 1e-18 or dy2 <= 1e-18:
        return None  # constant series — correlation undefined
    return num / math.sqrt(dx2 * dy2)


class CorrelationMatrix:
    """Lightweight pandas.DataFrame stand-in.

    Holds a symmetric matrix of Pearson r values keyed by strategy name.
    Provides .at[a,b], .index/.columns, and a __str__ for table printing.
    Values may be None when correlation is undefined (constant series).
    """

    def __init__(self, strategies: List[str], values: Dict[Tuple[str, str], Optional[float]]):
        self.strategies = list(strategies)
        self.index = list(strategies)
        self.columns = list(strategies)
        self._values = values

    def at(self, a: str, b: str) -> Optional[float]:
        return self._values.get((a, b))

    # pandas-style dict-of-tuples accessor
    def __getitem__(self, key):
        if isinstance(key, tuple) and len(key) == 2:
            return self._values.get(key)
        raise KeyError(key)

    def pairs(self):
        """Iterate unique unordered pairs (i<j) -> (a, b, r)."""
        for i, a in enumerate(self.strategies):
            for b in self.strategies[i + 1:]:
                yield a, b, self._values.get((a, b))

    def __str__(self) -> str:
        if not self.strategies:
            return "(empty)"
        col_w = max(12, max(len(s) for s in self.strategies) + 1)
        header = " " * col_w + "".join(f"{s[:col_w-1]:>{col_w}}" for s in self.strategies)
        lines = [header]
        for a in self.strategies:
            row_cells = []
            for b in self.strategies:
                v = self._values.get((a, b))
                row_cells.append(f"{'   n/a':>{col_w}}" if v is None else f"{v:>{col_w}.3f}")
            lines.append(f"{a[:col_w-1]:<{col_w}}" + "".join(row_cells))
        return "\n".join(lines)


def correlation_matrix(
    strategies: List[str],
    db_path: Optional[Path] = None,
) -> CorrelationMatrix:
    """Pairwise Pearson correlation of daily P&L over the union of trading days.

    Missing days are filled with 0.0 (flat = real signal). When a series is
    constant (all zeros, or one trade day) the correlation is undefined and
    stored as None — callers must handle.
    """
    series_by_strat: Dict[str, Dict[date, float]] = {
        s: daily_pnl_series(s, db_path) for s in strategies
    }
    # Union of all days that appear in any strategy
    all_days: set = set()
    for s in strategies:
        all_days.update(series_by_strat[s].keys())
    days_sorted = sorted(all_days)

    # Aligned vectors, missing days -> 0.0
    vectors: Dict[str, List[float]] = {
        s: [series_by_strat[s].get(d, 0.0) for d in days_sorted]
        for s in strategies
    }

    values: Dict[Tuple[str, str], Optional[float]] = {}
    for a in strategies:
        for b in strategies:
            if a == b:
                # Self-correlation: 1.0 if any non-zero day, else undefined
                if any(abs(v) > 1e-18 for v in vectors[a]):
                    values[(a, b)] = 1.0
                else:
                    values[(a, b)] = None
            else:
                values[(a, b)] = _pearson(vectors[a], vectors[b])

    return CorrelationMatrix(strategies, values)


def flag_high_correlation(
    matrix: CorrelationMatrix,
    threshold: float = 0.7,
) -> List[Tuple[str, str, float]]:
    """Return unique unordered pairs whose |r| >= threshold.

    Skips pairs with undefined correlation (None). Includes negative correlation
    above threshold in absolute value — strong anti-correlation is also a flag
    worth noticing (perfect hedge pair == redundant in a long-only book).
    """
    flagged: List[Tuple[str, str, float]] = []
    for a, b, r in matrix.pairs():
        if r is None:
            continue
        if abs(r) >= threshold:
            flagged.append((a, b, r))
    flagged.sort(key=lambda t: -abs(t[2]))
    return flagged


def format_correlation_section(strategies: List[str], db_path: Optional[Path] = None) -> str:
    if len(strategies) < 2:
        return (
            "📈 Correlation matrix (daily P&L, Pearson):\n"
            "(need ≥2 strategies; have " + str(len(strategies)) + ")\n"
            "⚠️  High-correlation pairs (>0.7): none"
        )
    matrix = correlation_matrix(strategies, db_path)
    flagged = flag_high_correlation(matrix, threshold=0.7)
    if flagged:
        flag_str = ", ".join(f"{a}↔{b} ({r:+.2f})" for a, b, r in flagged)
    else:
        flag_str = "none"
    return (
        "📈 Correlation matrix (daily P&L, Pearson):\n"
        f"{matrix}\n"
        f"⚠️  High-correlation pairs (>0.7): {flag_str}"
    )
