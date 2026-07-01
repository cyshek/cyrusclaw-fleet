"""Unit tests for runner/tom_overlay_paper_tracker.py — the TOM (Turn-of-Month)
leverage-concentration OVERLAY PAPER CLOCK.

These tests pin the make-or-break properties of the tracker WITHOUT touching the heavy
compute path (no network, no full backtest) — they exercise only the PURE helpers and the
DB layer, exactly like the crash_sleeve / daa / allocator tracker tests:

  * the TOM mask (reused verbatim from reports/_tom_overlay_harness.tom_mask) is a PURE
    function of the ordered date axis — leak-free by construction (no price input), and the
    +1-bar canary shift moves the window LATER, never earlier
  * the overlay_etf leg (reused primitive) delivers +tilt exposure in-window and pure 1x
    out-of-window, and falls back to 1x when the ETF has no bar (never invents a return)
  * snapshot_today idempotency on date (second same-day call inserts 0 rows)
  * 5-stream cum-since-start compounding (spx_overlay / spx_bh / ndx_overlay / ndx_bh / spx_index)
  * paper_clock_stats: per-book overlay-vs-B&H raw-return gap + forward Sharpe + TOM-engage rate
  * the staleness guard (trading_days_behind / stale), mirroring the crash_sleeve fixtures

Deterministic + offline by construction. The one heavy path (compute_tom_overlay_state, which
calls the harness engine over ALL history + refreshes bars over the network) is intentionally
NOT unit-tested here — mirrors the crash_sleeve / daa / allocator tracker test convention of
only testing the pure logic + DB semantics; the engine reproduction is smoke-verified against
the validated harness numbers at build time.
"""
from __future__ import annotations

import datetime as dt
import importlib
import sqlite3
from unittest import mock

import pytest

trk = importlib.import_module("runner.tom_overlay_paper_tracker")
_harness = importlib.import_module("reports._tom_overlay_harness")


# --------------------------------------------------------------------------- #
# helpers: a small deterministic calendar spanning two month-turns.
# --------------------------------------------------------------------------- #
def _month_turn_dates():
    """Trading days across a full Jan + full Feb 2025 (skips weekends), ascending, so BOTH
    the Dec->Jan and Jan->Feb turns are real and there are genuine interior out-of-window
    days. (A too-short array makes the harness see the array boundary as a month-end -- that
    is a synthetic-fixture artifact, not tracker behavior; a full-month calendar avoids it.)"""
    days = []
    for mo, last in ((1, 31), (2, 28)):
        for dom in range(1, last + 1):
            d = dt.date(2025, mo, dom)
            if d.weekday() < 5:  # Mon-Fri only
                days.append(d)
    return days


# --------------------------------------------------------------------------- #
# 1. TOM mask is a PURE, leak-free date function (reused harness primitive).
# --------------------------------------------------------------------------- #
def test_tom_mask_marks_last_pre_and_first_post():
    """With pre=2/post=3 the last 2 Jan days + first 3 Feb days are in-window; the
    interior days are out. Pure function of the date axis — no price input at all."""
    dates = _month_turn_dates()
    mask = _harness.tom_mask(dates, trk.PRE, trk.POST, shift=0)
    # Jan 30, Jan 31 = last 2 of Jan -> in
    assert mask[dates.index(dt.date(2025, 1, 30))] is True
    assert mask[dates.index(dt.date(2025, 1, 31))] is True
    # Feb 3, 4, 5 = first 3 of Feb -> in
    assert mask[dates.index(dt.date(2025, 2, 3))] is True
    assert mask[dates.index(dt.date(2025, 2, 4))] is True
    assert mask[dates.index(dt.date(2025, 2, 5))] is True
    # Feb 6, 7 = 4th/5th trading day of Feb -> OUT (interior; real Feb calendar extends past them)
    assert mask[dates.index(dt.date(2025, 2, 6))] is False
    assert mask[dates.index(dt.date(2025, 2, 7))] is False
    # A deep-interior Jan day (Jan 15) is also out-of-window
    assert mask[dates.index(dt.date(2025, 1, 15))] is False


def test_tom_mask_canary_shift_moves_window_later_not_earlier():
    """The +1-bar canary: shifting the mask +1 moves each True one index LATER
    (proves the window is an ordered-date function with no same-bar leakage)."""
    dates = _month_turn_dates()
    base = _harness.tom_mask(dates, trk.PRE, trk.POST, shift=0)
    lag = _harness.tom_mask(dates, trk.PRE, trk.POST, shift=1)
    # every lagged True at index i corresponds to a base True at i-1
    for i in range(1, len(dates)):
        if lag[i]:
            assert base[i - 1] is True
    # and index 0 can never be True under a +1 shift
    assert lag[0] is False


def test_tom_mask_is_price_independent():
    """The mask must not depend on any price series — same dates, different prices,
    identical mask (the structural leak-free guarantee)."""
    dates = _month_turn_dates()
    m1 = _harness.tom_mask(dates, trk.PRE, trk.POST, shift=0)
    m2 = _harness.tom_mask(dates, trk.PRE, trk.POST, shift=0)
    assert m1 == m2  # deterministic, no hidden state
    assert len(m1) == len(dates)


# --------------------------------------------------------------------------- #
# 2. overlay_etf leg: +tilt in-window, pure 1x out; ETF-missing falls back to 1x.
# --------------------------------------------------------------------------- #
def test_overlay_etf_adds_tilt_in_window_only():
    """On an in-window UP day the overlay return > the 1x return (extra 3x tilt);
    on an out-window day the overlay return == the 1x return (no leg held)."""
    dates = _month_turn_dates()
    # constant +1% index day-over-day; ETF (3x) ~ +3% those days.
    rets = [(dates[i], 0.01) for i in range(1, len(dates))]
    etf_d2r = {d: 0.03 for d in dates}
    mask = _harness.tom_mask(dates, trk.PRE, trk.POST, shift=0)
    ov = _harness.overlay_etf(dates, rets, mask, trk.SHELF_TILT, etf_d2r, trk.K_MULT)
    ov_map = dict(ov)
    # in-window day (Feb 4) -> blended (0.75*1% + 0.25*3%) = 1.5%, minus tiny cost only on entry
    in_day = dt.date(2025, 2, 4)
    assert ov_map[in_day] > 0.011, "in-window overlay must exceed the 1x 1%% return"
    # out-window day (Feb 7, deep interior of a full Feb) -> exactly the 1x return (no ETF leg)
    out_day = dt.date(2025, 2, 7)
    assert abs(ov_map[out_day] - 0.01) < 1e-12, "out-window overlay must equal 1x return"


def test_overlay_etf_missing_bar_falls_back_to_1x():
    """If the ETF has no return for an in-window date, that day is pure 1x (never
    invents an ETF return) — the honest-degradation guarantee."""
    dates = _month_turn_dates()
    rets = [(dates[i], 0.02) for i in range(1, len(dates))]
    # ETF map DELIBERATELY empty -> every in-window day must fall back to 1x.
    etf_d2r = {}
    mask = _harness.tom_mask(dates, trk.PRE, trk.POST, shift=0)
    ov = _harness.overlay_etf(dates, rets, mask, trk.SHELF_TILT, etf_d2r, trk.K_MULT)
    for d, r in ov:
        assert abs(r - 0.02) < 1e-12, "missing ETF bar must degrade to pure 1x on %s" % d


def test_etf_weight_matches_shelf_config():
    """The shelf constants are internally consistent: w = tilt/(k-1) = 0.25 for
    tilt=0.5 into a 3x ETF."""
    assert abs(trk.ETF_WEIGHT - 0.25) < 1e-12
    assert abs(trk.SHELF_TILT - 0.5) < 1e-12
    assert trk.K_MULT == 3.0
    assert trk.PRE == 2 and trk.POST == 3


# --------------------------------------------------------------------------- #
# 3. snapshot_today idempotency + 5-stream cum compounding.
# --------------------------------------------------------------------------- #
def _fake_state(mark_date, in_tom, spx_ov, spx_bh, ndx_ov, ndx_bh, spx_ix):
    """A compute_tom_overlay_state() return shaped exactly like the real one."""
    return {
        "mark_date": mark_date,
        "date_note": "ok",
        "in_tom_window": 1 if in_tom else 0,
        "spx_overlay_daily_ret": spx_ov,
        "spx_bh_daily_ret": spx_bh,
        "spx_overlay_full_sharpe": 0.9,
        "ndx_overlay_daily_ret": ndx_ov,
        "ndx_bh_daily_ret": ndx_bh,
        "ndx_overlay_full_sharpe": 0.99,
        "spx_index_daily_ret": spx_ix,
        "n_days_spx": 4279,
        "n_days_ndx": 4120,
        "window_spx": ["2009-06-25", mark_date],
        "window_ndx": ["2010-02-11", mark_date],
    }


def test_snapshot_today_idempotent_on_date(tmp_path):
    db = str(tmp_path / "tom_idem.db")
    # side_effect (fresh dict each call) — not return_value, which would alias one mutable dict.
    with mock.patch.object(trk, "compute_tom_overlay_state",
                           side_effect=lambda: _fake_state("2026-06-30", in_tom=True,
                               spx_ov=0.011, spx_bh=0.008, ndx_ov=0.025, ndx_bh=0.017, spx_ix=0.008)):
        first = trk.snapshot_today(db_path=db)
        second = trk.snapshot_today(db_path=db)
    assert first["inserted"] == 1
    assert second["inserted"] == 0, "second same-day call must insert 0 rows"
    assert first["rows_logged"] == 1 and second["rows_logged"] == 1


def test_snapshot_cum_compounds_five_streams(tmp_path):
    """Feed 3 synthetic daily rows on 3 distinct dates; each of the 5 cumulative streams
    must equal the product of (1+ret)-1 across the rows it has logged."""
    db = str(tmp_path / "tom_cum.db")
    rows = [
        # (date, spx_ov, spx_bh, ndx_ov, ndx_bh, spx_ix)
        ("2026-06-26", 0.010, 0.008, 0.020, 0.015, 0.006),
        ("2026-06-29", -0.020, -0.015, -0.030, -0.022, -0.012),
        ("2026-06-30", 0.005, 0.004, 0.011, 0.008, 0.003),
    ]
    for d, so, sb, no_, nb, si in rows:
        st = _fake_state(d, in_tom=(so > 0), spx_ov=so, spx_bh=sb, ndx_ov=no_, ndx_bh=nb, spx_ix=si)
        with mock.patch.object(trk, "compute_tom_overlay_state", return_value=st):
            trk.snapshot_today(db_path=db)

    def cumret(vals):
        p = 1.0
        for v in vals:
            p *= (1.0 + v)
        return p - 1.0

    exp = {
        "cum_spx_overlay_since_start": cumret([r[1] for r in rows]),
        "cum_spx_bh_since_start": cumret([r[2] for r in rows]),
        "cum_ndx_overlay_since_start": cumret([r[3] for r in rows]),
        "cum_ndx_bh_since_start": cumret([r[4] for r in rows]),
        "cum_spx_index_since_start": cumret([r[5] for r in rows]),
    }
    conn = sqlite3.connect(db)
    last = conn.execute(
        "SELECT cum_spx_overlay_since_start, cum_spx_bh_since_start, "
        "cum_ndx_overlay_since_start, cum_ndx_bh_since_start, cum_spx_index_since_start "
        "FROM daily_snapshots ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert abs(last[0] - exp["cum_spx_overlay_since_start"]) < 1e-12
    assert abs(last[1] - exp["cum_spx_bh_since_start"]) < 1e-12
    assert abs(last[2] - exp["cum_ndx_overlay_since_start"]) < 1e-12
    assert abs(last[3] - exp["cum_ndx_bh_since_start"]) < 1e-12
    assert abs(last[4] - exp["cum_spx_index_since_start"]) < 1e-12


def test_paper_clock_stats_reports_per_book_gap_and_engage_rate(tmp_path):
    """paper_clock_stats returns per-book overlay/B&H cum + the raw-return gap, a forward
    Sharpe on each overlay stream, and how often the TOM window engaged."""
    db = str(tmp_path / "tom_stats.db")
    rows = [
        ("2026-06-26", 0.010, 0.008, 0.020, 0.015, 0.006, 1),
        ("2026-06-29", -0.020, -0.015, -0.030, -0.022, -0.012, 0),
        ("2026-06-30", 0.005, 0.004, 0.011, 0.008, 0.003, 1),
    ]
    for d, so, sb, no_, nb, si, tom in rows:
        st = _fake_state(d, in_tom=bool(tom), spx_ov=so, spx_bh=sb, ndx_ov=no_, ndx_bh=nb, spx_ix=si)
        with mock.patch.object(trk, "compute_tom_overlay_state", return_value=st):
            trk.snapshot_today(db_path=db)

    stats = trk.paper_clock_stats(db_path=db)
    assert stats["n_days"] == 3
    assert stats["start_date"] == "2026-06-26"
    # TOM engaged 2 of 3 days
    assert stats["tom_window_days"] == 2
    assert abs(stats["tom_window_pct"] - (2 / 3 * 100)) < 1e-3
    # per-book gap = overlay_cum - bh_cum, present and finite for both books
    for book in ("spx_book", "ndx_book"):
        b = stats[book]
        assert abs(b["overlay_vs_bh_pp"] - (b["overlay_cum_pct"] - b["bh_cum_pct"])) < 1e-6
        assert "overlay_sharpe_since_start" in b
    assert "spx_index_cum_pct" in stats


def test_paper_clock_stats_empty(tmp_path):
    db = str(tmp_path / "tom_empty.db")
    trk._get_conn(db).close()
    stats = trk.paper_clock_stats(db_path=db)
    assert stats["n_days"] == 0


# --------------------------------------------------------------------------- #
# 4. Staleness guard — mirrors the crash_sleeve staleness test verbatim.
# --------------------------------------------------------------------------- #
CAL = [
    "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18",
    "2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25",
]


def _make_stale_db(tmp_path, dates):
    db = str(tmp_path / "tom_stale.db")
    conn = trk._get_conn(db)
    for d in dates:
        conn.execute(
            "INSERT INTO daily_snapshots (date, in_tom_window, "
            "spx_overlay_daily_ret, cum_spx_overlay_since_start, "
            "spx_bh_daily_ret, cum_spx_bh_since_start, "
            "ndx_overlay_daily_ret, cum_ndx_overlay_since_start, "
            "ndx_bh_daily_ret, cum_ndx_bh_since_start, "
            "spx_index_daily_ret, cum_spx_index_since_start, "
            "spx_overlay_full_sharpe, ndx_overlay_full_sharpe, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d, 0, 0.001, 0.001, 0.001, 0.001, 0.002, 0.002, 0.002, 0.002,
             0.001, 0.001, 0.9, 0.99, "x"),
        )
    conn.commit()
    conn.close()
    return db


@pytest.fixture(autouse=True)
def _patch_calendar(monkeypatch):
    monkeypatch.setattr(trk, "_spx_trading_dates", lambda: list(CAL))


def test_stale_current_zero_behind(tmp_path):
    db = _make_stale_db(tmp_path, CAL)
    st = trk.clock_staleness(db_path=db)
    assert st["last_logged"] == "2026-06-25"
    assert st["latest_closed_bar"] == "2026-06-25"
    assert st["trading_days_behind"] == 0
    assert st["stale"] is False


def test_stale_one_behind_not_stale(tmp_path):
    db = _make_stale_db(tmp_path, CAL[:-1])
    st = trk.clock_staleness(db_path=db)
    assert st["trading_days_behind"] == 1
    assert st["stale"] is False
    assert "self-heals" in st["note"]


def test_stale_two_behind_is_stale(tmp_path):
    db = _make_stale_db(tmp_path, CAL[:-2])
    st = trk.clock_staleness(db_path=db)
    assert st["trading_days_behind"] == 2
    assert st["stale"] is True
    assert "STALE" in st["note"]


def test_stale_empty_db_not_started(tmp_path):
    db = _make_stale_db(tmp_path, [])
    st = trk.clock_staleness(db_path=db)
    assert st["last_logged"] is None
    assert st["trading_days_behind"] is None
    assert st["stale"] is False
    assert "not started" in st["note"]


def test_stale_unreadable_calendar(tmp_path, monkeypatch):
    monkeypatch.setattr(trk, "_spx_trading_dates", lambda: [])
    db = _make_stale_db(tmp_path, CAL)
    st = trk.clock_staleness(db_path=db)
    assert st["latest_closed_bar"] is None
    assert st["trading_days_behind"] is None
    assert st["stale"] is False
    assert "cannot assess" in st["note"]
