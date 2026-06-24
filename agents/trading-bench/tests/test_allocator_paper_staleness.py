"""Unit tests for the paper-clock STALENESS GUARD in runner/allocator_paper_tracker.py.

The guard's job: catch the silent failure mode where the tracker runs rc=0 but logs
NO new row for several trading days (stale SPX cache / engine returns an old mark_date).
That leaves a hole in the forward track record discovered only when someone reads the DB.

These tests are fully deterministic: we build a temp SQLite DB shaped exactly like
daily_snapshots, monkeypatch the ^GSPC trading-day calendar to a synthetic fixed list,
and assert trading_days_behind / stale across every case. No network, no engine.
"""
from __future__ import annotations

import importlib
import sqlite3

import pytest

trk = importlib.import_module("runner.allocator_paper_tracker")


# Synthetic SPX trading calendar (NOTE: 06-19 omitted = Juneteenth holiday, like reality).
CAL = [
    "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18",
    "2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25",
]


def _make_db(tmp_path, dates):
    """Build a daily_snapshots DB containing rows for the given dates."""
    db = str(tmp_path / "stale_test.db")
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE daily_snapshots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               date TEXT UNIQUE,
               w_tqqq REAL, w_rot REAL, rot_holds TEXT,
               daily_ret REAL, cum_ret_since_start REAL,
               spx_daily_ret REAL, cum_spx_since_start REAL,
               engine_full_sharpe REAL, created_at TEXT)"""
    )
    for d in dates:
        conn.execute(
            "INSERT INTO daily_snapshots (date, w_tqqq, w_rot, rot_holds, daily_ret, "
            "cum_ret_since_start, spx_daily_ret, cum_spx_since_start, engine_full_sharpe, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (d, 0.44, 0.56, '["SPY","QQQ"]', 0.001, 0.001, 0.001, 0.001, 1.0, "x"),
        )
    conn.commit()
    conn.close()
    return db


@pytest.fixture(autouse=True)
def _patch_calendar(monkeypatch):
    """Force the SPX calendar to the synthetic CAL for every test in this module."""
    monkeypatch.setattr(trk, "_spx_trading_dates", lambda: list(CAL))


def test_current_zero_behind(tmp_path):
    # last logged == latest closed bar -> 0 behind, not stale
    db = _make_db(tmp_path, CAL)  # logged through 06-25 (== latest bar)
    st = trk.clock_staleness(db_path=db)
    assert st["last_logged"] == "2026-06-25"
    assert st["latest_closed_bar"] == "2026-06-25"
    assert st["trading_days_behind"] == 0
    assert st["stale"] is False


def test_one_behind_is_not_stale(tmp_path):
    # logged through 06-24, latest bar 06-25 -> exactly 1 behind = normal intraday
    db = _make_db(tmp_path, CAL[:-1])
    st = trk.clock_staleness(db_path=db)
    assert st["trading_days_behind"] == 1
    assert st["stale"] is False
    assert "self-heals" in st["note"]


def test_two_behind_is_stale(tmp_path):
    # logged through 06-23, latest bar 06-25 -> 2 trading days behind = STALE
    db = _make_db(tmp_path, CAL[:-2])
    st = trk.clock_staleness(db_path=db)
    assert st["trading_days_behind"] == 2
    assert st["stale"] is True
    assert "STALE" in st["note"]


def test_holiday_gap_does_not_count(tmp_path):
    # logged through 06-18 (Thu). 06-19 is Juneteenth (NOT in CAL). Next bar 06-22.
    # Behind should count 06-22..06-25 = 4 sessions, NOT include the holiday.
    db = _make_db(tmp_path, ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18"])
    st = trk.clock_staleness(db_path=db)
    assert st["trading_days_behind"] == 4  # 22,23,24,25 — holiday 06-19 excluded
    assert st["stale"] is True


def test_empty_db_not_started(tmp_path):
    db = _make_db(tmp_path, [])  # table exists, zero rows
    st = trk.clock_staleness(db_path=db)
    assert st["last_logged"] is None
    assert st["trading_days_behind"] is None
    assert st["stale"] is False
    assert "not started" in st["note"]


def test_unreadable_calendar(tmp_path, monkeypatch):
    # If the ^GSPC cache is unreadable, we must NOT crash and NOT false-alarm.
    monkeypatch.setattr(trk, "_spx_trading_dates", lambda: [])
    db = _make_db(tmp_path, CAL)
    st = trk.clock_staleness(db_path=db)
    assert st["latest_closed_bar"] is None
    assert st["trading_days_behind"] is None
    assert st["stale"] is False
    assert "cannot assess" in st["note"]
