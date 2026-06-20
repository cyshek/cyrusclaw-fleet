"""Tests for _workable_runner answer heuristics + option-picking (Cyrus: US
citizen, no sponsorship, authorized, open to relocate/onsite, 18+, EEO->decline).
Run: python3 -m pytest test_workable_runner.py -q
Importing the module is safe — playwright is imported lazily inside run()."""
import importlib.util, os

_spec = importlib.util.spec_from_file_location(
    "_workable_runner", os.path.join(os.path.dirname(__file__), "_workable_runner.py"))
wr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wr)


def test_sponsorship_is_no():
    assert wr.classify_question("Do you now or in the future require visa sponsorship?") == "no"
    assert wr.classify_question("Will you require H-1B sponsorship?") == "no"


def test_authorization_is_yes():
    assert wr.classify_question("Are you legally authorized to work in the United States?") == "yes"
    assert wr.classify_question("Do you have the right to work in the US?") == "yes"


def test_former_employee_is_no():
    assert wr.classify_question("Are you a former employee of Unusual Machines?") == "no"
    assert wr.classify_question("Have you previously worked here?") == "no"


def test_affirm_willingness_is_yes():
    assert wr.classify_question("Are you willing to relocate to Orlando?") == "yes"
    assert wr.classify_question("Are you comfortable working on-site/hybrid?") == "yes"
    assert wr.classify_question("Are you at least 18 years of age?") == "yes"
    assert wr.classify_question("Are you available to start within 2 weeks?") == "yes"


def test_eeo_is_decline():
    assert wr.classify_question("What is your gender?") == "decline"
    assert wr.classify_question("Race / Ethnicity (voluntary self-identification)") == "decline"
    assert wr.classify_question("Veteran status") == "decline"
    assert wr.classify_question("Do you have a disability?") == "decline"


def test_unknown_defaults_yes():
    assert wr.classify_question("Have you read the job description?") == "yes"


def test_pick_option_yes_no():
    opts = ["Yes", "No"]
    assert wr.pick_option(opts, "yes") == "Yes"
    assert wr.pick_option(opts, "no") == "No"


def test_pick_option_decline_prefers_decline_label():
    opts = ["Male", "Female", "Prefer not to disclose"]
    assert wr.pick_option(opts, "decline") == "Prefer not to disclose"
    opts2 = ["Yes", "No", "I do not wish to answer"]
    assert wr.pick_option(opts2, "decline") == "I do not wish to answer"


def test_pick_option_decline_falls_back_to_no_when_no_decline_label():
    # If no decline option exists, decline collapses to a No-ish answer.
    opts = ["Yes", "No"]
    assert wr.pick_option(opts, "decline") == "No"


def test_pick_option_no_match_returns_none():
    assert wr.pick_option(["Apple", "Banana"], "yes") is None
    assert wr.pick_option([], "yes") is None


def test_apply_url_from():
    base = "https://apply.workable.com/unusual-machines/j/AA281C63AF/"
    assert wr.apply_url_from(base) == base + "apply/"
    assert wr.apply_url_from(base.rstrip("/")) == base + "apply/"
    assert wr.apply_url_from(base + "apply") == base + "apply/"


def test_personal_constants():
    assert wr.EMAIL == "cyshekari@gmail.com"
    assert wr.PHONE == "3468040227"
    assert wr.FIRST == "Cyrus" and wr.LAST == "Shekari"


def test_classify_returns_valid_enum():
    for q in ["random text", "gender", "sponsorship visa", "authorized to work",
              "willing to relocate", "former employee"]:
        assert wr.classify_question(q) in ("yes", "no", "decline", "text")


# ---- Turnstile + tailored-answer regression (added 2026-06-03 after 2 real
# confirmed Workable submits via 2Captcha Turnstile) -------------------------

class _FakePage:
    """Minimal page stub for detect_turnstile: serves a scripted sequence of
    window.__cfParams states and records scroll calls."""
    def __init__(self, cfparams_seq, frames_urls=None):
        self._seq = list(cfparams_seq)
        self.frames = [type("F", (), {"url": u})() for u in (frames_urls or [])]
        self.scrolls = 0
        self.waits = 0
    def evaluate(self, js, *a):
        if "__cfParams" in js:
            return self._seq.pop(0) if self._seq else []
        if "data-sitekey" in js:
            return None
        if "scrollTo" in js:
            self.scrolls += 1
            return None
        return None
    def wait_for_timeout(self, ms):
        self.waits += 1


def test_detect_turnstile_reads_cfparams_sitekey_and_action():
    pg = _FakePage([[{"sitekey": "0xABC", "action": "application-form-submit"}]])
    sk, action = wr.detect_turnstile(pg, wait_ms=2000)
    assert sk == "0xABC"
    assert action == "application-form-submit"


def test_detect_turnstile_retries_until_widget_mounts():
    # First poll empty (widget not mounted yet), second poll has params.
    pg = _FakePage([[], [{"sitekey": "0xLATE", "action": "submit"}]])
    sk, action = wr.detect_turnstile(pg, wait_ms=3000)
    assert sk == "0xLATE"
    assert pg.scrolls >= 1  # nudged the widget to mount


def test_detect_turnstile_from_iframe_url():
    pg = _FakePage([[]], frames_urls=["https://challenges.cloudflare.com/turnstile/v0/?k=0xFRAME"])
    sk, action = wr.detect_turnstile(pg, wait_ms=1500)
    assert sk == "0xFRAME"


def test_id_field_regex_matches_job_id_variants():
    for lbl in ["Job ID", "Requisition #", "Posting ID", "Reference Code", "Vacancy ID"]:
        assert wr.ID_FIELD_RE.search(lbl), lbl
    # not a code field
    assert not wr.ID_FIELD_RE.search("Describe your product experience")


def test_location_is_cyrus_real_kirkland_not_orlando():
    assert "Kirkland" in wr.ADDRESS and wr.CITY == "Kirkland"
    assert wr.POSTCODE == "98033"
    assert "Orlando" not in wr.ADDRESS


def test_build_tailored_answers_id_field_gets_code_not_prose():
    qs = [{"kind": "text", "name": "QA_1", "req": True, "label": "Job ID"}]
    out = wr.build_tailored_answers(qs, "Acme", "PM", "", job_code="ABC123")
    assert out.get("QA_1") == "ABC123"
