#!/usr/bin/env python3
"""Unit tests for _phenom_runner (no live browser/LLM). FakePage stubs."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _phenom_runner as R


def test_apply_url_from_jd():
    u = R.apply_url_from("https://careers.starktech.com/us/en/job/STNSTLUSP100275EXTERNALENUS/Sales-Engineer-HVAC")
    assert u == "https://careers.starktech.com/us/en/apply?jobSeqNo=STNSTLUSP100275EXTERNALENUS", u


def test_apply_url_passthrough():
    u = "https://careers.nordstrom.com/us/en/apply?jobSeqNo=ABC123"
    assert R.apply_url_from(u) == u


class FakeFileInput:
    def __init__(self):
        self.files = []
    def set_input_files(self, p):
        self.files = [p]


class FakePage:
    """Minimal page that records evaluate calls and serves canned JS results."""
    def __init__(self, resume_commits=True, confirm_after=1):
        self._file = FakeFileInput()
        self.resume_commits = resume_commits
        self.confirm_after = confirm_after
        self._next_clicks = 0
        self.calls = []

    def query_selector(self, sel):
        if "file" in sel:
            return self._file
        return None

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, js, arg=None):
        self.calls.append((js[:40], arg))
        # resume poll
        if "resumeName" in js and "files" in js and arg is None and "bucket" in js:
            if self.resume_commits and self._file.files:
                return json.dumps({"files": 1, "resumeName": "Cyrus_Shekari_Resume.pdf",
                                   "bucket": "default-encrypted", "isResume": "true"})
            return json.dumps({"files": 0, "resumeName": "", "bucket": "", "isResume": ""})
        # JS_PICK_SELECT_ID (check first — also uses getElementById)
        if "el.options" in js and isinstance(arg, list):
            return arg[0] + "=matched"
        # JS_SET_ID
        if "getElementById(id)" in js and isinstance(arg, list):
            return arg[0] + ":ok"
        # has_form check
        if "firstName" in js and "input[type=file]" in js and arg is None:
            return True
        # confirmation
        if "confirmed" in js:
            self._next_clicks += 0
            confirmed = self._next_clicks >= self.confirm_after
            return json.dumps({"confirmed": confirmed, "url": "x/confirmation", "head": "Thank you for applying"})
        # click_next
        if "next|submit" in js or ("Next" in js and "scrollIntoView" in js):
            self._next_clicks += 1
            return "Next"
        # detect_alert
        if "mandatory|required" in js:
            return ""
        # current_step
        if "stepname=" in js:
            return json.dumps({"stepname": "eeo", "stepNum": "2", "url": "x"})
        return ""

    def screenshot(self, path=None, full_page=False):
        open(path, "w").close()

    def goto(self, *a, **k):
        pass

    def on(self, *a, **k):
        pass

    def set_default_timeout(self, *a):
        pass


def test_upload_resume_commits(tmp_path=None):
    p = FakePage(resume_commits=True)
    # point RESUME to an existing file
    R.RESUME = os.path.abspath(__file__)
    out = R.upload_resume(p)
    assert out.startswith("ok:"), out
    assert p._file.files, "set_input_files not called"


def test_upload_resume_uncommitted():
    p = FakePage(resume_commits=False)
    R.RESUME = os.path.abspath(__file__)
    out = R.upload_resume(p)
    assert out.startswith("uncommitted:"), out


def test_fill_personal_sets_all_fields():
    p = FakePage()
    R.RESUME = os.path.abspath(__file__)
    res = R.fill_personal(p, None)
    for k in ("firstName", "lastName", "email", "phone", "city", "zipCode", "country", "state", "applicantSource"):
        assert k in res, k
    assert res["firstName"] == "firstName:ok"
    assert "matched" in res["country"]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception:
            fails += 1; print("FAIL", fn.__name__); traceback.print_exc()
    print(f"\n{len(fns)-fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
