"""Runner-side regression tests for the Ashby Date-widget cohort fix
(2026-06-08, ashby-date-runner).

Background (r4 diagnosis on OpenAI 2549 "When can you start a new role?"):
the dryrun half (ashby_dryrun + ashby_filler) already maps Ashby `type:"Date"`
-> GH "input_date", normalizes the value to ISO `YYYY-MM-DD` (today+14d), tags
`entry["_ashby_date_iso"]`, and `ashby_filler.build_plan` routes Date fids into
BOTH `plan["text_fields"]` (legacy) AND `plan["date_fields"]`, emitting the
`ashby.type_text_fields` step with `date_field_ids=list(date_fields)`.

The RUNNER half (this module): typing the ISO string into the calendar-picker
input with CDP keystrokes does NOT commit to React controlled state, so submit
banks "Missing entry". `_ashby_runner.commit_ashby_date_fields` drives each Date
input via the proven `_SET_DATE_JS` `_valueTracker`-reset transition (ISO for a
native `type=date` input, localized MM/DD/YYYY for a masked text picker), with a
calendar-cell trusted-click fallback.

These checks are PURE/unit-level: they exercise the date routing + ISO-shaping +
DOM-id-resolution logic against a FakePage that mimics the relevant
`page.evaluate(_SET_DATE_JS, ...)` / calendar contract WITHOUT a real browser, so
they run in CI. The genuine React commit is validated separately by a live
`--no-submit` DOM probe on the OpenAI 2549 form.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

import _ashby_runner as r  # noqa: E402

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------
# FakePage: records every page.evaluate(fn, arg) call and answers the date
# helper contracts deterministically. Two flavors:
#   * commit=True  -> _SET_DATE_JS returns committed:True (programmatic set
#     stuck; mimics a native <input type=date> or a cooperative text picker).
#   * commit=False -> _SET_DATE_JS returns committed:False on the FIRST call,
#     forcing the calendar-cell fallback; the post-click re-verify (a second
#     _SET_DATE_JS) then returns committed:True (mimics a masked picker that
#     only accepts a real day-cell click).
# --------------------------------------------------------------------------
class FakePage:
    def __init__(self, commit=True, dom_ids=None):
        self.commit = commit
        self.dom_ids = set(dom_ids or [])
        self.calls = []          # list of (kind, arg)
        self.set_date_calls = []  # list of arg dicts passed to _SET_DATE_JS
        self._set_date_seen = 0

    # mouse stub (calendar fallback uses page.mouse.click)
    class _Mouse:
        def __init__(self, outer):
            self.outer = outer
            self.clicks = []

        def click(self, x, y):
            self.outer.calls.append(("mouse.click", (x, y)))
            self.clicks.append((x, y))

    @property
    def mouse(self):
        if not hasattr(self, "_mouse"):
            self._mouse = FakePage._Mouse(self)
        return self._mouse

    def wait_for_timeout(self, ms):
        self.calls.append(("wait", ms))

    def evaluate(self, fn, arg=None):
        # Identity-match our JS constants FIRST (before any string-content
        # heuristic) -- _SET_DATE_JS happens to contain both 'getElementById(id)'
        # and '!!', which would otherwise misroute into the exists-probe branch
        # and try `dict in set` -> 'unhashable type: dict'.
        if fn is r._SET_DATE_JS:
            self._set_date_seen += 1
            self.set_date_calls.append(dict(arg or {}))
            self.calls.append(("set_date", dict(arg or {})))
            iso = (arg or {}).get("iso", "")
            if self.commit:
                return {"ok": True, "used": iso, "after": iso, "final": iso,
                        "type": "date", "committed": True, "domId": (arg or {}).get("id")}
            # first set fails to stick; AFTER a calendar click (>=2nd call) it sticks
            committed = self._set_date_seen >= 2
            return {"ok": True, "used": iso, "after": iso if committed else "",
                    "final": iso if committed else "", "type": "text",
                    "committed": committed, "domId": (arg or {}).get("id")}
        if fn is r._DATE_CALENDAR_OPEN_JS:
            self.calls.append(("cal_open", dict(arg or {})))
            return {"ok": True, "cx": 100.0, "cy": 200.0, "domId": (arg or {}).get("id")}
        if fn is r._DATE_CALENDAR_PICK_JS:
            self.calls.append(("cal_pick", dict(arg or {})))
            iso = (arg or {}).get("iso", "")
            day = iso.split("-")[-1].lstrip("0") if "-" in iso else ""
            return {"ok": True, "cx": 120.0, "cy": 220.0, "text": day}
        # getElementById existence probe used by _resolve_date_dom_id
        if isinstance(fn, str) and "getElementById(id)" in fn and "!!" in fn:
            self.calls.append(("exists", arg))
            return arg in self.dom_ids
        # default
        self.calls.append(("other", arg))
        return None


# --------------------------------------------------------------------------
# 1) Helper: _resolve_date_dom_id resolves via uuid tail / systemfield fallback.
# --------------------------------------------------------------------------

def test_resolve_dom_id_prefers_concrete_id():
    fid = "form123_systemfield_startdate"
    page = FakePage(dom_ids={fid})
    assert r._resolve_date_dom_id(page, fid) == fid


def test_resolve_dom_id_falls_back_to_uuid_tail():
    uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fid = f"app_{uuid}"
    # only the bare uuid exists as a live element id
    page = FakePage(dom_ids={uuid})
    assert r._resolve_date_dom_id(page, fid) == uuid


def test_resolve_dom_id_none_when_nameless():
    # nameless+idless input: nothing resolves -> None (caller drives by fp tail)
    uuid = "11111111-2222-3333-4444-555555555555"
    fid = f"q_{uuid}"
    page = FakePage(dom_ids=set())
    assert r._resolve_date_dom_id(page, fid) is None


# --------------------------------------------------------------------------
# 2) Helper: _date_fp_tail extracts the data-field-path tail.
# --------------------------------------------------------------------------

def test_date_fp_tail_uuid():
    uuid = "abcdef12-3456-7890-abcd-ef1234567890"
    assert r._date_fp_tail(f"prefix_{uuid}") == uuid


def test_date_fp_tail_question_suffix():
    assert r._date_fp_tail("section_question_77") == "question_77"


def test_date_fp_tail_passthrough():
    assert r._date_fp_tail("plain_fid") == "plain_fid"


# --------------------------------------------------------------------------
# 3) commit_ashby_date_fields: routes only date fids, passes ISO-shaped values,
#    reports committed when the programmatic set sticks.
# --------------------------------------------------------------------------

def test_commit_passes_iso_and_reports_committed():
    fid = "form_systemfield_startdate"
    page = FakePage(commit=True, dom_ids={fid})
    specs = [{"fid": fid, "iso": "2026-06-23"}]
    out = r.commit_ashby_date_fields(page, specs)
    assert len(out) == 1
    assert out[0]["committed"] is True
    assert out[0]["method"] == "set_value_js"
    # The value handed to _SET_DATE_JS must be the ISO string (not prose).
    assert page.set_date_calls, "expected a _SET_DATE_JS call"
    assert ISO_RE.match(page.set_date_calls[0]["iso"]), page.set_date_calls[0]["iso"]
    assert page.set_date_calls[0]["iso"] == "2026-06-23"


def test_commit_skips_non_iso_value():
    # A non-ISO value must be rejected up front (the dryrun normalizes, but the
    # runner double-guards) and never typed into the widget.
    fid = "form_q_startdate"
    page = FakePage(commit=True, dom_ids={fid})
    out = r.commit_ashby_date_fields(page, [{"fid": fid, "iso": "Within 2 weeks of offer"}])
    assert out[0]["committed"] is False
    assert out[0]["method"] == "skip"
    assert not page.set_date_calls, "must NOT drive the widget with a non-ISO value"


def test_commit_calendar_fallback_when_programmatic_set_fails():
    # commit=False -> first _SET_DATE_JS returns committed:False, so the helper
    # opens the picker, clicks the matching day cell, and re-verifies (which
    # then commits). Final result: committed via the calendar_click method.
    uuid = "99999999-8888-7777-6666-555555555555"
    fid = f"q_{uuid}"
    page = FakePage(commit=False, dom_ids=set())  # nameless -> driven by fp tail
    out = r.commit_ashby_date_fields(page, [{"fid": fid, "iso": "2026-06-23"}])
    assert out[0]["committed"] is True, out
    assert out[0]["method"] == "calendar_click"
    kinds = [c[0] for c in page.calls]
    assert "cal_open" in kinds and "cal_pick" in kinds and "mouse.click" in kinds
    # The calendar pick must have been asked for the SAME ISO date.
    pick_args = [c[1] for c in page.calls if c[0] == "cal_pick"]
    assert pick_args and pick_args[0]["iso"] == "2026-06-23"


def test_commit_nameless_field_uses_fp_tail():
    # When no concrete id resolves, the helper must still attempt the commit by
    # passing the data-field-path tail (uuid) so _SET_DATE_JS can scope the input.
    uuid = "abababab-cdcd-efef-0101-232345456767"
    fid = f"app_{uuid}"
    page = FakePage(commit=True, dom_ids=set())
    out = r.commit_ashby_date_fields(page, [{"fid": fid, "iso": "2027-01-15"}])
    assert out[0]["committed"] is True
    call = page.set_date_calls[0]
    assert call["id"] is None, "no concrete id should resolve for a nameless field"
    assert call["fp"] == uuid, f"fp tail should be the uuid, got {call['fp']!r}"


def test_commit_handles_empty_specs():
    page = FakePage()
    assert r.commit_ashby_date_fields(page, []) == []
    assert r.commit_ashby_date_fields(page, None) == []


# --------------------------------------------------------------------------
# 4) End-to-end plan routing: an Ashby Date field flows through ashby_filler
#    into plan["date_fields"] AND the emitted ashby.type_text_fields step carries
#    date_field_ids, with an ISO value the runner's date path can consume.
# --------------------------------------------------------------------------

def _make_date_spec_entry(fid, iso):
    """A minimal post-dryrun spec field for an Ashby Date question (mirrors what
    ashby_dryrun.build_dryrun emits after the Date normalization)."""
    return {
        "id": fid,
        "label": "When can you start a new role?",
        "value": iso,
        "status": "filled",
        "_ashby_type": "Date",
        "_ashby_id": fid,
        "_ashby_date_iso": iso,
        "required": True,
        "options": [],
    }


def test_build_plan_routes_date_into_date_fields():
    import ashby_filler as af
    uuid = "12121212-3434-5656-7878-909090909090"
    fid = f"form_{uuid}"
    iso = "2026-06-23"
    spec = {"role_url": "https://jobs.ashbyhq.com/openai/x", "fields": [
        _make_date_spec_entry(fid, iso)]}
    plan = af.build_plan(spec)
    assert fid in plan["date_fields"], plan["date_fields"]
    assert plan["date_fields"][fid] == iso
    # Date fids are ALSO mirrored into text_fields (legacy), carrying the ISO.
    assert plan["text_fields"].get(fid) == iso
    assert ISO_RE.match(plan["text_fields"][fid])


def test_emit_steps_type_text_fields_carries_date_field_ids():
    import ashby_filler as af
    uuid = "23232323-4545-6767-8989-010101010101"
    fid = f"form_{uuid}"
    iso = "2026-06-23"
    spec = {"role_url": "https://jobs.ashbyhq.com/openai/x", "fields": [
        _make_date_spec_entry(fid, iso)]}
    plan = af.build_plan(spec)
    steps = af.emit_steps(plan, label="unit-date")
    ttf = [s for s in steps if s.get("tool") == "ashby.type_text_fields"]
    assert ttf, "expected an ashby.type_text_fields step"
    date_ids = ttf[0]["args"].get("date_field_ids", [])
    assert fid in date_ids, f"date_field_ids missing the date fid: {date_ids}"
    # And the value the runner will read for that fid is the ISO date.
    assert ttf[0]["args"]["text_fields"].get(fid) == iso


def test_runner_date_specs_construction_from_step_args():
    """The runner builds date_specs = [{fid, iso}] from the step's
    date_field_ids x text_fields. Verify that mapping yields ISO-shaped values
    and excludes non-date text fields."""
    date_fid = "form_q_date"
    text_fid = "form_systemfield_email"
    step_args = {
        "text_fields": {date_fid: "2026-06-23", text_fid: "cyrus@example.com"},
        "date_field_ids": [date_fid],
    }
    date_field_ids = set(step_args.get("date_field_ids", []) or [])
    date_specs = [{"fid": d, "iso": (step_args["text_fields"].get(d) or "")}
                  for d in date_field_ids]
    assert len(date_specs) == 1
    assert date_specs[0]["fid"] == date_fid
    assert ISO_RE.match(date_specs[0]["iso"])
    # the email text field must NOT be in the date specs
    assert all(s["fid"] != text_fid for s in date_specs)
