"""Tests for the CREDIT-STRESS data adapter (strategies_candidates/credit_stress/
credit_data.py).

Locks the make-or-break CORRECTNESS contracts of the lane's feature layer:

  (1) DailySeries.asof returns the last obs with obs_date <= D (inclusive,
      1-day discipline), None before the series starts, and NEVER a future obs.
  (2) ReleaseLaggedWeekly.asof returns the last WEEKLY value whose RELEASE date
      (obs_friday + lag) is <= D — the NFCI forward-fill-from-release that
      prevents the ~5-day weekly lookahead leak. Specifically:
        - a value dated Friday W is INVISIBLE on W (and on W+1..W+lag-1),
        - and becomes visible exactly on W + lag.
  (3) NO FUTURE LEAKAGE vs the ground truth: our fixed-lag fill, checked against
      what was ACTUALLY published (a synthetic ALFRED-style point-in-time
      release schedule), never returns a value before it was released.
  (4) align_daily produces parallel, as-of-correct series: every row's feature
      equals the wrapped accessor's asof for that date; the calendar is the
      sleeve's real bar dates clipped to feature_start; no None features once the
      panel has begun (require_all_features).

Network-free: the FRED + Yahoo caches are monkeypatched with synthetic in-memory
series (mirrors test_daily_bars_cache.py / test_fx_strategies.py fake-cache
style). One OPTIONAL live test cross-checks the real NFCI fixed-lag fill against
the real ALFRED vintage and skips if the FRED key/cache is unavailable.

Run: pytest tests/test_credit_data.py -q
"""
from __future__ import annotations

import pytest

from runner import fred_cache as fc
from runner import daily_bars_cache as dbc
from strategies_candidates.credit_stress import credit_data as cd


# --------------------------------------------------------------------------- #
# Fake FRED: monkeypatch fred_cache.get_series to return synthetic rows.
# --------------------------------------------------------------------------- #
def _install_fred(monkeypatch, series_by_id):
    """series_by_id: {series_id: [(date, value), ...]} ascending. value None =>
    missing ('.'-equivalent). Patches fc.get_series to serve these regardless of
    the start/end/vintage args (the adapter clips via its own as-of logic)."""
    store = {sid: [{"date": d, "value": v} for d, v in rows]
             for sid, rows in series_by_id.items()}

    def fake_get(series_id, start, end, vintage="latest", asof=None, use_cache=True):
        return list(store.get(series_id, []))
    monkeypatch.setattr(fc, "get_series", fake_get)
    return store


def _install_yahoo(monkeypatch, bars_by_sym):
    """bars_by_sym: {symbol: [(date, adjclose), ...]} ascending. Patches
    dbc.get_daily to serve synthetic bars and clears the memo so asof works."""
    built = {}
    for sym, rows in bars_by_sym.items():
        series = [{"date": d, "open": c, "high": c, "low": c, "close": c,
                   "adjclose": c, "volume": 0} for d, c in rows]
        built[dbc._sym_key(sym)] = series
        monkeypatch.setitem(dbc._SERIES_MEMO, dbc._sym_key(sym), series)
        monkeypatch.setitem(dbc._DATES_MEMO, dbc._sym_key(sym), [r["date"] for r in series])

    def fake_get(symbol, use_cache=True, refresh=False):
        return built[dbc._sym_key(symbol)]
    monkeypatch.setattr(dbc, "get_daily", fake_get)
    return built


# =========================================================================== #
# (1) DailySeries.asof — last obs <= D, inclusive, no future leak
# =========================================================================== #
def test_dailyseries_asof_inclusive_and_no_future(monkeypatch):
    _install_fred(monkeypatch, {
        "BAA10Y": [("2010-01-04", 2.0), ("2010-01-05", 2.1), ("2010-01-06", 2.2),
                   ("2010-01-08", 2.4)],  # note: no 2010-01-07 obs (gap)
    })
    s = cd.DailySeries("BAA10Y", "2010-01-01", "2010-12-31")
    # exact date -> that value
    assert s.asof("2010-01-05") == 2.1
    # gap date 2010-01-07 -> last prior obs (2010-01-06), NEVER the later 01-08
    assert s.asof("2010-01-07") == 2.2
    # before the series starts -> None
    assert s.asof("2009-12-31") is None
    # after the last obs -> the last obs (forward-fill, not a future value)
    assert s.asof("2010-02-01") == 2.4


def test_dailyseries_first_last(monkeypatch):
    _install_fred(monkeypatch, {"T10Y2Y": [("2008-01-02", 0.5), ("2008-01-03", 0.4)]})
    s = cd.DailySeries("T10Y2Y", "2008-01-01", "2008-12-31")
    assert s.first_date() == "2008-01-02"
    assert s.last_date() == "2008-01-03"
    assert s.n() == 2


# =========================================================================== #
# (2) ReleaseLaggedWeekly.asof — NFCI release-lag forward-fill
# =========================================================================== #
def test_nfci_release_lag_visibility(monkeypatch):
    # Two weekly Friday obs. With lag=7, the Friday-W value is visible on W+7.
    _install_fred(monkeypatch, {
        "NFCI": [("2020-03-06", -0.1),  # Friday
                 ("2020-03-13", 0.5),    # Friday (stress spike)
                 ("2020-03-20", 1.2)],   # Friday
    })
    w = cd.ReleaseLaggedWeekly("NFCI", lag_days=7, start="2020-01-01", end="2020-12-31")
    # On 2020-03-13 (the obs's OWN Friday), that value is NOT yet released; the
    # most-recent released value is the 2020-03-06 obs (released 2020-03-13).
    assert w.asof("2020-03-13") == -0.1
    assert w.asof_obs_date("2020-03-13") == "2020-03-06"
    # On 2020-03-19 (still before 03-13 obs's release on 03-20) -> still -0.1.
    assert w.asof("2020-03-19") == -0.1
    # On 2020-03-20 (exactly W+7 for the 03-13 obs) -> NOW the 0.5 print is live.
    assert w.asof("2020-03-20") == 0.5
    assert w.asof_obs_date("2020-03-20") == "2020-03-13"
    # Before any release -> None (first release is 2020-03-06 + 7 = 2020-03-13).
    assert w.asof("2020-03-12") is None
    assert w.asof("2020-03-13") == -0.1  # exactly first release date


def test_nfci_naive_fill_would_leak_but_release_fill_does_not(monkeypatch):
    """Demonstrate the bug we avoid: a NAIVE same-Friday fill would expose the
    03-13 stress value ON 03-13; our release-lag fill does NOT (it lags it to
    03-20). This is the core no-lookahead win for the weekly series."""
    _install_fred(monkeypatch, {
        "NFCI": [("2020-03-06", -0.1), ("2020-03-13", 0.5)],
    })
    w = cd.ReleaseLaggedWeekly("NFCI", lag_days=7, start="2020-01-01", end="2020-12-31")
    # naive (WRONG) would give 0.5 on 03-13; the safe fill gives the prior value.
    assert w.asof("2020-03-13") != 0.5
    assert w.asof("2020-03-13") == -0.1


# =========================================================================== #
# (3) No future leakage vs a synthetic point-in-time release schedule
# =========================================================================== #
def test_release_fill_never_beats_pit_schedule(monkeypatch):
    """Ground truth: a value dated Friday W was published (released) on W+5 (the
    real-world Wednesday). Our fixed lag is 7 (W+7), which is LATER => for every
    query date D, the obs our asof returns must have been ALREADY released under
    the W+5 ground truth (release_truth <= D). I.e. we never use a value before
    it actually existed. Iterate many dates and assert no leak."""
    from datetime import date, timedelta
    # Build 12 weekly Friday obs in 2019.
    fris = []
    d = date(2019, 1, 4)  # first Friday of 2019
    for _ in range(12):
        fris.append(d.isoformat())
        d += timedelta(days=7)
    obs = [(f, float(i)) for i, f in enumerate(fris)]
    _install_fred(monkeypatch, {"NFCI": obs})
    w = cd.ReleaseLaggedWeekly("NFCI", lag_days=7, start="2019-01-01", end="2019-12-31")

    def truth_release(obs_date):  # ground-truth real release = W + 5 days
        y, m, dd = (int(x) for x in obs_date.split("-"))
        return (date(y, m, dd) + timedelta(days=5)).isoformat()

    # Walk every calendar day across the span; the returned obs must satisfy
    # truth_release(obs) <= D (already public under the real schedule).
    start = date(2019, 1, 1)
    for k in range(120):
        D = (start + timedelta(days=k)).isoformat()
        used_obs = w.asof_obs_date(D)
        if used_obs is None:
            continue
        assert truth_release(used_obs) <= D, (
            f"LEAK: on {D} used obs {used_obs} released (truth) "
            f"{truth_release(used_obs)} > {D}")


# =========================================================================== #
# (4) align_daily — parallel, as-of-correct panel
# =========================================================================== #
def _mk_daily(dates, start_val, step):
    return [(d, start_val + step * i) for i, d in enumerate(dates)]


def test_align_daily_parallel_and_asof_correct(monkeypatch):
    # Sleeve/benchmark bars on a small business calendar; features as synthetic
    # FRED series. We assert each panel row equals the accessor asof for its date.
    cal = ["2010-01-04", "2010-01-05", "2010-01-06", "2010-01-07", "2010-01-08"]
    _install_yahoo(monkeypatch, {
        "SPY": _mk_daily(cal, 100.0, 1.0),
        "^GSPC": _mk_daily(cal, 1000.0, 5.0),
        "IEF": _mk_daily(cal, 90.0, 0.2),
    })
    _install_fred(monkeypatch, {
        "BAA10Y": [("2010-01-04", 2.0), ("2010-01-05", 2.1), ("2010-01-06", 2.2),
                   ("2010-01-07", 2.3), ("2010-01-08", 2.4)],
        "T10Y2Y": [("2010-01-04", 0.5), ("2010-01-06", 0.4), ("2010-01-08", 0.3)],
        # weekly NFCI: one Friday obs released within the window
        "NFCI": [("2009-12-25", -0.2), ("2010-01-01", -0.1)],
    })
    p = cd.align_daily(start="2010-01-01", end="2010-12-31",
                       sleeve_sym="SPY", riskoff_sym="IEF", nfci_lag_days=7)
    # all series parallel to dates
    n = len(p)
    assert n == len(cal)
    for lst in (p.spread, p.nfci, p.slope, p.spx, p.spy, p.riskoff):
        assert len(lst) == n
    # spread is daily exact-match
    assert p.spread == [2.0, 2.1, 2.2, 2.3, 2.4]
    # slope forward-fills across its gaps (no 01-05/01-07 obs)
    assert p.slope == [0.5, 0.5, 0.4, 0.4, 0.3]
    # NFCI: obs 2010-01-01 (Fri) releases 2010-01-08; so it's only visible on the
    # last day; before that the 2009-12-25 obs (released 2010-01-01) is live.
    assert p.nfci == [-0.2, -0.2, -0.2, -0.2, -0.1]
    # benchmark + sleeve match the bars
    assert p.spx == [1000.0, 1005.0, 1010.0, 1015.0, 1020.0]
    assert p.spy == [100.0, 101.0, 102.0, 103.0, 104.0]
    assert p.riskoff == [90.0, 90.2, 90.4, 90.6, 90.8]


def test_align_daily_cash_mode_riskoff_none(monkeypatch):
    cal = ["2010-01-04", "2010-01-05", "2010-01-06"]
    _install_yahoo(monkeypatch, {
        "SPY": _mk_daily(cal, 100.0, 1.0),
        "^GSPC": _mk_daily(cal, 1000.0, 5.0),
    })
    _install_fred(monkeypatch, {
        "BAA10Y": _mk_daily(cal, 2.0, 0.1),
        "T10Y2Y": _mk_daily(cal, 0.5, -0.05),
        "NFCI": [("2009-12-25", -0.2)],
    })
    p = cd.align_daily(start="2010-01-01", end="2010-12-31",
                       sleeve_sym="SPY", riskoff_sym=None, nfci_lag_days=7)
    assert p.riskoff_sym is None
    assert all(v is None for v in p.riskoff)


def test_align_daily_feature_start_clips_calendar(monkeypatch):
    """The panel must begin only once EVERY feature has started. Here the sleeve
    starts earlier than the spread; the panel must start at the spread's first
    date (the binding feature_start)."""
    cal = ["2009-12-28", "2009-12-29", "2009-12-30", "2009-12-31",
           "2010-01-04", "2010-01-05"]
    _install_yahoo(monkeypatch, {
        "SPY": _mk_daily(cal, 100.0, 1.0),
        "^GSPC": _mk_daily(cal, 1000.0, 5.0),
        "IEF": _mk_daily(cal, 90.0, 0.2),
    })
    _install_fred(monkeypatch, {
        # spread only starts 2010-01-04 -> binds the panel start
        "BAA10Y": [("2010-01-04", 2.0), ("2010-01-05", 2.1)],
        "T10Y2Y": _mk_daily(cal, 0.5, -0.01),
        "NFCI": [("2009-12-18", -0.2)],  # released 2009-12-25 (well before)
    })
    p = cd.align_daily(start="2009-01-01", end="2010-12-31",
                       sleeve_sym="SPY", riskoff_sym="IEF", nfci_lag_days=7)
    assert p.dates[0] == "2010-01-04"
    assert p.meta["feature_start"] == "2010-01-04"
    assert None not in p.spread  # no None spread once the panel begins


# =========================================================================== #
# OPTIONAL live cross-check: fixed-lag fill vs real ALFRED vintage (skips if no
# FRED key / cache). Proves the SHIPPED assumption on REAL data.
# =========================================================================== #
def test_live_nfci_fixed_lag_matches_alfred_pit():
    """For a handful of as-of dates, the obs date our fixed-lag (7d) fill uses
    must have been ALREADY published under the real ALFRED point-in-time vintage
    (i.e. it appears in the alfred pull as-of that date). Skips if FRED is
    unavailable. This is the real-data no-future-leak guarantee."""
    try:
        w = cd.ReleaseLaggedWeekly("NFCI", lag_days=7,
                                   start="2014-01-01", end="2024-12-31")
        if w.n() < 50:
            pytest.skip("NFCI not populated")
    except Exception:
        pytest.skip("FRED/NFCI unavailable")

    for asof in ["2015-06-15", "2020-03-25", "2024-06-20"]:
        used_obs = w.asof_obs_date(asof)
        if used_obs is None:
            continue
        try:
            pit = fc.get_series("NFCI", "2010-01-01", asof,
                                vintage="alfred", asof=asof)
        except Exception:
            pytest.skip("ALFRED unavailable")
        published = {r["date"] for r in pit if r["value"] is not None}
        assert used_obs in published, (
            f"as-of {asof}: fixed-lag used obs {used_obs} that ALFRED had NOT "
            f"published as-of that date -> would be a future leak")
