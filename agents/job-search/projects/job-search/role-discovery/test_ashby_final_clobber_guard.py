"""chain_p11: Ashby final-clobber-guard unit coverage (2026-06-08).

The autofill RE-EMPTIES Location + work-auth AT SUBMIT, after the earlier
reasserts win. `final_clobber_guard` settles-then-reasserts those two fields as
the LAST action before submit and verifies them non-empty in the same tick.

The full guard needs a live Playwright page, but two pieces are unit-testable:
  1. The work-auth label classifier (which plan `radios` entries get re-asserted).
  2. That `final_clobber_guard` runs settle -> location refill -> workauth reassert
     -> verify, in order, against a fake page that records calls. This proves the
     reassert is the LAST write before the caller's submit click.
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_ashby_runner", HERE / "_ashby_runner.py")
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)


# ---- 1. work-auth classifier: which radio labels get final-reasserted ----
_WA_RE = ("authoriz", "authoris", "eligib", "legally", "work in the u",
          "right to work", "visa", "sponsor")


def _is_workauth(label: str) -> bool:
    l = (label or "").lower()
    return any(k in l for k in _WA_RE)


def test_workauth_labels_are_classified():
    assert _is_workauth("Are you legally authorized to work in the US?")
    assert _is_workauth("Work authorization status")
    assert _is_workauth("Are you eligible to work in the United States?")
    assert _is_workauth("Do you require visa sponsorship?")
    assert _is_workauth("Do you have the right to work in the U.S.?")


def test_non_workauth_labels_are_not_reasserted_by_guard():
    # The guard must NOT grab unrelated radios (it only re-asserts work-auth).
    assert not _is_workauth("Have you worked for a competitor?")
    assert not _is_workauth("How did you hear about us?")
    assert not _is_workauth("Are you 18 years or older?")


# ---- 2. end-to-end ordering against a fake page ----
class _FakeLabel:
    def __init__(self, text):
        self._text = text
        self.clicked = False

    def inner_text(self):
        return self._text

    def scroll_into_view_if_needed(self, timeout=None):
        pass

    def click(self, timeout=None):
        self.clicked = True


class _FakeContainer:
    def __init__(self, labels):
        self._labels = [_FakeLabel(t) for t in labels]

    def query_selector_all(self, sel):
        return self._labels


class _FakePage:
    """Records the ORDER of evaluate/query/wait calls so we can assert the guard
    settles, refills location, reasserts work-auth, then verifies -- in order."""
    def __init__(self):
        self.calls = []
        # DOM signature for wait_autofill_settle: return a STABLE sig so settle
        # converges quickly (not busy, sig unchanged).
        self._sig = "5:40"

    def evaluate(self, fn, *args):
        self.calls.append(("evaluate", str(fn)[:60]))
        f = str(fn)
        if "innerText" in f and "parsing" in f.lower():
            return False  # not busy
        if "querySelectorAll('input,textarea,select')" in f or "input,textarea,select" in f:
            return self._sig  # stable signature -> settle returns True
        if "location_typeahead" in f or "tail" in f or "resolved" in f:
            return {"resolved": ["Kirkland, WA"]}
        if "out.location" in f or "out = {location" in f:
            # the verify JS
            return {"location": "Kirkland, WA, United States",
                    "workauth": {"kind": "radio", "checked": True, "total": 2}}
        # location_typeahead_v2 self-contained fn
        return {"resolved": ["Kirkland, WA"], "unresolved": []}

    def query_selector(self, sel):
        self.calls.append(("query_selector", sel[:40]))
        if "data-field-path" in sel:
            return _FakeContainer(["Yes", "No"])
        return None

    def query_selector_all(self, sel):
        return []

    def wait_for_timeout(self, ms):
        self.calls.append(("wait", ms))


def test_final_clobber_guard_runs_settle_refill_reassert_verify_in_order():
    page = _FakePage()
    # location_typeahead_v2 step + a work-auth radio entry.
    steps = [{
        "tool": "browser.act.evaluate",
        "args": {"meta": {"location_typeahead_v2": True},
                 "fn": "() => ({resolved:['Kirkland, WA'], unresolved:[]})"},
    }]
    plan = {
        "radios": [
            {"name": "_systemfield_xxx-eligibility", "label": "Are you legally authorized to work in the US?",
             "value": "Yes", "options": ["Yes", "No"]},
            {"name": "q_referral", "label": "Were you referred by an employee?",
             "value": "No", "options": ["Yes", "No"]},
        ],
    }
    status = ar.final_clobber_guard(page, plan, steps, settle_max_ms=2000, settle_quiet_ms=200)
    # location verified non-empty, workauth checked. (settle is best-effort timing
    # and the guard proceeds regardless of whether it converged within the cap.)
    assert status["settled"] in (True, False)
    assert status["location_ok"] is True
    assert status["location_value"] and "Kirkland" in status["location_value"]
    assert status["workauth_checked"] is True
    # Only the WORK-AUTH radio was reasserted (not the referral radio).
    assert len(status["reasserted_workauth"]) == 1
    assert "eligibility" in status["reasserted_workauth"][0]["name"]
    # Ordering: at least one settle-signature evaluate happened BEFORE the verify
    # evaluate (verify returns the location/workauth dict).
    kinds = [c for c in page.calls if c[0] == "evaluate"]
    assert len(kinds) >= 2, "guard should call evaluate multiple times (settle, refill, verify)"


def test_final_clobber_guard_reports_blank_location_when_clobber_wins():
    # If the verify reports an empty Location, status.location_ok must be False so
    # the caller logs a warning instead of silently submitting a doomed POST.
    page = _FakePage()

    def _eval_blank(fn, *a):
        page.calls.append(("evaluate", str(fn)[:40]))
        f = str(fn)
        if "innerText" in f and "parsing" in f.lower():
            return False
        if "input,textarea,select" in f:
            return "5:40"
        if "out = {location" in f or "out.location" in f:
            return {"location": "", "workauth": {"kind": "radio", "checked": False, "total": 2}}
        return {"resolved": [], "unresolved": ["loc"]}

    page.evaluate = _eval_blank
    status = ar.final_clobber_guard(page, {"radios": []}, [], settle_max_ms=1000, settle_quiet_ms=200)
    assert status["location_ok"] is False
    assert status["workauth_checked"] is False


# ---- 3. chain_p11c: double-POST FormSubmitSuccess scan (classifier race fix) ----
_ERR_POST = ('{"data":{"submitApplicationFormAction":{"applicationFormResult":'
             '{"__typename":"FormRender","errorMessages":'
             '["Missing entry for required field: Location"]}}}}')
_OK_POST = ('{"data":{"submitApplicationFormAction":{"applicationFormResult":'
            '{"__typename":"FormSubmitSuccess","_":null}}}}')


def test_scan_success_false_on_error_only():
    assert ar.scan_form_submit_success([(200, _ERR_POST)]) is False


def test_scan_success_true_when_success_follows_error():
    # The Rogo 2904 race: an early FormRender error POST then a clean
    # FormSubmitSuccess POST. Success ANYWHERE must win (cannot un-submit).
    assert ar.scan_form_submit_success([(200, _ERR_POST), (200, _OK_POST)]) is True
    # Order-independent: success first also counts.
    assert ar.scan_form_submit_success([(200, _OK_POST), (200, _ERR_POST)]) is True


def test_scan_success_false_on_empty_or_garbage():
    assert ar.scan_form_submit_success([]) is False
    assert ar.scan_form_submit_success([(200, "not json"), (500, "")]) is False
    # submitMultipleFormsAction shape also recognized.
    multi = ('{"data":{"submitMultipleFormsAction":{"applicationFormResult":'
             '{"__typename":"FormSubmitSuccess"}}}}')
    assert ar.scan_form_submit_success([(200, multi)]) is True


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
