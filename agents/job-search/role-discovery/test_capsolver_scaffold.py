#!/usr/bin/env python3
"""
test_capsolver_scaffold.py — Tests for the CapSolver scaffolding shipped
2026-05-27.

Covers three modules:
    1. capsolver_client.CapSolverClient — API-key gating, payload shape,
       response parsing, retry/backoff logic. All requests mocked.
    2. captcha_presubmit.solve_and_inject_recaptcha_v3 — runner integration:
       env-flag off = no client call; env-flag on but no key = clean
       fallback; mocked successful token = injection JS emitted correctly.
    3. greenhouse_iframe_runner / ashby_filler wiring — the brief asks
       us to verify the runners are wired but tolerant.

Run with:
    cd projects/job-search/role-discovery
    .venv/bin/python -m unittest test_capsolver_scaffold -v

NO real network calls. NO real captcha solves. ENABLE_CAPSOLVER and
CAPSOLVER_API_KEY are surgically set/unset per-test via unittest.mock.patch.dict.
"""
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

# Make role-discovery dir importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ---------------------------------------------------------------------------
# Test fixture: fake `requests.Session` that records POST calls and returns
# scripted responses.
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


class FakeSession:
    """Records POSTs, returns scripted responses in order."""

    def __init__(self, responses):
        # responses can be a list of FakeResponse OR a list of (predicate, response)
        # OR a callable(url, payload) -> FakeResponse.
        self.responses = list(responses)
        self.calls = []  # list of (url, payload)

    def post(self, url, json=None, timeout=None):  # noqa: A002 (shadow built-in)
        self.calls.append({"url": url, "payload": json, "timeout": timeout})
        if callable(self.responses):
            return self.responses(url, json)
        if not self.responses:
            raise AssertionError(
                f"FakeSession: ran out of scripted responses at call {len(self.calls)}: "
                f"url={url} payload={json}"
            )
        resp = self.responses.pop(0)
        return resp


# Avoid real sleeps in retry tests.
@mock.patch("capsolver_client.time.sleep", lambda *_a, **_k: None)
class CapSolverClientTests(unittest.TestCase):
    """Tests for capsolver_client.CapSolverClient."""

    # -- API key gating --------------------------------------------------

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_construct_raises_when_env_var_missing(self):
        # Defensive scrub — clear=False above just merges; we still need to
        # remove CAPSOLVER_API_KEY for this test.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPSOLVER_API_KEY", None)
            from capsolver_client import CapSolverClient, CapSolverDisabled
            with self.assertRaises(CapSolverDisabled):
                CapSolverClient()

    def test_construct_explicit_key_overrides_env(self):
        from capsolver_client import CapSolverClient
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPSOLVER_API_KEY", None)
            client = CapSolverClient(api_key="explicit-key")
            self.assertEqual(client.api_key, "explicit-key")

    def test_construct_reads_env_var(self):
        from capsolver_client import CapSolverClient
        with mock.patch.dict(os.environ, {"CAPSOLVER_API_KEY": "env-key-123"}, clear=False):
            client = CapSolverClient()
            self.assertEqual(client.api_key, "env-key-123")

    def test_construct_does_not_read_keyfile(self):
        """Explicit anti-feature: the brief-spec client MUST NOT fall back
        to .capsolver-key. That's the multi-vendor client's job."""
        from capsolver_client import CapSolverClient, CapSolverDisabled
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPSOLVER_API_KEY", None)
            # Even if a keyfile would have existed, we don't read it.
            with self.assertRaises(CapSolverDisabled):
                CapSolverClient()

    # -- payload shape ---------------------------------------------------

    def _client_with(self, responses):
        from capsolver_client import CapSolverClient
        session = FakeSession(responses)
        client = CapSolverClient(
            api_key="k",
            session=session,
            poll_interval_s=0,
            timeout_s=10,
        )
        return client, session

    def test_recaptcha_v3_enterprise_payload_shape(self):
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "T1"}),
            FakeResponse(200, {
                "errorId": 0, "status": "ready",
                "solution": {"gRecaptchaResponse": "tok-v3-ent"},
            }),
        ]
        client, sess = self._client_with(responses)
        out = client.recaptcha_v3_enterprise(
            sitekey="SK", page_url="https://x/y", action="login", min_score=0.5,
        )
        self.assertEqual(out, "tok-v3-ent")
        # First call = createTask.
        create_call = sess.calls[0]
        self.assertEqual(create_call["url"], "https://api.capsolver.com/createTask")
        self.assertEqual(create_call["payload"]["clientKey"], "k")
        task = create_call["payload"]["task"]
        self.assertEqual(task["type"], "ReCaptchaV3EnterpriseTaskProxyless")
        self.assertEqual(task["websiteURL"], "https://x/y")
        self.assertEqual(task["websiteKey"], "SK")
        self.assertEqual(task["pageAction"], "login")
        self.assertEqual(task["minScore"], 0.5)
        # Second call = getTaskResult.
        poll_call = sess.calls[1]
        self.assertEqual(poll_call["url"], "https://api.capsolver.com/getTaskResult")
        self.assertEqual(poll_call["payload"]["taskId"], "T1")

    def test_recaptcha_v3_non_enterprise_payload_shape(self):
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "T2"}),
            FakeResponse(200, {
                "errorId": 0, "status": "ready",
                "solution": {"gRecaptchaResponse": "tok-v3"},
            }),
        ]
        client, sess = self._client_with(responses)
        out = client.recaptcha_v3(
            sitekey="ASHBY-SK", page_url="https://jobs.ashbyhq.com/openai/x",
            action="submit", min_score=0.7,
        )
        self.assertEqual(out, "tok-v3")
        task = sess.calls[0]["payload"]["task"]
        self.assertEqual(task["type"], "ReCaptchaV3TaskProxyless")
        self.assertEqual(task["pageAction"], "submit")

    def test_hcaptcha_payload_shape(self):
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "T3"}),
            FakeResponse(200, {
                "errorId": 0, "status": "ready",
                "solution": {"gRecaptchaResponse": "tok-hcap"},
            }),
        ]
        client, sess = self._client_with(responses)
        out = client.hcaptcha(sitekey="HSK", page_url="https://jobs.lever.co/foo")
        self.assertEqual(out, "tok-hcap")
        task = sess.calls[0]["payload"]["task"]
        self.assertEqual(task["type"], "HCaptchaTaskProxyless")
        self.assertEqual(task["websiteKey"], "HSK")
        # hCaptcha task has NO pageAction or minScore.
        self.assertNotIn("pageAction", task)
        self.assertNotIn("minScore", task)

    def test_turnstile_payload_shape(self):
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "T4"}),
            FakeResponse(200, {
                "errorId": 0, "status": "ready",
                "solution": {"token": "tok-turn"},
            }),
        ]
        client, sess = self._client_with(responses)
        out = client.turnstile(sitekey="TSK", page_url="https://x/y")
        self.assertEqual(out, "tok-turn")
        task = sess.calls[0]["payload"]["task"]
        self.assertEqual(task["type"], "AntiTurnstileTaskProxyless")

    # -- response parsing & error mapping --------------------------------

    def test_solution_key_priority(self):
        """For hCaptcha we try multiple solution keys; first wins."""
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "T5"}),
            FakeResponse(200, {
                "errorId": 0, "status": "ready",
                "solution": {"captchaResponse": "fallback", "gRecaptchaResponse": "first"},
            }),
        ]
        client, _sess = self._client_with(responses)
        self.assertEqual(client.hcaptcha("SK", "https://x"), "first")

    def test_ready_but_no_token_raises(self):
        from capsolver_client import CapSolverError
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "T6"}),
            FakeResponse(200, {
                "errorId": 0, "status": "ready",
                "solution": {"unrelated_key": "x"},
            }),
        ]
        client, _ = self._client_with(responses)
        with self.assertRaises(CapSolverError) as cm:
            client.hcaptcha("SK", "https://x")
        self.assertIn("ready but no token", str(cm.exception))

    def test_create_task_no_task_id_raises(self):
        from capsolver_client import CapSolverError
        responses = [FakeResponse(200, {"errorId": 0})]  # no taskId
        client, _ = self._client_with(responses)
        with self.assertRaises(CapSolverError) as cm:
            client.hcaptcha("SK", "https://x")
        self.assertIn("no taskId", str(cm.exception))

    def test_balance_error_classified_as_quota(self):
        from capsolver_client import CapSolverQuotaExceeded
        responses = [
            FakeResponse(200, {
                "errorId": 1, "errorCode": "ERROR_KEY_DOES_NOT_EXIST",
                "errorDescription": "Account balance is too low",
            }),
        ]
        client, _ = self._client_with(responses)
        with self.assertRaises(CapSolverQuotaExceeded):
            client.hcaptcha("SK", "https://x")

    def test_processing_then_ready_polls_correctly(self):
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "Tpoll"}),
            FakeResponse(200, {"errorId": 0, "status": "processing"}),
            FakeResponse(200, {"errorId": 0, "status": "processing"}),
            FakeResponse(200, {"errorId": 0, "status": "ready",
                              "solution": {"gRecaptchaResponse": "tok-poll"}}),
        ]
        client, sess = self._client_with(responses)
        out = client.recaptcha_v3("SK", "https://x")
        self.assertEqual(out, "tok-poll")
        self.assertEqual(len(sess.calls), 4)

    def test_timeout_raises_after_deadline(self):
        from capsolver_client import CapSolverTimeout, CapSolverClient
        responses = [
            FakeResponse(200, {"errorId": 0, "taskId": "Ttimeout"}),
        ] + [FakeResponse(200, {"errorId": 0, "status": "processing"})] * 50
        sess = FakeSession(responses)
        # timeout_s=0 -> immediately past deadline on first poll attempt.
        client = CapSolverClient(
            api_key="k", session=sess, poll_interval_s=0, timeout_s=0,
        )
        with self.assertRaises(CapSolverTimeout):
            client.hcaptcha("SK", "https://x")

    # -- 429 retry / backoff ---------------------------------------------

    def test_429_retries_then_succeeds(self):
        # First two POSTs to createTask get 429, third succeeds.
        responses = [
            FakeResponse(429, text="rate", headers={"Retry-After": "0"}),
            FakeResponse(429, text="rate", headers={"Retry-After": "0"}),
            FakeResponse(200, {"errorId": 0, "taskId": "T-retry"}),
            FakeResponse(200, {
                "errorId": 0, "status": "ready",
                "solution": {"gRecaptchaResponse": "won-after-retry"},
            }),
        ]
        client, sess = self._client_with(responses)
        out = client.recaptcha_v3("SK", "https://x")
        self.assertEqual(out, "won-after-retry")
        # 2 retries + 1 success on createTask, then 1 poll = 4 calls.
        self.assertEqual(len(sess.calls), 4)

    def test_429_exhausts_retries_then_raises(self):
        from capsolver_client import CapSolverRateLimited, CapSolverClient
        responses = [
            FakeResponse(429, text="rate", headers={"Retry-After": "0"}),
        ] * 10
        sess = FakeSession(responses)
        client = CapSolverClient(
            api_key="k", session=sess, poll_interval_s=0,
            max_retries=2,  # 1 initial + 2 retries = 3 attempts
        )
        with self.assertRaises(CapSolverRateLimited):
            client.recaptcha_v3("SK", "https://x")
        self.assertEqual(len(sess.calls), 3)

    def test_4xx_non_429_raises_immediately_no_retry(self):
        from capsolver_client import CapSolverError, CapSolverClient
        responses = [FakeResponse(500, text="boom")]
        sess = FakeSession(responses)
        client = CapSolverClient(
            api_key="k", session=sess, poll_interval_s=0, max_retries=5,
        )
        with self.assertRaises(CapSolverError) as cm:
            client.recaptcha_v3("SK", "https://x")
        self.assertIn("HTTP 500", str(cm.exception))
        self.assertEqual(len(sess.calls), 1)

    def test_non_json_response_raises(self):
        from capsolver_client import CapSolverError, CapSolverClient
        bad = FakeResponse(200, payload=None, text="<html>oops</html>")
        # Force .json() to fail (already does because payload=None)
        sess = FakeSession([bad])
        client = CapSolverClient(
            api_key="k", session=sess, poll_interval_s=0,
        )
        with self.assertRaises(CapSolverError) as cm:
            client.recaptcha_v3("SK", "https://x")
        self.assertIn("non-JSON", str(cm.exception))

    # -- get_balance -----------------------------------------------------

    def test_get_balance_success(self):
        responses = [FakeResponse(200, {"errorId": 0, "balance": 12.34})]
        client, _ = self._client_with(responses)
        self.assertEqual(client.get_balance(), 12.34)

    def test_get_balance_error(self):
        from capsolver_client import CapSolverError
        responses = [FakeResponse(200, {"errorId": 1, "errorDescription": "bad key"})]
        client, _ = self._client_with(responses)
        with self.assertRaises(CapSolverError):
            client.get_balance()


class IsEnabledTests(unittest.TestCase):
    """Tests for capsolver_client.is_enabled()."""

    def test_disabled_when_no_env(self):
        from capsolver_client import is_enabled
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPSOLVER_API_KEY", None)
            os.environ.pop("ENABLE_CAPSOLVER", None)
            self.assertFalse(is_enabled())

    def test_disabled_when_only_key_set(self):
        from capsolver_client import is_enabled
        with mock.patch.dict(os.environ, {"CAPSOLVER_API_KEY": "k"}, clear=False):
            os.environ.pop("ENABLE_CAPSOLVER", None)
            self.assertFalse(is_enabled())

    def test_disabled_when_only_flag_set(self):
        from capsolver_client import is_enabled
        with mock.patch.dict(os.environ, {"ENABLE_CAPSOLVER": "1"}, clear=False):
            os.environ.pop("CAPSOLVER_API_KEY", None)
            self.assertFalse(is_enabled())

    def test_enabled_when_both_set(self):
        from capsolver_client import is_enabled
        with mock.patch.dict(
            os.environ,
            {"CAPSOLVER_API_KEY": "k", "ENABLE_CAPSOLVER": "1"},
            clear=False,
        ):
            self.assertTrue(is_enabled())

    def test_disabled_when_flag_is_zero(self):
        from capsolver_client import is_enabled
        with mock.patch.dict(
            os.environ,
            {"CAPSOLVER_API_KEY": "k", "ENABLE_CAPSOLVER": "0"},
            clear=False,
        ):
            self.assertFalse(is_enabled())


# ---------------------------------------------------------------------------
# Presubmit integration: solve_and_inject_recaptcha_v3
# ---------------------------------------------------------------------------

class FakeFrame:
    """Stand-in for Playwright Frame. evaluate(fn, arg=None) -> scripted result."""

    def __init__(self, scripts):
        # scripts: list of return values to hand back in order.
        self.scripts = list(scripts)
        self.calls = []  # list of (fn_str, arg)

    def evaluate(self, fn, arg=None):
        self.calls.append({"fn": fn, "arg": arg})
        if not self.scripts:
            raise AssertionError(
                f"FakeFrame: ran out of scripted return values at call "
                f"{len(self.calls)}"
            )
        result = self.scripts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class PresubmitTests(unittest.TestCase):
    """Tests for captcha_presubmit.solve_and_inject_recaptcha_v3."""

    def _env_off(self):
        return mock.patch.dict(os.environ, {}, clear=True)

    def _env_on_no_key(self):
        return mock.patch.dict(
            os.environ, {"ENABLE_CAPSOLVER": "1"}, clear=True,
        )

    def _env_on(self):
        return mock.patch.dict(
            os.environ,
            {"ENABLE_CAPSOLVER": "1", "CAPSOLVER_API_KEY": "test-key"},
            clear=True,
        )

    def test_disabled_returns_clean_noop(self):
        from captcha_presubmit import solve_and_inject_recaptcha_v3
        with self._env_off():
            frame = FakeFrame([])
            out = solve_and_inject_recaptcha_v3(frame)
            self.assertFalse(out["enabled"])
            self.assertFalse(out["injected"])
            # No evaluate calls at all.
            self.assertEqual(frame.calls, [])

    def test_flag_on_but_no_key_returns_clean_noop(self):
        from captcha_presubmit import solve_and_inject_recaptcha_v3
        with self._env_on_no_key():
            frame = FakeFrame([])
            out = solve_and_inject_recaptcha_v3(frame)
            # is_enabled() checks BOTH; without key -> disabled.
            self.assertFalse(out["enabled"])
            self.assertEqual(frame.calls, [])

    def test_enabled_no_sitekey_no_fallback_returns_failure(self):
        from captcha_presubmit import solve_and_inject_recaptcha_v3
        with self._env_on():
            # detect returns {sitekey: null}
            frame = FakeFrame([
                {"sitekey": None, "page_url": "https://x/y", "enterprise": False},
            ])
            out = solve_and_inject_recaptcha_v3(frame)
            self.assertTrue(out["enabled"])
            self.assertFalse(out["injected"])
            self.assertIn("no sitekey", out["reason"])

    def test_enabled_uses_fallback_sitekey_and_injects(self):
        from captcha_presubmit import solve_and_inject_recaptcha_v3, CapSolverClient
        with self._env_on():
            frame = FakeFrame([
                # detect: no sitekey found
                {"sitekey": None, "page_url": "https://jobs.ashbyhq.com/openai/x",
                 "enterprise": False},
                # inject result
                {"injected_into": ["g-recaptcha-response",
                                  "g-recaptcha-response-100000"],
                 "created": ["g-recaptcha-response-100000"],
                 "token_len": 24},
            ])
            # Mock client that returns a token.
            client = mock.MagicMock(spec=CapSolverClient)
            client.recaptcha_v3.return_value = "MOCK_TOKEN_XYZ123ABCDEFGH"
            out = solve_and_inject_recaptcha_v3(
                frame,
                fallback_sitekey="6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
                client=client,
            )
            self.assertTrue(out["injected"])
            self.assertEqual(out["sitekey"], "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y")
            self.assertEqual(out["token_len"], len("MOCK_TOKEN_XYZ123ABCDEFGH"))
            self.assertFalse(out["enterprise"])
            # Client called with right args.
            client.recaptcha_v3.assert_called_once_with(
                sitekey="6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
                page_url="https://jobs.ashbyhq.com/openai/x",
                action="submit",
                min_score=0.7,
            )
            # Frame got two evaluate calls (detect + inject).
            self.assertEqual(len(frame.calls), 2)
            # Second call passes the token as `arg`.
            self.assertEqual(frame.calls[1]["arg"], "MOCK_TOKEN_XYZ123ABCDEFGH")

    def test_enterprise_loader_auto_detected(self):
        from captcha_presubmit import solve_and_inject_recaptcha_v3, CapSolverClient
        with self._env_on():
            frame = FakeFrame([
                {"sitekey": "AUTO-SK", "page_url": "https://x/y",
                 "loader_src": "https://www.google.com/recaptcha/enterprise.js?render=AUTO-SK",
                 "enterprise": True},
                {"injected_into": ["g-recaptcha-response"], "created": [], "token_len": 5},
            ])
            client = mock.MagicMock(spec=CapSolverClient)
            client.recaptcha_v3_enterprise.return_value = "ENTOK"
            out = solve_and_inject_recaptcha_v3(frame, client=client)
            self.assertTrue(out["injected"])
            self.assertTrue(out["enterprise"])
            client.recaptcha_v3_enterprise.assert_called_once()
            client.recaptcha_v3.assert_not_called()

    def test_solver_error_returns_failure_no_inject(self):
        from captcha_presubmit import solve_and_inject_recaptcha_v3, CapSolverClient
        from capsolver_client import CapSolverError
        with self._env_on():
            frame = FakeFrame([
                {"sitekey": "SK", "page_url": "https://x/y", "enterprise": False},
            ])
            client = mock.MagicMock(spec=CapSolverClient)
            client.recaptcha_v3.side_effect = CapSolverError("boom")
            out = solve_and_inject_recaptcha_v3(frame, client=client)
            self.assertTrue(out["enabled"])
            self.assertFalse(out["injected"])
            self.assertIn("solver error", out["reason"])
            # Only the detect evaluate happened; no inject.
            self.assertEqual(len(frame.calls), 1)

    def test_inject_js_failure_returns_failure_with_token_len(self):
        from captcha_presubmit import solve_and_inject_recaptcha_v3, CapSolverClient
        with self._env_on():
            frame = FakeFrame([
                {"sitekey": "SK", "page_url": "https://x/y", "enterprise": False},
                RuntimeError("frame went away"),
            ])
            client = mock.MagicMock(spec=CapSolverClient)
            client.recaptcha_v3.return_value = "TOKEN-VALUE"
            out = solve_and_inject_recaptcha_v3(frame, client=client)
            self.assertTrue(out["enabled"])
            self.assertFalse(out["injected"])
            self.assertIn("inject-JS failed", out["reason"])
            self.assertEqual(out["token_len"], len("TOKEN-VALUE"))

    def test_detect_js_exception_handled_with_fallback(self):
        """If detect-JS crashes, we can still solve if a fallback_sitekey is given."""
        from captcha_presubmit import solve_and_inject_recaptcha_v3, CapSolverClient
        with self._env_on():
            frame = FakeFrame([
                RuntimeError("eval crash"),
                {"injected_into": ["g-recaptcha-response"], "created": [], "token_len": 4},
            ])
            client = mock.MagicMock(spec=CapSolverClient)
            client.recaptcha_v3.return_value = "TOK!"
            out = solve_and_inject_recaptcha_v3(
                frame,
                page_url="https://manual/url",
                fallback_sitekey="MANUAL-SK",
                client=client,
            )
            self.assertTrue(out["injected"])
            self.assertEqual(out["sitekey"], "MANUAL-SK")

    def test_hcaptcha_wrapper_disabled_returns_noop(self):
        from captcha_presubmit import solve_and_inject_hcaptcha
        with self._env_off():
            frame = FakeFrame([])
            out = solve_and_inject_hcaptcha(frame)
            self.assertFalse(out["enabled"])
            self.assertEqual(frame.calls, [])


# ---------------------------------------------------------------------------
# Runner / filler wiring smoke
# ---------------------------------------------------------------------------

class RunnerWiringTests(unittest.TestCase):
    """Smoke tests that the runner imports the helper without crashing
    and that the Ashby filler step now includes the driver_exec block."""

    def test_greenhouse_iframe_runner_imports_presubmit(self):
        """The runner module must reference captcha_presubmit; if someone
        renames the module, this test fails fast."""
        runner_path = Path(__file__).resolve().parent / "greenhouse_iframe_runner.py"
        src = runner_path.read_text()
        self.assertIn("from captcha_presubmit import", src)
        self.assertIn("solve_and_inject_recaptcha_v3", src)
        self.assertIn("ENABLE_CAPSOLVER", src)

    def test_ashby_filler_step_includes_driver_exec_block(self):
        """The strict-Ashby fix step must carry an executable driver_exec
        spec (not just a documentation comment)."""
        from ashby_filler import emit_steps
        # Minimal plan stub — emit_steps needs `plan['url']` and several fields.
        # Build the smallest valid plan that exercises the FIX 5 path.
        plan = {
            "url": "https://jobs.ashbyhq.com/openai/test",
            "text_fields": [],
            "radios": [],
            "checkboxes": [],
            "resume_path": "",
            "location_fields": [],
            "date_fields": {},
        }
        steps = emit_steps(plan, label="test")
        fix5_steps = [
            s for s in steps
            if isinstance(s, dict) and s.get("tool") == "ashby.maybe_solve_recaptcha_v3"
        ]
        self.assertEqual(len(fix5_steps), 1,
                        "expected exactly one ashby.maybe_solve_recaptcha_v3 step")
        args = fix5_steps[0]["args"]
        self.assertEqual(
            args["known_strict_sitekey"],
            "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
        )
        # The driver_exec block is the new contract.
        self.assertIn("driver_exec", args)
        driver_exec = args["driver_exec"]
        self.assertEqual(driver_exec["module"], "captcha_presubmit")
        self.assertEqual(driver_exec["function"], "solve_and_inject_recaptcha_v3")
        self.assertEqual(driver_exec["gate_env"], "ENABLE_CAPSOLVER")
        self.assertEqual(driver_exec["gate_value"], "1")
        self.assertEqual(
            driver_exec["kwargs"]["fallback_sitekey"],
            "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
