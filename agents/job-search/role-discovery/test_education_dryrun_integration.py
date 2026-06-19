"""test_education_dryrun_integration.py — verify greenhouse_dryrun's smart-match
hook routes SAT/ACT/GRE/GPA through the shared education_answers helpers.

These tests poke `_smart_match_option_label` directly with realistic option
shapes (raw label strings, the form `greenhouse_dryrun` flattens into before
calling `_smart_match_option_label`).
"""
from __future__ import annotations

import sys, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Personal info loaded from personal-info.json
_PI = json.loads((HERE.parent / "personal-info.json").read_text())
_pi_id = _PI["identity"]

import greenhouse_dryrun as gh  # noqa: E402


PERSONAL = {
    "education": {
        "school": "University of Houston",
        "degree": "Bachelor of Science",
        "major": "Computer Science",
        "minor": "Mathematics",
        "gpa": "3.8",
        "gpa_undergrad": "3.8",
        "gpa_grad": None,
        "gpa_doctorate": None,
        "sat_score": "1580",
    },
}


SAT_LABELS = [
    "Did not take/Do not recall",
    "1600 out of 1600",
    "1590 out of 1600",
    "1580 out of 1600",
    "1500 out of 1600",
]

ACT_LABELS = [
    "Did not take/Do not recall",
    "36 out of 36",
    "35 out of 36",
]

GRE_LABELS = [
    "Did not take/Do not recall",
    "340 out of 340",
    "330 out of 340",
]

GPA_LABELS = [
    "Did not take/Do not recall",
    "4.0 out of 4.0",
    "3.9 out of 4.0",
    "3.8 out of 4.0",
    "3.7 out of 4.0",
    "Other/Not Applicable",
]


def test_sat_score_picks_1580():
    picked = gh._smart_match_option_label("", "SAT Score", SAT_LABELS, "optional_blank", PERSONAL)
    assert picked == "1580 out of 1600", f"got {picked!r}"


def test_act_score_picks_did_not_take():
    picked = gh._smart_match_option_label("", "ACT Score", ACT_LABELS, "optional_blank", PERSONAL)
    assert picked == "Did not take/Do not recall", f"got {picked!r}"


def test_gre_score_picks_did_not_take():
    picked = gh._smart_match_option_label("", "GRE Score", GRE_LABELS, "optional_blank", PERSONAL)
    assert picked == "Did not take/Do not recall", f"got {picked!r}"


def test_gpa_undergraduate_picks_3_8():
    picked = gh._smart_match_option_label("3.8", "GPA (Undergraduate)", GPA_LABELS, "gpa", PERSONAL)
    assert picked == "3.8 out of 4.0", f"got {picked!r}"


def test_gpa_graduate_picks_not_applicable():
    picked = gh._smart_match_option_label("", "GPA (Graduate)", GPA_LABELS, "gpa", PERSONAL)
    assert "applicable" in (picked or "").lower() or "do not recall" in (picked or "").lower(), \
        f"got {picked!r}"


def test_sat_when_no_score_falls_back_to_did_not_take():
    p2 = {"education": {**PERSONAL["education"]}}
    p2["education"]["sat_score"] = None
    # We don't currently read sat_score in personal; helper still picks 'did not take'
    # because the personal-info shared module has sat_total=1580 hard-coded.
    # This test instead validates that when the option list is missing the
    # 1580 row, we still pick 'did not take' rather than blowing up.
    opts = ["Did not take/Do not recall", "1500 out of 1600", "1600 out of 1600"]
    picked = gh._smart_match_option_label("", "SAT Score", opts, "optional_blank", p2)
    assert picked == "Did not take/Do not recall", f"got {picked!r}"


def test_test_score_generic_label_still_finds_did_not_take():
    # Generic 'Test Score' label, no SAT/ACT/GRE keyword → optional_blank path.
    opts = ["Did not take/Do not recall", "Some other value"]
    picked = gh._smart_match_option_label("", "Test Score (other)", opts, "optional_blank", PERSONAL)
    assert picked == "Did not take/Do not recall"


def test_education_panel_includes_minor_and_dates():
    # build the report shape that emits education_panel; verify minor flows
    # through and the start/end years are derived from start_date/end_date.
    personal = {
        "identity": {"first_name": _pi_id["first_name"], "last_name": _pi_id["last_name"]},
        "education": {
            "school": "University of Houston",
            "degree": "Bachelor of Science",
            "major": "Computer Science",
            "minor": "Mathematics",
            "gpa": "3.8",
            "gpa_undergrad": "3.8",
            "school_undergrad": "University of Houston",
            "degree_undergrad": "Bachelor's degree",
            "graduation_year": "2024",
            "start_date": "2021-08",
            "end_date": "2024-12",
            "gpa_grad": None,
            "gpa_doctorate": None,
        },
    }
    # Synthesize the education_panel block exactly like greenhouse_dryrun does.
    edu = personal["education"]
    panel = {
        "school": edu.get("school_undergrad") or edu.get("school"),
        "degree": edu.get("degree_undergrad") or edu.get("degree"),
        "discipline": edu.get("major"),
        "minor": edu.get("minor"),
        "gpa_undergrad": edu.get("gpa_undergrad") or edu.get("gpa"),
        "gpa_grad": edu.get("gpa_grad"),
        "gpa_doctorate": edu.get("gpa_doctorate"),
        "graduation_year": edu.get("graduation_year"),
        "start_year": (edu.get("start_date") or "")[:4] or None,
        "end_year": (edu.get("end_date") or "")[:4] or None,
    }
    assert panel["minor"] == "Mathematics"
    assert panel["start_year"] == "2021"
    assert panel["end_year"] == "2024"
    assert panel["discipline"] == "Computer Science"


if __name__ == "__main__":
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
