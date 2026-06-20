"""Regression: chain_p12 (2026-06-10, Klarity 1434) — Ashby dryrun resolves a
work-auth/sponsorship ValueSelect (visa-status options, NO plain 'No' option) to
the US-citizen / green-card option for a citizen profile, instead of banking the
literal 'No' as filled_needs_review.

Bug: Klarity's "Do you require sponsorship now or in the future...?" has options
[US Citizen/Green Card, H-1B, H-1B I-140, OPT]. The needs_sponsorship rule
resolves a citizen to "No", but Rule 1 only matched options starting with "no",
so pick stayed None -> field demoted to filled_needs_review with value "No"
(which matches NO option) -> the live submit silently DROPS the required field.

Fix: Rule 1b (workauth_citizen_status) picks the citizen/green-card option when
the profile is a US citizen and the answer is the no-sponsorship negative.

This test monkeypatches fetch_form with the captured Klarity applicationForm
fixture so it runs offline.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import ashby_dryrun as a  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "_fixture_klarity_form.json")
ROLE_URL = "https://jobs.ashbyhq.com/klarity-ai/4843b6cd-405e-412f-8261-d1a2d6acd850"

CITIZEN_PERSONAL = {
    "identity": {"first_name": "Cyrus", "last_name": "Shekari"},
    "contact": {"email": "cyshekari@gmail.com", "linkedin": "https://linkedin.com/in/cyshekari"},
    "files": {"resume_path": "resume/Cyrus_Shekari_Resume.pdf"},
    "work_authorization": {
        "authorized_to_work_us": "yes",
        "status": "us_citizen",
        "sponsorship_required_now": "no",
        "sponsorship_required_future": "no",
        "security_clearance": "none",
    },
    "preferences": {"willing_to_travel_pct": 50, "willing_to_relocate": "yes"},
    "location": {"city": "Kirkland", "state": "WA"},
}


def _load_posting():
    with open(FIXTURE) as fh:
        return json.load(fh)


def _build(monkey_personal=None):
    posting = _load_posting()
    orig = a.fetch_form
    a.fetch_form = lambda org, job_id: posting  # type: ignore
    try:
        return a.build_dryrun(monkey_personal or CITIZEN_PERSONAL, ROLE_URL)
    finally:
        a.fetch_form = orig


def _sponsorship_field(spec):
    for f in spec["fields"]:
        if "sponsorship" in (f.get("label") or "").lower():
            return f
    return None


def test_sponsorship_value_select_resolves_to_citizen_option():
    spec = _build()
    f = _sponsorship_field(spec)
    assert f is not None, "sponsorship field missing from spec"
    assert f["value"] == "I am a US Citizen / Green Card Holder", \
        f"expected citizen option, got {f['value']!r} (source={f.get('source')})"
    assert f["status"] == "filled", f"expected filled, got {f['status']!r}"
    assert "workauth_citizen_status" in (f.get("source") or "")


def test_sponsorship_field_not_left_needs_review():
    spec = _build()
    f = _sponsorship_field(spec)
    # the whole point: it must NOT be a needs_review bank with the bogus "No"
    assert f["status"] != "filled_needs_review"
    assert f["value"] != "No"


def test_no_blockers_and_all_filled_for_citizen():
    spec = _build()
    c = spec["counts"]
    assert c["blockers"] == 0, spec.get("blockers")
    assert c["filled_needs_review"] == 0, "no field should bank as needs_review"
    assert c["unresolved"] == 0


def test_citizen_rule_never_picks_h1b_or_opt():
    # guard: the citizen rule must never select a visa-needed option
    spec = _build()
    f = _sponsorship_field(spec)
    v = (f["value"] or "").lower()
    assert "h-1b" not in v and "opt" not in v and "transfer" not in v
