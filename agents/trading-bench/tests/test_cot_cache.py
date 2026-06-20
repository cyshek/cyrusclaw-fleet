"""Tests for runner.cot_cache — the CFTC COT (TFF) point-in-time positioning cache.

The make-or-break property under test is the LOOKAHEAD GUARD: a COT report is
snapshotted on a Tuesday but only PUBLISHED the following Friday (~3-day lag).
A backtest must never read a snapshot before its release date, or it leaks
future information and silently inflates Sharpe. These tests prove:

  1. release_date_for() maps a Tuesday snapshot forward to its Friday release.
  2. released_asof() returns the most recent report whose RELEASE <= asof, and
     NEVER a report whose release is after asof (the no-leak invariant).
  3. On the day AFTER a snapshot but BEFORE its release, released_asof returns
     the PRIOR (already-released) report, not the fresh-but-unreleased one.
  4. released_history() contains only already-released reports (all release<=asof).

These run against the locally cached TFF data (data_cache/cot/), no network.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from runner import cot_cache


def test_release_date_is_friday_after_tuesday_snapshot():
    # Tuesday 2025-12-30 -> +3 days = Fri 2026-01-02 (the documented worked example)
    snap = date(2025, 12, 30)
    rel = cot_cache.release_date_for(snap)
    assert rel >= snap + timedelta(days=cot_cache.RELEASE_LAG_DAYS)
    assert rel.weekday() == 4  # Friday
    assert rel == date(2026, 1, 2)


def test_release_always_after_snapshot():
    # For a year of Tuesdays, release is strictly after the snapshot, >= the lag.
    d = date(2024, 1, 2)  # a Tuesday
    for _ in range(52):
        rel = cot_cache.release_date_for(d)
        assert rel > d
        assert (rel - d).days >= cot_cache.RELEASE_LAG_DAYS
        d += timedelta(days=7)


def _first_market():
    for m in ("ES", "NQ", "ZN"):
        try:
            if cot_cache.matched_contract_names(m):
                return m
        except Exception:
            continue
    pytest.skip("no COT market resolvable from cache")


def test_released_asof_never_returns_unreleased_report():
    mkt = _first_market()
    # Sample a range of as-of dates; every returned report must have release<=asof.
    d = date(2018, 1, 1)
    end = date(2026, 1, 1)
    checked = 0
    while d < end:
        rec = cot_cache.released_asof(mkt, d.isoformat())
        if rec is not None:
            rel = date.fromisoformat(rec["release"])
            assert rel <= d, (
                f"LOOKAHEAD: asof={d} got report released {rel} (> asof)")
            checked += 1
        d += timedelta(days=11)
    assert checked > 50  # sanity: we actually exercised the accessor


def test_snapshot_not_visible_before_its_release():
    """The core no-leak test: find a real (snapshot, release) pair, then assert
    that ON the snapshot date (before release) released_asof returns a report
    whose release is strictly EARLIER than this snapshot's release — i.e. the
    fresh snapshot is NOT yet visible."""
    mkt = _first_market()
    # Pull the full released history as-of a late date to enumerate real reports.
    hist = cot_cache.released_history(mkt, "2026-01-15", lookback=400)
    assert hist and len(hist) > 50
    # pick a report well inside the series (has a predecessor + successor)
    target = hist[len(hist) // 2]
    snap = date.fromisoformat(target["snapshot"])
    rel = date.fromisoformat(target["release"])
    assert rel > snap  # precondition: release lags snapshot

    # On the snapshot date itself (strictly before release), the fresh report
    # must NOT be served. released_asof should return something released earlier.
    seen = cot_cache.released_asof(mkt, snap.isoformat())
    assert seen is not None
    seen_rel = date.fromisoformat(seen["release"])
    assert seen_rel <= snap, f"served report released {seen_rel} on asof {snap}"
    assert seen_rel < rel, (
        "leak: the target report (or later) was visible on its own snapshot date")
    # And the target's OWN snapshot value must differ from / not be the served one
    assert seen["snapshot"] != target["snapshot"]


def test_target_report_becomes_visible_on_its_release_date():
    """Complement: ON/after the release date, the report IS visible."""
    mkt = _first_market()
    hist = cot_cache.released_history(mkt, "2026-01-15", lookback=400)
    target = hist[len(hist) // 2]
    rel = date.fromisoformat(target["release"])
    seen = cot_cache.released_asof(mkt, rel.isoformat())
    assert seen is not None
    seen_rel = date.fromisoformat(seen["release"])
    # the most recent released report as-of the release date is THIS one (its
    # release == asof) — or conceivably a later one if two released same day; in
    # all cases release<=asof and >= target's predecessor.
    assert seen_rel <= rel
    assert seen_rel >= rel  # exactly the release date -> this report is now live
    assert seen["snapshot"] == target["snapshot"]


def test_released_history_only_contains_released_reports():
    mkt = _first_market()
    asof = "2022-06-15"
    hist = cot_cache.released_history(mkt, asof, lookback=156)
    assert hist
    for r in hist:
        assert date.fromisoformat(r["release"]) <= date.fromisoformat(asof)


def test_selftest_lookahead_guard_passes():
    """The module's own bundled lookahead selftest must report every invariant True.

    selftest_lookahead_guard() returns a diagnostic dict of named boolean checks
    (no single 'ok' key). Assert that every boolean it reports is True -- i.e.
    the worked example, the invisible-before-release checks, and the no-leak
    checks all hold.
    """
    out = cot_cache.selftest_lookahead_guard()
    assert isinstance(out, dict)
    bool_checks = {k: v for k, v in out.items() if isinstance(v, bool)}
    assert bool_checks, f"selftest returned no boolean checks: {out}"
    failed = {k: v for k, v in bool_checks.items() if v is not True}
    assert not failed, f"cot_cache selftest_lookahead_guard checks failed: {failed} (full: {out})"
    # spot-check the specific invariants we care about are present + True
    for key in ("release_is_after_snapshot", "visible_on_release",
                "no_leak_on_day_before"):
        assert out.get(key) is True, f"missing/false invariant {key!r}: {out}"
