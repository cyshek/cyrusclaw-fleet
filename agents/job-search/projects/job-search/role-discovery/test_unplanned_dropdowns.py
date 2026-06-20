"""Tests for the chain_011 unplanned-required-dropdown filler.

Validates JS payload invariants + runner wiring + default pattern table.
No browser; pure structural checks.
"""

import re
import unittest

import greenhouse_filler as gf
import greenhouse_iframe_runner as runner


class TestJsPayload(unittest.TestCase):
    def test_payload_present_and_nonempty(self):
        self.assertTrue(hasattr(gf, "JS_FILL_UNPLANNED_DROPDOWNS"))
        self.assertGreater(len(gf.JS_FILL_UNPLANNED_DROPDOWNS), 1500)

    def test_payload_async_arrow(self):
        self.assertIn("async ({ patterns })", gf.JS_FILL_UNPLANNED_DROPDOWNS)

    def test_payload_skips_filled_dropdowns(self):
        # Must check select__single-value before opening
        self.assertIn(".select__single-value", gf.JS_FILL_UNPLANNED_DROPDOWNS)
        self.assertIn("continue", gf.JS_FILL_UNPLANNED_DROPDOWNS)

    def test_payload_demographic_skip(self):
        # Demographic safety net
        self.assertIn("DEMO_KEYS", gf.JS_FILL_UNPLANNED_DROPDOWNS)
        self.assertIn("gender", gf.JS_FILL_UNPLANNED_DROPDOWNS)
        self.assertIn("race", gf.JS_FILL_UNPLANNED_DROPDOWNS)
        self.assertIn("veteran", gf.JS_FILL_UNPLANNED_DROPDOWNS)

    def test_payload_match_priority_ladder(self):
        # Same priority ladder as JS_PICK_DROPDOWNS
        body = gf.JS_FILL_UNPLANNED_DROPDOWNS
        self.assertIn("startsWith(ansLc)", body)
        self.assertIn("includes(ansLc)", body)

    def test_payload_uses_native_react_select_pattern(self):
        # mousedown+mouseup+click on .select__control to open menu
        body = gf.JS_FILL_UNPLANNED_DROPDOWNS
        self.assertIn("mousedown", body)
        self.assertIn("mouseup", body)
        self.assertIn("react-select-", body)


class TestDefaultPatterns(unittest.TestCase):
    def test_lyft_716_proximity_pattern(self):
        pats = gf.DEFAULT_UNPLANNED_DROPDOWN_PATTERNS
        self.assertTrue(any(p["pattern"] == "commutable proximity" for p in pats))
        prox = next(p for p in pats if p["pattern"] == "commutable proximity")
        # Must be the EXACT positive option text (case-insensitive-exact match
        # in JS_PICK_DROPDOWNS) to bulletproof against the negation
        # "I am not willing to relocate before starting employment."
        positive = "I am willing to relocate before starting employment."
        negation = "I am not willing to relocate before starting employment."
        self.assertEqual(prox["answer"], positive)
        # Sanity: exact case-insensitive match against positive, not negation
        self.assertEqual(prox["answer"].lower(), positive.lower())
        self.assertNotEqual(prox["answer"].lower(), negation.lower())

    def test_all_patterns_have_required_keys(self):
        for p in gf.DEFAULT_UNPLANNED_DROPDOWN_PATTERNS:
            self.assertIn("pattern", p)
            self.assertIn("answer", p)
            self.assertEqual(p["pattern"], p["pattern"].lower(),
                "patterns must be lowercase (case-insensitive include match)")


class TestRunnerWiring(unittest.TestCase):
    def test_runner_calls_unplanned_dropdowns(self):
        # Make sure the step is wired and uses default pattern table
        import inspect
        src = inspect.getsource(runner)
        self.assertIn("JS_FILL_UNPLANNED_DROPDOWNS", src)
        self.assertIn("DEFAULT_UNPLANNED_DROPDOWN_PATTERNS", src)
        self.assertIn("unplanned_dropdowns", src)

    def test_runner_step_runs_before_resume_upload(self):
        # New step should be positioned AFTER work_experience_block and BEFORE
        # the resume upload (so dropdowns are filled before the final submit).
        import inspect
        src = inspect.getsource(runner)
        i_unplanned = src.find("JS_FILL_UNPLANNED_DROPDOWNS")
        i_resume = src.find("Resume upload")
        self.assertGreater(i_unplanned, 0)
        self.assertGreater(i_resume, 0)
        self.assertLess(i_unplanned, i_resume,
            "unplanned_dropdowns step must fire before resume upload + submit")


if __name__ == "__main__":
    unittest.main()
