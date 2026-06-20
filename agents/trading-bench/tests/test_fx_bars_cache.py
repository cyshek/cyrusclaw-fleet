"""Tests for runner.fx_bars_cache — the lookahead-safe Yahoo FX-majors adapter.

Locks the REAL contracts of the adapter, not trivia:
  (1) asof / asof_strict point-in-time semantics (inclusive vs strictly-before),
  (2) THE LOOKAHEAD GUARD: a FUTURE bar appended after a date cannot change the
      as-of value at that date (the make-or-break property),
  (3) the asof accessors raise rather than silently leak a future bar,
  (4) close_series forward-fills WITHOUT looking ahead,
  (5) FX invariant: adjclose == close (no splits/divs),
  (6) the live disk cache for EURUSD=X really is 5843 bars 2003-12-01..2026-06-09
      (a thin integration check that the cached data matches the lane's claims).

No network for the unit tests: a fake in-memory series is injected by swapping
the module's memo dicts (mirrors the monkeypatch-cache style in
tests/test_daily_bars_cache.py / tests/test_leveraged_long_trend_voltarget.py).

Run: pytest tests/test_fx_bars_cache.py -q
"""
import json
from pathlib import Path

import pytest

from runner import fx_bars_cache as fxc


WORKSPACE = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fake-series injection helper
# --------------------------------------------------------------------------- #
def _install_fake(monkeypatch, symbol, rows):
    """Install a fake parsed series for `symbol` directly into the module memos
    so get_daily/asof read it without hitting disk or network. rows: list of
    (date, close)."""
    key = fxc._sym_key(symbol)
    series = [{"date": d, "open": c, "high": c, "low": c,
               "close": c, "adjclose": c, "volume": 0} for d, c in rows]
    monkeypatch.setitem(fxc._SERIES_MEMO, key, series)
    monkeypatch.setitem(fxc._DATES_MEMO, key, [r["date"] for r in series])
    # Also short-circuit get_daily for this symbol so a cache-miss can't refetch.
    real_get = fxc.get_daily

    def fake_get(sym, use_cache=True, refresh=False):
        if fxc._sym_key(sym) == key:
            return series
        return real_get(sym, use_cache=use_cache, refresh=refresh)
    monkeypatch.setattr(fxc, "get_daily", fake_get)
    return series


SAMPLE = [("2020-01-02", 1.10), ("2020-01-03", 1.11), ("2020-01-06", 1.12),
          ("2020-01-07", 1.13), ("2020-01-08", 1.14)]


# --------------------------------------------------------------------------- #
# asof / asof_strict semantics
# --------------------------------------------------------------------------- #
def test_asof_inclusive_returns_same_date_bar(monkeypatch):
    _install_fake(monkeypatch, "EURUSD=X", SAMPLE)
    rec = fxc.asof("EURUSD=X", "2020-01-06")
    assert rec is not None and rec["date"] == "2020-01-06"
    assert rec["close"] == 1.12


def test_asof_strict_excludes_same_date_bar(monkeypatch):
    _install_fake(monkeypatch, "EURUSD=X", SAMPLE)
    rec = fxc.asof_strict("EURUSD=X", "2020-01-06")
    assert rec is not None and rec["date"] == "2020-01-03"  # last STRICTLY before
    assert rec["close"] == 1.11


def test_asof_between_dates_returns_prior(monkeypatch):
    _install_fake(monkeypatch, "EURUSD=X", SAMPLE)
    # 2020-01-04/05 are weekend (no bars); asof should return Friday 01-03.
    rec = fxc.asof("EURUSD=X", "2020-01-05")
    assert rec is not None and rec["date"] == "2020-01-03"


def test_asof_before_first_bar_is_none(monkeypatch):
    _install_fake(monkeypatch, "EURUSD=X", SAMPLE)
    assert fxc.asof("EURUSD=X", "2019-12-31") is None
    assert fxc.asof_strict("EURUSD=X", "2020-01-02") is None  # nothing strictly before


def test_asof_far_future_returns_last_bar(monkeypatch):
    _install_fake(monkeypatch, "EURUSD=X", SAMPLE)
    rec = fxc.asof("EURUSD=X", "2999-01-01")
    assert rec is not None and rec["date"] == "2020-01-08"


# --------------------------------------------------------------------------- #
# THE LOOKAHEAD GUARD — appending a future bar cannot change an as-of value
# --------------------------------------------------------------------------- #
def test_future_bar_cannot_change_asof_value(monkeypatch):
    """The defining property: the as-of value at date D must be IDENTICAL whether
    or not bars dated > D exist. We compute asof at a mid date, then append a wild
    future bar and recompute — the value must not move."""
    _install_fake(monkeypatch, "EURUSD=X", SAMPLE)
    before = fxc.asof("EURUSD=X", "2020-01-06")["close"]
    before_strict = fxc.asof_strict("EURUSD=X", "2020-01-06")["close"]

    extended = SAMPLE + [("2020-01-09", 99.0), ("2020-01-10", 0.01)]
    _install_fake(monkeypatch, "EURUSD=X", extended)
    after = fxc.asof("EURUSD=X", "2020-01-06")["close"]
    after_strict = fxc.asof_strict("EURUSD=X", "2020-01-06")["close"]

    assert before == after == 1.12, "future bar leaked into asof()"
    assert before_strict == after_strict == 1.11, "future bar leaked into asof_strict()"


def test_asof_raises_on_constructed_future_leak(monkeypatch):
    """If the dates index is corrupted so a 'most-recent' lookup would return a
    bar dated AFTER the query, the accessor must RAISE FxBarsLookaheadError, not
    silently return the future bar."""
    key = fxc._sym_key("EURUSD=X")
    series = [{"date": "2020-01-02", "open": 1, "high": 1, "low": 1,
               "close": 1.10, "adjclose": 1.10, "volume": 0},
              {"date": "2020-06-01", "open": 1, "high": 1, "low": 1,
               "close": 1.20, "adjclose": 1.20, "volume": 0}]
    monkeypatch.setitem(fxc._SERIES_MEMO, key, series)
    # Corrupt the dates index: claim both bars are <= the query date when the
    # underlying series row is actually the future one.
    monkeypatch.setitem(fxc._DATES_MEMO, key, ["2020-01-02", "2020-01-02"])
    monkeypatch.setattr(fxc, "get_daily", lambda *a, **k: series)
    with pytest.raises(fxc.FxBarsLookaheadError):
        fxc.asof("EURUSD=X", "2020-01-02")


# --------------------------------------------------------------------------- #
# close_series forward-fill (never looks ahead)
# --------------------------------------------------------------------------- #
def test_close_series_forward_fills_without_lookahead(monkeypatch):
    _install_fake(monkeypatch, "EURUSD=X", SAMPLE)
    # request a weekend date that has no bar -> forward-fill from prior close
    dates = ["2020-01-03", "2020-01-04", "2020-01-06"]
    out = fxc.close_series("EURUSD=X", dates)
    assert out == [1.11, 1.11, 1.12]   # 01-04 filled from 01-03, not 01-06


# --------------------------------------------------------------------------- #
# FX invariant: adjclose == close
# --------------------------------------------------------------------------- #
def test_fx_adjclose_equals_close_on_live_cache():
    bars = fxc.get_daily("EURUSD=X")
    assert all(b["adjclose"] == b["close"] for b in bars[:200])


# --------------------------------------------------------------------------- #
# Live disk-cache integration check (the lane's load-bearing claim)
# --------------------------------------------------------------------------- #
def test_live_eurusd_cache_span_matches_lane_claim():
    """The FX lane report claims EURUSD=X is 5843 bars 2003-12-01..2026-06-09.
    This is an integration check against the on-disk parsed cache (no network if
    the cache exists). Skips only if the cache file is entirely absent."""
    parsed = WORKSPACE / "data_cache" / "yahoo_fx" / "EURUSD_X_parsed.json"
    if not parsed.exists():
        pytest.skip("EURUSD parsed cache not present")
    sp = fxc.span("EURUSD=X")
    assert sp["n"] == 5843, f"expected 5843 EURUSD bars, got {sp['n']}"
    assert sp["first"] == "2003-12-01"
    assert sp["last"] == "2026-06-09"


def test_dates_strictly_ascending_on_live_cache():
    bars = fxc.get_daily("USDJPY=X")
    assert all(bars[i]["date"] < bars[i + 1]["date"] for i in range(len(bars) - 1))
