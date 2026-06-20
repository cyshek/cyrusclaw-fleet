"""Unit tests for runner/kelly.py — Kelly-fraction position sizer.

All tests use an in-memory SQLite DB (no disk I/O, no tournament.db touched).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from runner.kelly import kelly_notional, _fifo_round_trip_pnls, MIN_ROUND_TRIPS
from runner.risk import MAX_NOTIONAL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(rows: list[dict]) -> Path:
    """Create an in-memory SQLite DB file at a temp path with the minimal
    trades schema, populated with the given rows.

    Each row dict may have: strategy, side, qty, price, notional_usd, status.
    Defaults: strategy="test_strat", status="filled".
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE trades (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc       TEXT    NOT NULL DEFAULT '2024-01-01T00:00:00Z',
                strategy     TEXT    NOT NULL,
                symbol       TEXT    NOT NULL DEFAULT 'BTC/USD',
                side         TEXT    NOT NULL,
                qty          REAL    NOT NULL,
                notional_usd REAL,
                price        REAL,
                status       TEXT    NOT NULL DEFAULT 'filled',
                reason       TEXT,
                raw          TEXT
            )
        """)
        for r in rows:
            conn.execute(
                "INSERT INTO trades (strategy, symbol, side, qty, price, notional_usd, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    r.get("strategy", "test_strat"),
                    r.get("symbol", "BTC/USD"),
                    r["side"],
                    r["qty"],
                    r.get("price"),
                    r.get("notional_usd"),
                    r.get("status", "filled"),
                ),
            )
        conn.commit()
    return db_path


def _make_round_trips(
    n: int,
    win_rate: float,
    avg_win_usd: float,
    avg_loss_usd: float,
    strategy: str = "test_strat",
    entry_notional: float = 100.0,
) -> list[dict]:
    """Generate `n` round-trip trade pairs (buy + sell) with the given win_rate.

    Each round-trip:
      - Buy: qty=1, price=entry_notional (cost basis = entry_notional)
      - Sell: qty=1, price = entry_notional + avg_win_usd (win) or
                             entry_notional - avg_loss_usd (loss)
    """
    rows: list[dict] = []
    n_wins = round(n * win_rate)
    for i in range(n):
        buy_price = entry_notional
        rows.append({"strategy": strategy, "side": "buy",
                     "qty": 1.0, "price": buy_price, "notional_usd": buy_price})
        if i < n_wins:
            sell_price = entry_notional + avg_win_usd
        else:
            sell_price = max(0.01, entry_notional - avg_loss_usd)
        rows.append({"strategy": strategy, "side": "sell",
                     "qty": 1.0, "price": sell_price, "notional_usd": sell_price})
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInsufficientHistory:
    """Flat fallback when round-trips < MIN_ROUND_TRIPS."""

    def test_zero_trades_returns_flat_notional(self):
        db_path = _make_db([])  # empty DB
        params = {"notional_usd": 75.0}
        result = kelly_notional("test_strat", params, db_path=db_path)
        assert result == 75.0, f"Expected 75.0 (flat fallback), got {result}"

    def test_below_threshold_returns_flat_notional(self):
        # 10 round-trips (19 < MIN_ROUND_TRIPS=20)
        rows = _make_round_trips(10, win_rate=0.6, avg_win_usd=20.0, avg_loss_usd=10.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 80.0}
        result = kelly_notional("test_strat", params, min_round_trips=20, db_path=db_path)
        assert result == 80.0, f"Expected 80.0 (flat fallback), got {result}"

    def test_exactly_threshold_activates_kelly(self):
        """At exactly min_round_trips, Kelly should be used (not fallback)."""
        rows = _make_round_trips(20, win_rate=0.6, avg_win_usd=20.0, avg_loss_usd=10.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 80.0}
        result = kelly_notional("test_strat", params, min_round_trips=20, db_path=db_path)
        # Should NOT be the flat fallback — Kelly is positive here.
        assert result != 80.0, "Expected Kelly to activate at exactly the threshold"
        assert result > 0.0


class TestPositiveKelly:
    """60% win rate, 2:1 avg win:loss → Kelly fraction > 0."""

    def test_positive_kelly_returns_positive_notional(self):
        # p=0.6, b=2, f=(0.6*2-0.4)/2 = (1.2-0.4)/2 = 0.8/2 = 0.4; half-Kelly: 0.2
        rows = _make_round_trips(30, win_rate=0.6, avg_win_usd=20.0, avg_loss_usd=10.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        result = kelly_notional("test_strat", params, half_kelly=True, db_path=db_path)
        assert result > 0.0, f"Expected positive notional, got {result}"
        assert result <= MAX_NOTIONAL, f"Exceeded MAX_NOTIONAL: {result}"

    def test_positive_kelly_within_bounds(self):
        rows = _make_round_trips(40, win_rate=0.6, avg_win_usd=20.0, avg_loss_usd=10.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        result = kelly_notional("test_strat", params, max_notional=MAX_NOTIONAL,
                                half_kelly=True, db_path=db_path)
        assert 0.0 < result <= MAX_NOTIONAL, f"Out of bounds: {result}"

    def test_positive_kelly_full_kelly_larger_than_half(self):
        rows = _make_round_trips(30, win_rate=0.6, avg_win_usd=20.0, avg_loss_usd=10.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        full = kelly_notional("test_strat", params, half_kelly=False, db_path=db_path)
        half = kelly_notional("test_strat", params, half_kelly=True, db_path=db_path)
        assert full > half, f"Full Kelly ({full}) should be greater than half Kelly ({half})"


class TestNegativeKelly:
    """30% win rate, 1:2 avg win:loss → Kelly fraction < 0 → 0.0."""

    def test_negative_kelly_returns_zero(self):
        # p=0.3, b=0.5, f=(0.3*0.5-0.7)/0.5 = (0.15-0.7)/0.5 = -0.55/0.5 < 0
        rows = _make_round_trips(30, win_rate=0.3, avg_win_usd=10.0, avg_loss_usd=20.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        result = kelly_notional("test_strat", params, half_kelly=True, db_path=db_path)
        assert result == 0.0, f"Expected 0.0 (negative edge), got {result}"

    def test_negative_kelly_full_kelly_also_zero(self):
        rows = _make_round_trips(30, win_rate=0.3, avg_win_usd=10.0, avg_loss_usd=20.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        result = kelly_notional("test_strat", params, half_kelly=False, db_path=db_path)
        assert result == 0.0, f"Expected 0.0 (negative edge), got {result}"


class TestHalfKelly:
    """half_kelly=True should yield exactly half of half_kelly=False."""

    def test_half_kelly_is_exactly_half(self):
        rows = _make_round_trips(40, win_rate=0.6, avg_win_usd=20.0, avg_loss_usd=10.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}

        full = kelly_notional("test_strat", params, half_kelly=False, db_path=db_path)
        half = kelly_notional("test_strat", params, half_kelly=True, db_path=db_path)

        # Only holds when neither is capped at max_notional.
        # Use a small max_notional so both are under the cap.
        full_uncapped = kelly_notional("test_strat", params, half_kelly=False,
                                      max_notional=50_000.0, db_path=db_path)
        half_uncapped = kelly_notional("test_strat", params, half_kelly=True,
                                      max_notional=50_000.0, db_path=db_path)
        assert abs(half_uncapped - full_uncapped / 2) < 1e-9, (
            f"half={half_uncapped}, full/2={full_uncapped/2}"
        )


class TestCapsAtMaxNotional:
    """Extreme history should never produce a notional > max_notional."""

    def test_caps_at_max_notional(self):
        # 100% win rate, huge wins → full Kelly = 1.0 → notional = max_notional.
        rows = _make_round_trips(30, win_rate=1.0, avg_win_usd=1000.0, avg_loss_usd=0.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        custom_max = 500.0
        result = kelly_notional("test_strat", params, max_notional=custom_max,
                                half_kelly=False, db_path=db_path)
        assert result <= custom_max, f"Exceeded max_notional {custom_max}: {result}"

    def test_caps_at_default_max_notional(self):
        rows = _make_round_trips(30, win_rate=1.0, avg_win_usd=1000.0, avg_loss_usd=0.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        result = kelly_notional("test_strat", params, half_kelly=False, db_path=db_path)
        assert result <= MAX_NOTIONAL, f"Exceeded MAX_NOTIONAL {MAX_NOTIONAL}: {result}"

    def test_caps_with_half_kelly(self):
        rows = _make_round_trips(30, win_rate=0.99, avg_win_usd=500.0, avg_loss_usd=1.0)
        db_path = _make_db(rows)
        params = {"notional_usd": 100.0}
        result = kelly_notional("test_strat", params, half_kelly=True, db_path=db_path)
        assert result <= MAX_NOTIONAL, f"Exceeded MAX_NOTIONAL with half_kelly: {result}"


class TestFifoRoundTrips:
    """Unit tests for the FIFO matching helper directly."""

    def test_single_round_trip_win(self):
        rows = [
            {"side": "buy", "qty": 1.0, "price": 100.0, "notional_usd": 100.0},
            {"side": "sell", "qty": 1.0, "price": 110.0, "notional_usd": 110.0},
        ]
        pnls = _fifo_round_trip_pnls(rows)
        assert len(pnls) == 1
        assert abs(pnls[0] - 10.0) < 1e-9

    def test_single_round_trip_loss(self):
        rows = [
            {"side": "buy", "qty": 1.0, "price": 100.0, "notional_usd": 100.0},
            {"side": "sell", "qty": 1.0, "price": 90.0, "notional_usd": 90.0},
        ]
        pnls = _fifo_round_trip_pnls(rows)
        assert len(pnls) == 1
        assert abs(pnls[0] - (-10.0)) < 1e-9

    def test_no_sells_no_pnl(self):
        rows = [
            {"side": "buy", "qty": 1.0, "price": 100.0, "notional_usd": 100.0},
        ]
        pnls = _fifo_round_trip_pnls(rows)
        assert pnls == []

    def test_multiple_round_trips(self):
        rows = [
            {"side": "buy", "qty": 1.0, "price": 100.0, "notional_usd": 100.0},
            {"side": "sell", "qty": 1.0, "price": 120.0, "notional_usd": 120.0},
            {"side": "buy", "qty": 1.0, "price": 100.0, "notional_usd": 100.0},
            {"side": "sell", "qty": 1.0, "price": 80.0, "notional_usd": 80.0},
        ]
        pnls = _fifo_round_trip_pnls(rows)
        assert len(pnls) == 2
        assert abs(pnls[0] - 20.0) < 1e-9
        assert abs(pnls[1] - (-20.0)) < 1e-9
