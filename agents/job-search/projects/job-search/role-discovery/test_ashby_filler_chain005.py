#!/usr/bin/env python3
"""Unit tests for chain_005 driver-port wins in ashby_filler.

Covers:
- P1: native-setter fast-path emission (`JS_FAST_FILL_TEXT_FIELDS` + flag).
- P3: Ashby Date fields route through text_fields + recorded in date_fields.
- P4: Ashby Location fields route through location_fields + multi-step emit
      (NOT into text_fields, since combobox typeahead needs real keystrokes).
- General: skipped list should not contain Date/Location anymore.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ashby_filler as af  # noqa: E402


def _spec_with(fields):
    """Build a minimal dryrun-shaped spec with the given fields list."""
    return {
        "role_url": "https://jobs.ashbyhq.com/example/00000000-0000-0000-0000-000000000000",
        "fields": fields,
    }


# ---------------------------------------------------------------------------
# P1: native-setter fast path
# ---------------------------------------------------------------------------
class TestP1FastPath(unittest.TestCase):
    def test_kill_switch_flag_exists_and_defaults_true(self):
        self.assertTrue(hasattr(af, "USE_NATIVE_SETTER_FAST_PATH"))
        self.assertIs(af.USE_NATIVE_SETTER_FAST_PATH, True)

    def test_fast_fill_js_helper_exists_and_uses_value_tracker(self):
        # Should be a string ending with `}` and reference setNativeValue
        self.assertIn("setNativeValue", af.JS_FAST_FILL_TEXT_FIELDS)
        self.assertIn("dispatchEvent", af.JS_FAST_FILL_TEXT_FIELDS)
        # input event only on fast path (no change/blur)
        self.assertIn("'input'", af.JS_FAST_FILL_TEXT_FIELDS)

    def test_emit_steps_inserts_fast_path_before_cdp_fallback(self):
        spec = _spec_with([
            {"id": "fid-1", "label": "Full Name", "value": "Cyrus",
             "status": "filled", "_ashby_type": "String", "required": True},
        ])
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="test")
        # Expected order: open, sleep, resolve, FAST, type_text_fields, ...
        tools = [s["tool"] for s in steps]
        # Find indices
        i_fast = next(i for i, s in enumerate(steps)
                      if s["tool"] == "browser.act.evaluate"
                      and "fast_path" in (s["args"].get("meta") or {}))
        i_cdp = tools.index("ashby.type_text_fields")
        self.assertLess(i_fast, i_cdp,
                        "fast-path step must come before CDP keystroke step")

    def test_kill_switch_false_suppresses_fast_path(self):
        spec = _spec_with([
            {"id": "fid-1", "label": "Full Name", "value": "Cyrus",
             "status": "filled", "_ashby_type": "String", "required": True},
        ])
        plan = af.build_plan(spec)
        orig = af.USE_NATIVE_SETTER_FAST_PATH
        try:
            af.USE_NATIVE_SETTER_FAST_PATH = False
            steps = af.emit_steps(plan, label="test")
            fast = [s for s in steps if "fast_path" in (s["args"].get("meta") or {})]
            self.assertEqual(fast, [],
                "fast-path step should NOT emit when kill switch is False")
        finally:
            af.USE_NATIVE_SETTER_FAST_PATH = orig


# ---------------------------------------------------------------------------
# P3: Date branch
# ---------------------------------------------------------------------------
class TestP3Date(unittest.TestCase):
    def test_date_routes_through_text_fields(self):
        spec = _spec_with([
            {"id": "date-fid", "label": "Earliest start?",
             "value": "Two weeks from offer", "status": "filled",
             "_ashby_type": "Date", "required": True},
        ])
        plan = af.build_plan(spec)
        self.assertIn("date-fid", plan["text_fields"])
        self.assertEqual(plan["text_fields"]["date-fid"], "Two weeks from offer")
        # Also tracked separately for Enter-press follow-up
        self.assertIn("date-fid", plan["date_fields"])
        # Should NOT be in skipped
        self.assertNotIn("date-fid", [s["id"] for s in plan["skipped"]])

    def test_date_field_ids_passed_to_cdp_step(self):
        spec = _spec_with([
            {"id": "date-fid", "label": "When", "value": "06/09/2026",
             "status": "filled", "_ashby_type": "Date", "required": True},
        ])
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="test")
        cdp = next(s for s in steps if s["tool"] == "ashby.type_text_fields")
        self.assertIn("date_field_ids", cdp["args"])
        self.assertIn("date-fid", cdp["args"]["date_field_ids"])


# ---------------------------------------------------------------------------
# P4: Location typeahead branch
# ---------------------------------------------------------------------------
class TestP4Location(unittest.TestCase):
    def test_location_routes_to_location_fields_not_text(self):
        spec = _spec_with([
            {"id": "loc-fid", "label": "Where do you live?",
             "value": "Kirkland", "status": "filled",
             "_ashby_type": "Location", "required": True},
        ])
        plan = af.build_plan(spec)
        # NOT in text_fields (combobox needs real keypress)
        self.assertNotIn("loc-fid", plan["text_fields"])
        self.assertEqual(len(plan["location_fields"]), 1)
        lf = plan["location_fields"][0]
        self.assertEqual(lf["fid"], "loc-fid")
        self.assertEqual(lf["value"], "Kirkland")
        self.assertTrue(lf["required"])
        # NOT in skipped
        self.assertNotIn("loc-fid", [s["id"] for s in plan["skipped"]])

    def test_location_emits_self_contained_typeahead_step(self):
        # chain_028 (Speak 1015 guard): default path is the self-contained
        # async-JS evaluate. Legacy `ashby.location_typeahead_fill` virtual
        # tool step is only emitted when the kill switch is flipped OFF.
        spec = _spec_with([
            {"id": "loc-fid", "label": "City", "value": "Kirkland, WA",
             "status": "filled", "_ashby_type": "Location", "required": False},
        ])
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="test")
        # Find the self-contained typeahead step.
        sc = [s for s in steps
              if s["tool"] == "browser.act.evaluate"
              and (s["args"].get("meta") or {}).get("self_contained_typeahead")]
        self.assertEqual(len(sc), 1,
            "Default path must emit exactly one self-contained Location typeahead step")
        # And the legacy virtual-tool step must NOT be emitted by default.
        self.assertNotIn("ashby.location_typeahead_fill",
                         [s["tool"] for s in steps],
                         "Legacy virtual-tool step must not emit when self-contained is on")

    def test_location_typeahead_skipped_when_no_location_fields(self):
        spec = _spec_with([
            {"id": "text-fid", "label": "Name", "value": "X",
             "status": "filled", "_ashby_type": "String", "required": True},
        ])
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="test")
        tools = [s["tool"] for s in steps]
        self.assertNotIn("ashby.location_typeahead_fill", tools)
        # And no self-contained typeahead either.
        sc = [s for s in steps
              if s["tool"] == "browser.act.evaluate"
              and (s["args"].get("meta") or {}).get("self_contained_typeahead")]
        self.assertEqual(sc, [])


# ---------------------------------------------------------------------------
# chain_028 (2026-05-29 Speak 1015 guard): defensive Location typeahead.
# ---------------------------------------------------------------------------
class TestChain028LocationGuard(unittest.TestCase):
    def test_kill_switch_flag_exists_and_defaults_true(self):
        self.assertTrue(hasattr(af, "USE_LOCATION_TYPEAHEAD_SELF_CONTAINED"))
        self.assertIs(af.USE_LOCATION_TYPEAHEAD_SELF_CONTAINED, True)

    def test_helper_js_has_setNative_and_keyboard_fallback(self):
        js = af.JS_FILL_ASHBY_LOCATION_TYPEAHEAD
        # FAST PATH: setNative
        self.assertIn("setNative", js)
        # FALLBACK: per-char KeyboardEvent (chain_026 async-typeahead recipe)
        self.assertIn("KeyboardEvent", js)
        self.assertIn("keydown", js)
        self.assertIn("keyup", js)
        # GRACEFUL: structured return shape (resolved/unresolved arrays)
        self.assertIn("resolved", js)
        self.assertIn("unresolved", js)
        # Bounded wait (does not hang forever)
        self.assertIn("2500", js)  # waitForOptions budget
        # Must NOT throw on missing options -> uses unresolved.push, not throw
        self.assertNotIn("throw new", js)

    def test_helper_js_handles_missing_input_gracefully(self):
        # The JS must push to unresolved when input is missing, not throw.
        js = af.JS_FILL_ASHBY_LOCATION_TYPEAHEAD
        self.assertIn("no-input", js)
        self.assertIn("no-options-after-2500ms", js)

    def test_default_emit_uses_self_contained_evaluate(self):
        spec = _spec_with([
            {"id": "loc-fid", "label": "City", "value": "Kirkland",
             "status": "filled", "_ashby_type": "Location", "required": True},
        ])
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="test")
        sc = [s for s in steps
              if s["tool"] == "browser.act.evaluate"
              and (s["args"].get("meta") or {}).get("self_contained_typeahead")]
        self.assertEqual(len(sc), 1)
        # The fn payload must wrap the helper around the locFields arg.
        fn = sc[0]["args"]["fn"]
        self.assertIn("loc-fid", fn)
        self.assertIn("Kirkland", fn)
        self.assertIn("setNative", fn)
        self.assertIn("KeyboardEvent", fn)

    def test_kill_switch_off_falls_back_to_legacy_two_step(self):
        spec = _spec_with([
            {"id": "loc-fid", "label": "City", "value": "Kirkland",
             "status": "filled", "_ashby_type": "Location", "required": True},
        ])
        plan = af.build_plan(spec)
        orig = af.USE_LOCATION_TYPEAHEAD_SELF_CONTAINED
        try:
            af.USE_LOCATION_TYPEAHEAD_SELF_CONTAINED = False
            steps = af.emit_steps(plan, label="test")
            tools = [s["tool"] for s in steps]
            # Legacy two-step path: resolver evaluate + virtual-tool fill
            self.assertIn("ashby.location_typeahead_fill", tools)
            sc = [s for s in steps
                  if s["tool"] == "browser.act.evaluate"
                  and (s["args"].get("meta") or {}).get("self_contained_typeahead")]
            self.assertEqual(sc, [],
                "self-contained step must NOT emit when kill switch is False")
        finally:
            af.USE_LOCATION_TYPEAHEAD_SELF_CONTAINED = orig

    def test_required_flag_is_passed_into_helper_payload(self):
        spec = _spec_with([
            {"id": "loc-fid", "label": "City", "value": "Kirkland",
             "status": "filled", "_ashby_type": "Location", "required": True},
            {"id": "loc-fid-opt", "label": "Other", "value": "Seattle",
             "status": "filled", "_ashby_type": "Location", "required": False},
        ])
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="test")
        sc = [s for s in steps
              if s["tool"] == "browser.act.evaluate"
              and (s["args"].get("meta") or {}).get("self_contained_typeahead")]
        self.assertEqual(len(sc), 1)
        fn = sc[0]["args"]["fn"]
        # Required flag must propagate so driver can distinguish
        # required-blocker vs optional-skip.
        self.assertIn('"required": true', fn)
        self.assertIn('"required": false', fn)

    def test_speak_1015_real_spec_emits_self_contained_step(self):
        # Regression for Speak 1015 chain_013 crash: a Location field with
        # _ashby_type=Location and value="Kirkland, WA" must NOT route to
        # the legacy virtual-tool step (which was crash-prone). Must emit
        # exactly one self-contained evaluate step.
        spec = _spec_with([
            {"id": "de256c32__systemfield_name", "label": "Full Name",
             "value": "Cyrus Shekari", "status": "filled",
             "_ashby_type": "String", "required": True},
            {"id": "de256c32__systemfield_location", "label": "Location",
             "value": "Kirkland, WA", "status": "filled",
             "_ashby_type": "Location", "required": True},
        ])
        plan = af.build_plan(spec)
        self.assertEqual(len(plan["location_fields"]), 1)
        steps = af.emit_steps(plan, label="speak-1015")
        sc = [s for s in steps
              if s["tool"] == "browser.act.evaluate"
              and (s["args"].get("meta") or {}).get("self_contained_typeahead")]
        self.assertEqual(len(sc), 1)
        self.assertNotIn("ashby.location_typeahead_fill",
                         [s["tool"] for s in steps])
        # Helper payload includes the Speak fid + value.
        fn = sc[0]["args"]["fn"]
        self.assertIn("systemfield_location", fn)
        self.assertIn("Kirkland, WA", fn)


# ---------------------------------------------------------------------------
# Regression: combined plan from a real-shape spec produces 0 skipped for
# Date + Location + String + Boolean + File.
# ---------------------------------------------------------------------------
class TestRegressionCombinedSpec(unittest.TestCase):
    def test_combined_spec_no_date_or_location_in_skipped(self):
        spec = _spec_with([
            {"id": "name-fid", "label": "Name", "value": "Cyrus",
             "status": "filled", "_ashby_type": "String", "required": True},
            {"id": "date-fid", "label": "Earliest start?",
             "value": "Two weeks from offer", "status": "filled",
             "_ashby_type": "Date", "required": True},
            {"id": "loc-fid", "label": "City", "value": "Kirkland",
             "status": "filled", "_ashby_type": "Location", "required": True},
            {"id": "bool-fid", "label": "Authorized?", "value": "Yes",
             "status": "filled", "_ashby_type": "Boolean", "required": True},
        ])
        plan = af.build_plan(spec)
        skipped_ids = [s["id"] for s in plan["skipped"]]
        self.assertEqual(skipped_ids, [],
            f"No fields should be skipped; got: {skipped_ids}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
