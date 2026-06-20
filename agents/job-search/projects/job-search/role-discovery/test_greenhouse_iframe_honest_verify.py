#!/usr/bin/env python3
"""Unit tests for greenhouse_iframe_runner.honest_verify_post_submit.

Chain_006 sidecar (2026-05-26). Pure-function helper; no Playwright import.

Regression context: Lyft 1343 chain_005 attempt — runner reported
`step:submit, result:{ok:True}` and `verify_resume.strict_bound=True` DURING
the run but post-submit page showed 8 unfilled required fields. The misleading
ok:True signal nearly polluted the tracker. This helper downgrades that signal
when post_submit.fieldErrs is non-empty.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Import the helper without importing playwright (the helper is module-level
# and runs at import time, but playwright is imported at module top).
# Trick: stub playwright before import so import succeeds.
import types
fake_pw = types.ModuleType("playwright")
fake_pw_sync = types.ModuleType("playwright.sync_api")
fake_pw_sync.sync_playwright = lambda *a, **k: None
class _PWT(Exception): ...
fake_pw_sync.TimeoutError = _PWT
sys.modules.setdefault("playwright", fake_pw)
sys.modules.setdefault("playwright.sync_api", fake_pw_sync)

mod = importlib.import_module("greenhouse_iframe_runner")
honest_verify_post_submit = mod.honest_verify_post_submit


import unittest


class HonestVerifyTests(unittest.TestCase):
    def test_no_fieldErrs_no_change(self):
        report = {"outcome": "SUBMITTED", "events": [
            {"step": "submit", "result": {"ok": True, "label": "Submit Application"}},
        ]}
        last = {"conf": True, "fieldErrs": []}
        out = honest_verify_post_submit(report, last)
        self.assertEqual(out["outcome"], "SUBMITTED")
        self.assertTrue(out["events"][0]["result"]["ok"])
        self.assertNotIn("honest_verify", out)

    def test_fieldErrs_downgrades_submit_event(self):
        report = {"outcome": "TIMEOUT", "events": [
            {"step": "text_fields", "result": {}},
            {"step": "submit", "result": {"ok": True, "label": "Submit Application"}},
        ]}
        last = {"conf": False, "fieldErrs": [
            "Resume/CV is required", "Company name is required", "Title is required",
        ]}
        out = honest_verify_post_submit(report, last)
        self.assertEqual(out["outcome"], "BLOCKED_FIELD_ERRORS")
        submit_ev = out["events"][1]
        self.assertFalse(submit_ev["result"]["ok"])
        self.assertTrue(submit_ev["result"]["downgraded_from_clicked"])
        self.assertEqual(len(submit_ev["result"]["field_errors"]), 3)
        self.assertEqual(out["honest_verify"]["downgraded"], True)
        self.assertEqual(len(out["honest_verify"]["field_errors"]), 3)

    def test_idempotent(self):
        report = {"outcome": "TIMEOUT", "events": [
            {"step": "submit", "result": {"ok": True}},
        ]}
        last = {"conf": False, "fieldErrs": ["A required"]}
        honest_verify_post_submit(report, last)
        # Second call should not re-mutate or add a second downgrade marker.
        out = honest_verify_post_submit(report, last)
        self.assertFalse(out["events"][0]["result"]["ok"])
        self.assertTrue(out["events"][0]["result"]["downgraded_from_clicked"])

    def test_captcha_gate_terminal_blocker_wins(self):
        report = {"outcome": "CAPTCHA_GATE", "events": [
            {"step": "submit", "result": {"ok": True}},
        ]}
        last = {"conf": False, "fieldErrs": ["Resume required"]}
        out = honest_verify_post_submit(report, last)
        # Still downgrades the event but does NOT overwrite a more specific terminal blocker.
        self.assertEqual(out["outcome"], "CAPTCHA_GATE")
        self.assertFalse(out["events"][0]["result"]["ok"])

    def test_verification_fail_terminal_blocker_wins(self):
        report = {"outcome": "VERIFICATION_FAIL", "events": [
            {"step": "submit", "result": {"ok": True}},
        ]}
        last = {"conf": False, "fieldErrs": ["X required"]}
        out = honest_verify_post_submit(report, last)
        self.assertEqual(out["outcome"], "VERIFICATION_FAIL")

    def test_handles_none_last(self):
        report = {"outcome": "TIMEOUT", "events": []}
        out = honest_verify_post_submit(report, None)
        self.assertEqual(out["outcome"], "TIMEOUT")  # no fieldErrs to honest about

    def test_handles_missing_events(self):
        report = {"outcome": "TIMEOUT"}
        last = {"fieldErrs": ["X required"]}
        out = honest_verify_post_submit(report, last)
        self.assertEqual(out["outcome"], "BLOCKED_FIELD_ERRORS")
        self.assertEqual(out["honest_verify"]["downgraded"], True)

    def test_handles_non_submit_events_skipped(self):
        report = {"outcome": "TIMEOUT", "events": [
            {"step": "text_fields", "result": {"ok": True}},  # NOT submit, should not be touched
            {"step": "submit", "result": {"ok": True}},
        ]}
        last = {"fieldErrs": ["X required"]}
        out = honest_verify_post_submit(report, last)
        self.assertTrue(out["events"][0]["result"]["ok"])  # text_fields untouched
        self.assertFalse(out["events"][1]["result"]["ok"])

    def test_conf_true_with_fieldErrs_still_downgrades_event(self):
        # Defense in depth: even on conf=True, if fieldErrs non-empty something is fishy.
        # We don't override outcome (conf=True is a strong signal) BUT we mark honest_verify.
        # NOTE current implementation overrides outcome=BLOCKED_FIELD_ERRORS only if outcome
        # is NOT in terminal_blockers. SUBMITTED is NOT in terminal_blockers, so it WILL get
        # overridden. This is intentional: conf+fieldErrs is a contradiction, prefer caution.
        report = {"outcome": "SUBMITTED", "events": [
            {"step": "submit", "result": {"ok": True}},
        ]}
        last = {"conf": True, "fieldErrs": ["Stray error"]}
        out = honest_verify_post_submit(report, last)
        self.assertEqual(out["outcome"], "BLOCKED_FIELD_ERRORS")
        self.assertTrue(out["honest_verify"]["downgraded"])

    def test_returns_report_unchanged_for_non_dict(self):
        self.assertEqual(honest_verify_post_submit("not a dict", {"fieldErrs": ["x"]}), "not a dict")


if __name__ == "__main__":
    unittest.main()
