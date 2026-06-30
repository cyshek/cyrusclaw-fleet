"""Tests for runner.gate_tracker — the forward-paper GATE-tracker dashboard.

Focused on the three correctness pillars the task demands:
  (a) synthetic-row filter drops 'any'/'backstop_test'/'bp2' + short/None order ids;
  (b) round-trip proxy = Σ min(buys, sells) per symbol;
  (c) the < 20-day small-sample warning fires when n < 20 and NOT when n >= 20.

All fixtures are tiny temp SQLite DBs; the script is exercised read-only.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from runner import gate_tracker as gt


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------
def _make_trades_db(path: str, rows: list[tuple]) -> None:
    """rows: (ts_utc, strategy, symbol, side, alpaca_order_id, status)."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE trades ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts_utc TEXT NOT NULL, strategy TEXT NOT NULL, symbol TEXT NOT NULL,"
        " side TEXT NOT NULL, qty REAL NOT NULL DEFAULT 1, notional_usd REAL,"
        " price REAL, alpaca_order_id TEXT, status TEXT NOT NULL,"
        " reason TEXT, raw TEXT)"
    )
    conn.executemany(
        "INSERT INTO trades (ts_utc, strategy, symbol, side, alpaca_order_id, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _make_snapshots_db(path: str, n_days: int) -> None:
    """Minimal daily_snapshots DB with n_days rows of plausible returns."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE daily_snapshots ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT UNIQUE,"
        " daily_ret REAL, cum_ret_since_start REAL, spx_daily_ret REAL,"
        " cum_spx_since_start REAL, engine_full_sharpe REAL, created_at TEXT)"
    )
    cum_s = 0.0
    cum_b = 0.0
    for i in range(n_days):
        ds = 0.001 * ((i % 5) - 2)   # small alternating returns
        db = 0.0008 * ((i % 4) - 1)
        cum_s = (1 + cum_s) * (1 + ds) - 1
        cum_b = (1 + cum_b) * (1 + db) - 1
        d = f"2026-06-{(i % 28) + 1:02d}"  # date string; uniqueness not required for n-count
        try:
            conn.execute(
                "INSERT INTO daily_snapshots (date, daily_ret, cum_ret_since_start,"
                " spx_daily_ret, cum_spx_since_start, engine_full_sharpe, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"{d}-{i}", ds, cum_s, db, cum_b, 1.01, "2026-06-30T00:00:00+00:00"),
            )
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# (a) Synthetic-row filter.
# ---------------------------------------------------------------------------
def test_is_synthetic_unit():
    real = "51b1625f-8220-4653-8bd2-02070c05031b"  # 36-char UUID
    # synthetic by strategy name
    assert gt.is_synthetic("any", real) is True
    assert gt.is_synthetic("backstop_test", real) is True
    assert gt.is_synthetic("bp2", real) is True
    # synthetic by order id
    assert gt.is_synthetic("real_strat", None) is True
    assert gt.is_synthetic("real_strat", "order-1") is True
    assert gt.is_synthetic("real_strat", "ord-seed") is True
    assert gt.is_synthetic("real_strat", "short") is True          # len < 20
    assert gt.is_synthetic("real_strat", "x" * 19) is True         # boundary: 19 -> drop
    # real
    assert gt.is_synthetic("real_strat", real) is False
    assert gt.is_synthetic("real_strat", "y" * 20) is False        # boundary: 20 -> keep


def test_synthetic_rows_dropped_in_trade_metrics(tmp_path):
    real1 = "51b1625f-8220-4653-8bd2-02070c05031b"
    real2 = "fe22185f-4357-4515-8010-29c5938f348d"
    db = str(tmp_path / "trades.db")
    rows = [
        # 2 REAL fills for our strategy (1 buy, 1 sell on QQQ)
        ("2026-06-20T13:30:00+00:00", "mystrat", "QQQ", "buy", real1, "filled"),
        ("2026-06-21T13:30:00+00:00", "mystrat", "QQQ", "sell", real2, "filled"),
        # synthetic: short/seed order ids on same strategy name -> must be dropped
        ("2026-06-20T13:30:00+00:00", "mystrat", "QQQ", "buy", "order-1", "filled"),
        ("2026-06-20T13:30:00+00:00", "mystrat", "QQQ", "buy", "ord-seed", "filled"),
        ("2026-06-20T13:30:00+00:00", "mystrat", "QQQ", "buy", None, "filled"),
        # synthetic strategy names -> dropped even with a real-looking id
        ("2026-06-20T13:30:00+00:00", "any", "QQQ", "buy", real1, "filled"),
        ("2026-06-20T13:30:00+00:00", "backstop_test", "QQQ", "buy", real2, "filled"),
        # non-filled status -> not a fill
        ("2026-06-20T13:30:00+00:00", "mystrat", "QQQ", "sell", real1, "rejected"),
    ]
    _make_trades_db(db, rows)
    conn = gt._connect_ro(db)
    try:
        m = gt.compute_trade_metrics(conn, "mystrat")
    finally:
        conn.close()
    # only the 2 real filled rows survive
    assert m["fills"] == 2
    assert m["buys"] == 1
    assert m["sells"] == 1


# ---------------------------------------------------------------------------
# (b) Round-trip proxy = Σ min(buys, sells) per symbol.
# ---------------------------------------------------------------------------
def test_round_trip_proxy_min_buys_sells_per_symbol(tmp_path):
    rid = lambda k: f"{k:0<36}"  # 36-char-ish unique real order ids
    db = str(tmp_path / "rt.db")
    rows = [
        # QQQ: 3 buys, 1 sell -> min = 1
        ("2026-06-20T13:30:00+00:00", "s", "QQQ", "buy", rid("a1"), "filled"),
        ("2026-06-20T13:31:00+00:00", "s", "QQQ", "buy", rid("a2"), "filled"),
        ("2026-06-20T13:32:00+00:00", "s", "QQQ", "buy", rid("a3"), "filled"),
        ("2026-06-21T13:30:00+00:00", "s", "QQQ", "sell", rid("a4"), "filled"),
        # IWM: 2 buys, 2 sells -> min = 2
        ("2026-06-20T14:30:00+00:00", "s", "IWM", "buy", rid("b1"), "filled"),
        ("2026-06-20T14:31:00+00:00", "s", "IWM", "buy", rid("b2"), "filled"),
        ("2026-06-21T14:30:00+00:00", "s", "IWM", "sell", rid("b3"), "filled"),
        ("2026-06-21T14:31:00+00:00", "s", "IWM", "sell", rid("b4"), "filled"),
        # SPY: 1 buy, 0 sells -> min = 0
        ("2026-06-20T15:30:00+00:00", "s", "SPY", "buy", rid("c1"), "filled"),
    ]
    _make_trades_db(db, rows)
    conn = gt._connect_ro(db)
    try:
        m = gt.compute_trade_metrics(conn, "s")
    finally:
        conn.close()
    # per-symbol min: QQQ=1, IWM=2, SPY=0 -> total 3
    assert m["round_trips"] == 3
    assert m["buys"] == 6
    assert m["sells"] == 3
    assert m["fills"] == 9
    assert m["symbols"] == ["IWM", "QQQ", "SPY"]


# ---------------------------------------------------------------------------
# (c) Small-sample warning fires for n<20, not for n>=20.
# ---------------------------------------------------------------------------
def test_small_sample_flag_fires_below_20(tmp_path):
    db = str(tmp_path / "snap_small.db")
    _make_snapshots_db(db, n_days=7)
    m = gt.compute_realized_metrics(db, "SPX")
    assert m is not None
    assert m["n_days"] == 7
    assert m["small_sample"] is True
    # and the warning text appears in the rendered block
    block = "\n".join(gt.render_strategy_block(
        "demo",
        {"fills": 0, "buys": 0, "sells": 0, "round_trips": 0, "symbols": [],
         "first_fill": None, "last_fill": None, "days_live": 0},
        m,
    ))
    assert "SAMPLE TOO SMALL" in block


def test_small_sample_flag_clears_at_or_above_20(tmp_path):
    db = str(tmp_path / "snap_big.db")
    _make_snapshots_db(db, n_days=25)
    m = gt.compute_realized_metrics(db, "SPX")
    assert m is not None
    assert m["n_days"] == 25
    assert m["small_sample"] is False
    block = "\n".join(gt.render_strategy_block(
        "demo",
        {"fills": 4, "buys": 2, "sells": 2, "round_trips": 2, "symbols": ["QQQ"],
         "first_fill": None, "last_fill": None, "days_live": 30},
        m,
    ))
    assert "SAMPLE TOO SMALL" not in block


def test_small_sample_boundary_exactly_20(tmp_path):
    db = str(tmp_path / "snap_20.db")
    _make_snapshots_db(db, n_days=20)
    m = gt.compute_realized_metrics(db, "SPX")
    assert m is not None
    assert m["n_days"] == 20
    # n == SMALL_SAMPLE_DAYS (20) is NOT small (strict <)
    assert m["small_sample"] is False


# ---------------------------------------------------------------------------
# Bonus: math + read-only / absent-DB robustness.
# ---------------------------------------------------------------------------
def test_annualized_sharpe_and_drawdown():
    # constant positive returns -> infinite Sharpe (std 0) -> None by design
    assert gt._annualized_sharpe([0.01, 0.01, 0.01]) is None
    # mixed returns -> finite number
    s = gt._annualized_sharpe([0.01, -0.005, 0.008, -0.002, 0.006])
    assert s is not None and isinstance(s, float)
    # drawdown of a path that drops then recovers is negative
    mdd = gt._max_drawdown([0.10, -0.20, 0.05])
    assert mdd is not None and mdd < 0


def test_absent_db_returns_none():
    assert gt.compute_realized_metrics("/nonexistent/path/nope.db", "SPX") is None
    assert gt._connect_ro("/nonexistent/path/nope.db") is None


def test_render_and_markdown_smoke():
    """Full render against the real on-disk DBs must not raise and must carry the honesty banner."""
    report = gt._build_report(gt.LIVE_STRATEGIES)
    text = gt.render_dashboard(report)
    md = gt.render_markdown(report)
    assert "GATE-TRACKER DASHBOARD" in text
    assert "track-record" in text.lower()
    assert "INFORMATIONAL" in text
    assert "GATE-TRACKER DASHBOARD" in md
    # every live + tracker strategy name shows up
    for name in gt.LIVE_STRATEGIES + gt.STANDALONE_TRACKERS:
        assert name in md
