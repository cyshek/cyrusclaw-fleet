"""Regression: required multi_value_multi_select consent/ack fields must be
COMMITTED in-browser and CAUGHT by the pre-submit empty-required scan.

Bug (2026-06-04, Pure Storage 7254748/7671846/7857995): GH tenants render a
required `multi_value_multi_select` consent field (e.g. "Personal Information
Policy" with sole option "Acknowledge/Confirm") as a REACT-SELECT MULTI widget,
NOT a native <fieldset.checkbox>. The old JS_TICK_MULTI_CHECKBOXES only searched
<fieldset>, so the ack stayed unset -> Greenhouse silently bounced the submit
(status=uncertain, emptyRequired:[], lands back on the job page). The pre-submit
scan also missed it because react-select consent has no DOM [required] attr.

These are structural/pure-Python checks (no browser): they lock the commit
mechanism + the scan wiring + the planner routing so the regression can't
silently come back.
"""

import re
import unittest

import greenhouse_filler as gf


class TestMultiSelectConsentCommit(unittest.TestCase):
    def test_tick_multi_is_async(self):
        # React multi-select commit needs to open the menu + await the click,
        # exactly like the single-select JS_PICK_DROPDOWNS. A sync payload
        # could not click a react option.
        self.assertTrue(gf.JS_TICK_MULTI_CHECKBOXES.strip().startswith("async"))

    def test_tick_multi_has_react_select_fallback(self):
        body = gf.JS_TICK_MULTI_CHECKBOXES
        # Native fieldset path still present...
        self.assertIn("fieldset", body)
        # ...plus the react-select fallback when no fieldset is found.
        self.assertIn("react_select", body)
        self.assertIn(".select__control", body)
        # commits by clicking the matching option (same recipe as single-select)
        self.assertIn("mousedown", body)
        self.assertIn("mouseup", body)
        self.assertIn("react-select-", body)
        # verifies the chip persisted
        self.assertIn(".select__multi-value", body)

    def test_tick_multi_commits_sole_option_ack(self):
        # A consent field whose ONLY option is "Acknowledge/Confirm" must be
        # committed even if value-text matching whiffs (forced-choice ack).
        body = gf.JS_TICK_MULTI_CHECKBOXES
        self.assertIn("opts.length === 1", body)

    def test_planner_routes_consent_multi_to_multi_checkboxes(self):
        spec = {
            "org": "purestorage", "job_id": "7254748", "role_url": "https://x",
            "fields": [{
                "id": "question_60213478[]",
                "label": "Personal Information Policy",
                "type": "multi_value_multi_select",
                "required": True,
                "value": "Acknowledge/Confirm",
                "status": "filled",
                "options": [{"label": "Acknowledge/Confirm", "value": 1}],
            }],
        }
        plan = gf.build_plan(spec)
        mc = plan.get("multi_checkboxes") or []
        self.assertEqual(len(mc), 1, f"expected 1 multi_checkbox, got {mc}")
        self.assertEqual(mc[0]["id"], "question_60213478[]")
        self.assertIn("Acknowledge/Confirm", mc[0]["values"])
        # it must NOT be misrouted to the demographic decline-only bucket
        self.assertFalse(plan.get("declined_demo_multi"))

    def test_emit_steps_includes_tick_multi_step(self):
        spec = {
            "org": "purestorage", "job_id": "7254748", "role_url": "https://x",
            "fields": [{
                "id": "question_60213478[]",
                "label": "Personal Information Policy",
                "type": "multi_value_multi_select",
                "required": True, "value": "Acknowledge/Confirm", "status": "filled",
                "options": [{"label": "Acknowledge/Confirm", "value": 1}],
            }],
        }
        steps = gf.emit_steps(gf.build_plan(spec), label="purestorage")
        fns = [s["args"].get("fn") for s in steps if s.get("tool") == "browser.act.evaluate"]
        self.assertIn(gf.JS_TICK_MULTI_CHECKBOXES, fns)


class TestPreSubmitScanCatchesMultiSelect(unittest.TestCase):
    def test_gh_submit_scan_includes_multiunset(self):
        # The pre-submit empty-required scan in _gh_submit.py must additionally
        # flag uncommitted required react-select MULTI widgets so a missed
        # consent/ack is caught BEFORE submit instead of silently bouncing.
        from pathlib import Path
        src = Path(__file__).with_name("_gh_submit.py").read_text()
        # the scan that builds preSubmitState
        self.assertIn("multiUnset", src)
        self.assertIn("select__multi-value", src)
        self.assertIn("--is-multi", src)
        # multiUnset entries get merged into emptyRequired so existing
        # downstream gating (no_empties / hosted-flow-bounce) sees them.
        self.assertTrue(re.search(r"empty\.push\(k\)", src),
                        "multiUnset keys must be merged into emptyRequired")


if __name__ == "__main__":
    unittest.main(verbosity=2)
