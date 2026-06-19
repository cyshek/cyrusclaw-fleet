"""Contract tests for the needs_review_dropdowns cohort commit fix (2026-06-08).

Background: greenhouse_filler parks every dryrun `filled_needs_review`
single-select into plan['needs_review_dropdowns'] as
{id, label:<resolved answer>, alternates:["United States","Yes","No"], question}.
_gh_submit previously committed dropdowns/countries/phone/--answers/multi_checkboxes
but NEVER iterated needs_review_dropdowns -> those required selects stayed EMPTY
-> emptyRequired -> submit silently no-ops / status 'uncertain'. The per-row
--answers workaround papered over it. plan_needs_review_specs() is the pure
(no-browser) helper that turns those parked specs into ordered SEL_PICK candidate
labels so main() can commit them with no manual --answers.
"""
import _gh_submit as g


def _by_id(specs):
    return {s["id"]: s for s in specs}


def test_resolved_label_first_then_alternates_then_doctrine():
    plan = {"needs_review_dropdowns": [
        {"id": "q1", "label": "Yes",
         "alternates": ["United States", "Yes", "No"],
         "question": "Are you willing to relocate?"},
    ]}
    out = _by_id(g.plan_needs_review_specs(plan))
    c = out["q1"]["candidates"]
    # resolved answer FIRST
    assert c[0] == "Yes"
    # alternates follow, de-duplicated case-insensitively (the dup "Yes" dropped)
    assert "United States" in c and "No" in c
    assert c.count("Yes") == 1
    # doctrine affirmatives appended as last resort
    assert c[-1] == "Agree"
    assert "I acknowledge" in c


def test_country_residency_resolved_value_leads():
    plan = {"needs_review_dropdowns": [
        {"id": "q2", "label": "United States",
         "alternates": ["United States", "Yes", "No"],
         "question": "Country of residence"},
    ]}
    out = _by_id(g.plan_needs_review_specs(plan))
    assert out["q2"]["candidates"][0] == "United States"
    # no duplicate United States even though it's also in alternates
    assert out["q2"]["candidates"].count("United States") == 1


def test_offbeat_resolved_value_kept_first_with_yesno_fallback():
    # Real artifact case: dryrun resolved "Open to discuss" (notice period) but
    # the live select may render as Yes/No -> we try the resolved value first,
    # then Yes/No from alternates so it still commits.
    plan = {"needs_review_dropdowns": [
        {"id": "q3", "label": "Open to discuss",
         "alternates": ["United States", "Yes", "No"],
         "question": "Notice period"},
    ]}
    c = _by_id(g.plan_needs_review_specs(plan))["q3"]["candidates"]
    assert c[0] == "Open to discuss"
    assert "Yes" in c and "No" in c


def test_blank_resolved_label_does_NOT_inject_doctrine_affirmative():
    # If the dryrun did not actually resolve a concrete value, we must NOT
    # auto-affirm (the question could be a negative like sponsorship). Only the
    # generic alternates are tried; no doctrine 'Yes'/'Agree' is appended.
    plan = {"needs_review_dropdowns": [
        {"id": "q4", "label": "", "alternates": ["United States", "Yes", "No"],
         "question": "Do you require visa sponsorship?"},
    ]}
    c = _by_id(g.plan_needs_review_specs(plan))["q4"]["candidates"]
    # alternates only; NO doctrine-only affirmations injected
    assert "I acknowledge" not in c and "Agree" not in c
    assert "I agree" not in c
    # the generic alternates are still there (best-effort, not fabrication)
    assert "United States" in c


def test_placeholder_resolved_label_treated_as_blank():
    plan = {"needs_review_dropdowns": [
        {"id": "q5", "label": "Select...", "alternates": [],
         "question": "Pick one"},
    ]}
    out = g.plan_needs_review_specs(plan)
    # placeholder label + no real alternates + no doctrine (label not real)
    # -> nothing committable -> spec dropped entirely
    assert all(s["id"] != "q5" for s in out)


def test_placeholder_candidates_filtered_but_real_ones_kept():
    plan = {"needs_review_dropdowns": [
        {"id": "q6", "label": "Yes",
         "alternates": ["-- Select --", "No", "please select"],
         "question": "ack"},
    ]}
    c = _by_id(g.plan_needs_review_specs(plan))["q6"]["candidates"]
    # placeholder alternates dropped, real ones kept
    assert "-- Select --" not in c
    assert all(not x.lower().startswith("please select") for x in c)
    assert "No" in c and c[0] == "Yes"


def test_skips_non_dict_and_missing_id_and_empty_plan():
    assert g.plan_needs_review_specs({}) == []
    assert g.plan_needs_review_specs({"needs_review_dropdowns": []}) == []
    plan = {"needs_review_dropdowns": [
        "notadict",
        {"label": "Yes"},                 # no id -> skipped
        {"id": "ok", "label": "Yes", "alternates": [], "question": "q"},
    ]}
    out = g.plan_needs_review_specs(plan)
    assert [s["id"] for s in out] == ["ok"]


def test_question_text_preserved_for_logging():
    plan = {"needs_review_dropdowns": [
        {"id": "q7", "label": "Yes", "alternates": [],
         "question": "Are you authorized to work in the United States?"},
    ]}
    out = _by_id(g.plan_needs_review_specs(plan))
    assert out["q7"]["question"].startswith("Are you authorized")


def test_main_wires_the_helper():
    # Cheap guard against the regression returning: main() must reference the
    # helper + emit a 'needs_review' step. (String check avoids a live browser.)
    import inspect
    src = inspect.getsource(g.main)
    assert "plan_needs_review_specs" in src
    assert "needs_review" in src
