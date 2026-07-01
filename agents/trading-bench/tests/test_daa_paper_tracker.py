"""Unit tests for runner/daa_paper_tracker.py — the Keller/Keuning DAA canary PAPER CLOCK.

These tests pin the make-or-break properties of the tracker WITHOUT touching the heavy
compute_daa_state() engine (no network, no full run_daa) — they exercise only the PURE
helpers + DB layer, exactly like the crash_sleeve / allocator tracker tests:

  * schema columns (the side-DB contract a future session reads)
  * canary regime classification (risk_on / half / crash_off) cascade, incl. undefined->defensive,
    and that it stays VERBATIM-equal to _daa_confirm.run_daa's cascade
  * 13612W calculation correctness (delegates to _daa_confirm._mom_13612w byte-for-byte)
  * lookahead-safe ranking: the current-month signal readout decodes on the PRIOR month-end
    close (cal[mf-1]); a future price move cannot change today's decision
  * defensive-fraction tracking (w_defensive in {0.0, 0.5, 1.0} matched to the regime)
  * FIRST-ROW invariant: equities start at 1.0, daily returns 0.0, but regime/canary/held logged
  * cost accounting: the tracker hands the SAME 2bps one-way the validated engines use
  * snapshot_today idempotency on date (second same-day call inserts 0 rows)
  * 3-stream equity compounding (daa / control / spx) after inception
  * the staleness guard (trading_days_behind / stale), mirroring the crash-sleeve fixtures

Deterministic + offline by construction. The one heavy path (compute_daa_state, which calls the
validated engines over network) is intentionally NOT unit-tested here — mirrors the crash-sleeve /
allocator tracker convention of only testing the pure logic.
"""
from __future__ import annotations

import importlib
import sqlite3
from unittest import mock

import pytest

trk = importlib.import_module("runner.daa_paper_tracker")
daa = importlib.import_module("_daa_confirm")


# --------------------------------------------------------------------------- #
# 1. Schema contract — the side-DB columns a future session relies on.
# --------------------------------------------------------------------------- #
def test_schema_has_required_columns(tmp_path):
    db = str(tmp_path / "daa_schema.db")
    conn = trk._get_conn(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_snapshots)").fetchall()}
    conn.close()
    required = {
        "date", "daa_equity", "control_equity", "spx_equity", "regime", "w_defensive",
        "daa_daily_return", "control_daily_return", "spx_daily_return",
        "canary_vwo_13612w", "canary_bnd_13612w", "top_risk_assets", "defensive_asset",
        "engine_full_sharpe", "created_at",
    }
    missing = required - cols
    assert not missing, "schema missing columns: %s" % sorted(missing)


def test_date_is_unique(tmp_path):
    """`date` must be UNIQUE so a re-run can never duplicate a trading day."""
    db = str(tmp_path / "daa_uniq.db")
    conn = trk._get_conn(db)
    conn.execute("INSERT INTO daily_snapshots (date) VALUES ('2026-06-30')")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO daily_snapshots (date) VALUES ('2026-06-30')")
        conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
# 2. Canary regime classification cascade (risk_on / half / crash_off).
# --------------------------------------------------------------------------- #
def test_classify_both_canaries_positive_is_risk_on():
    assert trk._classify_regime(0.10, 0.05) == (trk.REGIME_RISK_ON, 0.0)


def test_classify_one_canary_positive_is_half():
    assert trk._classify_regime(0.10, -0.05) == (trk.REGIME_HALF, 0.5)
    assert trk._classify_regime(-0.10, 0.05) == (trk.REGIME_HALF, 0.5)


def test_classify_both_canaries_nonpositive_is_crash_off():
    assert trk._classify_regime(-0.10, -0.05) == (trk.REGIME_CRASH_OFF, 1.0)
    # exactly zero is NOT > 0 -> treated as down (matches `cmom > 0.0` in driver)
    assert trk._classify_regime(0.0, 0.0) == (trk.REGIME_CRASH_OFF, 1.0)


def test_classify_undefined_canary_treated_as_defensive():
    """Undefined (None) momentum is treated as <=0 (defensive), VERBATIM to
    _daa_confirm.run_daa's `cmom[c] is not None and cmom[c] > 0.0` guard."""
    assert trk._classify_regime(None, 0.10) == (trk.REGIME_HALF, 0.5)
    assert trk._classify_regime(None, None) == (trk.REGIME_CRASH_OFF, 1.0)
    assert trk._classify_regime(0.10, None) == (trk.REGIME_HALF, 0.5)


def test_classify_matches_daa_confirm_cascade_verbatim():
    """Cross-check the classifier against _daa_confirm.run_daa's exact n_up branch logic
    over a grid of canary scores so the tracker can NEVER drift from the validated cascade."""
    grid = [None, -0.2, -1e-9, 0.0, 1e-9, 0.2]
    for v in grid:
        for b in grid:
            # replicate the driver's branch
            n_up = sum(1 for m in (v, b) if (m is not None and m > 0.0))
            if n_up == 2:
                exp = (trk.REGIME_RISK_ON, 0.0)
            elif n_up == 1:
                exp = (trk.REGIME_HALF, 0.5)
            else:
                exp = (trk.REGIME_CRASH_OFF, 1.0)
            assert trk._classify_regime(v, b) == exp, "mismatch at v=%s b=%s" % (v, b)


def test_w_defensive_matched_to_regime():
    """The defensive fraction is exactly {risk_on:0.0, half:0.5, crash_off:1.0}."""
    assert trk._classify_regime(0.1, 0.1)[1] == 0.0
    assert trk._classify_regime(0.1, -0.1)[1] == 0.5
    assert trk._classify_regime(-0.1, -0.1)[1] == 1.0


# --------------------------------------------------------------------------- #
# 3. 13612W calculation correctness (delegates to _daa_confirm — byte-identical).
# --------------------------------------------------------------------------- #
def _synth_cal_close(symbol, base=100.0, daily_growth=0.0):
    """Build a flat-or-growing synthetic price series over 21*12+5 trading days so the
    13612W (which needs ~21*12 lookback) is computable at the last index."""
    n = 21 * 12 + 5
    # index-stamped strictly-ascending unique dates (boundaries irrelevant for _mom_13612w)
    cal = ["d%04d" % i for i in range(n)]
    px = {cal[i]: base * ((1.0 + daily_growth) ** i) for i in range(n)}
    return cal, {symbol: px}


def test_13612w_matches_daa_confirm_exactly():
    """The tracker's _mom_13612w must equal _daa_confirm._mom_13612w on the same inputs
    (it delegates, so this pins that the delegation is intact)."""
    cal, close = _synth_cal_close("VWO", base=100.0, daily_growth=0.001)
    end_idx = len(cal) - 1
    got = trk._mom_13612w(close, "VWO", cal, end_idx)
    exp = daa._mom_13612w(close, "VWO", cal, end_idx)
    assert got is not None
    assert got == exp


def test_13612w_formula_value_on_known_series():
    """On a series growing at a constant daily rate g, rN = (1+g)^(21*N) - 1; verify the
    13612W weighted blend equals (12*r1 + 4*r3 + 2*r6 + 1*r12)/4."""
    g = 0.0005
    cal, close = _synth_cal_close("BND", base=50.0, daily_growth=g)
    end_idx = len(cal) - 1

    def rN(N):
        return (1.0 + g) ** (21 * N) - 1.0

    exp = (12.0 * rN(1) + 4.0 * rN(3) + 2.0 * rN(6) + 1.0 * rN(12)) / 4.0
    got = trk._mom_13612w(close, "BND", cal, end_idx)
    assert got is not None
    assert abs(got - exp) < 1e-9


def test_13612w_insufficient_history_returns_none():
    """Not enough lookback (< 21*12 bars) -> None (defensive)."""
    cal = ["d%03d" % i for i in range(50)]  # far fewer than 21*12
    close = {"VWO": {d: 100.0 for d in cal}}
    assert trk._mom_13612w(close, "VWO", cal, len(cal) - 1) is None


# --------------------------------------------------------------------------- #
# 4. Lookahead-safe ranking: signal readout decodes on PRIOR month-end (cal[mf-1]);
#    a future price move cannot change today's decision.
# --------------------------------------------------------------------------- #
def _build_monthly_cal(n_months=15, days_per_month=21):
    """A calendar with clean YYYY-MM month boundaries so compute_signal_state can find
    month-firsts. Returns (cal, month_first_indices)."""
    cal = []
    for m in range(n_months):
        ym = "20%02d-%02d" % (20 + m // 12, 1 + m % 12)
        for d in range(days_per_month):
            cal.append("%s-%02d" % (ym, 1 + d))
    mf = []
    seen = set()
    for i, d in enumerate(cal):
        if d[:7] not in seen:
            seen.add(d[:7])
            mf.append(i)
    return cal, mf


def test_signal_decision_uses_prior_month_end_not_future():
    """compute_signal_state reads canary scores at cal[mf-1] (prior month-end). Mutating a
    price STRICTLY AFTER that decision day must NOT change the regime/canary scores."""
    cal, mf = _build_monthly_cal(n_months=15)
    last_mf = mf[-1]
    sig_idx = last_mf - 1

    close = {a: {cal[i]: 100.0 * (1.0 + 0.001 * i) for i in range(len(cal))}
             for a in daa.ALL_TICKERS}

    base = trk.compute_signal_state(cal, close)
    assert base["decision_date"] == cal[sig_idx]

    # Perturb EVERY price strictly AFTER the decision day (indices > sig_idx).
    close2 = {a: dict(close[a]) for a in close}
    for a in close2:
        for i in range(sig_idx + 1, len(cal)):
            close2[a][cal[i]] = close2[a][cal[i]] * 5.0  # huge future spike

    after = trk.compute_signal_state(cal, close2)
    assert after["regime"] == base["regime"], "future move changed the regime -> lookahead leak"
    assert after["canary_vwo_13612w"] == base["canary_vwo_13612w"]
    assert after["canary_bnd_13612w"] == base["canary_bnd_13612w"]
    assert after["decision_date"] == base["decision_date"]


def test_signal_state_decision_date_is_strictly_before_held_month():
    """decision_date (cal[mf-1]) must be in a STRICTLY EARLIER month than the held month
    (cal[mf]) — the leak-free contract."""
    cal, mf = _build_monthly_cal(n_months=15)
    close = {a: {cal[i]: 100.0 * (1.0 + 0.0005 * i) for i in range(len(cal))}
             for a in daa.ALL_TICKERS}
    sig = trk.compute_signal_state(cal, close)
    held_month = cal[mf[-1]][:7]
    decision_month = sig["decision_date"][:7]
    assert decision_month < held_month


def test_signal_state_risk_on_holds_six_legs_no_defensive():
    """When both canaries are up, regime=risk_on, w_defensive=0, top_risk has up to 6 legs,
    defensive_asset is None."""
    cal, mf = _build_monthly_cal(n_months=15)
    close = {a: {cal[i]: 100.0 * (1.0 + 0.001 * i) for i in range(len(cal))}
             for a in daa.ALL_TICKERS}
    sig = trk.compute_signal_state(cal, close)
    assert sig["regime"] == trk.REGIME_RISK_ON
    assert sig["w_defensive"] == 0.0
    assert sig["defensive_asset"] is None
    assert 0 < len(sig["top_risk_assets"]) <= trk.TOP_RISK_FULL


def test_signal_state_crash_off_holds_bond_no_risk():
    """When both canaries are down, regime=crash_off, w_defensive=1.0, top_risk empty,
    defensive_asset set to a bond from {SHY,IEF,LQD}."""
    cal, mf = _build_monthly_cal(n_months=15)
    close = {a: {cal[i]: 200.0 * (1.0 - 0.0008 * i) for i in range(len(cal))}
             for a in daa.ALL_TICKERS}
    sig = trk.compute_signal_state(cal, close)
    assert sig["regime"] == trk.REGIME_CRASH_OFF
    assert sig["w_defensive"] == 1.0
    assert sig["top_risk_assets"] == []
    assert sig["defensive_asset"] in trk.CASH


# --------------------------------------------------------------------------- #
# 5. FIRST-ROW invariant + idempotency + 3-stream compounding + cost constant.
# --------------------------------------------------------------------------- #
def _fake_state(mark_date, regime, daa_ret, control_ret, spx_ret,
                vwo=0.12, bnd=0.03, top=None, bond=None):
    """A compute_daa_state() return shaped exactly like the real one."""
    w_def = {trk.REGIME_RISK_ON: 0.0, trk.REGIME_HALF: 0.5,
             trk.REGIME_CRASH_OFF: 1.0}[regime]
    return {
        "mark_date": mark_date,
        "regime": regime,
        "w_defensive": w_def,
        "canary_vwo_13612w": vwo,
        "canary_bnd_13612w": bnd,
        "top_risk_assets": top if top is not None else ["SPY", "QQQ", "GLD", "TLT", "IWM", "VGK"],
        "defensive_asset": bond,
        "daa_daily_return": daa_ret,
        "control_daily_return": control_ret,
        "spx_daily_return": spx_ret,
        "engine_full_sharpe": 0.8,
        "n_days": 4000,
        "window": ["2007-04-13", mark_date],
    }


def test_first_row_invariant_equities_one_returns_zero_but_regime_logged(tmp_path):
    """On the FIRST run: all three equities == 1.0, all three daily returns == 0.0,
    but regime / canary scores / held assets ARE persisted (so engagement is verifiable)."""
    db = str(tmp_path / "daa_first.db")
    st = _fake_state("2026-06-30", trk.REGIME_RISK_ON, daa_ret=0.02,
                     control_ret=0.015, spx_ret=0.012,
                     top=["SPY", "QQQ", "GLD", "TLT", "IWM", "VGK"], bond=None)
    with mock.patch.object(trk, "compute_daa_state", return_value=st):
        out = trk.snapshot_today(db_path=db)
    assert out["inserted"] == 1
    assert out["is_first_row"] is True
    assert out["daa_equity"] == 1.0 and out["control_equity"] == 1.0 and out["spx_equity"] == 1.0

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM daily_snapshots WHERE date='2026-06-30'").fetchone()
    conn.close()
    # returns zeroed on inception
    assert row["daa_daily_return"] == 0.0
    assert row["control_daily_return"] == 0.0
    assert row["spx_daily_return"] == 0.0
    # but the engagement state is logged
    assert row["regime"] == trk.REGIME_RISK_ON
    assert row["w_defensive"] == 0.0
    assert abs(row["canary_vwo_13612w"] - 0.12) < 1e-12
    assert abs(row["canary_bnd_13612w"] - 0.03) < 1e-12
    import json as _json
    assert _json.loads(row["top_risk_assets"]) == ["SPY", "QQQ", "GLD", "TLT", "IWM", "VGK"]


def test_first_row_crash_off_logs_defensive_asset(tmp_path):
    """First-row invariant also holds in crash_off: equities 1.0, returns 0.0, and the
    defensive_asset (best bond) is persisted with w_defensive=1.0."""
    db = str(tmp_path / "daa_first_crash.db")
    st = _fake_state("2026-06-30", trk.REGIME_CRASH_OFF, daa_ret=-0.03,
                     control_ret=-0.02, spx_ret=-0.025, vwo=-0.2, bnd=-0.1,
                     top=[], bond="IEF")
    with mock.patch.object(trk, "compute_daa_state", return_value=st):
        trk.snapshot_today(db_path=db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM daily_snapshots WHERE date='2026-06-30'").fetchone()
    conn.close()
    assert row["daa_equity"] == 1.0
    assert row["daa_daily_return"] == 0.0  # inception zeroed even though state had -0.03
    assert row["regime"] == trk.REGIME_CRASH_OFF
    assert row["w_defensive"] == 1.0
    assert row["defensive_asset"] == "IEF"


def test_snapshot_today_idempotent_on_date(tmp_path):
    db = str(tmp_path / "daa_idem.db")
    with mock.patch.object(trk, "compute_daa_state",
                           side_effect=lambda: _fake_state("2026-06-30", trk.REGIME_RISK_ON,
                               daa_ret=0.01, control_ret=0.012, spx_ret=0.009)):
        first = trk.snapshot_today(db_path=db)
        second = trk.snapshot_today(db_path=db)
    assert first["inserted"] == 1
    assert second["inserted"] == 0, "second same-day call must insert 0 rows"
    assert first["rows_logged"] == 1 and second["rows_logged"] == 1


def test_three_stream_equity_compounds_after_inception(tmp_path):
    """Feed 3 synthetic daily rows on 3 dates. Inception row = 1.0 / returns 0; subsequent
    rows compound each stream's equity = prior * (1 + daily_ret)."""
    db = str(tmp_path / "daa_cum.db")
    rows = [
        # (date, daa, control, spx)
        ("2026-06-26", 0.010, 0.008, 0.006),   # inception -> forced to 0 / equity 1.0
        ("2026-06-29", -0.020, -0.015, -0.012),
        ("2026-06-30", 0.005, 0.004, 0.003),
    ]
    for d, g, c, s in rows:
        st = _fake_state(d, trk.REGIME_RISK_ON, daa_ret=g, control_ret=c, spx_ret=s)
        with mock.patch.object(trk, "compute_daa_state", return_value=st):
            trk.snapshot_today(db_path=db)

    # inception zeroed -> equity path uses only the LATER two daily returns
    exp_daa = 1.0 * (1.0 - 0.020) * (1.0 + 0.005)
    exp_ctrl = 1.0 * (1.0 - 0.015) * (1.0 + 0.004)
    exp_spx = 1.0 * (1.0 - 0.012) * (1.0 + 0.003)

    conn = sqlite3.connect(db)
    last = conn.execute(
        "SELECT daa_equity, control_equity, spx_equity FROM daily_snapshots "
        "ORDER BY date DESC LIMIT 1").fetchone()
    first = conn.execute(
        "SELECT daa_equity, daa_daily_return FROM daily_snapshots ORDER BY date ASC LIMIT 1"
    ).fetchone()
    conn.close()
    assert first[0] == 1.0 and first[1] == 0.0  # inception row pinned
    assert abs(last[0] - exp_daa) < 1e-12
    assert abs(last[1] - exp_ctrl) < 1e-12
    assert abs(last[2] - exp_spx) < 1e-12


def test_cost_bps_constant_handed_to_engines():
    """Cost accounting: the tracker charges the SAME 2bps one-way the validated engines use
    (it hands COST_BPS straight to run_daa's default + run_sector_rotation). Pin the constant
    so a silent change to the cost model is caught."""
    assert trk.COST_BPS == 2.0
    assert trk.COST_BPS == daa.COST_BPS  # inherited from the validated driver, not re-set


def test_paper_clock_stats_reports_three_cum_and_defensive_rate(tmp_path):
    """paper_clock_stats returns cum for all 3 streams, a forward Sharpe on the DAA stream,
    and how often the canary de-risked (defensive_days / crash_off_days)."""
    db = str(tmp_path / "daa_stats.db")
    rows = [
        ("2026-06-24", 0.010, 0.008, 0.006, trk.REGIME_RISK_ON),    # inception (zeroed)
        ("2026-06-25", -0.020, -0.015, -0.012, trk.REGIME_HALF),    # defensive (half)
        ("2026-06-26", 0.005, 0.004, 0.003, trk.REGIME_CRASH_OFF),  # defensive (crash_off)
    ]
    for d, g, c, s, reg in rows:
        st = _fake_state(d, reg, daa_ret=g, control_ret=c, spx_ret=s,
                         bond=("IEF" if reg != trk.REGIME_RISK_ON else None))
        with mock.patch.object(trk, "compute_daa_state", return_value=st):
            trk.snapshot_today(db_path=db)

    stats = trk.paper_clock_stats(db_path=db)
    assert stats["n_days"] == 3
    assert stats["start_date"] == "2026-06-24"
    # 2 of 3 days are defensive (half + crash_off); 1 of 3 is crash_off
    assert stats["defensive_days"] == 2
    assert stats["crash_off_days"] == 1
    assert abs(stats["defensive_pct"] - (2 / 3 * 100)) < 1e-3
    for k in ("cum_daa_pct", "cum_control_pct", "cum_spx_pct", "daa_vs_control_pp"):
        assert k in stats and isinstance(stats[k], float)
    assert "sharpe_since_start" in stats
    assert stats["current_regime"] == trk.REGIME_CRASH_OFF
    assert stats["current_w_defensive"] == 1.0


def test_paper_clock_stats_empty(tmp_path):
    db = str(tmp_path / "daa_empty.db")
    trk._get_conn(db).close()  # touch the schema, no rows
    stats = trk.paper_clock_stats(db_path=db)
    assert stats["n_days"] == 0


# --------------------------------------------------------------------------- #
# 6. Staleness guard — mirrors the crash-sleeve staleness test verbatim.
# --------------------------------------------------------------------------- #
CAL = [
    "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18",
    "2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25",
]


def _make_stale_db(tmp_path, dates):
    db = str(tmp_path / "daa_stale.db")
    conn = trk._get_conn(db)
    for d in dates:
        conn.execute(
            "INSERT INTO daily_snapshots (date, daa_equity, control_equity, spx_equity, "
            "regime, w_defensive, daa_daily_return, control_daily_return, spx_daily_return, "
            "canary_vwo_13612w, canary_bnd_13612w, top_risk_assets, defensive_asset, "
            "engine_full_sharpe, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d, 1.0, 1.0, 1.0, trk.REGIME_RISK_ON, 0.0, 0.001, 0.001, 0.001,
             0.1, 0.02, "[]", None, 0.8, "x"),
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