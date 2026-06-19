"""Regression tests for the Ashby Date-widget cohort fix (2026-06-08).

Background (r4 diagnosis on OpenAI 2549 "When can you start a new role?"):
Ashby renders `type:"Date"` fields as a CALENDAR-PICKER widget. They were
mapped to GH "input_text", so `gh.resolve_field` handed the earliest_start
resolver a *text* type -> it returned the PROSE fallback
"Within 2 weeks of offer" instead of an ISO date. The runner then typed that
prose into a date input that never committed -> the form banked
"Missing entry" and the submit failed (NOT a captcha/score wall).

The fix:
  1. ASHBY_TO_GH_TYPE maps "Date" -> "input_date" so the date resolvers emit a
     real YYYY-MM-DD (today+14d).
  2. A build_dryrun normalization safety-net guarantees the resolved value for
     any Ashby Date field is ISO-date-shaped before it reaches the runner's
     date-picker path, coercing anything non-ISO (prose, a select label, or an
     empty essay placeholder for a *required* date) to today+14d, and tagging
     `_ashby_date_iso`.

These are pure/unit-level checks (no browser). The runner-side date-picker
commit is validated separately on the live form.
"""
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import ashby_dryrun as a  # noqa: E402

gh = a.gh

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------
# 1) Type mapping: Ashby "Date" must map to GH "input_date" (NOT input_text),
#    while preserving _ashby_type=="Date" so the runner can drive the picker.
# --------------------------------------------------------------------------

def test_date_field_maps_to_input_date():
    fe = {
        "id": "form123_q_startdate",
        "isRequired": True,
        "field": {"type": "Date", "title": "When can you start a new role?"},
    }
    gf, label = a.adapt_field(fe)
    assert gf["type"] == "input_date", f"expected input_date, got {gf['type']!r}"
    assert gf["_ashby_type"] == "Date"
    assert label == "When can you start a new role?"


def test_non_date_types_unchanged():
    # Guard: the Date remap must not have disturbed the other type mappings.
    assert a.ASHBY_TO_GH_TYPE["String"] == "input_text"
    assert a.ASHBY_TO_GH_TYPE["Email"] == "input_text"
    assert a.ASHBY_TO_GH_TYPE["LongText"] == "textarea"
    assert a.ASHBY_TO_GH_TYPE["File"] == "input_file"
    assert a.ASHBY_TO_GH_TYPE["Boolean"] == "multi_value_single_select"


# --------------------------------------------------------------------------
# 2) Resolver output: with the input_date mapping, "When can you start a new
#    role?" resolves to a real ISO date (today+14d), NOT the prose fallback.
# --------------------------------------------------------------------------

def test_start_date_resolves_to_iso_via_input_date():
    fld = {"type": "input_date", "values": [], "_ashby_type": "Date", "required": True}
    ent = gh.resolve_field({}, "When can you start a new role?", True, fld,
                           rules=a._ASHBY_COMBINED_RULES)
    assert ISO_RE.match(ent.get("value") or ""), (
        f"expected ISO date, got {ent.get('value')!r}")
    assert ent.get("value") == (date.today() + timedelta(days=14)).isoformat()
    assert ent.get("status") == "filled"


def test_start_date_as_input_text_would_be_prose():
    # Documents the OLD (broken) behavior the fix corrects: as input_text the
    # resolver returns prose, which is exactly what failed to commit.
    fld = {"type": "input_text", "values": [], "_ashby_type": "Date", "required": True}
    ent = gh.resolve_field({}, "When can you start a new role?", True, fld,
                           rules=a._ASHBY_COMBINED_RULES)
    assert not ISO_RE.match(ent.get("value") or ""), (
        "input_text path should NOT yield an ISO date (that is the bug)")


# --------------------------------------------------------------------------
# 3) Normalization safety-net (build_dryrun): exercised directly against the
#    coercion logic for an Ashby Date entry regardless of how the resolver
#    routed it (prose, select label, empty required placeholder, or a value
#    that is already a valid ISO date).
# --------------------------------------------------------------------------

def _normalize_date_entry(entry):
    """Mirror of the build_dryrun Date-normalization block, applied to a
    finished entry dict (so we can unit-test the coercion without a live
    fetch_form). Kept in lockstep with ashby_dryrun.build_dryrun."""
    _dv = (entry.get("value") or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _dv):
        _iso = (date.today() + timedelta(days=14)).isoformat()
        entry["value"] = _iso
        if entry["status"] in ("unresolved", "needs_essay", "filled_needs_review"):
            entry["status"] = "filled"
        entry["source"] = f"ashby_date_normalized (calendar widget -> today+14d ISO; was {_dv!r})"
    entry["_ashby_date_iso"] = entry["value"]
    return entry


def test_normalize_coerces_prose_to_iso():
    e = _normalize_date_entry({"value": "Within 2 weeks of offer", "status": "filled"})
    assert ISO_RE.match(e["value"])
    assert e["_ashby_date_iso"] == e["value"]
    assert "ashby_date_normalized" in e["source"]


def test_normalize_coerces_empty_required_to_iso_and_fills():
    # A required date that came back as an empty essay placeholder must become
    # a committable ISO date AND flip to 'filled' so it stops blocking submit.
    e = _normalize_date_entry({"value": "", "status": "needs_essay"})
    assert ISO_RE.match(e["value"])
    assert e["status"] == "filled"


def test_normalize_preserves_valid_iso():
    e = _normalize_date_entry({"value": "2027-01-15", "status": "filled"})
    assert e["value"] == "2027-01-15", "an already-valid ISO date must be left intact"
    assert e["_ashby_date_iso"] == "2027-01-15"
    # No spurious re-source when the value was already good.
    assert "ashby_date_normalized" not in e.get("source", "")


def test_normalize_tags_iso_for_runner():
    # The runner keys its date-picker path on _ashby_date_iso; it must always
    # be present and ISO-shaped after normalization.
    for v, st in [("garbage", "filled"), ("2026-12-01", "filled"), ("", "unresolved")]:
        e = _normalize_date_entry({"value": v, "status": st})
        assert ISO_RE.match(e["_ashby_date_iso"]), f"{v!r} -> {e['_ashby_date_iso']!r}"
