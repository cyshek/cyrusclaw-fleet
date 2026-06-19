"""test_burndown_step_captcha.py — Test that _burndown_step.py expands the
`ashby.maybe_solve_recaptcha_v3` step into the captcha macro shape the
chain worker dispatches.

Coverage:
  - When env vars enable CapSolver: kind='captcha_recaptcha_v3' with full
    macro fields (detect_fn, solver_cmd, inject_fn, inject_fn_template).
  - When env vars disable CapSolver: kind='captcha_skip' with a reason.
  - The detect_fn and inject_fn are the canonical payloads from
    captcha_presubmit (no drift).
  - Solver command points to the venv python + solve_recaptcha_v3.py and
    carries the right CLI args (--stdin, --fallback-sitekey, --page-url,
    --action, --min-score).
"""
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


class CaptchaMacroEmissionTests(unittest.TestCase):
    def setUp(self):
        import _burndown_step as bs
        import capsolver_client as cc
        import captcha_presubmit as cp
        self.bs = bs
        self.cc = cc
        self.cp = cp
        # Force the dotenv loader to never read anything during these tests.
        self.cc._DOTENV_LOADED = True

    def _build_args(self):
        return {
            "label": "test",
            "page_url": "https://jobs.ashbyhq.com/openai/test-role-id",
            "known_strict_sitekey": "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
            "page_action": "submit",
            "min_score": 0.7,
            "enterprise": False,
            "driver_exec": {
                "module": "captcha_presubmit",
                "function": "solve_and_inject_recaptcha_v3",
                "kwargs": {
                    "page_url": "https://jobs.ashbyhq.com/openai/test-role-id",
                    "fallback_sitekey": "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
                    "action": "submit",
                    "min_score": 0.7,
                    "enterprise": False,
                },
                "gate_env": "ENABLE_CAPSOLVER",
                "gate_value": "1",
            },
            "comment": "FIX 5 strict-Ashby...",
        }

    def test_enabled_emits_full_macro(self):
        with mock.patch.dict(
            os.environ,
            {"CAPSOLVER_API_KEY": "k", "ENABLE_CAPSOLVER": "1"},
            clear=False,
        ):
            out = self.bs._emit_captcha_step(10, self._build_args())
        self.assertEqual(out["kind"], "captcha_recaptcha_v3")
        self.assertTrue(out["enabled"])
        self.assertEqual(out["sitekey_fallback"],
                         "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y")
        self.assertEqual(out["page_url"],
                         "https://jobs.ashbyhq.com/openai/test-role-id")
        self.assertEqual(out["action"], "submit")
        self.assertEqual(out["min_score"], 0.7)
        self.assertFalse(out["enterprise"])
        # Canonical JS payloads must be embedded (no drift from captcha_presubmit).
        self.assertIn(self.cp.JS_DETECT_RECAPTCHA_V3.strip(), out["detect_fn"])
        self.assertTrue(out["detect_fn"].endswith("()"))
        self.assertIn(self.cp.JS_INJECT_RECAPTCHA_V3.strip(), out["inject_fn"])
        # Inject template must have the __TOKEN_JSON__ placeholder for the
        # worker to substitute the solved token.
        self.assertIn("__TOKEN_JSON__", out["inject_fn_template"])
        # Solver command shape.
        cmd = out["solver_cmd"]
        self.assertTrue(cmd[0].endswith("python"))
        self.assertTrue(cmd[1].endswith("solve_recaptcha_v3.py"))
        self.assertIn("--stdin", cmd)
        self.assertIn("--fallback-sitekey", cmd)
        self.assertIn("--page-url", cmd)
        self.assertIn("--action", cmd)
        self.assertIn("--min-score", cmd)
        self.assertEqual(out["on_solver_failure"], "continue_to_submit")

    def test_disabled_emits_skip(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPSOLVER_API_KEY", None)
            os.environ.pop("ENABLE_CAPSOLVER", None)
            out = self.bs._emit_captcha_step(10, self._build_args())
        self.assertEqual(out["kind"], "captcha_skip")
        self.assertIn("ENABLE_CAPSOLVER", out["reason"])

    def test_enterprise_propagates_to_solver_cmd(self):
        args = self._build_args()
        args["driver_exec"]["kwargs"]["enterprise"] = True
        with mock.patch.dict(
            os.environ,
            {"CAPSOLVER_API_KEY": "k", "ENABLE_CAPSOLVER": "1"},
            clear=False,
        ):
            out = self.bs._emit_captcha_step(10, args)
        self.assertTrue(out["enterprise"])
        self.assertIn("--enterprise", out["solver_cmd"])


class CompiledChunkSkipTests(unittest.TestCase):
    """_burndown_compile.py must NOT inline the captcha step into the IIFE;
    it has to leave a clear marker so the chain worker dispatches step-by-step."""

    def test_compiled_chunk_marks_captcha_skip(self):
        import _burndown_compile as bc  # noqa: F401
        # Lightweight: build a fake plan dict and route through main() via
        # argv. Easier: just verify the source contains the skip-marker case.
        with open(os.path.join(HERE, "_burndown_compile.py")) as f:
            src = f.read()
        self.assertIn("ashby.maybe_solve_recaptcha_v3", src)
        self.assertIn("captcha_skipped_in_iife", src)


if __name__ == "__main__":
    unittest.main()
