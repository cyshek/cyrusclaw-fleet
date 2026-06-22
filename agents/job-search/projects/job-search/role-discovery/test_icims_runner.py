"""Tests for _icims_runner — knockout resolver + flow primitives with FakePage/
FakeFrame/FakeInput stubs (NO live browser/LLM). Run:
  python3 -m pytest test_icims_runner.py -q

Importing the module is safe — playwright is imported lazily inside run().
"""
import importlib.util, os, json
from pathlib import Path
_PI = json.loads((Path(__file__).resolve().parents[1] / "personal-info.json").read_text())

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
    assert ir.EMAIL == _PI["contact"]["email"]
    assert ir.PHONE == _PI["contact"]["phone"].replace("-", "")
    assert ir.FIRST == _PI["identity"]["first_name"] and ir.LAST == _PI["identity"]["last_name"]
    assert ir.ADDR_STATE == _PI["address"]["state"] and ir.ADDR_CITY == _PI["address"]["city"]


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


# ===========================================================================
# Email-OTP verification tests (gate detect + Gmail fetch + fill + EXIT 10).
# ===========================================================================
import gmail_imap as gi


def test_extract_icims_otp_plaintext():
    assert gi._extract_icims_otp("Your verification code is 482913.", "") == "482913"


def test_extract_icims_otp_html_element():
    body = "<html><body><p>Enter the code</p><h1>730145</h1></body></html>"
    assert gi._extract_icims_otp(body, "Verify your email") == "730145"


def test_extract_icims_otp_keyword_anchored():
    assert gi._extract_icims_otp("Use 6-digit code 884412 to continue.", "") == "884412"


def test_extract_icims_otp_rejects_8char_alnum_and_empty():
    # 8-char Greenhouse-style code must NOT be returned by the 6-digit extractor.
    assert gi._extract_icims_otp("Your verification code is AB12CD34", "") is None
    assert gi._extract_icims_otp("Welcome to iCIMS, no code here", "") is None


def test_looks_like_icims_accepts_icims_rejects_workday():
    assert gi._looks_like_icims("Your iCIMS Verification Code",
                                "no-reply@icims.com",
                                "Your verification code is 111111") is True
    # A Workday code in the inbox must not be claimed by the iCIMS filter.
    assert gi._looks_like_icims("Verify your candidate account",
                                "no-reply@otp.workday.com",
                                "Your code is 222222") is False


# ---- Fake page/frame for OTP gate detection + fill --------------------------
class OtpFrame:
    """Frame stub that answers the OTP detect/fill/continue JS by substring and
    records fill/continue invocations. `detect` is the dict returned by the
    detect JS (or {present:False})."""
    def __init__(self, url="inner", detect=None, fill_result="ok:482913",
                 seg_result="seg_ok:6", continue_result="Verify"):
        self.url = url
        self._detect = detect or {"present": False}
        self._fill_result = fill_result
        self._seg_result = seg_result
        self._continue_result = continue_result
        self.fill_calls = []
        self.continue_calls = []
        self._detect_calls = 0
        # toggled True after a successful fill+continue so re-detect clears.
        self.cleared = False

    def evaluate(self, fn, arg=None):
        if "singles.length" in fn:            # _OTP_DETECT_JS
            self._detect_calls += 1
            if self.cleared:
                return {"present": False}
            return dict(self._detect)
        if "OTP_INPUT_MISSING" in fn:         # _OTP_FILL_SINGLE_JS
            self.fill_calls.append(("single", arg))
            return self._fill_result
        if "SEG_TOO_FEW" in fn:               # _OTP_FILL_SEGMENTED_JS
            self.fill_calls.append(("seg", arg))
            return self._seg_result
        if "verify code" in fn.lower() or "x.value||x.textContent" in fn:  # continue
            self.continue_calls.append(arg)
            self.cleared = True               # gate clears after continue
            return self._continue_result
        return None

    def query_selector(self, sel):
        return None


class OtpPage:
    def __init__(self, frames, url="https://x.icims.com/jobs/1/x/login"):
        self.frames = frames
        self.url = url
    def wait_for_timeout(self, ms):
        pass
    def set_default_timeout(self, ms):
        pass
    def screenshot(self, **k):
        pass


class FakeGmail:
    """Stand-in for gmail_imap with a programmable wait_for_icims_otp."""
    def __init__(self, code=None, raise_timeout=False):
        self._code = code
        self._raise = raise_timeout
        self.calls = 0
    def wait_for_icims_otp(self, timeout_seconds=90, since_epoch=None):
        self.calls += 1
        if self._raise:
            raise TimeoutError("No iCIMS OTP within %ss" % timeout_seconds)
        return self._code


def test_detect_otp_gate_named_field():
    fr = OtpFrame(detect={"present": True, "segmented": False, "n": 1,
                          "sel": "#otp", "why": "named:otp"})
    res = ir.detect_otp_gate(OtpPage([fr]))
    assert res["present"] and res["segmented"] is False and res["sel"] == "#otp"


def test_detect_otp_gate_segmented():
    fr = OtpFrame(detect={"present": True, "segmented": True, "n": 6,
                          "sel": None, "why": "segmented:6"})
    res = ir.detect_otp_gate(OtpPage([fr]))
    assert res["present"] and res["segmented"] is True and res["n"] == 6


def test_detect_otp_gate_absent():
    fr = OtpFrame(detect={"present": False})
    assert ir.detect_otp_gate(OtpPage([fr]))["present"] is False


def test_handle_otp_gate_happy_path():
    fr = OtpFrame(detect={"present": True, "segmented": False, "n": 1,
                          "sel": "#otp", "why": "named:otp"})
    page = OtpPage([fr])
    gmail = FakeGmail(code="482913")
    res = ir.handle_otp_gate(page, gmail_mod=gmail, timeout=5)
    assert res["status"] == "passed"
    assert gmail.calls == 1
    assert fr.fill_calls and fr.continue_calls
    # exit code for a passed OTP run continues; uncertain/applied decide final code
    assert ir.exit_code_for({"status": "applied"}) == 0


def test_handle_otp_gate_segmented_fill():
    fr = OtpFrame(detect={"present": True, "segmented": True, "n": 6,
                          "sel": None, "why": "segmented:6"})
    res = ir.handle_otp_gate(OtpPage([fr]), gmail_mod=FakeGmail(code="730145"), timeout=5)
    assert res["status"] == "passed"
    assert fr.fill_calls[0][0] == "seg"          # used segmented fill path
    assert fr.fill_calls[0][1] == [list("730145")]  # digits passed per-cell


def test_handle_otp_gate_absent_noop():
    fr = OtpFrame(detect={"present": False})
    gmail = FakeGmail(code="999999")
    res = ir.handle_otp_gate(OtpPage([fr]), gmail_mod=gmail, timeout=5)
    assert res["status"] == "absent"
    assert gmail.calls == 0                       # never queried Gmail


def test_handle_otp_gate_timeout_maps_exit_10():
    fr = OtpFrame(detect={"present": True, "segmented": False, "n": 1,
                          "sel": "#otp", "why": "named:otp"})
    res = ir.handle_otp_gate(OtpPage([fr]), gmail_mod=FakeGmail(raise_timeout=True), timeout=2)
    assert res["status"] == "timeout"
    # The run() flow stamps status='otp_timeout' on this -> EXIT 10.
    assert ir.exit_code_for({"status": "otp_timeout"}) == 10
    assert ir.exit_code_for({"status": "blocked",
                             "block_reason": "icims-otp-timeout:empty-code"}) == 10


def test_fill_otp_single_strips_nondigits():
    fr = OtpFrame()
    out = ir.fill_otp(fr, " 48-29 13 ", segmented=False, n=1)
    assert out == "ok:482913"
    # single-field path passes [None, "482913"]
    assert fr.fill_calls[0] == ("single", [None, "482913"])


def test_exit_code_map_full():
    cases = {
        "applied": 0, "dryrun-ready": 0, "already_applied": 7, "closed": 6,
        "otp_timeout": 10, "uncertain": 3,
    }
    for st, code in cases.items():
        assert ir.exit_code_for({"status": st}) == code
    assert ir.exit_code_for({"status": "blocked",
                             "block_reason": "icims-no-submit-button"}) == 4
    assert ir.exit_code_for({"status": "blocked"}) == 2
