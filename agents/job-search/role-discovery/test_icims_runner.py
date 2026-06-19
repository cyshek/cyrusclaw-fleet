"""Tests for _icims_runner — knockout resolver + flow primitives with FakePage/
FakeFrame/FakeInput stubs (NO live browser/LLM). Run:
  python3 -m pytest test_icims_runner.py -q

Importing the module is safe — playwright is imported lazily inside run().
"""
import importlib.util, os

_spec = importlib.util.spec_from_file_location(
    "_icims_runner", os.path.join(os.path.dirname(__file__), "_icims_runner.py"))
ir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ir)


# ---- Truthful knockout resolver -------------------------------------------
def test_sponsorship_now_is_no():
    assert ir.resolve_knockout("Will you now or in the future require sponsorship?") == "no"
    assert ir.resolve_knockout("Do you require visa sponsorship to work in the US?") == "no"


def test_work_authorization_is_yes():
    assert ir.resolve_knockout("Are you legally authorized to work in the United States?") == "yes"
    assert ir.resolve_knockout("Do you have the right to work in the US?") == "yes"


def test_citizen_is_yes():
    assert ir.resolve_knockout("Are you a U.S. citizen?") == "yes"


def test_clearance_is_no():
    assert ir.resolve_knockout("Do you currently hold an active security clearance?") == "no"


def test_relocate_and_travel_are_yes():
    assert ir.resolve_knockout("Are you willing to relocate for this role?") == "yes"
    assert ir.resolve_knockout("This role requires up to 50% travel. Are you able to travel?") == "yes"


def test_former_employee_is_no():
    assert ir.resolve_knockout("Are you a former employee of this company?") == "no"
    assert ir.resolve_knockout("Have you previously worked here?") == "no"


def test_eeo_questions_decline():
    for q in ("What is your gender?", "Please indicate your race/ethnicity.",
              "Are you a protected veteran?", "Do you have a disability?",
              "Voluntary self-identify"):
        assert ir.resolve_knockout(q) == ir.EEO_DECLINE == "decline"


def test_unrecognized_returns_none():
    assert ir.resolve_knockout("What is your favorite color?") is None
    assert ir.resolve_knockout("") is None


def test_knockout_answers_table_truthful():
    a = ir.KNOCKOUT_ANSWERS
    assert a["require_sponsorship_now"] == "no"
    assert a["require_sponsorship_future"] == "no"
    assert a["authorized_to_work_us"] == "yes"
    assert a["us_citizen"] == "yes"
    assert a["security_clearance"] == "no"
    assert a["willing_to_relocate"] == "yes"
    assert a["willing_to_travel"] == "yes"
    assert a["former_employee"] == "no"


def test_identity_constants():
    import json as _j, re as _re, os as _os
    _pi = _j.load(open(_os.path.join(_os.path.dirname(__file__), "..", "personal-info.json")))
    _id = _pi["identity"]; _ad = _pi.get("address", {})
    _digits = lambda p: _re.sub(r'[^0-9]','',p or '')
    assert ir._EMAIL() == _id["email"]
    assert ir._PHONE() == _digits(_id["phone"])
    assert ir._FIRST() == _id["first_name"] and ir._LAST() == _id["last_name"]
    assert ir._ADDR_STATE() == _ad["state"] and ir._ADDR_CITY() == _ad["city"]


# ---- Fake page/frame stubs (no live browser) ------------------------------
class FakeInput:
    def __init__(self):
        self.files = []
    def set_input_files(self, path):
        self.files = [path]


class FakeFrame:
    def __init__(self, url="about:blank", selectors=None, evals=None, file_input=None,
                 body_text=""):
        self.url = url
        self._selectors = selectors or set()
        self._evals = evals or {}
        self._file_input = file_input
        self._body_text = body_text
        self.eval_calls = []

    def evaluate(self, fn, arg=None):
        self.eval_calls.append((fn, arg))
        # selector-presence probe used by find_form_frame
        if "querySelector(s)" in fn:
            return arg in self._selectors
        if "document.body.innerText" in fn and "conf" not in fn:
            return self._body_text
        # any custom registered eval by substring key
        for key, val in self._evals.items():
            if key in fn:
                return val(arg) if callable(val) else val
        return None

    def query_selector(self, sel):
        if sel == "input[type=file]" and self._file_input is not None:
            return self._file_input
        return None


class FakePage:
    def __init__(self, frames, url="https://careers-x.icims.com/jobs/1/x/login"):
        self.frames = frames
        self.url = url
        self.timeouts = []
    def wait_for_timeout(self, ms):
        self.timeouts.append(ms)
    def set_default_timeout(self, ms):
        pass


def test_find_form_frame_locates_email_frame():
    f1 = FakeFrame(url="outer", selectors=set())
    f2 = FakeFrame(url="inner", selectors={"#email, input[name='css_loginName'], input[type=email]"})
    page = FakePage([f1, f2])
    found = ir.find_form_frame(page, "#email, input[name='css_loginName'], input[type=email]")
    assert found is f2


def test_upload_resume_calls_set_input_files(monkeypatch, tmp_path):
    # Point RESUME at a real temp file so the existence check passes.
    fake_resume = tmp_path / "resume.pdf"
    fake_resume.write_text("pdf")
    monkeypatch.setattr(ir, "RESUME", str(fake_resume))
    finp = FakeInput()
    fr = FakeFrame(url="inner", file_input=finp,
                   evals={"files.length": lambda a: 1})
    page = FakePage([fr])
    res = ir.upload_resume_anyframe(page)
    assert finp.files == [str(fake_resume)]        # set_input_files was called
    assert res.startswith("files=1")


def test_upload_resume_no_input():
    fr = FakeFrame(url="inner", file_input=None)
    page = FakePage([fr])
    assert ir.upload_resume_anyframe(page) == "no-file-input"


def test_detect_hcaptcha_present():
    fr = FakeFrame(evals={"hcFrame": lambda a: {"hcFrame": True, "sitekey": "abc123",
                                                "hasResp": True, "respFilled": False}})
    page = FakePage([fr])
    present, sitekey = ir.detect_hcaptcha(page)
    assert present and sitekey == "abc123"


def test_detect_hcaptcha_absent():
    fr = FakeFrame(evals={"hcFrame": lambda a: {"hcFrame": False, "sitekey": None,
                                                "hasResp": False, "respFilled": False}})
    page = FakePage([fr])
    present, sitekey = ir.detect_hcaptcha(page)
    assert present is False


def test_detect_terminal_already_applied():
    fr = FakeFrame(body_text="You have already applied for this position.")
    page = FakePage([fr])
    assert ir.detect_terminal(page) == "already_applied"


def test_detect_terminal_closed():
    fr = FakeFrame(body_text="This position is no longer accepting applications.")
    page = FakePage([fr])
    assert ir.detect_terminal(page) == "closed"


def test_detect_terminal_none():
    fr = FakeFrame(body_text="Enter Your Information. Email.")
    page = FakePage([fr])
    assert ir.detect_terminal(page) is None


def test_try_solve_hcaptcha_no_vendor(monkeypatch):
    # Force CaptchaSolver to raise SolverNotConfigured for every vendor ->
    # runner must surface the precise 'icims-hcaptcha-no-vendor' reason.
    import captcha_solver as cs
    def boom(*a, **k):
        raise cs.SolverNotConfigured("no key")
    monkeypatch.setattr(cs, "CaptchaSolver", boom)
    token, reason = ir.try_solve_hcaptcha("sitekey", "https://x/login")
    assert token is None
    assert reason == "icims-hcaptcha-no-vendor"
