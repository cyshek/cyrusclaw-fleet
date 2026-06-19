"""Tests for lever_dryrun required-select fallbacks added 2026-06-03.

Covers the two fallbacks that prevent a required Lever dropdown from silently
blocking submit (observed live on Palantir 817):
  1. "How did you hear about this opportunity?" -> prefer LinkedIn.
  2. Generic last-resort for any required single-select -> first real option.
"""
import json, os
import lever_dryrun as ld

_pi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "personal-info.json")
_pi_id = json.load(open(_pi_path))["identity"]

PERSONAL = {
    "identity": {"first_name": _pi_id["first_name"]},
    "work_authorization": {"status": "us_citizen"},
}


def _field(text, options, required=True, ftype="multiple-choice"):
    return {
        "text": text,
        "required": required,
        "type": ftype,
        "options": [{"text": o, "optionId": o} for o in options],
    }


def test_how_did_you_hear_prefers_linkedin():
    f = _field("How did you hear about this opportunity?",
               ["Indeed", "LinkedIn", "Company Website"], ftype="dropdown")
    out = ld.resolve_card_field(PERSONAL, "", f, "cardX[field0]")
    assert out["status"] in ("filled", "filled_needs_review")
    assert out["value"] == "LinkedIn"


def test_how_did_you_hear_falls_back_to_first_real_option():
    # No LinkedIn/job-board option present; the pref-order includes 'Other' as a
    # sensible default for an unknown source, so 'Other' is chosen over 'Friend'.
    f = _field("Where did you hear about us?",
               ["Select...", "Friend", "Other"], ftype="dropdown")
    out = ld.resolve_card_field(PERSONAL, "", f, "cardX[field1]")
    assert out["status"] in ("filled", "filled_needs_review")
    assert out["value"] == "Other"


def test_how_did_you_hear_no_pref_picks_first_real():
    # Only non-pref options -> first real (non-placeholder) option.
    f = _field("How did you hear about this opportunity?",
               ["Select...", "Friend", "Conference"], ftype="dropdown")
    out = ld.resolve_card_field(PERSONAL, "", f, "cardX[field1b]")
    assert out["value"] == "Friend"


def test_required_select_last_resort_picks_first_real_option():
    # An unmapped REQUIRED single-select that no resolver/rule handles must
    # still get a value so the form is submittable.
    f = _field("Which internal team referred you?",
               ["Please select", "Platform", "Growth"],
               ftype="dropdown")
    out = ld.resolve_card_field(PERSONAL, "", f, "cardX[field2]")
    assert out["status"] in ("filled", "filled_needs_review")
    assert out["value"] in ("Platform", "Growth")
    assert out["value"] != "Please select"


def test_non_required_unmapped_select_not_forced():
    f = _field("Optional: favorite color?", ["Select...", "Red", "Blue"],
               required=False, ftype="dropdown")
    out = ld.resolve_card_field(PERSONAL, "", f, "cardX[field3]")
    # not required -> must NOT be force-filled by the last-resort rule
    assert out["status"] != "filled" or out.get("source", "") and "last-resort" not in (out.get("source") or "")


if __name__ == "__main__":
    import sys, pytest
    sys.exit(pytest.main([__file__, "-q"]))
