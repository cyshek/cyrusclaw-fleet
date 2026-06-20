"""Tests for runner/postmortem.py.

All tests use temporary SQLite DBs and temp dirs; never touch tournament.db.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Ensure workspace is on the path
WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runner.postmortem import (  # noqa: E402
    COST_BLOWOUT,
    REGIME_MISMATCH,
    SIGNAL_DECAY,
    THIN_SAMPLE,
    UNKNOWN,
    _classify_cause,
    _compute_stats,
    _fifo_round_trips,
    get_postmortem_directive_hint,
    run_postmortem,
    run_postmortems_for_all,
)


# ---------------------------------------------------------------------------
# Helpers to build test DBs
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc      TEXT    NOT NULL,
    strategy    TEXT    NOT NULL,
    symbol      TEXT    NOT NULL,
    side        TEXT    NOT NULL,
    qty         REAL,
    price       REAL,
    notional_usd REAL,
    status      TEXT    DEFAULT 'filled'
);
"""


def _make_db(path: Path) -> Path:
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


def _insert_trade(conn: sqlite3.Connection, strategy: str, side: str,
                  qty: float, price: float, notional: float = 0.0,
                  ts_offset_hours: float = 0.0):
    """Insert a trade with ts_utc = now - ts_offset_hours."""
    ts = (datetime.now(timezone.utc) - timedelta(hours=ts_offset_hours)).isoformat()
    notional = notional or (qty * price)
    conn.execute(
        "INSERT INTO trades (ts_utc, strategy, symbol, side, qty, price, notional_usd, status) "
        "VALUES (?, ?, 'BTC/USD', ?, ?, ?, ?, 'filled')",
        (ts, strategy, side, qty, price, notional),
    )


def _make_losing_strategy(db_path: Path, strategy: str = "test_loser",
                           n_round_trips: int = 6,
                           buy_price: float = 100.0, sell_price: float = 95.0,
                           hours_ago: float = 24.0):
    """Insert n round-trips where each sell is below buy (losing)."""
    with sqlite3.connect(db_path) as conn:
        for i in range(n_round_trips):
            offset_buy = hours_ago + (i * 2)
            offset_sell = hours_ago + (i * 2) - 1
            _insert_trade(conn, strategy, "buy", 1.0, buy_price,
                          ts_offset_hours=offset_buy)
            _insert_trade(conn, strategy, "sell", 1.0, sell_price,
                          ts_offset_hours=offset_sell)


def _make_profitable_strategy(db_path: Path, strategy: str = "test_winner",
                               n_round_trips: int = 6,
                               buy_price: float = 100.0, sell_price: float = 110.0,
                               hours_ago: float = 24.0):
    """Insert n round-trips where each sell is above buy (winning)."""
    with sqlite3.connect(db_path) as conn:
        for i in range(n_round_trips):
            offset_buy = hours_ago + (i * 2)
            offset_sell = hours_ago + (i * 2) - 1
            _insert_trade(conn, strategy, "buy", 1.0, buy_price,
                          ts_offset_hours=offset_buy)
            _insert_trade(conn, strategy, "sell", 1.0, sell_price,
                          ts_offset_hours=offset_sell)


# ---------------------------------------------------------------------------
# Test 1: no postmortem when profitable
# ---------------------------------------------------------------------------

def test_no_postmortem_when_profitable():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")
        _make_profitable_strategy(db_path, strategy="winner")

        result = run_postmortem(
            "winner",
            n_days=7,
            loss_threshold_usd=-1.0,
            workspace=tmpdir,
            db_path=db_path,
        )
        assert result is None, f"Expected None for profitable strategy, got {result}"


# ---------------------------------------------------------------------------
# Test 2: postmortem written when losing
# ---------------------------------------------------------------------------

def test_postmortem_written_when_losing():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")
        _make_losing_strategy(db_path, strategy="loser")

        result = run_postmortem(
            "loser",
            n_days=7,
            loss_threshold_usd=-1.0,
            workspace=tmpdir,
            db_path=db_path,
        )
        assert result is not None, "Expected a Path to be returned for a losing strategy"
        assert result.exists(), f"Postmortem file not found at {result}"
        text = result.read_text()
        assert "loser" in text
        assert "Postmortem" in text


# ---------------------------------------------------------------------------
# Test 3: idempotent — second call returns None
# ---------------------------------------------------------------------------

def test_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")
        _make_losing_strategy(db_path, strategy="loser")

        result1 = run_postmortem(
            "loser", n_days=7, loss_threshold_usd=-1.0, workspace=tmpdir, db_path=db_path
        )
        assert result1 is not None, "First call should write a file"

        result2 = run_postmortem(
            "loser", n_days=7, loss_threshold_usd=-1.0, workspace=tmpdir, db_path=db_path
        )
        assert result2 is None, "Second call same week should be idempotent (return None)"


# ---------------------------------------------------------------------------
# Test 4: cause = THIN_SAMPLE when < 5 round-trips
# ---------------------------------------------------------------------------

def test_cause_thin_sample():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")
        # Only 3 round-trips (< 5 threshold)
        _make_losing_strategy(db_path, strategy="thin", n_round_trips=3)

        result = run_postmortem(
            "thin", n_days=7, loss_threshold_usd=-1.0, workspace=tmpdir, db_path=db_path
        )
        assert result is not None
        text = result.read_text()
        assert THIN_SAMPLE in text


# ---------------------------------------------------------------------------
# Test 5: cause = SIGNAL_DECAY — profitable all-time, recent loss
# ---------------------------------------------------------------------------

def test_cause_signal_decay():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")
        strategy = "decay_strat"

        # Old profitable trades (more than 7 days ago — outside the window)
        with sqlite3.connect(db_path) as conn:
            for i in range(10):
                # 15+ days ago = outside 7-day window but inside all-time
                old_offset = 360 + i * 2  # hours = 15+ days back
                _insert_trade(conn, strategy, "buy", 1.0, 100.0, ts_offset_hours=old_offset)
                _insert_trade(conn, strategy, "sell", 1.0, 115.0, ts_offset_hours=old_offset - 1)

            # Recent losing trades (within 7-day window)
            for i in range(6):
                _insert_trade(conn, strategy, "buy", 1.0, 100.0, ts_offset_hours=24 + i * 2)
                _insert_trade(conn, strategy, "sell", 1.0, 94.0, ts_offset_hours=24 + i * 2 - 1)

        result = run_postmortem(
            strategy, n_days=7, loss_threshold_usd=-1.0, workspace=tmpdir, db_path=db_path
        )
        assert result is not None
        text = result.read_text()
        assert SIGNAL_DECAY in text, f"Expected SIGNAL_DECAY in postmortem, got:\n{text}"


# ---------------------------------------------------------------------------
# Test 6: directive hint section in output
# ---------------------------------------------------------------------------

def test_directive_hint_in_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")
        _make_losing_strategy(db_path, strategy="loser2")

        result = run_postmortem(
            "loser2", n_days=7, loss_threshold_usd=-1.0, workspace=tmpdir, db_path=db_path
        )
        assert result is not None
        text = result.read_text()
        assert "Suggested Mutation Directives" in text, \
            "Expected 'Suggested Mutation Directives' section in postmortem"
        # Should have at least one directive line
        assert "**Directive" in text or "No directives" in text


# ---------------------------------------------------------------------------
# Test 7: run_postmortems_for_all — only loser gets a file
# ---------------------------------------------------------------------------

def test_run_postmortems_for_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")

        _make_profitable_strategy(db_path, strategy="winner_multi")
        _make_losing_strategy(db_path, strategy="loser_multi")

        paths = run_postmortems_for_all(
            n_days=7,
            loss_threshold_usd=-1.0,
            workspace=tmpdir,
            db_path=db_path,
        )

        # Only the loser should produce a file
        assert len(paths) == 1, f"Expected exactly 1 postmortem, got {len(paths)}: {paths}"
        assert "loser_multi" in paths[0].name, \
            f"Expected loser_multi in path, got {paths[0].name}"

        # Winner should have no file
        pm_dir = tmpdir / "reports" / "postmortem"
        winner_files = list(pm_dir.glob("winner_multi_*.md"))
        assert len(winner_files) == 0, \
            f"Unexpected postmortem files for winner: {winner_files}"


# ---------------------------------------------------------------------------
# Additional: test _classify_cause logic directly
# ---------------------------------------------------------------------------

def test_classify_thin_sample_direct():
    recent = {"n_rt": 3, "realized_pnl": -5.0, "avg_trade_pnl": -1.67,
               "win_rate": 0.0, "turnover": 300.0, "n_buys": 3, "n_sells": 3}
    alltime = {"realized_pnl": -5.0}
    assert _classify_cause(recent, alltime) == THIN_SAMPLE


def test_classify_cost_blowout_direct():
    recent = {"n_rt": 10, "realized_pnl": -15.0, "avg_trade_pnl": -1.5,
               "win_rate": 0.3, "turnover": 500.0, "n_buys": 10, "n_sells": 10}
    alltime = {"realized_pnl": -15.0}
    assert _classify_cause(recent, alltime) == COST_BLOWOUT


def test_classify_signal_decay_direct():
    recent = {"n_rt": 8, "realized_pnl": -30.0, "avg_trade_pnl": -3.75,
               "win_rate": 0.25, "turnover": 200.0, "n_buys": 8, "n_sells": 8}
    alltime = {"realized_pnl": 200.0}  # profitable all-time
    assert _classify_cause(recent, alltime) == SIGNAL_DECAY


def test_classify_regime_mismatch_direct():
    # Low win rate + mostly buys → regime mismatch
    recent = {"n_rt": 8, "realized_pnl": -40.0, "avg_trade_pnl": -5.0,
               "win_rate": 0.25, "turnover": 100.0, "n_buys": 10, "n_sells": 5}
    alltime = {"realized_pnl": -40.0}  # no all-time profit
    assert _classify_cause(recent, alltime) == REGIME_MISMATCH


def test_fifo_round_trips_basic():
    """Test that FIFO matching correctly computes PnL."""
    rows = [
        {"side": "buy", "qty": 1.0, "price": 100.0, "notional_usd": 100.0},
        {"side": "sell", "qty": 1.0, "price": 110.0, "notional_usd": 110.0},
        {"side": "buy", "qty": 1.0, "price": 100.0, "notional_usd": 100.0},
        {"side": "sell", "qty": 1.0, "price": 90.0, "notional_usd": 90.0},
    ]
    pnls = _fifo_round_trips(rows)
    assert len(pnls) == 2
    assert abs(pnls[0] - 10.0) < 1e-6, f"Expected +10, got {pnls[0]}"
    assert abs(pnls[1] - (-10.0)) < 1e-6, f"Expected -10, got {pnls[1]}"


def test_overwrite_flag():
    """With overwrite=True, a second call should overwrite and return a path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = _make_db(tmpdir / "test.db")
        _make_losing_strategy(db_path, strategy="loser_ow")

        r1 = run_postmortem(
            "loser_ow", n_days=7, loss_threshold_usd=-1.0, workspace=tmpdir, db_path=db_path
        )
        assert r1 is not None

        r2 = run_postmortem(
            "loser_ow", n_days=7, loss_threshold_usd=-1.0, workspace=tmpdir, db_path=db_path,
            overwrite=True,
        )
        assert r2 is not None, "overwrite=True should return a path even if file exists"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
