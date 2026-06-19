"""Regression tests for YOE experience parsing + the <=3 keep/drop rule.

Cyrus doctrine (reconciled 2026-06-02):
  - A RANGE counts as its LOWER bound: 2-4 -> 2 (KEEP), 3-10 -> 3 (KEEP),
    4-8 -> 4 (DROP). The range's UPPER number must never be re-read as a
    separate 'min' requirement.
  - Across DISTINCT phrases the MAX lower-bound wins (5y overall beats a
    secondary 1-2y of a specific skill).
  - Scan the FULL JD (no char cap) so deep requirements aren't mislabelled
    'unstated'. Only truly silent JDs -> unstated -> KEEP.
"""
import core


def _keep(jd: str) -> bool:
    return core.is_qualifying_experience(core.parse_experience(jd))


def _tag(jd: str) -> str:
    return core.parse_experience(jd)


def test_range_lower_bound_keep():
    assert _tag("2-4 years experience") == "exp:2-4yrs"
    assert _keep("2-4 years experience")            # 2 <= 3
    assert _tag("3-10 years of experience") == "exp:3-10yrs"
    assert _keep("3-10 years of experience")        # 3 <= 3
    assert _tag("2 to 4 years in product") == "exp:2-4yrs"
    assert _keep("2 to 4 years in product")


def test_range_lower_bound_drop():
    assert _tag("4-8 years of experience") == "exp:4-8yrs"
    assert not _keep("4-8 years of experience")     # 4 > 3


def test_range_upper_not_read_as_min():
    # The bare-min pattern must NOT pick up the range's upper number.
    assert _tag("2-4 years experience") == "exp:2-4yrs"   # not exp:4+yrs
    assert _keep("2-4 years of PM experience, plus 1 year of SQL")


def test_bare_min_drop_and_keep():
    assert not _keep("5 years of product management experience")
    assert not _keep("Minimum of 6 years")
    assert _keep("3+ years of experience")
    assert _keep("at least 2 years")
    assert _keep("1 year of experience")


def test_max_lower_bound_wins_across_distinct_phrases():
    # primary 5y beats a secondary 1-2y of a specific skill
    jd = "Over 5 years of experience including a minimum of 1-2 years of X"
    assert _tag(jd) == "exp:5+yrs"
    assert not _keep(jd)


def test_false_unstated_repairs():
    # apostrophe-possessive, yrs abbrev — previously slipped to 'unstated'
    assert not _keep("Requires 5+ years' experience in PM")
    assert not _keep("5 yrs of experience required")
    assert _tag("5 yrs of experience required") == "exp:5+yrs"


def test_deep_in_jd_not_capped():
    # requirement past the old 8000-char cap must still be found
    jd = "blah " * 2000 + " minimum 7 years of experience"
    assert _tag(jd) == "exp:7+yrs"
    assert not _keep(jd)


def test_truly_unstated_keeps():
    assert _tag("") == "exp:unstated"
    assert _keep("")
    assert _tag("We value curiosity. No specific YOE listed.") == "exp:unstated"
    assert _keep("We value curiosity. No specific YOE listed.")
