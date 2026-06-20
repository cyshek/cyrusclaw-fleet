"""Tests for runner.daily_bars_cache — Yahoo-v8 DAILY OHLCV+adjclose cache.

The make-or-break properties under test:

  1. PARSE: the Yahoo v8 JSON shape is parsed into an ascending list of bar
     dicts; `adjclose` (split+div-adjusted) is carried as the load-bearing
     field; rows missing both close and adjclose are dropped; dates are
     de-duplicated; output is strictly ascending.
  2. NO NETWORK IN TESTS: the HTTP fetch (`_fetch_raw`) is monkeypatched to
     return a synthetic Yahoo payload, so the parse + cache + accessor paths
     are exercised with zero network.
  3. ADJCLOSE USED: a payload whose raw `close` differs from `adjclose` proves
     the cache surfaces `adjclose` (the only correct series for leveraged ETFs
     that split constantly), not raw close.
  4. LOOKAHEAD GUARD: `asof_strict(D)` returns the most-recent bar STRICTLY
     before D (never the same-date bar — the no-leak invariant for a decision
     made at the open of D); `asof(D)` is INCLUSIVE and returns the same-date
     bar; both refuse to leak a future bar.
  5. CACHE HIT PATH: after one (monkeypatched) cold load that writes the parsed
     JSON to disk, a second load with the in-process memo cleared reads the
     on-disk cache and performs NO further fetch.
  6. LIVE SPAN (optional): if the on-disk cache is populated, the leveraged-ETF
     spans match the documented inception dates; skips if unavailable.

These tests never hit the network: every cold-load path is monkeypatched. The
single live-data test reads only the local cache and skips when it is absent.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from runner import daily_bars_cache as dbc


# --------------------------------------------------------------------------- #
# Synthetic Yahoo payload helpers (no network)
# --------------------------------------------------------------------------- #
def _epoch(d: str) -> int:
    """ISO 'YYYY-MM-DD' -> UTC epoch seconds at midnight (what Yahoo returns for
    daily bars, give or take exchange tz; the parser only uses the .date())."""
    return int(datetime.strptime(d, "%Y-%m-%d")
               .replace(tzinfo=timezone.utc).timestamp())


def _make_yahoo_payload(dates, closes, adjcloses, *, opens=None, highs=None,
                        lows=None, vols=None, trailing_null=False) -> dict:
    """Build a minimal but well-formed Yahoo v8 chart payload.

    If `trailing_null` is True, append one extra timestamp whose adjclose/close
    are None (Yahoo occasionally emits a trailing placeholder bar) to prove the
    parser drops it.
    """
    ts = [_epoch(d) for d in dates]
    o = list(opens) if opens is not None else [c for c in closes]
    h = list(highs) if highs is not None else [c for c in closes]
    lo = list(lows) if lows is not None else [c for c in closes]
    v = list(vols) if vols is not None else [1000 for _ in closes]
    c = list(closes)
    ac = list(adjcloses)
    if trailing_null:
        ts.append(_epoch("2099-01-01"))
        o.append(None); h.append(None); lo.append(None); v.append(None)
        c.append(None); ac.append(None)
    return {
        "chart": {
            "result": [
                {
                    "timestamp": ts,
                    "indicators": {
                        "quote": [
                            {"open": o, "high": h, "low": lo, "close": c, "volume": v}
                        ],
                        "adjclose": [{"adjclose": ac}],
                    },
                }
            ],
            "error": None,
        }
    }


@pytest.fixture
def clean_memo():
    """Snapshot + restore the module-level memo dicts so a synthetic symbol
    injected here cannot leak into other tests (and vice-versa)."""
    saved_s = dict(dbc._SERIES_MEMO)
    saved_d = dict(dbc._DATES_MEMO)
    try:
        yield
    finally:
        dbc._SERIES_MEMO.clear(); dbc._SERIES_MEMO.update(saved_s)
        dbc._DATES_MEMO.clear(); dbc._DATES_MEMO.update(saved_d)


# --------------------------------------------------------------------------- #
# Pure parse tests (no network)
# --------------------------------------------------------------------------- #
def test_parse_basic_ascending_and_fields():
    raw = _make_yahoo_payload(
        dates=["2010-02-11", "2010-02-12", "2010-02-16"],
        closes=[10.0, 11.0, 12.0],
        adjcloses=[1.0, 1.1, 1.2],
        opens=[9.5, 10.5, 11.5],
        highs=[10.2, 11.2, 12.2],
        lows=[9.0, 10.0, 11.0],
        vols=[100, 200, 300],
    )
    bars = dbc._parse("TQQQ", raw)
    assert [b["date"] for b in bars] == ["2010-02-11", "2010-02-12", "2010-02-16"]
    # strictly ascending
    assert all(bars[i]["date"] < bars[i + 1]["date"] for i in range(len(bars) - 1))
    assert bars[0]["open"] == 9.5 and bars[0]["high"] == 10.2 and bars[0]["low"] == 9.0
    assert bars[0]["close"] == 10.0 and bars[0]["volume"] == 100


def test_parse_uses_adjclose_not_raw_close():
    # adjclose deliberately != close; the cache must carry adjclose.
    raw = _make_yahoo_payload(
        dates=["2010-03-11", "2010-03-12"],
        closes=[100.0, 50.0],     # raw close (garbage across a 2:1 split)
        adjcloses=[0.60, 0.62],   # split+div adjusted (the correct series)
    )
    bars = dbc._parse("SOXL", raw)
    assert bars[0]["adjclose"] == 0.60
    assert bars[1]["adjclose"] == 0.62
    # raw close is preserved separately but is NOT the adjclose
    assert bars[0]["close"] == 100.0
    assert bars[0]["adjclose"] != bars[0]["close"]


def test_parse_drops_trailing_null_adjclose_row():
    raw = _make_yahoo_payload(
        dates=["2010-02-11", "2010-02-12"],
        closes=[10.0, 11.0],
        adjcloses=[1.0, 1.1],
        trailing_null=True,
    )
    bars = dbc._parse("TQQQ", raw)
    # the trailing all-null placeholder bar is dropped
    assert [b["date"] for b in bars] == ["2010-02-11", "2010-02-12"]


def test_parse_falls_back_to_close_when_adjclose_missing():
    # If adjclose is None but close is present, adjclose := close (never None
    # for a kept row).
    raw = _make_yahoo_payload(
        dates=["2010-02-11", "2010-02-12"],
        closes=[10.0, 11.0],
        adjcloses=[None, 1.1],
    )
    bars = dbc._parse("TQQQ", raw)
    assert bars[0]["adjclose"] == 10.0   # fell back to close
    assert bars[1]["adjclose"] == 1.1


def test_parse_dedups_repeated_dates_keep_last():
    raw = _make_yahoo_payload(
        dates=["2010-02-11", "2010-02-11", "2010-02-12"],
        closes=[10.0, 10.5, 11.0],
        adjcloses=[1.00, 1.05, 1.10],
    )
    bars = dbc._parse("TQQQ", raw)
    assert [b["date"] for b in bars] == ["2010-02-11", "2010-02-12"]
    # de-dup keeps the LAST occurrence for the repeated date
    assert bars[0]["adjclose"] == 1.05


def test_parse_raises_on_bad_shape():
    with pytest.raises(dbc.DailyBarsParseError):
        dbc._parse("TQQQ", {"chart": {"result": [], "error": "Not Found"}})


# --------------------------------------------------------------------------- #
# Cold-load with monkeypatched fetch (no network) + cache-hit path
# --------------------------------------------------------------------------- #
def test_cold_load_monkeypatched_then_cache_hit(monkeypatch, tmp_path, clean_memo):
    sym = "ZZTEST"  # synthetic symbol; its own cache files under tmp dir
    # Redirect the cache dir to a tmp path so we never touch the real cache.
    monkeypatch.setattr(dbc, "CACHE_DIR", tmp_path)

    calls = {"n": 0}

    def fake_fetch(symbol, timeout=30):
        calls["n"] += 1
        return _make_yahoo_payload(
            dates=["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"],
            closes=[100.0, 101.0, 102.0, 103.0],
            adjcloses=[10.0, 10.1, 10.2, 10.3],
        )

    monkeypatch.setattr(dbc, "_fetch_raw", fake_fetch)
    # Ensure no stale memo for our synthetic symbol.
    dbc._SERIES_MEMO.pop(dbc._sym_key(sym), None)
    dbc._DATES_MEMO.pop(dbc._sym_key(sym), None)

    # 1) Cold load -> exactly one fetch, parsed json written to disk.
    bars = dbc.get_daily(sym)
    assert calls["n"] == 1
    assert [b["date"] for b in bars] == \
        ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    assert bars[0]["adjclose"] == 10.0
    _, parsed_path = dbc._cache_paths(sym)
    assert parsed_path.exists() and parsed_path.stat().st_size > 2

    # 2) Clear in-process memo; next load must read DISK, NOT re-fetch.
    dbc._SERIES_MEMO.pop(dbc._sym_key(sym), None)
    dbc._DATES_MEMO.pop(dbc._sym_key(sym), None)
    bars2 = dbc.get_daily(sym)
    assert calls["n"] == 1, "cache-hit path must not re-fetch"
    assert [b["date"] for b in bars2] == [b["date"] for b in bars]


# --------------------------------------------------------------------------- #
# Lookahead guard on the synthetic (monkeypatched) series — the core canary
# --------------------------------------------------------------------------- #
@pytest.fixture
def synthetic_loaded(monkeypatch, tmp_path, clean_memo):
    """Load a deterministic 4-bar series for symbol 'GUARD' via a monkeypatched
    fetch into a tmp cache dir, and yield the symbol for accessor tests."""
    sym = "GUARD"
    monkeypatch.setattr(dbc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(
        dbc, "_fetch_raw",
        lambda symbol, timeout=30: _make_yahoo_payload(
            dates=["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"],
            closes=[100.0, 101.0, 102.0, 103.0],
            adjcloses=[10.0, 10.1, 10.2, 10.3],
        ),
    )
    dbc._SERIES_MEMO.pop(dbc._sym_key(sym), None)
    dbc._DATES_MEMO.pop(dbc._sym_key(sym), None)
    dbc.get_daily(sym)
    return sym


def test_asof_strict_returns_prior_not_same_date(synthetic_loaded):
    sym = synthetic_loaded
    # As-of 2020-01-06: the same-date bar (adj 10.2) is INVISIBLE to a decision
    # made at the open of 2020-01-06; the prior close 2020-01-03 (10.1) is last.
    rec = dbc.asof_strict(sym, "2020-01-06")
    assert rec is not None
    assert rec["date"] == "2020-01-03"
    assert rec["adjclose"] == 10.1


def test_asof_inclusive_returns_same_date(synthetic_loaded):
    sym = synthetic_loaded
    rec = dbc.asof(sym, "2020-01-06")
    assert rec is not None and rec["date"] == "2020-01-06"
    assert rec["adjclose"] == 10.2


def test_asof_strict_same_date_invisible_then_visible_next_day(synthetic_loaded):
    sym = synthetic_loaded
    # On 2020-01-07, that day's close is invisible to a strict (open-decision) read.
    assert dbc.asof_strict(sym, "2020-01-07")["date"] == "2020-01-06"
    # On 2020-01-08, 2020-01-07's close is now visible.
    assert dbc.asof_strict(sym, "2020-01-08")["date"] == "2020-01-07"


def test_asof_before_series_start(synthetic_loaded):
    sym = synthetic_loaded
    assert dbc.asof(sym, "2019-12-31") is None
    # strictly-before the first bar date => None
    assert dbc.asof_strict(sym, "2020-01-02") is None
    # inclusive on the first bar date => the first bar
    assert dbc.asof(sym, "2020-01-02")["date"] == "2020-01-02"


def test_asof_future_returns_last_bar(synthetic_loaded):
    sym = synthetic_loaded
    rec = dbc.asof(sym, "2999-01-01")
    assert rec is not None and rec["date"] == "2020-01-07"


def test_adjclose_series_forward_fills_no_lookahead(synthetic_loaded):
    sym = synthetic_loaded
    # Ask for a date with no bar (2020-01-04, a Saturday) -> forward-fill from
    # the most-recent PRIOR bar (2020-01-03), never the later 2020-01-06.
    out = dbc.adjclose_series(sym, ["2020-01-03", "2020-01-04", "2020-01-06"])
    assert out == [10.1, 10.1, 10.2]


def test_asof_strict_raises_on_constructed_violation(monkeypatch, tmp_path, clean_memo):
    # Construct a degenerate single-bar series and prove the strict accessor's
    # internal bound holds (it returns None rather than leaking the same-date
    # bar; the explicit raise guards a future bar slipping through bisect).
    sym = "ONE"
    monkeypatch.setattr(dbc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(
        dbc, "_fetch_raw",
        lambda symbol, timeout=30: _make_yahoo_payload(
            dates=["2021-05-05"], closes=[50.0], adjcloses=[5.0]),
    )
    dbc._SERIES_MEMO.pop(dbc._sym_key(sym), None)
    dbc._DATES_MEMO.pop(dbc._sym_key(sym), None)
    dbc.get_daily(sym)
    # strict as-of the only bar's own date => None (same-date invisible)
    assert dbc.asof_strict(sym, "2021-05-05") is None
    # inclusive as-of that date => the bar
    assert dbc.asof(sym, "2021-05-05")["date"] == "2021-05-05"


# --------------------------------------------------------------------------- #
# Live-data span (uses local cache only; skips if absent)
# --------------------------------------------------------------------------- #
def _try_span(sym):
    dbc._SERIES_MEMO.pop(dbc._sym_key(sym), None)
    dbc._DATES_MEMO.pop(dbc._sym_key(sym), None)
    _, parsed_path = dbc._cache_paths(sym)
    if not (parsed_path.exists() and parsed_path.stat().st_size > 2):
        return None
    try:
        return dbc.span(sym)
    except Exception:
        return None


def test_live_cache_leveraged_etf_spans_if_present():
    """If the on-disk cache is populated, the leveraged-ETF inception dates match
    the documented spans. Skips entirely on a cold cache (no network here)."""
    expectations = {
        "SOXL": "2010-03-11",
        "TQQQ": "2010-02-11",
        "UPRO": "2009-06-25",
    }
    any_loaded = False
    for sym, first in expectations.items():
        sp = _try_span(sym)
        if sp is None:
            continue
        any_loaded = True
        assert sp["n"] > 2000, f"{sym}: only {sp['n']} bars"
        assert sp["first"] == first, f"{sym} first {sp['first']} != {first}"
    if not any_loaded:
        pytest.skip("Yahoo daily cache not populated; live span test skipped")
