#!/usr/bin/env python3
"""Tests for the FREE-TEXT questionnaire handler (workday-freetext-questions 2026-06-10).

GEICO 2358 EXIT-5 root cause (the ack widget was a red herring): Workday rendered two
REQUIRED free-text questions as <input>/<textarea> with id^=primaryQuestionnaire --
'What is your desired salary?' and 'List your reasons for leaving your last three
positions.' These are NOT listboxes/checkboxes, so no listbox/checkbox handler touched
them and the listbox-only DIAG reported unanswered:[] / errors:[] while 'The field X is
required and must have a value' bounced Next forever.

fill_freetext_questions() + _freetext_answer_for() fill required empty free-text fields
from label keywords (generic, reusable across tenants).
"""
import importlib.util, pathlib, inspect

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


# ---- _freetext_answer_for: pure label->answer logic ------------------------

def test_answer_salary_is_numeric_in_range():
    v = wd._freetext_answer_for("what is your desired salary?")
    assert v.isdigit(), f"salary answer should be numeric, got {v!r}"
    assert 50000 <= int(v) <= 500000, f"salary out of sane range: {v}"


def test_answer_salary_variants():
    for lab in ["desired salary", "compensation expectation", "expected pay",
                "target comp", "base salary expectation", "what is your desired pay"]:
        v = wd._freetext_answer_for(lab)
        assert v.isdigit(), f"{lab!r} -> non-numeric {v!r}"


def test_answer_reasons_for_leaving_is_professional_text():
    v = wd._freetext_answer_for("list your reasons for leaving your last three positions.")
    assert len(v) > 20 and "N/A" != v, f"reasons-for-leaving too short/empty: {v!r}"
    assert "scope" in v.lower() or "growth" in v.lower() or "opportunit" in v.lower()


def test_answer_notice_period():
    assert "week" in wd._freetext_answer_for("what is your notice period?").lower()


def test_answer_how_did_you_hear():
    assert wd._freetext_answer_for("how did you hear about us?") == "LinkedIn"


def test_answer_generic_text_nonempty():
    """An unknown required text field still gets a non-empty value (so Next won't bounce)."""
    v = wd._freetext_answer_for("please describe something unusual", ftype="text")
    assert v and v.strip(), "generic text answer must be non-empty"


def test_answer_generic_number_is_numeric():
    v = wd._freetext_answer_for("some unknown numeric prompt", ftype="number")
    assert v.isdigit()


# ---- fill_freetext_questions: end-to-end with a FakePage -------------------

class FakePage:
    """Reports two required empty free-text fields (salary + reasons), records _set_native."""
    def __init__(self, fields):
        self._fields = fields
        self.set_calls = []   # (id, value)
        self._set_native_orig = None
    def evaluate(self, js, *a, **k):
        # the enumeration JS (queries id^=primaryQuestionnaire input/textarea)
        if "primaryQuestionnaire" in js and "out.push" in js:
            return list(self._fields)
        return None
    def wait_for_timeout(self, *a, **k): pass


def test_fill_freetext_questions_fills_salary_and_reasons(monkeypatch=None):
    fields = [
        {"id": "primaryQuestionnaire--xxx_c3c50002", "tag": "INPUT", "type": "text",
         "label": "What is your desired salary?"},
        {"id": "primaryQuestionnaire--xxx_c3c50001", "tag": "TEXTAREA", "type": "text",
         "label": "List your reasons for leaving your last three positions."},
    ]
    page = FakePage(fields)
    set_calls = []
    # patch module-level _set_native to record instead of touching a browser
    orig = wd._set_native
    wd._set_native = lambda pg, fid, val: (set_calls.append((fid, val)) or True)
    try:
        wd.fill_freetext_questions(page)
    finally:
        wd._set_native = orig
    assert len(set_calls) == 2, f"expected 2 fills, got {set_calls}"
    by_id = dict(set_calls)
    sal = by_id["primaryQuestionnaire--xxx_c3c50002"]
    assert sal.isdigit(), f"salary fill not numeric: {sal!r}"
    reasons = by_id["primaryQuestionnaire--xxx_c3c50001"]
    assert len(reasons) > 20, f"reasons fill too short: {reasons!r}"


def test_fill_freetext_skips_already_filled():
    """The enumeration JS already excludes filled fields; handler fills only what's returned."""
    page = FakePage([])  # nothing required-empty
    set_calls = []
    orig = wd._set_native
    wd._set_native = lambda pg, fid, val: (set_calls.append((fid, val)) or True)
    try:
        wd.fill_freetext_questions(page)
    finally:
        wd._set_native = orig
    assert set_calls == [], "should not fill when no required-empty fields reported"


def test_fill_freetext_wired_into_handle_questions():
    src = inspect.getsource(wd.handle_questions)
    assert "fill_freetext_questions(page)" in src, "fill_freetext_questions not wired into handle_questions"
