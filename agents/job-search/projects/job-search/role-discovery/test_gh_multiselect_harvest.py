"""Tests for the multi_value_multi_select STEP-harvest fallback in
plan_multiselect_commit_specs (shipped 2026-06-10, DigiCert 2752).

Real inline plans from greenhouse_filler.build_plan have an EMPTY top-level
plan['multi_checkboxes']; the resolved specs are baked into a JS_TICK step's
args.arg. Before the fix, plan_multiselect_commit_specs read only the top-level
key and committed nothing -> required education/years multiselects stayed
multiUnset -> submit no-op'd. The harvest fallback recovers them.
"""
import _gh_submit as gs


def _plan_with_step():
    return {
        "steps": [
            {"tool": "browser.act.evaluate", "args": {"label": "x", "fn": "async()=>{}", "arg": None}},
            {"tool": "browser.act.evaluate", "args": {"label": "x", "fn": "async(specs)=>{}",
             "arg": [{"id": "question_35787069002[]",
                      "legend_re": "What is your highest level of completed education",
                      "values": ["Bachelors Degree"]}]}},
        ],
        "multi_checkboxes": [],  # build_plan leaves this empty
    }


def test_harvest_from_steps_recovers_spec():
    h = gs._harvest_multi_checkbox_specs_from_steps(_plan_with_step())
    assert len(h) == 1
    assert h[0]["id"] == "question_35787069002[]"
    assert h[0]["values"] == ["Bachelors Degree"]


def test_commit_specs_uses_harvest_when_toplevel_empty():
    specs = gs.plan_multiselect_commit_specs(_plan_with_step(), ["question_35787069002[]"])
    assert specs == [{"id": "question_35787069002[]", "label": ["Bachelors Degree"]}]


def test_harvest_skips_demographic_decline_steps():
    # demographic decline-only steps carry `labels`, NOT `values` -> must be skipped
    plan = {"steps": [
        {"tool": "browser.act.evaluate", "args": {"fn": "x", "arg": [
            {"id": "question_demo[]", "legend_re": "Race / Ethnicity",
             "labels": ["Decline To Self Identify"]}]}}],
        "multi_checkboxes": []}
    assert gs._harvest_multi_checkbox_specs_from_steps(plan) == []
    assert gs.plan_multiselect_commit_specs(plan, ["question_demo[]"]) == []


def test_toplevel_multi_checkboxes_still_wins():
    # if the top-level key IS populated, harvest is not needed and that path is used
    plan = {"multi_checkboxes": [{"id": "q1[]", "legend_re": "L", "values": ["Yes"]}], "steps": []}
    specs = gs.plan_multiselect_commit_specs(plan, ["q1[]"])
    assert specs == [{"id": "q1[]", "label": ["Yes"]}]


def test_no_multiunset_returns_empty():
    assert gs.plan_multiselect_commit_specs(_plan_with_step(), []) == []
