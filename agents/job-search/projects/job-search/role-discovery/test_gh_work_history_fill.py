"""Tests for the GH-Remix WORK-HISTORY repeater fill builder
(`plan_work_history_specs`) added 2026-06-09 for the Zuora 2755 cohort.

The live GH Remix employment-history section (a 'Current role' checkbox +
start/end date-month/year React-Selects) is DOM-only — the boards-API dryrun
never sees it, and the generic remix_recover correctly refuses to fabricate
month names. This builder fills block 0 truthfully from personal-info
work_experience[0]. These tests exercise the pure (no-browser) builder.
"""
import _gh_submit as g


def test_current_role_fills_start_only_no_end():
    pi = {"work_experience": [{
        "company": "Microsoft", "title": "Technical Program Manager",
        "start_month": "March", "start_year": "2024",
        "end_month": "", "end_year": "", "current": True,
    }]}
    spec = g.plan_work_history_specs(pi)
    assert spec is not None
    assert spec["checkCurrent"] is True
    assert spec["selects"] == [{"id": "start-date-month-0", "label": "March"}]
    assert spec["start_year"] == "2024"
    assert spec["company"] == "Microsoft"
    assert spec["title"] == "Technical Program Manager"
    # current role => no end-date fill
    assert spec["end_selects"] == []
    assert spec["end_year"] == ""


def test_numeric_month_normalized_to_name():
    pi = {"work_experience": [{
        "start_month": "3", "start_year": "2024", "current": True,
    }]}
    spec = g.plan_work_history_specs(pi)
    assert spec["selects"] == [{"id": "start-date-month-0", "label": "March"}]


def test_past_role_fills_end_date():
    pi = {"work_experience": [{
        "company": "Acme", "start_month": "January", "start_year": "2020",
        "end_month": "June", "end_year": "2022", "current": False,
    }]}
    spec = g.plan_work_history_specs(pi)
    assert spec["checkCurrent"] is False
    assert spec["selects"] == [{"id": "start-date-month-0", "label": "January"}]
    assert spec["start_year"] == "2020"
    assert spec["end_selects"] == [{"id": "end-date-month-0", "label": "June"}]
    assert spec["end_year"] == "2022"


def test_no_work_experience_returns_none():
    assert g.plan_work_history_specs({}) is None
    assert g.plan_work_history_specs({"work_experience": []}) is None
    assert g.plan_work_history_specs({"work_experience": [None]}) is None


def test_real_personal_info_current_role():
    import json, os
    here = os.path.dirname(os.path.abspath(__file__))
    pi = json.load(open(os.path.join(here, "..", "personal-info.json")))
    spec = g.plan_work_history_specs(pi)
    # Cyrus's single source of truth: Microsoft TPM, March 2024 - Present
    assert spec is not None
    assert spec["checkCurrent"] is True
    assert spec["selects"] == [{"id": "start-date-month-0", "label": "March"}]
    assert spec["start_year"] == "2024"
    assert spec["company"] == "Microsoft"
    assert spec["title"] == "Technical Program Manager"
    assert spec["end_selects"] == []


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception as e:
            failed += 1; print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
