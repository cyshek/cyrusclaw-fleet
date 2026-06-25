"""Tests for runner.tsmom_blend_paper_tracker (80/20 equity-book x core4 paper clock).

Fast: the heavy build_ingredients() (8 backtests + core4) is monkeypatched with
synthetic maps so these run in milliseconds. We assert the DB schema/idempotency,
cum-since-start compounding, blend arithmetic, the vol-normalize-then-ERC book
construction math, and the wall-clock staleness guard.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from runner import tsmom_blend_paper_tracker as T


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="tsmom_blend_test_")
    os.close(fd)
    try:
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)


def _fake_ingredients(book, core4, spy, holds=None, weights=None):
    """Return a build_ingredients() replacement yielding the given maps."""
    holds = holds or {}
    weights = weights or {nm: 1.0 / len(T.LIVE8) for nm in T.LIVE8}

    def _bi():
        return dict(book), dict(core4), dict(spy), dict(holds), dict(weights)
    return _bi


# --------------------------------------------------------------------------- #
# schema + idempotency
# --------------------------------------------------------------------------- #
def test_ddl_creates_table(db_path):
    conn = T._get_conn(db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_snapshots)")}
    conn.close()
    assert {"date", "x_book", "daily_ret", "cum_ret_since_start",
            "spx_daily_ret", "cum_spx_since_start", "engine_full_sharpe",
            "engine_book_sharpe", "core4_holds", "created_at"} <= cols


def test_snapshot_logs_latest_common_day(db_path, monkeypatch):
    book = {"2026-06-16": 0.001, "2026-06-17": 0.002, "2026-06-18": 0.003}
    core4 = {"2026-06-16": 0.0, "2026-06-17": 0.001, "2026-06-18": -0.001}
    spy = {"2026-06-16": 0.004, "2026-06-17": 0.005, "2026-06-18": 0.006}
    monkeypatch.setattr(T, "build_ingredients", _fake_ingredients(book, core4, spy))
    row = T.snapshot_today(db_path)
    assert row["date"] == "2026-06-18"          # latest common day
    assert row["_already_logged"] is False
    # blend = 0.8*book + 0.2*core4 on the mark day
    assert row["daily_ret"] == pytest.approx(0.8 * 0.003 + 0.2 * (-0.001))
    assert row["book_daily_ret"] == pytest.approx(0.003)
    assert row["core4_daily_ret"] == pytest.approx(-0.001)
    assert row["spx_daily_ret"] == pytest.approx(0.006)


def test_snapshot_is_idempotent(db_path, monkeypatch):
    book = {"2026-06-18": 0.003}
    core4 = {"2026-06-18": -0.001}
    spy = {"2026-06-18": 0.006}
    monkeypatch.setattr(T, "build_ingredients", _fake_ingredients(book, core4, spy))
    r1 = T.snapshot_today(db_path)
    r2 = T.snapshot_today(db_path)
    assert r1["_already_logged"] is False
    assert r2["_already_logged"] is True
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM daily_snapshots").fetchone()[0]
    conn.close()
    assert n == 1                                # never double-logged


def test_no_common_day_raises(db_path, monkeypatch):
    monkeypatch.setattr(
        T, "build_ingredients",
        _fake_ingredients({"2026-06-18": 0.0}, {"2026-06-17": 0.0}, {"2026-06-16": 0.0}))
    with pytest.raises(RuntimeError):
        T.snapshot_today(db_path)


# --------------------------------------------------------------------------- #
# cum-since-start compounding across multiple forward days
# --------------------------------------------------------------------------- #
def test_cum_since_start_compounds(db_path, monkeypatch):
    # day 1: only 06-17 common
    monkeypatch.setattr(
        T, "build_ingredients",
        _fake_ingredients({"2026-06-17": 0.010}, {"2026-06-17": 0.000},
                          {"2026-06-17": 0.020}))
    d1 = T.snapshot_today(db_path)
    assert d1["cum_ret_since_start"] == pytest.approx(0.8 * 0.010)        # 0.008
    assert d1["cum_spx_since_start"] == pytest.approx(0.020)

    # day 2: 06-18 now also present -> marks 06-18, compounds onto prior cum
    monkeypatch.setattr(
        T, "build_ingredients",
        _fake_ingredients({"2026-06-17": 0.010, "2026-06-18": 0.005},
                          {"2026-06-17": 0.000, "2026-06-18": 0.000},
                          {"2026-06-17": 0.020, "2026-06-18": 0.010}))
    d2 = T.snapshot_today(db_path)
    assert d2["date"] == "2026-06-18"
    blend2 = 0.8 * 0.005
    assert d2["cum_ret_since_start"] == pytest.approx((1 + 0.008) * (1 + blend2) - 1)
    assert d2["cum_spx_since_start"] == pytest.approx((1 + 0.020) * (1 + 0.010) - 1)


# --------------------------------------------------------------------------- #
# core4 holds resolution (most-recent rebalance <= mark)
# --------------------------------------------------------------------------- #
def test_core4_holds_resolves_to_latest_rebalance(db_path, monkeypatch):
    book = {"2026-06-18": 0.003}
    core4 = {"2026-06-18": -0.001}
    spy = {"2026-06-18": 0.006}
    holds = {"2026-05-01": ["DBC", "GLD"], "2026-06-01": ["GLD", "TLT", "UUP"]}
    monkeypatch.setattr(
        T, "build_ingredients", _fake_ingredients(book, core4, spy, holds=holds))
    row = T.snapshot_today(db_path)
    assert sorted(row["core4_holds"]) == ["GLD", "TLT", "UUP"]   # 06-01 snapshot


# --------------------------------------------------------------------------- #
# vol-normalize-then-ERC book math (the validated construction)
# --------------------------------------------------------------------------- #
def test_ann_vol_matches_blend_volnorm():
    rets = [0.01, -0.02, 0.015, -0.005, 0.0, 0.008, -0.011, 0.004]
    n = len(rets)
    m = sum(rets) / n
    v = sum((x - m) ** 2 for x in rets) / (n - 1)
    expected = math.sqrt(v) * math.sqrt(252)
    assert T._ann_vol(rets) == pytest.approx(expected)
    assert T._ann_vol([0.01]) == 0.0            # too few -> 0


def test_build_ingredients_volnorm_construction(monkeypatch, tmp_path):
    """book_ret[t] must equal Σ rwn_i · (TARGET_VOL/vol_i) · series_i[t]."""
    # two-day synthetic series for the 8 sleeves with distinct vols.
    dates = [f"2026-06-{d:02d}" for d in range(1, 41)]   # 40 days for stable vol
    rng = [0.001 * ((i % 7) - 3) for i in range(len(dates))]
    series = {}
    for k, nm in enumerate(T.LIVE8):
        amp = 1.0 + k                            # different vol per sleeve
        series[nm] = {dates[i]: amp * rng[i] for i in range(len(dates))}

    class _FakeX:
        @staticmethod
        def build_all_series():
            spy = {d: 0.0005 for d in dates}
            return series, {}, spy

    class _FakeE:
        @staticmethod
        def run_tsmom(*a, **k):
            return {"dates": dates, "net": [0.0 for _ in dates], "weights_hist": []}

    monkeypatch.setitem(__import__("sys").modules, "_xstrat_corr", _FakeX)
    monkeypatch.setitem(__import__("sys").modules, "_tsmom_engine", _FakeE)

    # equal risk weights so we can recompute expected by hand.
    eqrw = {nm: 1.0 / len(T.LIVE8) for nm in T.LIVE8}
    monkeypatch.setattr(T, "_load_risk_weights", lambda: eqrw)

    book, core4, spy, holds, w = T.build_ingredients()

    # recompute expected scale per sleeve and the book on the last day.
    last = dates[-1]
    scale = {}
    for nm in T.LIVE8:
        vol = T._ann_vol([series[nm][d] for d in dates])
        scale[nm] = (T.TARGET_VOL / vol) if vol > 1e-9 else 0.0
    expected_last = sum(eqrw[nm] * scale[nm] * series[nm][last] for nm in T.LIVE8)
    assert book[last] == pytest.approx(expected_last)
    # each sleeve scaled to ~TARGET_VOL => equal-weighted book vol ~<= TARGET_VOL
    book_vol = T._ann_vol([book[d] for d in dates])
    assert book_vol <= T.TARGET_VOL + 1e-6


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #
def test_paper_clock_stats_empty(db_path):
    assert T.paper_clock_stats(db_path) == {"n_rows": 0}


def test_paper_clock_stats_after_rows(db_path, monkeypatch):
    monkeypatch.setattr(
        T, "build_ingredients",
        _fake_ingredients({"2026-06-18": 0.01}, {"2026-06-18": 0.0},
                          {"2026-06-18": 0.02}))
    T.snapshot_today(db_path)
    st = T.paper_clock_stats(db_path)
    assert st["n_rows"] == 1
    assert st["first_date"] == "2026-06-18"
    assert st["blend_cum_ret"] == pytest.approx(0.8 * 0.01)
    assert st["spx_cum_ret"] == pytest.approx(0.02)
    assert st["blend_minus_spx_cum"] == pytest.approx(0.008 - 0.02)


# --------------------------------------------------------------------------- #
# staleness (wall-clock)
# --------------------------------------------------------------------------- #
def test_staleness_empty_is_fresh(db_path):
    assert T.check_staleness(db_path) == 0


def test_staleness_recent_row_is_fresh(db_path, monkeypatch):
    monkeypatch.setattr(
        T, "build_ingredients",
        _fake_ingredients({"2026-06-18": 0.01}, {"2026-06-18": 0.0},
                          {"2026-06-18": 0.02}))
    T.snapshot_today(db_path)
    assert T.check_staleness(db_path) == 0       # just written


def test_staleness_old_row_flags(db_path):
    conn = T._get_conn(db_path)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    conn.execute(
        "INSERT INTO daily_snapshots (date, x_book, core4_holds, book_daily_ret, "
        "core4_daily_ret, daily_ret, cum_ret_since_start, spx_daily_ret, "
        "cum_spx_since_start, engine_full_sharpe, engine_book_sharpe, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("2026-06-08", 0.8, "[]", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, old))
    conn.commit()
    conn.close()
    assert T.check_staleness(db_path) == 3       # >4 days old -> STALE
    assert T.check_staleness(db_path, max_age_days=30) == 0   # tolerant -> fresh


# --------------------------------------------------------------------------- #
# config sanity (catch silent drift of the validated knobs)
# --------------------------------------------------------------------------- #
def test_config_constants_match_validated_blend():
    assert T.BLEND_X == 0.80
    assert T.CORE4_ASSETS == ["DBC", "GLD", "TLT", "UUP"]
    assert T.CORE4_LOOKBACK_M == 12 and T.CORE4_SKIP_M == 1
    assert T.CORE4_WEIGHTING == "ew"
    assert T.TARGET_VOL == 0.10
    assert len(T.LIVE8) == 8
    assert T.ERC_RISK_KEY == "risk_weights"
