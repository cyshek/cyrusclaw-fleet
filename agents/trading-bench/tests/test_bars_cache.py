"""Unit tests for `runner.bars_cache`.

Currently focused on the `_iso_date` cache-key serializer. The original
implementation stripped time-of-day, causing two intraday fetches on the
same calendar day (e.g. 14:30 UTC and 15:30 UTC) to collide on the same
cache file — the second fetch silently returned the first fetch's data.
This was a real concern flagged during the F2 cache-key audit response
(see `BACKLOG.md` P2 / 2026-05-30). Daily/UTC-day-snapped fetches still
emit the short `YYYY-MM-DD` form so the existing daily cache layout is
preserved.
"""

from __future__ import annotations

from datetime import datetime, timezone

from runner.bars_cache import _iso_date


def test_iso_date_midnight_utc_is_short_form():
    """Midnight-UTC timestamps keep the legacy YYYY-MM-DD cache-key form so
    daily backtests continue to share the same cache file across reruns
    within the same UTC day."""
    d = datetime(2026, 5, 30, 0, 0, 0, tzinfo=timezone.utc)
    assert _iso_date(d) == "2026-05-30"


def test_iso_date_intraday_uses_full_timestamp():
    """Non-midnight timestamps must serialize the time component so two
    distinct intraday fetches don't collide in the bars cache."""
    d_1430 = datetime(2026, 5, 30, 14, 30, 0, tzinfo=timezone.utc)
    d_1530 = datetime(2026, 5, 30, 15, 30, 0, tzinfo=timezone.utc)
    assert _iso_date(d_1430) != _iso_date(d_1530)
    assert _iso_date(d_1430) == "2026-05-30T143000Z"
    assert _iso_date(d_1530) == "2026-05-30T153000Z"


def test_iso_date_seconds_distinguished():
    """Sub-minute precision matters for high-frequency intraday fetches."""
    d_1430_00 = datetime(2026, 5, 30, 14, 30, 0, tzinfo=timezone.utc)
    d_1430_45 = datetime(2026, 5, 30, 14, 30, 45, tzinfo=timezone.utc)
    assert _iso_date(d_1430_00) != _iso_date(d_1430_45)


def test_iso_date_one_microsecond_past_midnight_uses_full_form():
    """Defensive: anything non-zero in {h,m,s,us} forces full-timestamp
    serialization. Prevents a clock-skew sub-microsecond from silently
    collapsing into the short form."""
    d = datetime(2026, 5, 30, 0, 0, 0, 1, tzinfo=timezone.utc)
    assert _iso_date(d) == "2026-05-30T000000Z"
