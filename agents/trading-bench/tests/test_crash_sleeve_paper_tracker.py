"""Unit tests for runner/crash_sleeve_paper_tracker.py — the REGIME-GATED crash-
insurance 3rd-sleeve PAPER CLOCK.

These tests pin the make-or-break properties of the tracker WITHOUT touching the
live build_sleeves() engine (no network, no heavy run) — they exercise only the
PURE helpers, exactly like the allocator/staleness tracker tests:

  * the PAST-ONLY regime gate (a deep drop at index t must NOT flip the flag at any
    month-open <= t; it may only flip at the first month-open AFTER the drawdown is
    visible through idx-1)
  * the gated target-weight function: weights sum to 1 in both regime states; the
    hedge weight is exactly 0.0 when OFF and 0.15*… when ON; the two risk sleeves
    keep their inv-vol RATIO when the hedge engages
  * snapshot_today idempotency on date (second same-day call inserts 0 rows)
  * 3-stream cum-since-start compounding (gated / baseline / spx)
  * the staleness guard (trading_days_behind / stale), mirroring the allocator
    staleness test fixtures verbatim

Deterministic + offline by construction. The one heavy path (compute_*_state, which
calls the live engine over network) is intentionally NOT unit-tested here — mirrors
the allocator/polymarket tracker test convention of only testing the pure logic.
"""
from __future__ import annotations

import importlib
import sqlite3
from unittest import mock

import pytest

trk = importlib.import_module("runner.crash_sleeve_paper_tracker")


# --------------------------------------------------------------------------- #
# 1. Regime gate is PAST-ONLY (the make-or-break — no same-bar peeking).
# --------------------------------------------------------------------------- #
def test_regime_flags_past_only_deep_drop_does_not_flip_same_bar():
    """A deep one-bar drop at index t must NOT turn the regime flag ON at index t
    (the drawdown is only visible through idx-1). The flag may only flip ON at
    indices STRICTLY AFTER the drop becomes past-visible."""
    # Flat for a while, then a single -20% crash bar at index 10, then flat.
    n = 20
    spx_r = [0.0] * n
    spx_r[10] = -0.20  # the crash happens AT index 10

    flags = trk._build_regime_flags(spx_r, trk.DD_TRIGGER_PCT)  # threshold -0.10

    # At/before the crash bar, the running peak->price drawdown through idx-1 has NOT
    # yet seen the drop, so the flag is OFF at every index <= 10.
    for idx in range(0, 11):
        assert flags[idx] is False, "flag must be OFF at idx=%d (drop not yet past-visible)" % idx

    # At idx=11 the cut index (idx-1=10) finally sees the -20% bar -> drawdown -20% <= -10% -> ON.
    assert flags[11] is True
    # And it stays ON while price remains >10% below the running peak.
    assert flags[12] is True


def test_regime_flags_past_only_at_month_opens():
    """Stronger statement of the spec: with a deep drop at index t, NO month-open
    index <= t flips the regime flag; only the first month-open AFTER the drawdown
    is visible (through idx-1) flips it."""
    n = 40
    spx_r = [0.0] * n
    drop_at = 20
    spx_r[drop_at] = -0.30
    flags = trk._build_regime_flags(spx_r, trk.DD_TRIGGER_PCT)

    # Pretend month-opens at a handful of indices straddling the drop.
    month_opens = [0, 5, 15, 20, 21, 30]
    for mo in month_opens:
        if mo <= drop_at:
            assert flags[mo] is False, "month-open %d <= drop %d must be OFF" % (mo, drop_at)
        else:
            assert flags[mo] is True, "month-open %d > drop %d must be ON" % (mo, drop_at)


def test_regime_flags_extra_lag_shifts_one_more_bar():
    """The +1-bar canary semantics: with extra_lag=1 the flag flips one bar LATER
    than same-bar, never earlier (proves strictly-past, lag-robust)."""
    n = 20
    spx_r = [0.0] * n
    spx_r[10] = -0.25
    f0 = trk._build_regime_flags(spx_r, trk.DD_TRIGGER_PCT, extra_lag=0)
    f1 = trk._build_regime_flags(spx_r, trk.DD_TRIGGER_PCT, extra_lag=1)
    # same-bar flips ON at idx 11; lag+1 flips ON at idx 12 (one later, never earlier).
    assert f0[11] is True and f0[10] is False
    assert f1[11] is False and f1[12] is True


def test_regime_flags_shallow_drop_below_threshold_stays_off():
    """A drawdown shallower than the -10% trigger never engages."""
    n = 20
    spx_r = [0.0] * n
    spx_r[10] = -0.05  # only -5%, above the -10% trigger
    flags = trk._build_regime_flags(spx_r, trk.DD_TRIGGER_PCT)
    assert not any(flags), "a -5% drawdown must never trip the -10% gate"


# --------------------------------------------------------------------------- #
# 2. Gated target-weight function: sums to 1; hedge 0 when OFF / 0.15 when ON;
#    risk sleeves keep their inv-vol ratio.
# --------------------------------------------------------------------------- #
def _ratio(a, b):
    return a / b if b else float("inf")


def test_gated_weights_off_sum_to_one_hedge_zero():
    """Regime OFF -> [b0, b1, 0.0], sums to 1, hedge exactly 0."""
    n = 100
    # give the two sleeves different vols so base weights are non-trivial
    tqqq_r = [0.02 if i % 2 == 0 else -0.02 for i in range(n)]   # higher vol
    rot_r = [0.005 if i % 2 == 0 else -0.005 for i in range(n)]  # lower vol
    flags = [False] * n
    wfn = trk._make_gated_wfn(tqqq_r, rot_r, flags, trk.HEDGE_WEIGHT)
    idx = 80
    w = wfn(idx)
    assert len(w) == 3
    assert abs(sum(w) - 1.0) < 1e-12
    assert w[2] == 0.0, "hedge weight must be exactly 0 when regime OFF"
    assert w[0] > 0 and w[1] > 0


def test_gated_weights_on_hedge_exactly_15pct_and_ratio_preserved():
    """Regime ON -> [b0*(1-wh), b1*(1-wh), wh]; sums to 1; hedge == 0.15;
    and the two risk sleeves keep their OFF-state inv-vol ratio exactly."""
    n = 100
    tqqq_r = [0.02 if i % 2 == 0 else -0.02 for i in range(n)]
    rot_r = [0.005 if i % 2 == 0 else -0.005 for i in range(n)]
    flags_off = [False] * n
    flags_on = [True] * n
    idx = 80
    w_off = trk._make_gated_wfn(tqqq_r, rot_r, flags_off, trk.HEDGE_WEIGHT)(idx)
    w_on = trk._make_gated_wfn(tqqq_r, rot_r, flags_on, trk.HEDGE_WEIGHT)(idx)

    # hedge engaged at EXACTLY the configured weight
    assert abs(w_on[2] - trk.HEDGE_WEIGHT) < 1e-12
    assert abs(trk.HEDGE_WEIGHT - 0.15) < 1e-12  # the conservative wh15 config
    # sums to 1
    assert abs(sum(w_on) - 1.0) < 1e-12
    # each risk sleeve is exactly base*(1-wh)
    assert abs(w_on[0] - w_off[0] * (1.0 - trk.HEDGE_WEIGHT)) < 1e-12
    assert abs(w_on[1] - w_off[1] * (1.0 - trk.HEDGE_WEIGHT)) < 1e-12
    # and the inv-vol RATIO between the two risk sleeves is preserved
    assert abs(_ratio(w_on[0], w_on[1]) - _ratio(w_off[0], w_off[1])) < 1e-9


def test_gated_weights_degenerate_early_index():
    """idx < 2 falls back to the 50/50 base; still sums to 1 in both states."""
    tqqq_r = [0.01, 0.01, 0.01]
    rot_r = [0.01, 0.01, 0.01]
    w_off = trk._make_gated_wfn(tqqq_r, rot_r, [False, False, False], trk.HEDGE_WEIGHT)(1)
    w_on = trk._make_gated_wfn(tqqq_r, rot_r, [True, True, True], trk.HEDGE_WEIGHT)(1)
    assert abs(sum(w_off) - 1.0) < 1e-12
    assert abs(sum(w_on) - 1.0) < 1e-12
    assert w_off == [0.5, 0.5, 0.0]
    assert abs(w_on[2] - trk.HEDGE_WEIGHT) < 1e-12


# --------------------------------------------------------------------------- #
# 3. snapshot_today idempotency + 3-stream cum compounding.
# --------------------------------------------------------------------------- #
def _fake_state(mark_date, regime_on, dd_pct, gated_ret, baseline_ret, spx_ret):
    """A compute_crash_sleeve_state() return shaped exactly like the real one."""
    return {
        "mark_date": mark_date,
        "regime_on": regime_on,
        "trailing_dd_pct": dd_pct,
        "w_tqqq": 0.40, "w_rot": 0.45, "w_hedge": (trk.HEDGE_WEIGHT if regime_on else 0.0),
        "gated_daily_ret": gated_ret,
        "baseline_daily_ret": baseline_ret,
        "spx_daily_ret": spx_ret,
        "engine_full_sharpe": 1.0,
        "n_days": 100,
        "window": ["2010-02-12", mark_date],
    }


def test_snapshot_today_idempotent_on_date(tmp_path):
    db = str(tmp_path / "crash_idem.db")
    # NOTE: compute_crash_sleeve_state returns a FRESH dict each real call; mirror that
    # with side_effect (not return_value, which would alias one mutable dict across both
    # calls and let the 2nd call's mutation clobber the 1st return's inserted flag).
    with mock.patch.object(trk, "compute_crash_sleeve_state",
                           side_effect=lambda: _fake_state("2026-06-30", regime_on=0,
                               dd_pct=-0.02, gated_ret=0.01, baseline_ret=0.012, spx_ret=0.009)):
        first = trk.snapshot_today(db_path=db)
        second = trk.snapshot_today(db_path=db)
    assert first["inserted"] == 1
    assert second["inserted"] == 0, "second same-day call must insert 0 rows"
    assert first["rows_logged"] == 1 and second["rows_logged"] == 1


def test_snapshot_cum_compounds_three_streams(tmp_path):
    """Feed 3 synthetic daily rows on 3 distinct dates and check each cumulative
    stream equals the product of (1+ret)-1 across the rows it has logged."""
    db = str(tmp_path / "crash_cum.db")
    rows = [
        # (date, gated, baseline, spx)
        ("2026-06-26", 0.010, 0.008, 0.006),
        ("2026-06-29", -0.020, -0.015, -0.012),
        ("2026-06-30", 0.005, 0.004, 0.003),
    ]
    for d, g, b, s in rows:
        st = _fake_state(d, regime_on=(1 if g < 0 else 0), dd_pct=-0.03,
                         gated_ret=g, baseline_ret=b, spx_ret=s)
        with mock.patch.object(trk, "compute_crash_sleeve_state", return_value=st):
            trk.snapshot_today(db_path=db)

    # expected cumulative RETURN (product of growth factors minus 1)
    def cumret(vals):
        p = 1.0
        for v in vals:
            p *= (1.0 + v)
        return p - 1.0

    exp_gated = cumret([g for _, g, _, _ in rows])
    exp_base = cumret([b for _, _, b, _ in rows])
    exp_spx = cumret([s for _, _, _, s in rows])

    conn = sqlite3.connect(db)
    last = conn.execute(
        "SELECT cum_gated_since_start, cum_baseline_since_start, cum_spx_since_start "
        "FROM daily_snapshots ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert abs(last[0] - exp_gated) < 1e-12
    assert abs(last[1] - exp_base) < 1e-12
    assert abs(last[2] - exp_spx) < 1e-12


def test_paper_clock_stats_reports_three_cum_and_engage_rate(tmp_path):
    """paper_clock_stats returns cum for all 3 streams, a forward Sharpe on the
    gated stream, and how often the regime engaged."""
    db = str(tmp_path / "crash_stats.db")
    rows = [
        ("2026-06-26", 0.010, 0.008, 0.006, 0),
        ("2026-06-29", -0.020, -0.015, -0.012, 1),
        ("2026-06-30", 0.005, 0.004, 0.003, 1),
    ]
    for d, g, b, s, on in rows:
        st = _fake_state(d, regime_on=on, dd_pct=-0.11 if on else -0.02,
                         gated_ret=g, baseline_ret=b, spx_ret=s)
        with mock.patch.object(trk, "compute_crash_sleeve_state", return_value=st):
            trk.snapshot_today(db_path=db)

    stats = trk.paper_clock_stats(db_path=db)
    assert stats["n_days"] == 3
    assert stats["start_date"] == "2026-06-26"
    # engaged 2 of 3 days
    assert stats["regime_engaged_days"] == 2
    assert abs(stats["regime_engaged_pct"] - (2 / 3 * 100)) < 1e-3  # impl rounds to 4dp
    # all three cum keys present and finite
    for k in ("cum_gated_pct", "cum_baseline_pct", "cum_spx_pct"):
        assert k in stats and isinstance(stats[k], float)
    assert "sharpe_since_start" in stats


def test_paper_clock_stats_empty(tmp_path):
    db = str(tmp_path / "crash_empty.db")
    # touch the schema then read with no rows
    trk._get_conn(db).close()
    stats = trk.paper_clock_stats(db_path=db)
    assert stats["n_days"] == 0


# --------------------------------------------------------------------------- #
# 4. Staleness guard — mirrors the allocator staleness test verbatim.
# --------------------------------------------------------------------------- #
CAL = [
    "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18",
    "2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25",
]


def _make_stale_db(tmp_path, dates):
    db = str(tmp_path / "crash_stale.db")
    conn = trk._get_conn(db)
    for d in dates:
        conn.execute(
            "INSERT INTO daily_snapshots (date, regime_on, trailing_dd_pct, w_tqqq, "
            "w_rot, w_hedge, gated_daily_ret, cum_gated_since_start, baseline_daily_ret, "
            "cum_baseline_since_start, spx_daily_ret, cum_spx_since_start, "
            "engine_full_sharpe, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d, 0, -0.02, 0.44, 0.56, 0.0, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 1.0, "x"),
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


def test_stale_holiday_gap_excluded(tmp_path):
    db = _make_stale_db(tmp_path, ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18"])
    st = trk.clock_staleness(db_path=db)
    assert st["trading_days_behind"] == 4  # 22,23,24,25 — Juneteenth 06-19 excluded
    assert st["stale"] is True


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
