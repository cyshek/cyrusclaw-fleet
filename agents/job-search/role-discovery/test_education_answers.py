"""test_education_answers.py — unit tests for the shared academic-fields module.

Covers:
- SAT/ACT/GRE option matching (numeric pick when score on file; 'did not take'
  when score is None or no numeric option matches).
- GPA option matching (3.8 -> '3.8 out of 4.0').
- Degree option selection across long/short option lists.
- High-school detection (so drivers can block correctly).
- Shape-tolerance for option lists: raw strings AND Greenhouse-style
  {'label','value'} dicts both work.

Pure unit tests. No browser, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from education_answers import (  # noqa: E402
    EDUCATION_ANSWERS,
    match_sat_option,
    match_act_option,
    match_gre_option,
    match_gpa_option,
    pick_degree_for_options,
    is_high_school_required,
)


# Realistic SpaceX-style option list (label/value dict shape).
SAT_OPTIONS_DICT = [
    {"label": "Did not take/Do not recall", "value": 240031387002},
    {"label": "1600 out of 1600", "value": 240031388002},
    {"label": "1590 out of 1600", "value": 240031389002},
    {"label": "1580 out of 1600", "value": 240031390002},
    {"label": "1570 out of 1600", "value": 240031391002},
]

ACT_OPTIONS_STR = [
    "Did not take/Do not recall",
    "36 out of 36",
    "35 out of 36",
    "34 out of 36",
]

GRE_OPTIONS_DICT = [
    {"label": "Did not take/Do not recall", "value": 1},
    {"label": "340 out of 340", "value": 2},
    {"label": "339 out of 340", "value": 3},
]

GPA_OPTIONS_DICT = [
    {"label": "Did not take/Do not recall", "value": 1},
    {"label": "4.0 out of 4.0", "value": 2},
    {"label": "3.9 out of 4.0", "value": 3},
    {"label": "3.8 out of 4.0", "value": 4},
    {"label": "3.7 out of 4.0", "value": 5},
    {"label": "Below 3.0", "value": 6},
    {"label": "Other/Not Applicable", "value": 7},
]


def test_constants_match_memory_md():
    """Ground truth — MEMORY.md 2026-05-29."""
    assert EDUCATION_ANSWERS["school"] == "University of Houston"
    assert EDUCATION_ANSWERS["major"] == "Computer Science"
    assert EDUCATION_ANSWERS["minor"] == "Mathematics"
    assert EDUCATION_ANSWERS["gpa"] == "3.8"
    assert EDUCATION_ANSWERS["sat_total"] == 1580
    assert EDUCATION_ANSWERS["sat_scale"] == 1600
    assert EDUCATION_ANSWERS["act_total"] is None
    assert EDUCATION_ANSWERS["gre_total"] is None


def test_sat_picks_1580_dict_shape():
    picked = match_sat_option(SAT_OPTIONS_DICT)
    assert isinstance(picked, dict)
    assert picked["label"] == "1580 out of 1600"


def test_sat_picks_1580_string_shape():
    str_opts = [o["label"] for o in SAT_OPTIONS_DICT]
    picked = match_sat_option(str_opts)
    assert picked == "1580 out of 1600"


def test_sat_falls_back_when_only_did_not_take_present():
    opts = [{"label": "Did not take/Do not recall", "value": 1}]
    picked = match_sat_option(opts)
    assert picked["label"] == "Did not take/Do not recall"


def test_sat_falls_back_when_no_matching_score():
    # No 1580 option — should pick 'did not take' as safe fallback.
    opts = [
        {"label": "Did not take/Do not recall", "value": 1},
        {"label": "1600 out of 1600", "value": 2},
        {"label": "1500 out of 1600", "value": 3},
    ]
    picked = match_sat_option(opts)
    assert picked["label"] == "Did not take/Do not recall"


def test_act_picks_did_not_take_when_score_null():
    picked = match_act_option(ACT_OPTIONS_STR)
    assert picked == "Did not take/Do not recall"


def test_gre_picks_did_not_take_when_score_null():
    picked = match_gre_option(GRE_OPTIONS_DICT)
    assert picked["label"] == "Did not take/Do not recall"


def test_gpa_picks_3_8_out_of_4():
    picked = match_gpa_option(GPA_OPTIONS_DICT)
    assert picked["label"] == "3.8 out of 4.0"


def test_gpa_explicit_override():
    picked = match_gpa_option(GPA_OPTIONS_DICT, gpa="3.7")
    assert picked["label"] == "3.7 out of 4.0"


def test_gpa_no_match_returns_none():
    opts = [{"label": "4.0 out of 4.0", "value": 1}, {"label": "Below 3.0", "value": 2}]
    picked = match_gpa_option(opts, gpa="3.8")
    assert picked is None  # No numeric match and no "did not take" — caller decides fallback.


def test_degree_picks_bachelor_of_science():
    opts = ["High School", "Associate", "Bachelor of Science", "Master of Science", "PhD"]
    picked = pick_degree_for_options(opts)
    assert picked == "Bachelor of Science"


def test_degree_picks_bachelors_when_no_long_form():
    opts = ["High School", "Associate", "Bachelor's Degree", "Master's Degree", "Doctorate"]
    picked = pick_degree_for_options(opts)
    assert picked == "Bachelor's Degree"


def test_degree_falls_back_to_substring_bachelor():
    opts = ["No degree", "BSc / Bachelor in Engineering", "MSc"]
    picked = pick_degree_for_options(opts)
    assert "bachelor" in picked.lower()


def test_high_school_detection():
    assert is_high_school_required("High School Name") is True
    assert is_high_school_required("Secondary school you attended") is True
    assert is_high_school_required("University") is False
    assert is_high_school_required("College name") is False
    assert is_high_school_required("") is False


def test_sat_split_score_helpers_present():
    # Some forms ask for the SAT split (Math vs Reading). Constants must
    # expose them so per-ATS adapters can fill correctly.
    assert EDUCATION_ANSWERS["sat_math"] == 800
    assert EDUCATION_ANSWERS["sat_reading_writing"] == 780
    assert EDUCATION_ANSWERS["sat_math"] + EDUCATION_ANSWERS["sat_reading_writing"] == EDUCATION_ANSWERS["sat_total"]


def test_dict_options_with_name_field():
    # Some Ashby option lists use 'name' instead of 'label'. Helpers should
    # tolerate both.
    opts = [
        {"name": "Did not take", "value": 1},
        {"name": "1580 out of 1600", "value": 2},
    ]
    picked = match_sat_option(opts)
    assert picked["name"] == "1580 out of 1600"


def test_did_not_take_synonyms():
    # Confirm a variety of "I didn't take this" labels are detected.
    for not_taken in [
        "Did not take/Do not recall",
        "I did not take this test",
        "Not applicable",
        "N/A",
        "Other/Not Applicable",
        "I haven't taken the SAT",
    ]:
        opts = [not_taken]
        assert match_act_option(opts) == not_taken, f"failed for: {not_taken!r}"


if __name__ == "__main__":
    # Tiny self-runner so the file works without pytest.
    import inspect
    failures = 0
    tests = [(n, fn) for n, fn in inspect.getmembers(sys.modules[__name__]) if n.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            failures += 1
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
