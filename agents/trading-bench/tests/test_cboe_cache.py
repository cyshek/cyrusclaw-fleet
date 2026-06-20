"""Tests for runner.cboe_cache — the CBOE VIX-complex point-in-time index cache.

The make-or-break property under test is the LOOKAHEAD GUARD: these are
END-OF-DAY index levels, so the close for trading date D is not known until D's
close. A decision made on date D may therefore use ONLY levels dated < D.
Serving date D's own close to a decision on date D is a silent lookahead leak.
These tests prove:

  1. CSV parse handles BOTH layouts (VIX/VIX3M OHLC; VVIX/SKEW single-value) and
     MM/DD/YYYY dates, producing oldest-first records with a `close` level.
  2. asof() returns the most recent record STRICTLY BEFORE the as-of date and
     NEVER the same-date (or later) record (the no-leak invariant).
  3. On the value-date itself, asof() returns the PRIOR record; only on a LATER
     date does that record become visible.
  4. history_asof() contains only records dated strictly before the as-of date.
  5. The module's bundled selftest_lookahead_guard reports every invariant True.

Tests run against the locally cached CBOE CSVs (data_cache/cboe/), populated on
first run from the CBOE CDN. If the network and cache are both unavailable the
ingest-dependent tests skip rather than fail the suite.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from runner import cboe_cache


# ---------------------------------------------------------------------------
# Pure parse tests (no network) — both CSV layouts + date format
# ---------------------------------------------------------------------------

def test_parse_ohlc_layout():
    text = (
        "DATE,OPEN,HIGH,LOW,CLOSE\n"
        "01/02/1990,17.24,17.24,17.24,17.24\n"
        "01/03/1990,18.19,18.50,18.00,18.19\n"
    )
    rows = cboe_cache._parse_csv_text(text, "VIX")
    assert len(rows) == 2
    assert rows[0]["date"] == "1990-01-02"
    assert rows[0]["close"] == 17.24
    assert rows[1]["open"] == 18.19 and rows[1]["high"] == 18.50
    # oldest-first
    assert rows[0]["date"] < rows[1]["date"]


def test_parse_single_value_layout():
    text = "DATE,SKEW\n01/02/1990,126.09\n01/03/1990,127.50\n"
    rows = cboe_cache._parse_csv_text(text, "SKEW")
    assert len(rows) == 2
    # single-value column is stored as `close` so all callers read .close
    assert rows[0]["close"] == 126.09
    assert "open" not in rows[0]


def test_parse_skips_bad_rows_and_blanks():
    text = (
        "DATE,VVIX\n"
        "03/06/2006,71.73\n"
        "garbage,line,here\n"
        "03/07/2006,\n"            # blank value -> skipped
        "03/08/2006,72.10\n"
    )
    rows = cboe_cache._parse_csv_text(text, "VVIX")
    dates = [r["date"] for r in rows]
    assert dates == ["2006-03-06", "2006-03-08"]


def test_parse_mmddyyyy_and_iso_tolerated():
    assert cboe_cache._parse_mmddyyyy("12/31/2020") == date(2020, 12, 31)
    assert cboe_cache._parse_mmddyyyy("2020-12-31") == date(2020, 12, 31)
    assert cboe_cache._parse_mmddyyyy("not a date") is None


# ---------------------------------------------------------------------------
# Lookahead guard on a SYNTHETIC series (no network) — the core canary
# ---------------------------------------------------------------------------

def _install_synthetic(monkeypatch, idx="VIX"):
    """Inject a tiny deterministic series into the in-process memo so the
    point-in-time accessors run without network/disk.

    IMPORTANT: this mutates module-level memo dicts, which would otherwise
    poison the later live-data tests in the same process. Callers MUST take the
    `synthetic` fixture (below), whose teardown restores the original memo so
    test ORDER cannot leak a 4-row VIX series into the real-ingest assertions.
    """
    series = [
        {"date": "2020-01-02", "close": 14.0},
        {"date": "2020-01-03", "close": 15.0},
        {"date": "2020-01-06", "close": 16.0},
        {"date": "2020-01-07", "close": 17.0},
    ]
    cboe_cache._SERIES_MEMO[idx] = series
    cboe_cache._DATES_MEMO[idx] = [r["date"] for r in series]
    # Make load_series a no-op that returns the injected series.
    monkeypatch.setattr(cboe_cache, "load_series",
                        lambda i, use_cache=True: cboe_cache._SERIES_MEMO[i.upper()])
    return series


@pytest.fixture
def synthetic(monkeypatch):
    """Install the synthetic series and GUARANTEE the module memo is restored
    afterwards, so live-data tests later in the session see the real cache."""
    saved_series = dict(cboe_cache._SERIES_MEMO)
    saved_dates = dict(cboe_cache._DATES_MEMO)
    _install_synthetic(monkeypatch)
    try:
        yield
    finally:
        cboe_cache._SERIES_MEMO.clear()
        cboe_cache._SERIES_MEMO.update(saved_series)
        cboe_cache._DATES_MEMO.clear()
        cboe_cache._DATES_MEMO.update(saved_dates)


def test_asof_returns_strictly_prior_record(synthetic):
    # As-of the value-date 2020-01-06, the SAME-date close (16.0) must NOT be
    # served; the prior record 2020-01-03 (15.0) is the latest usable.
    rec = cboe_cache.asof("VIX", "2020-01-06")
    assert rec is not None
    assert rec["date"] == "2020-01-03"
    assert rec["close"] == 15.0


def test_asof_same_date_invisible_then_visible_next_day(synthetic):
    # On 2020-01-07 the 2020-01-07 close (17.0) is invisible -> get 2020-01-06.
    rec_same = cboe_cache.asof("VIX", "2020-01-07")
    assert rec_same["date"] == "2020-01-06"
    # On 2020-01-08 (a later date), 2020-01-07's close IS now visible.
    rec_next = cboe_cache.asof("VIX", "2020-01-08")
    assert rec_next["date"] == "2020-01-07"
    assert rec_next["close"] == 17.0


def test_asof_before_series_start_returns_none(synthetic):
    assert cboe_cache.asof("VIX", "2019-12-31") is None
    # Exactly the first date: strictly-before => still None.
    assert cboe_cache.asof("VIX", "2020-01-02") is None


def test_history_asof_only_strictly_prior(synthetic):
    hist = cboe_cache.history_asof("VIX", "2020-01-07")
    assert [r["date"] for r in hist] == ["2020-01-02", "2020-01-03", "2020-01-06"]
    assert all(r["date"] < "2020-01-07" for r in hist)
    # lookback trimming
    hist2 = cboe_cache.history_asof("VIX", "2020-01-07", lookback=2)
    assert [r["date"] for r in hist2] == ["2020-01-03", "2020-01-06"]


def test_lookahead_guard_raises_on_violation(synthetic):
    # Directly assert the canary refuses a same-date record.
    bad = {"date": "2020-01-06", "close": 16.0}
    with pytest.raises(cboe_cache.CboeLookaheadError):
        cboe_cache._assert_no_lookahead(bad, "2020-01-06", "VIX")
    # A strictly-prior record passes.
    good = {"date": "2020-01-03", "close": 15.0}
    cboe_cache._assert_no_lookahead(good, "2020-01-06", "VIX")  # no raise


# ---------------------------------------------------------------------------
# Live-data ingest + span (uses CDN/cache; skips if unreachable)
# ---------------------------------------------------------------------------

def _try_load(idx):
    # Defensively evict any in-process memo before loading the REAL cache.
    # Under randomized test order a synthetic-series test may have left a tiny
    # stub in the module memo; clearing it here guarantees these live-data
    # assertions read from the on-disk/CDN cache regardless of order.
    cboe_cache._SERIES_MEMO.pop(idx.upper(), None)
    cboe_cache._DATES_MEMO.pop(idx.upper(), None)
    try:
        return cboe_cache.load_series(idx)
    except Exception:
        return None


def test_ingest_core_indices_have_expected_spans():
    """VIX/SKEW reach 1990, VVIX 2006, VIX3M 2009-09; current to ~T-1."""
    expectations = {
        "VIX": "1990-01-02",
        "SKEW": "1990-01-02",
        "VVIX": "2006-03-06",
        "VIX3M": "2009-09-18",
    }
    any_loaded = False
    for idx, first in expectations.items():
        s = _try_load(idx)
        if s is None:
            continue
        any_loaded = True
        assert len(s) > 1000, f"{idx}: only {len(s)} rows"
        assert s[0]["date"] == first, f"{idx} first {s[0]['date']} != {first}"
        # All closes positive and finite.
        assert all(r["close"] is not None and r["close"] > 0 for r in s[:50])
    if not any_loaded:
        pytest.skip("CBOE CDN + cache both unavailable; ingest test skipped")


def test_selftest_lookahead_guard_passes_on_real_data():
    s = _try_load("VIX")
    if s is None:
        pytest.skip("CBOE data unavailable")
    out = cboe_cache.selftest_lookahead_guard("VIX")
    bool_checks = {k: v for k, v in out.items() if isinstance(v, bool)}
    assert bool_checks, f"selftest returned no boolean checks: {out}"
    failed = {k: v for k, v in bool_checks.items() if v is not True}
    assert not failed, f"cboe_cache lookahead selftest failed: {failed} (full: {out})"
    for key in ("asof_target_returns_prev", "asof_target_strictly_before",
                "history_newest_before_target"):
        assert out.get(key) is True, f"missing/false invariant {key!r}: {out}"
