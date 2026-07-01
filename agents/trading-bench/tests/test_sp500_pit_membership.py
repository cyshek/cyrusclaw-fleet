"""Tests for runner.sp500_pit_membership — free PIT S&P 500 membership spine.

These pin the PARSING + AS-OF semantics against a small synthetic change-log so
they never depend on the network. A separate live smoke (not in the unit suite)
exercises the real Wikipedia fetch.

The point-in-time guarantee under test: members_asof(D) returns exactly the set
of tickers that were in the index on date D, reconstructed by replaying the
dated add/remove change-log backward from a known current snapshot. No ticker
that was added AFTER D may appear; no ticker removed ON/BEFORE D may appear
(removal effective at start of its date), and a ticker removed AFTER D must
still appear.
"""
import datetime as dt

import pytest

from runner import sp500_pit_membership as pit


# --- synthetic fixtures -------------------------------------------------------

# "today" snapshot: the 4 names currently in the index.
CURRENT = {"AAA", "BBB", "CCC", "DDD"}

# change-log rows: (date, added, removed). Most-recent first is NOT required;
# the parser sorts. Effective convention: a change dated D took effect at the
# OPEN of D (so on date D the post-change membership holds; on D-1 it does not).
CHANGES = [
    # 2024-01-10: EEE removed, AAA added
    {"date": "2024-01-10", "added": "AAA", "removed": "EEE"},
    # 2023-06-01: FFF removed, BBB added
    {"date": "2023-06-01", "added": "BBB", "removed": "FFF"},
    # 2022-03-15: CCC added (no removal recorded that day)
    {"date": "2022-03-15", "added": "CCC", "removed": ""},
]


@pytest.fixture()
def table():
    return pit.build_membership_table(CURRENT, CHANGES)


# --- parsing ------------------------------------------------------------------

def test_parse_change_date_accepts_long_form():
    assert pit._parse_change_date("January 10, 2024") == dt.date(2024, 1, 10)
    assert pit._parse_change_date("June 1, 2023") == dt.date(2023, 6, 1)


def test_parse_change_date_accepts_iso():
    assert pit._parse_change_date("2024-01-10") == dt.date(2024, 1, 10)


def test_parse_change_date_bad_returns_none():
    assert pit._parse_change_date("not a date") is None
    assert pit._parse_change_date("") is None


# --- as-of reconstruction -----------------------------------------------------

def test_asof_today_equals_current(table):
    today = dt.date.today()
    assert pit.members_asof(table, today) == CURRENT


def test_asof_just_after_a_change_includes_added(table):
    # On 2024-01-10 (the change date) AAA is in, EEE is out.
    s = pit.members_asof(table, dt.date(2024, 1, 10))
    assert "AAA" in s
    assert "EEE" not in s


def test_asof_day_before_change_reverses_it(table):
    # On 2024-01-09 the 2024-01-10 change had NOT happened yet:
    # AAA not yet added, EEE still a member.
    s = pit.members_asof(table, dt.date(2024, 1, 9))
    assert "AAA" not in s
    assert "EEE" in s


def test_asof_walks_back_multiple_changes(table):
    # Before 2022-03-15, CCC had not been added yet.
    s_before = pit.members_asof(table, dt.date(2022, 3, 14))
    assert "CCC" not in s_before
    s_after = pit.members_asof(table, dt.date(2022, 3, 15))
    assert "CCC" in s_after


def test_asof_far_past_reverses_all_adds(table):
    # Way before any recorded change, none of the later-added names exist,
    # but the names that were only ever REMOVED later must be present.
    s = pit.members_asof(table, dt.date(2000, 1, 1))
    assert "AAA" not in s and "BBB" not in s and "CCC" not in s
    assert "EEE" in s and "FFF" in s
    # DDD never appears in the change-log and is current => present throughout.
    assert "DDD" in s


def test_membership_table_is_pure_no_network(table):
    # build_membership_table must not require network; it's a pure transform.
    assert isinstance(table, dict)
    assert "current" in table and "changes" in table
    assert table["current"] == CURRENT


def test_asof_rejects_naive_string_or_requires_date(table):
    with pytest.raises((TypeError, AttributeError)):
        pit.members_asof(table, "2024-01-10")  # must pass a date, not a str
