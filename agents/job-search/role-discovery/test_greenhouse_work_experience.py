#!/usr/bin/env python3
"""Unit tests for the Greenhouse work-experience repeater adapter.

Chain_006 sidecar (2026-05-26). Three concerns:
1. `detect_work_experience_block_in_html` correctly identifies the Lyft fixture
   and returns False on a no-repeater fabricated GH HTML.
2. `build_work_experience_payload` propagates personal-info.json.work_experience
   into the JS-ready list of entries (and falls back to experience_summary if
   the array is absent).
3. JS_FILL_WORK_EXPERIENCE_BLOCK constant exists and contains the expected
   selectors (snapshot-style smoke check).
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Stub playwright so greenhouse_filler import succeeds (no real browser dep
# for greenhouse_filler itself; but greenhouse_iframe_runner pulls it in via
# our other test file's import chain).
fake_pw = types.ModuleType("playwright")
fake_pw_sync = types.ModuleType("playwright.sync_api")
fake_pw_sync.sync_playwright = lambda *a, **k: None
class _PWT(Exception): ...
fake_pw_sync.TimeoutError = _PWT
sys.modules.setdefault("playwright", fake_pw)
sys.modules.setdefault("playwright.sync_api", fake_pw_sync)

import greenhouse_filler as gf  # noqa: E402
import greenhouse_dryrun as gd  # noqa: E402


FIXTURE = HERE / "tests" / "fixtures" / "lyft-8550252002-embed.html"


class DetectionTests(unittest.TestCase):
    def test_detects_lyft_fixture(self):
        self.assertTrue(FIXTURE.exists(), f"missing fixture: {FIXTURE}")
        html = FIXTURE.read_text()
        result = gd.detect_work_experience_block_in_html(html)
        self.assertTrue(result["detected"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["max_index"], 0)
        self.assertEqual(result["indices"], [0])

    def test_no_repeater_returns_false(self):
        html = """<html><body><form>
            <input id="first_name" type="text"/>
            <input id="last_name" type="text"/>
            <input id="resume" type="file"/>
        </form></body></html>"""
        result = gd.detect_work_experience_block_in_html(html)
        self.assertFalse(result["detected"])
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["max_index"])

    def test_multi_row_repeater(self):
        html = '''<input id="company-name-0"/><input id="company-name-1"/><input id="company-name-2"/>'''
        result = gd.detect_work_experience_block_in_html(html)
        self.assertTrue(result["detected"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["max_index"], 2)

    def test_handles_empty_input(self):
        self.assertFalse(gd.detect_work_experience_block_in_html("")["detected"])
        self.assertFalse(gd.detect_work_experience_block_in_html(None)["detected"])  # type: ignore[arg-type]
        self.assertFalse(gd.detect_work_experience_block_in_html(123)["detected"])  # type: ignore[arg-type]


class PayloadTests(unittest.TestCase):
    def test_prefers_work_experience_array(self):
        p = {
            "work_experience": [
                {"company": "Microsoft", "title": "TPM", "start_month": "March",
                 "start_year": "2024", "end_month": "", "end_year": "",
                 "current": True, "country": "United States"},
            ],
            "experience_summary": {"current_employer": "WRONG", "current_title": "WRONG"},
        }
        out = gf.build_work_experience_payload(p)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["company"], "Microsoft")
        self.assertEqual(out[0]["title"], "TPM")
        self.assertEqual(out[0]["start_year"], "2024")
        self.assertTrue(out[0]["current"])

    def test_falls_back_to_experience_summary(self):
        p = {
            "experience_summary": {
                "current_employer": "Microsoft",
                "current_title": "Technical Program Manager",
                "current_start": "2024-03",
            },
            "address": {"country": "United States"},
        }
        out = gf.build_work_experience_payload(p)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["company"], "Microsoft")
        self.assertEqual(out[0]["title"], "Technical Program Manager")
        self.assertEqual(out[0]["start_month"], "March")
        self.assertEqual(out[0]["start_year"], "2024")
        self.assertTrue(out[0]["current"])

    def test_returns_empty_when_no_data(self):
        self.assertEqual(gf.build_work_experience_payload({}), [])

    def test_multiple_entries_preserved(self):
        p = {"work_experience": [
            {"company": "Microsoft", "title": "TPM", "start_month": "March",
             "start_year": "2024", "current": True, "country": "United States"},
            {"company": "Amazon", "title": "PM", "start_month": "June",
             "start_year": "2022", "end_month": "February", "end_year": "2024",
             "current": False, "country": "United States"},
        ]}
        out = gf.build_work_experience_payload(p)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["company"], "Microsoft")
        self.assertEqual(out[1]["company"], "Amazon")
        self.assertEqual(out[1]["end_year"], "2024")
        self.assertFalse(out[1]["current"])

    def test_real_personal_info_loads(self):
        """Smoke test against actual personal-info.json so we catch schema drift."""
        import json
        pinfo_path = HERE.parent / "personal-info.json"
        self.assertTrue(pinfo_path.exists())
        pinfo = json.loads(pinfo_path.read_text())
        out = gf.build_work_experience_payload(pinfo)
        self.assertGreater(len(out), 0)
        self.assertIn("company", out[0])
        self.assertEqual(out[0]["country"], "United States")


class JSConstantTests(unittest.TestCase):
    def test_js_constant_exists_and_has_selectors(self):
        js = gf.JS_FILL_WORK_EXPERIENCE_BLOCK
        self.assertIsInstance(js, str)
        # All the selectors we expect to query
        for needle in [
            'company-name-',
            'title-',
            'start-date-year-',
            'end-date-year-',
            'start-date-month-',
            'end-date-month-',
            'role=option',
            'select__single-value',
        ]:
            self.assertIn(needle, js, f"JS missing expected selector/fragment: {needle}")

    def test_js_handles_idempotency(self):
        """JS should skip already-filled fields (regression guard)."""
        self.assertIn("already-filled", gf.JS_FILL_WORK_EXPERIENCE_BLOCK)
        self.assertIn("already-picked", gf.JS_FILL_WORK_EXPERIENCE_BLOCK)

    def test_js_is_async_for_combobox(self):
        # Combobox interactions need awaits between keystrokes
        self.assertIn("async", gf.JS_FILL_WORK_EXPERIENCE_BLOCK)
        self.assertIn("await sleep", gf.JS_FILL_WORK_EXPERIENCE_BLOCK)


if __name__ == "__main__":
    unittest.main()
