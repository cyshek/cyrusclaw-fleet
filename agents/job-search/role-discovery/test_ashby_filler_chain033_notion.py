#!/usr/bin/env python3
"""Unit tests for chain_033 Notion-Ashby filler fix.

Covers the regression discovered in chain_031/chain_032: Ashby tenants like
Notion / Speak / Baseten / Plain render Boolean (Yes/No) questions NOT as
`<input type=radio>` but as

    <div class="_fieldEntry_..." data-field-path="<fieldUuid|_systemfield_X>">
      <div class="_yesno_..."><button>Yes</button><button>No</button></div>
      <input type="checkbox" name="<fid>" hidden>   <!-- React ignores this -->
    </div>

Pre-chain_033, `JS_RESOLVE_RADIO_LABELS` only looked at `input[type=radio]`,
returned `missing` for every Boolean field on these tenants, and the submit
validator reported "Missing entry for required field: ... Anchor Days ...
Sponsor ...". Now the resolver falls back to the yesno-button widget,
returning the matching button's bounding-rect center so the driver can
clickCoords on it (same recipe as the traditional `<label>` path).

Tests:
1. JS-string sanity (sentinel substrings present).
2. JS execution via Node+jsdom on synthetic Notion-style DOM.
3. Backward compatibility: traditional radio path still resolves.
4. Mixed page (Boolean yesno + Boolean traditional + ValueSelect radios)
   should resolve all three with the right `kind`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ashby_filler as af  # noqa: E402

# jsdom shipped via `npm install jsdom` in /tmp during chain_033 dev. Tests
# skip JS-execution layer if jsdom is absent so CI without npm still passes
# the string-level checks.
_JSDOM_NODE_MODULES = Path("/tmp/node_modules/jsdom")
HAVE_JSDOM = _JSDOM_NODE_MODULES.exists() and shutil.which("node") is not None


# ---------------------------------------------------------------------------
# 1. String-sanity tests (no Node required)
# ---------------------------------------------------------------------------
class TestYesnoFallbackStringSanity(unittest.TestCase):
    def test_resolver_mentions_yesno_class(self):
        # chain_033 sentinel: the resolver must scan for _yesno_ divs.
        self.assertIn('_yesno_', af.JS_RESOLVE_RADIO_LABELS,
            "Yesno-button fallback missing from JS_RESOLVE_RADIO_LABELS")

    def test_resolver_uses_data_field_path(self):
        # Container lookup keyed on Ashby's stable data-field-path attribute.
        self.assertIn('data-field-path', af.JS_RESOLVE_RADIO_LABELS,
            "Resolver should use [data-field-path] container selector")

    def test_resolver_returns_kind_field(self):
        # Driver dispatches on `kind` (radio_label vs yesno_button).
        self.assertIn("kind: 'yesno_button'", af.JS_RESOLVE_RADIO_LABELS)
        self.assertIn("kind: 'radio_label'", af.JS_RESOLVE_RADIO_LABELS)

    def test_resolver_picks_button_text_yes_no(self):
        # Must match buttons by visible text (Yes/No) case-insensitively.
        # Sentinel: lowercases candidate before comparing button textContent.
        self.assertIn('toLowerCase', af.JS_RESOLVE_RADIO_LABELS)

    def test_emit_steps_comment_mentions_yesno_button(self):
        # Driver contract must document the yesno_button kind so the
        # human-readable comment surfaces in step plans.
        spec = {
            "role_url": "https://jobs.ashbyhq.com/notion/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "fields": [
                {"id": "form_field1", "label": "Sponsor?", "value": "No",
                 "status": "filled", "_ashby_type": "Boolean", "required": True},
            ],
        }
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="notion")
        radio_steps = [s for s in steps
                       if isinstance(s.get('args'), dict)
                       and 'Resolve' in (s['args'].get('comment') or '')
                       and 'radio' in (s['args'].get('comment') or '').lower()]
        # Don't be brittle: pick the step whose comment mentions yesno_button.
        yesno_step = next((s for s in steps
                           if isinstance(s.get('args'), dict)
                           and 'yesno_button' in (s['args'].get('comment') or '')),
                          None)
        self.assertIsNotNone(yesno_step,
            "emit_steps should emit a comment documenting yesno_button kind")


# ---------------------------------------------------------------------------
# 2. JS-execution tests (require jsdom; skip gracefully if absent)
# ---------------------------------------------------------------------------
def _run_resolver(html: str, radios: list[dict]) -> dict:
    """Execute JS_RESOLVE_RADIO_LABELS against a synthetic jsdom DOM.

    Returns the resolver's output object: {picked, missing, no_match}.
    """
    js_fn = af.JS_RESOLVE_RADIO_LABELS
    # Wrap into a self-invoking module that sets up window/document then
    # calls the resolver with the supplied radios payload.
    driver = f"""
const {{ JSDOM }} = require('jsdom');
const dom = new JSDOM({json.dumps(html)});
global.window = dom.window;
global.document = dom.window.document;
const resolver = {js_fn};
const result = resolver({json.dumps(radios)});
console.log(JSON.stringify(result));
"""
    proc = subprocess.run(
        ["node", "--experimental-vm-modules", "-e", driver],
        capture_output=True, text=True,
        env={**os.environ, "NODE_PATH": "/tmp/node_modules"},
        timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"node exit={proc.returncode}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        )
    return json.loads(proc.stdout.strip().splitlines()[-1])


# Synthetic Notion-style Boolean field. `_fieldEntry_` container with
# data-field-path = trailing UUID, _yesno_ inner div with two <button>s,
# hidden checkbox using full-fid name.
NOTION_YESNO_HTML = """
<!doctype html><html><body>
<form>
  <div class="_fieldEntry_abc123" data-field-path="e01a85db-feaa-42b3-a9ad-69b1dcbbab3f">
    <label>Are you able to commit to working from one of our offices on Anchor Days each week?</label>
    <div class="_yesno_17tft_149 _yesno_root_xyz">
      <button type="button" class="_yesnoButton_xyz">Yes</button>
      <button type="button" class="_yesnoButton_xyz">No</button>
    </div>
    <input type="checkbox"
           name="0583862f-a941-4ce5-803a-c3566583c954_e01a85db-feaa-42b3-a9ad-69b1dcbbab3f"
           hidden>
  </div>
  <div class="_fieldEntry_def456" data-field-path="790b5934-74f5-46f5-897a-675b7f37f2f3">
    <label>Will you now or in the future require Notion to sponsor an immigration case?</label>
    <div class="_yesno_17tft_149">
      <button type="button">Yes</button>
      <button type="button">No</button>
    </div>
    <input type="checkbox"
           name="0583862f-a941-4ce5-803a-c3566583c954_790b5934-74f5-46f5-897a-675b7f37f2f3"
           hidden>
  </div>
</form>
</body></html>
"""

# Traditional ValueSelect radio group (pronouns / EEOC).
TRADITIONAL_RADIO_HTML = """
<!doctype html><html><body>
<form>
  <div class="_fieldEntry_pronoun" data-field-path="b0a5aba8-dbb7-41a9-b548-f72cc3e48956">
    <fieldset>
      <input type="radio" id="grp1-labeled-radio-0"
             name="0583862f-a941-4ce5-803a-c3566583c954_b0a5aba8-dbb7-41a9-b548-f72cc3e48956"
             value="They/Them">
      <label for="grp1-labeled-radio-0">They/Them</label>
      <input type="radio" id="grp1-labeled-radio-1"
             name="0583862f-a941-4ce5-803a-c3566583c954_b0a5aba8-dbb7-41a9-b548-f72cc3e48956"
             value="Decline">
      <label for="grp1-labeled-radio-1">Decline to answer</label>
    </fieldset>
  </div>
</form>
</body></html>
"""

# Mixed page: Notion yesno + traditional radio together.
MIXED_HTML = NOTION_YESNO_HTML.replace("</body></html>", "") + \
    TRADITIONAL_RADIO_HTML.split("<body>")[1]


@unittest.skipUnless(HAVE_JSDOM, "jsdom not installed at /tmp/node_modules")
class TestYesnoFallbackExecution(unittest.TestCase):
    """Drive the actual JS against synthetic DOM via Node+jsdom."""

    def test_yesno_only_resolves_via_button(self):
        radios = [{
            "name": "0583862f-a941-4ce5-803a-c3566583c954_e01a85db-feaa-42b3-a9ad-69b1dcbbab3f",
            "value": "Yes",
            "alternates": ["yes", "i agree"],
        }]
        out = _run_resolver(NOTION_YESNO_HTML, radios)
        self.assertEqual(out.get("missing"), [], f"unexpected missing: {out}")
        self.assertEqual(out.get("no_match"), [], f"unexpected no_match: {out}")
        self.assertEqual(len(out["picked"]), 1)
        pick = out["picked"][0]
        self.assertEqual(pick["kind"], "yesno_button")
        self.assertEqual(pick["label_text"], "Yes")
        # cx/cy populated (even if rect is 0x0 in jsdom they exist as numbers).
        self.assertIn("cx", pick)
        self.assertIn("cy", pick)

    def test_yesno_no_value_picked(self):
        radios = [{
            "name": "0583862f-a941-4ce5-803a-c3566583c954_790b5934-74f5-46f5-897a-675b7f37f2f3",
            "value": "No",
            "alternates": ["no"],
        }]
        out = _run_resolver(NOTION_YESNO_HTML, radios)
        self.assertEqual(out.get("missing"), [])
        self.assertEqual(len(out["picked"]), 1)
        self.assertEqual(out["picked"][0]["label_text"], "No")
        self.assertEqual(out["picked"][0]["kind"], "yesno_button")

    def test_traditional_radio_still_resolves(self):
        radios = [{
            "name": "0583862f-a941-4ce5-803a-c3566583c954_b0a5aba8-dbb7-41a9-b548-f72cc3e48956",
            "value": "Decline to answer",
            "alternates": [],
        }]
        out = _run_resolver(TRADITIONAL_RADIO_HTML, radios)
        self.assertEqual(out.get("missing"), [])
        self.assertEqual(len(out["picked"]), 1)
        pick = out["picked"][0]
        self.assertEqual(pick["kind"], "radio_label")
        self.assertEqual(pick["label_text"], "Decline to answer")
        self.assertEqual(pick["label_for"], "grp1-labeled-radio-1")

    def test_mixed_page_resolves_both_kinds(self):
        radios = [
            {"name": "0583862f-a941-4ce5-803a-c3566583c954_e01a85db-feaa-42b3-a9ad-69b1dcbbab3f",
             "value": "Yes", "alternates": []},
            {"name": "0583862f-a941-4ce5-803a-c3566583c954_b0a5aba8-dbb7-41a9-b548-f72cc3e48956",
             "value": "Decline to answer", "alternates": []},
        ]
        out = _run_resolver(MIXED_HTML, radios)
        self.assertEqual(out.get("missing"), [], f"unexpected missing: {out}")
        kinds = {p["name"]: p["kind"] for p in out["picked"]}
        self.assertEqual(
            kinds.get("0583862f-a941-4ce5-803a-c3566583c954_e01a85db-feaa-42b3-a9ad-69b1dcbbab3f"),
            "yesno_button")
        self.assertEqual(
            kinds.get("0583862f-a941-4ce5-803a-c3566583c954_b0a5aba8-dbb7-41a9-b548-f72cc3e48956"),
            "radio_label")

    def test_yesno_unknown_value_lands_in_no_match(self):
        radios = [{
            "name": "0583862f-a941-4ce5-803a-c3566583c954_e01a85db-feaa-42b3-a9ad-69b1dcbbab3f",
            "value": "Maybe",
            "alternates": [],
        }]
        out = _run_resolver(NOTION_YESNO_HTML, radios)
        self.assertEqual(out.get("picked"), [])
        self.assertEqual(len(out.get("no_match", [])), 1)
        nm = out["no_match"][0]
        self.assertEqual(nm.get("kind"), "yesno_button")
        # Options surfaced for diagnostics:
        self.assertIn("yes", nm.get("options", []))
        self.assertIn("no", nm.get("options", []))

    def test_no_container_at_all_still_missing(self):
        # Empty form: neither radio nor yesno container exists for the name.
        empty_html = "<!doctype html><html><body><form></form></body></html>"
        radios = [{"name": "0583862f-a941-4ce5-803a-c3566583c954_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                   "value": "Yes", "alternates": []}]
        out = _run_resolver(empty_html, radios)
        self.assertEqual(out.get("picked"), [])
        self.assertEqual(len(out.get("missing", [])), 1)


# ---------------------------------------------------------------------------
# 3. End-to-end: real Notion 930 dryrun spec -> build_plan + emit_steps
# ---------------------------------------------------------------------------
NOTION_930_DRYRUN = (HERE.parent / "applications" / "dryrun"
                     / "notion-35785e61-c4c3-44ec-a401-6741d89dd16a.json")


class TestNotion930PlanShape(unittest.TestCase):
    """Plan shape doesn't change, but the resolver step it emits is the
    chain_033-patched one. This guards against accidental re-introduction
    of the old radio-only resolver in emit_steps."""

    @unittest.skipUnless(NOTION_930_DRYRUN.exists(),
                         "Notion 930 dryrun spec not present")
    def test_notion_930_radios_include_two_booleans(self):
        spec = json.loads(NOTION_930_DRYRUN.read_text())
        plan = af.build_plan(spec)
        # Two Boolean (Anchor Days + Sponsor) + one ValueSelect (Pronouns).
        self.assertEqual(len(plan["radios"]), 3,
            f"Expected 3 radio entries for Notion 930, got {len(plan['radios'])}")
        # Sanity: labels should mention Anchor Days, sponsor, pronouns.
        joined = " | ".join(r.get("label", "") for r in plan["radios"]).lower()
        self.assertIn("anchor days", joined)
        self.assertIn("sponsor", joined)
        self.assertIn("pronouns", joined)

    def test_emit_steps_radio_step_uses_chain033_resolver(self):
        # Build a plan with a Boolean field; ensure the emitted radio-step
        # JS string is the chain_033 version (contains _yesno_ sentinel).
        spec = {
            "role_url": "https://jobs.ashbyhq.com/notion/x",
            "fields": [
                {"id": "form_yesno", "label": "Sponsor?", "value": "No",
                 "status": "filled", "_ashby_type": "Boolean", "required": True},
            ],
        }
        plan = af.build_plan(spec)
        steps = af.emit_steps(plan, label="notion")
        radio_step = next((s for s in steps
                           if isinstance(s.get('args'), dict)
                           and 'JS_RESOLVE_RADIO' in (s['args'].get('fn') or '')
                           or '_yesno_' in (s['args'].get('fn') or '')),
                          None)
        self.assertIsNotNone(radio_step,
            "emit_steps should emit a radio resolver step with chain_033 yesno fallback")
        self.assertIn('_yesno_', radio_step['args']['fn'])
        self.assertIn('data-field-path', radio_step['args']['fn'])


if __name__ == "__main__":
    unittest.main()
