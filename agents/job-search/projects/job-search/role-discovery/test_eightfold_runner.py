#!/usr/bin/env python3
# test_eightfold_runner.py -- Unit tests for _eightfold_runner.py
# Mocked HTTP (no live network). Run: python3 -m pytest test_eightfold_runner.py -v
from __future__ import annotations
import json, sys, types, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

_PI_REAL = json.loads((Path(__file__).resolve().parents[1] / "personal-info.json").read_text())

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Minimal stubs so playwright does not need to be present for import
# ---------------------------------------------------------------------------
playwright_stub = types.ModuleType("playwright")
playwright_sync_stub = types.ModuleType("playwright.sync_api")
playwright_stub.sync_api = playwright_sync_stub
sys.modules["playwright"] = playwright_stub
sys.modules["playwright.sync_api"] = playwright_sync_stub

import _eightfold_runner as R

# Add sync_playwright as attribute to the stub so patch() can find it
import sys
sync_playwright_mock = MagicMock()
sys.modules["playwright.sync_api"].sync_playwright = sync_playwright_mock


class TestDeriveHelpers(unittest.TestCase):
    def test_derive_domain_netflix(self):
        url = "https://explore.jobs.netflix.net/careers/job/790316069889"
        self.assertEqual(R._derive_domain(url), "netflix.com")

    def test_derive_domain_starbucks(self):
        url = "https://careers.starbucks.com/careers/apply?pid=12345678"
        self.assertEqual(R._derive_domain(url), "starbucks.com")

    def test_derive_host(self):
        url = "https://explore.jobs.netflix.net/careers/job/790316069889"
        self.assertEqual(R._derive_host(url), "explore.jobs.netflix.net")

    def test_pid_from_url_careers_job(self):
        url = "https://explore.jobs.netflix.net/careers/job/790316069889"
        self.assertEqual(R._pid_from_url(url), "790316069889")

    def test_pid_from_url_query_param(self):
        url = "https://explore.jobs.netflix.net/careers/apply?pid=790316069889"
        self.assertEqual(R._pid_from_url(url), "790316069889")

    def test_pid_from_url_path_digit(self):
        url = "https://explore.jobs.netflix.net/careers/apply/790316069889/"
        result = R._pid_from_url(url)
        self.assertEqual(result, "790316069889")

    def test_build_apply_url(self):
        url = R._build_apply_url("https://explore.jobs.netflix.net/careers/job/123456789",
                                  "123456789", "explore.jobs.netflix.net")
        self.assertEqual(url, "https://explore.jobs.netflix.net/careers/apply?pid=123456789")

    def test_build_apply_url_already_apply(self):
        url = "https://explore.jobs.netflix.net/careers/apply?pid=123456789"
        result = R._build_apply_url(url, "123456789", "explore.jobs.netflix.net")
        self.assertEqual(result, url)


class TestJSPayloads(unittest.TestCase):
    def test_js_upload_resume_is_string(self):
        self.assertIsInstance(R.JS_UPLOAD_RESUME, str)
        self.assertIn("fetch(uploadUrl", R.JS_UPLOAD_RESUME)
        self.assertIn("FormData", R.JS_UPLOAD_RESUME)
        self.assertIn("resume", R.JS_UPLOAD_RESUME)

    def test_js_submit_is_string(self):
        # JS_SUBMIT replaced by button-click approach; verify new hook scripts exist
        self.assertIsInstance(R.JS_HOOK_FETCH, str)
        self.assertIn("ef_submit_result", R.JS_HOOK_FETCH)
        self.assertIsInstance(R.JS_READ_SUBMIT_RESULT, str)
        self.assertIn("ef_submit_result", R.JS_READ_SUBMIT_RESULT)

    def test_js_get_page_state_is_string(self):
        self.assertIsInstance(R.JS_GET_PAGE_STATE, str)
        self.assertIn("csrf", R.JS_GET_PAGE_STATE)
        self.assertIn("pids", R.JS_GET_PAGE_STATE)
        self.assertIn("EF_REDUX_STORE", R.JS_GET_PAGE_STATE)

    def test_js_check_confirmation_is_string(self):
        self.assertIsInstance(R.JS_CHECK_CONFIRMATION, str)
        self.assertIn("thankYou", R.JS_CHECK_CONFIRMATION)


def _make_page(csrf="test-csrf-token", pids="790316069889", extra_qs=None):
    # Build a mock Playwright page for unit testing.
    page = MagicMock()
    page.url = "https://explore.jobs.netflix.net/careers/apply?pid=790316069889"
    page_state = {
        "csrf": csrf,
        "pids": pids,
        "formPresent": True,
        "recaptchaSitekey": None,
        "recaptchaEnterprise": False,
        "extraQs": extra_qs or [],
        "url": page.url,
    }
    upload_response = {
        "ok": True,
        "status": 200,
        "data": {
            "status": 200,
            "data": {
                "profile": {
                    "encId": "testEncId123",
                    "resumeFilename": "Cyrus_Shekari_Resume.pdf",
                    "hasResume": True,
                }
            }
        }
    }
    # Button-click submit: runner reads JS_READ_SUBMIT_RESULT to get the response
    submit_response = {"ok": True, "status": 201, "data": {"status": 201}}
    confirm_response = {
        "confirmed": True,
        "thank_you": True,
        "form_gone": True,
        "confirm_url": False,
        "confirm_element": True,
        "snippet": "Thank you for applying!",
        "url": "https://explore.jobs.netflix.net/careers/apply/success",
        "body_sample": "Thank you for applying!",
    }
    _hook_called = [False]
    _read_calls = [0]
    def evaluate_side_effect(js, *args):
        if "JS_GET_PAGE_STATE" in js or ("csrf" in js and "pids" in js and "EF_REDUX_STORE" in js):
            return page_state
        if js == R.JS_GET_PAGE_STATE:
            return page_state
        if js == R.JS_UPLOAD_RESUME:
            return upload_response
        if js == R.JS_HOOK_FETCH:
            _hook_called[0] = True
            return None
        if js == R.JS_READ_SUBMIT_RESULT:
            # Return submit_response only once hook was called
            _read_calls[0] += 1
            if _hook_called[0] and _read_calls[0] >= 1:
                return submit_response
            return None  # Not yet available
        if js == R.JS_CHECK_CONFIRMATION:
            return confirm_response
        return {"ok": True, "status": 200, "data": {}}
    page.evaluate.side_effect = evaluate_side_effect
    # Mock locator for button click
    btn_mock = MagicMock()
    btn_mock.count.return_value = 1
    btn_mock.first = btn_mock
    def locator_side_effect(selector):
        if "Submit application" in selector:
            return btn_mock
        loc = MagicMock()
        loc.count.return_value = 0
        return loc
    page.locator.side_effect = locator_side_effect
    return page, page_state, upload_response, submit_response, confirm_response


PERSONAL_INFO = {
    "identity": {"first_name": _PI_REAL["identity"]["first_name"], "last_name": _PI_REAL["identity"]["last_name"]},
    "contact": {"email": _PI_REAL["contact"]["email"], "phone": _PI_REAL["contact"]["phone"]},
    "address": {"city": _PI_REAL["address"]["city"], "state": _PI_REAL["address"]["state"]},
    "work_authorization": {"authorized_to_work_us": "yes", "status": "us_citizen"},
    "common_form_answers": {"how_did_you_hear_about_us": "LinkedIn"},
}


class TestRunEightfold(unittest.TestCase):
    def setUp(self):
        # Create a minimal fake PDF
        import tempfile, os
        self.tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        self.tmp.write(b"%PDF-1.4 fake\n")
        self.tmp.close()
        self.resume_path = self.tmp.name

    def tearDown(self):
        import os
        try:
            os.unlink(self.resume_path)
        except Exception:
            pass

    def _run(self, dry_run=False, page_override=None, pids="790316069889"):
        page, ps, up_resp, sub_resp, conf_resp = _make_page(pids=pids)
        if page_override:
            page = page_override
        mock_browser = MagicMock()
        mock_browser.contexts = [MagicMock()]
        mock_browser.contexts[0].new_page.return_value = page
        # _make_page already sets up evaluate.side_effect and locator.side_effect
        page.url = "https://explore.jobs.netflix.net/careers/apply?pid=790316069889"

        with patch.object(sys.modules["playwright.sync_api"], "sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
            result = R.run_eightfold(
                role_id=2880,
                apply_url="https://explore.jobs.netflix.net/careers/job/790316069889",
                personal_info=PERSONAL_INFO,
                resume_pdf_path=self.resume_path,
                dry_run=dry_run,
            )
        return result

    def test_dryrun_returns_dryrun_status(self):
        result = self._run(dry_run=True)
        self.assertEqual(result["status"], "dryrun")
        self.assertEqual(result["enc_id"], "testEncId123")
        self.assertEqual(result["pids"], "790316069889")
        self.assertIn("enc_id", result["confirmation"])

    def test_live_returns_submitted_status(self):
        result = self._run(dry_run=False)
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["enc_id"], "testEncId123")
        self.assertEqual(result["pids"], "790316069889")

    def test_missing_resume_returns_error(self):
        import os
        page, ps, up_resp, sub_resp, conf_resp = _make_page()
        with patch("playwright.sync_api.sync_playwright"):
            result = R.run_eightfold(
                role_id=2880,
                apply_url="https://explore.jobs.netflix.net/careers/job/790316069889",
                personal_info=PERSONAL_INFO,
                resume_pdf_path="/nonexistent/resume.pdf",
                dry_run=True,
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["error"])

    def test_csrf_not_found_returns_error(self):
        page, ps, up_resp, sub_resp, conf_resp = _make_page(csrf=None)
        mock_browser = MagicMock()
        mock_browser.contexts = [MagicMock()]
        mock_browser.contexts[0].new_page.return_value = page

        def ev(js, *args):
            if js == R.JS_GET_PAGE_STATE:
                return {"csrf": None, "pids": "790316069889", "extraQs": [], "url": ""}
            return {"ok": True, "status": 200, "data": {}}
        page.evaluate.side_effect = ev
        page.url = "https://explore.jobs.netflix.net/careers/apply?pid=790316069889"

        with patch.object(sys.modules["playwright.sync_api"], "sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
            result = R.run_eightfold(2880,
                "https://explore.jobs.netflix.net/careers/job/790316069889",
                PERSONAL_INFO, self.resume_path, dry_run=True)
        self.assertEqual(result["status"], "error")
        self.assertIn("CSRF", result["error"])

    def test_pids_not_found_returns_error(self):
        page, ps, up_resp, sub_resp, conf_resp = _make_page(pids=None)
        mock_browser = MagicMock()
        mock_browser.contexts = [MagicMock()]
        mock_browser.contexts[0].new_page.return_value = page

        def ev(js, *args):
            if js == R.JS_GET_PAGE_STATE:
                return {"csrf": "test-csrf", "pids": None, "extraQs": [], "url": ""}
            return {"ok": True, "status": 200, "data": {}}
        page.evaluate.side_effect = ev
        page.url = "https://explore.jobs.netflix.net/careers/apply?pid=xxx"

        # Use a URL with no extractable pid
        with patch.object(sys.modules["playwright.sync_api"], "sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
            result = R.run_eightfold(2880,
                "https://explore.jobs.netflix.net/careers/apply",
                PERSONAL_INFO, self.resume_path, dry_run=True)
        self.assertEqual(result["status"], "error")
        self.assertIn("pids", result["error"])

    def test_upload_failure_returns_error(self):
        page, ps, up_resp, sub_resp, conf_resp = _make_page()
        mock_browser = MagicMock()
        mock_browser.contexts = [MagicMock()]
        mock_browser.contexts[0].new_page.return_value = page

        _hook_called = [False]
        def ev(js, *args):
            if js == R.JS_GET_PAGE_STATE:
                return {"csrf": "test-csrf", "pids": "790316069889", "extraQs": [], "url": ""}
            if js == R.JS_UPLOAD_RESUME:
                return {"ok": False, "status": 403, "data": {"error": "forbidden"}}
            if js == R.JS_HOOK_FETCH:
                _hook_called[0] = True
                return None
            if js == R.JS_READ_SUBMIT_RESULT:
                return {"ok": True, "status": 201, "data": {}} if _hook_called[0] else None
            if js == R.JS_CHECK_CONFIRMATION:
                return conf_resp
            return {"ok": True, "status": 200, "data": {}}
        page.evaluate.side_effect = ev
        page.url = "https://explore.jobs.netflix.net/careers/apply?pid=790316069889"

        with patch.object(sys.modules["playwright.sync_api"], "sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
            result = R.run_eightfold(2880,
                "https://explore.jobs.netflix.net/careers/job/790316069889",
                PERSONAL_INFO, self.resume_path, dry_run=False)
        self.assertEqual(result["status"], "error")
        self.assertIn("403", result["error"])

    def test_submit_422_returns_error(self):
        import os as _os
        _os.environ["EF_SUBMIT_WAIT_ITERS"] = "1"  # Speed up test
        page, ps, up_resp, sub_resp, conf_resp = _make_page()
        mock_browser = MagicMock()
        mock_browser.contexts = [MagicMock()]
        mock_browser.contexts[0].new_page.return_value = page

        _hook_called = [False]
        def ev(js, *args):
            if js == R.JS_GET_PAGE_STATE:
                return {"csrf": "test-csrf", "pids": "790316069889", "extraQs": [], "url": ""}
            if js == R.JS_UPLOAD_RESUME:
                return up_resp
            if js == R.JS_HOOK_FETCH:
                _hook_called[0] = True
                return None
            if js == R.JS_READ_SUBMIT_RESULT:
                return {"ok": False, "status": 422, "data": {"error": "missing pids"}} if _hook_called[0] else None
            if js == R.JS_CHECK_CONFIRMATION:
                return conf_resp
            return {"ok": True, "status": 200, "data": {}}
        page.evaluate.side_effect = ev
        page.url = "https://explore.jobs.netflix.net/careers/apply?pid=790316069889"

        try:
            with patch.object(sys.modules["playwright.sync_api"], "sync_playwright") as mock_pw:
                mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
                result = R.run_eightfold(2880,
                    "https://explore.jobs.netflix.net/careers/job/790316069889",
                    PERSONAL_INFO, self.resume_path, dry_run=False)
        finally:
            _os.environ.pop("EF_SUBMIT_WAIT_ITERS", None)
        self.assertEqual(result["status"], "error")
        self.assertIn("422", result["error"])

    def test_captcha_block_returns_blocked(self):
        # With button-click approach, "no response in N iters" = blocked (reCAPTCHA blocking)
        import os as _os
        _os.environ["EF_SUBMIT_WAIT_ITERS"] = "1"  # Speed up test
        page, ps, up_resp, sub_resp, conf_resp = _make_page()
        mock_browser = MagicMock()
        mock_browser.contexts = [MagicMock()]
        mock_browser.contexts[0].new_page.return_value = page

        def ev(js, *args):
            if js == R.JS_GET_PAGE_STATE:
                return {"csrf": "test-csrf", "pids": "790316069889", "extraQs": [], "url": "", "recaptchaSitekey": None}
            if js == R.JS_UPLOAD_RESUME:
                return up_resp
            if js == R.JS_HOOK_FETCH:
                return None
            if js == R.JS_READ_SUBMIT_RESULT:
                # reCAPTCHA blocked: no response captured
                return None
            if js == R.JS_CHECK_CONFIRMATION:
                return {"confirmed": False, "thank_you": False, "form_gone": False, "snippet": "", "url": "", "body_sample": ""}
            return {"ok": True, "status": 200, "data": {}}
        page.evaluate.side_effect = ev
        page.url = "https://explore.jobs.netflix.net/careers/apply?pid=790316069889"

        try:
            with patch.object(sys.modules["playwright.sync_api"], "sync_playwright") as mock_pw:
                mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
                result = R.run_eightfold(2880,
                    "https://explore.jobs.netflix.net/careers/job/790316069889",
                    PERSONAL_INFO, self.resume_path, dry_run=False)
        finally:
            _os.environ.pop("EF_SUBMIT_WAIT_ITERS", None)
        self.assertEqual(result["status"], "blocked")


class TestExtraQuestions(unittest.TestCase):
    def test_work_auth_yes(self):
        page = MagicMock()
        page.locator.return_value.count.return_value = 0
        qs = [{"id": "q1", "label": "Are you legally authorized to work in the US?"}]
        answers = R._handle_extra_questions(page, qs, PERSONAL_INFO, 0)
        self.assertEqual(answers["q1"], "Yes")

    def test_sponsorship_no(self):
        page = MagicMock()
        page.locator.return_value.count.return_value = 0
        qs = [{"id": "q2", "label": "Will you require visa sponsorship?"}]
        answers = R._handle_extra_questions(page, qs, PERSONAL_INFO, 0)
        self.assertEqual(answers["q2"], "No")

    def test_background_check_yes(self):
        page = MagicMock()
        page.locator.return_value.count.return_value = 0
        qs = [{"id": "q3", "label": "Are you willing to undergo a background check?"}]
        answers = R._handle_extra_questions(page, qs, PERSONAL_INFO, 0)
        self.assertEqual(answers["q3"], "Yes")


if __name__ == "__main__":
    unittest.main()
