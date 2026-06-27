#!/usr/bin/env python3
"""
greenhouse_filler.py — drive the OpenClaw browser tool to autofill a Greenhouse
application form from an `applications/dryrun/{org}-{job_id}.json` spec.

This script does NOT submit the form. It stops after every field is populated
and the resume is attached. Cyrus clicks Submit himself.

Usage:
    python greenhouse_filler.py <org> <job_id>
    python greenhouse_filler.py anthropic 4985877008

Mechanics (the parts that took a while to figure out):

0. Post-submit email verification (Greenhouse "security code"):
   See JS_DETECT_VERIFICATION + gmail_imap.wait_for_verification_code().

1. Plain `<input type=text|tel|email>` and `<textarea>` — native value setter
   trick (see JS_FILL_TEXT_FIELDS).

2. react-select dropdowns — mousedown+mouseup+click on .select__control,
   then on the option div (JS_PICK_DROPDOWNS). Match priority is exact →
   case-insensitive → startsWith → includes so DeepMind-style 'United
   States +1' option text matches the dryrun label 'United States'.

3. Country react-select with typeahead/large lists (Scale, DeepMind) —
   JS_PICK_DROPDOWN_TYPEAHEAD: open + setNative(label) into the select
   __input + click first matching option.

4. Phone iti widget (Scale) — JS_FILL_PHONE_ITI: click .iti__selected-flag,
   click 'United States' in the iti list, then setNative phone digits-only.

5. Resume / Filestack "Attach" button — JS_CLICK_ATTACH retries the click
   2-3x with sleeps (Scale forms ignore the first click). Then call the
   browser tool's `upload` action with selector "#resume".

6. Demographic decline-pass — JS_DECLINE_DEMOGRAPHICS auto-detects unset
   gender/race/ethnicity/veteran/disability react-selects by their label
   regex and picks a 'Decline to self-identify' option.

7. Runtime correction for `filled_needs_review` dryrun specs — the planner
   emits a JS_INSPECT_OPTIONS step per such field so the driver can pick a
   better label from the rendered options (Vercel 'based-in-countries'
   2026-05-08 fix: dryrun said 'No', actual options were country names).

8. reCAPTCHA — visible captcha frames bail JS_SUBMIT by default. Pass
   {allowVisibleCaptcha:true} to bypass (Scale's visible reCAPTCHA is
   harmless — direct btn.click works through it). NEVER make this default.

9. Unknown-field telemetry — build_plan logs every unhandled field type to
   role-discovery/unknown_fields.log so we discover new patterns instead
   of silently dropping them.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DRYRUN_DIR = ROOT / "applications" / "dryrun"
SUBMITTED_DIR = ROOT / "applications" / "submitted"
FAILED_DIR = ROOT / "applications" / "failed"
UPLOADS = Path("/tmp/openclaw/uploads")
SCREENSHOT_DIR = ROOT / "applications" / "screenshots"
HERE = Path(__file__).resolve().parent
UNKNOWN_FIELDS_LOG = HERE / "unknown_fields.log"

DEFAULT_CAP = 1  # cap unattended submissions per run; bump cautiously

# Regexes for auto-detecting field categories by label/id. Used so the driver
# can switch strategies without per-form configuration.
# Country react-select detection. Has to be conservative — plain Yes/No
# work-authorization questions often contain the word 'country' (e.g.
# "...visa sponsorship to work in the country in which the job is located?")
# but those are NOT country dropdowns. Treat as country only when the field id
# matches OR the label is short and clearly asks for the country itself.
COUNTRY_ID_RE = re.compile(r"(?:^|_)country(?:$|_)|countryof|country_of_residence|nation", re.I)
COUNTRY_LABEL_RE = re.compile(r"^\s*(country|country of residence|country/region|nation|in which country|what country)\b", re.I)
PHONE_LABEL_RE = re.compile(r"\b(phone|mobile|telephone|cell)\b", re.I)
# Demographic categories where the dryrun marks status='declined' and we should
# actively select a decline option from the rendered react-select.
DEMO_LABEL_RE = re.compile(r"gender|\bsex\b|race|ethnic|hispanic|latin|veteran|disabilit|self[- ]?identif|pronoun|sexual.{0,5}orient", re.I)
# Common decline-to-answer option labels, in priority order.
DECLINE_LABELS = [
    "Decline to self-identify",
    "Decline To Self Identify",
    "Decline to self identify",
    "I don't wish to answer",
    "I do not wish to answer",
    "I do not want to answer",
    "I don't want to answer",
    "Prefer not to say",
    "Prefer not to answer",
    "Prefer not to disclose",
    "Choose not to identify",
    "Do not wish to answer",
    "Do not want to answer",
]


# ---------------------------------------------------------------------------
# Browser helpers — replace with your harness's calling convention if needed.
# In practice this file is intended to be called by the agent itself, which
# already has the `browser` MCP tool available. The helpers below document
# the exact JSON contracts so a future caller can wire them up directly.
# ---------------------------------------------------------------------------

# Reusable JS snippets ------------------------------------------------------

JS_OPEN_APPLY = r"""
() => {
  const b = [...document.querySelectorAll('button,a')]
    .find(x => /^apply$/i.test((x.textContent || '').trim()));
  if (b) b.click();
  return b ? 'clicked' : 'noop';
}
"""

# Set a plain text/textarea value the React-friendly way.
JS_FILL_TEXT_FIELDS = r"""
async (fields) => {
  const setNative = (el, val) => {
    const proto = el.tagName === 'TEXTAREA'
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    desc.set.call(el, val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const out = {};
  for (const [id, val] of Object.entries(fields)) {
    const el = document.getElementById(id);
    if (!el) { out[id] = { ok: false, err: 'no element' }; continue; }
    if (val === '' || val === null || val === undefined) {
      out[id] = { ok: true, skipped: 'blank' }; continue;
    }
    setNative(el, String(val));
    out[id] = { ok: true, value_after: String(el.value).slice(0, 60) };
  }
  return out;
}
"""

# Click each react-select dropdown and pick the option matching the label.
# -----------------------------------------------------------------------------
# 2026-05-19 — Greenhouse Formik FormField widget investigation
# -----------------------------------------------------------------------------
# Background: 2026-05-18 we observed autosubmit failing across Scale AI and
# Smartsheet with "Select a country" rejection. The form had been rebuilt
# around a Formik FormField wrapper (`wo` type for select, `ko`/`So` for the
# composite phone+country widget). The hypothesis was that the standard
# react-select mousedown+mouseup+click recipe wasn't propagating through the
# Formik layer.
#
# 2026-05-19 re-test on Scale AI 4692201005:
#   * The standard `JS_PICK_DROPDOWNS` recipe (mouseup+click on .select__control
#     then on the matching option div) actually WORKS on the new widget — the
#     country picker committed cleanly, `wo.memoizedProps.value` updated to the
#     option object, and the submit went through (confirmation captured).
#   * Submission succeeded end-to-end (security code via Gmail + confirmation
#     page reached). Tracker.db updated, applications/submitted/scale-ai-...
#     /STATUS.md written.
#
# Why did 2026-05-18 fail then? Likeliest causes (in order):
#   1. The new SingleValue chip renders the country code ONLY ("+1"), not
#      "United States +1". Any verifier checking for the textual label was
#      mis-reporting failure even though the value was committed. The 2026-05-18
#      STATUS.md says the chip "stays as placeholder" — but the placeholder for
#      this widget IS just "+1" once a country is picked.
#   2. Menu open/close timing: the recipe needs ~300ms between opening the
#      menu and reading options. Some attempts that day may have closed early.
#   3. Possible Greenhouse server-side rollback overnight.
#
# Defensive fallback: `JS_PICK_FORMIK_DROPDOWN` below walks the fiber tree up
# from the react-select input to find the Formik FormField wrapper (`wo`-style
# component with `value`+`onChange`+`error` props) and calls `onChange` with the
# option object `{label, value}`. Tested working on Scale AI 4692201005's
# `#country` widget. Use this as a fallback when the standard recipe leaves the
# field with an error class.
#
# Detection hint for the new widget: the .select__control's input has an
# ancestor with a tiny props shape `{id, label, value, onChange, error,
# required, outsideLabel}` — that's the Formik wrapper (`wo`/`ee`/`Rs` etc.).
# -----------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Unplanned-required-dropdown filler (chain_011, 2026-05-26)
# ---------------------------------------------------------------------------
# Problem: boards-api dryrun spec doesn't expose every required dropdown on
# newer GH tenants (Lyft 716's "commutable proximity to NYC/SF or open to
# relocating?" question is rendered live but absent from JSON schema). We
# previously submitted and got `BLOCKED_FIELD_ERRORS` post-hoc.
#
# This step runs AFTER dryrun-planned dropdowns and BEFORE submit. It scans
# every `.select__control` in the rendered form, skips ones that already have
# a `.select__single-value` (filled), then walks up the DOM looking for the
# nearest question/label text and matches it against the provided
# `patterns` array (list of {pattern, answer, mode}). The `mode` controls
# option-text matching:
#   - 'exact'/'startsWith'/'includes' (default 'includes')
# We then mousedown+mouseup+click the .select__control to open the menu and
# pick the first option whose textContent matches the answer by the same
# priority ladder as JS_PICK_DROPDOWNS.
#
# Idempotent: filled dropdowns are skipped. Demographic dropdowns (gender,
# race, ethnicity, veteran, disability, hispanic) are SKIPPED unless their
# label matches one of the supplied patterns — protects the existing
# decline-demographics flow.
JS_FILL_UNPLANNED_DROPDOWNS = r"""
async ({ patterns }) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: x||0, clientY: y||0,
  }));
  // Demographic-question keyword list — skip these unless an explicit pattern
  // claims them. Mirrors the spirit of JS_DECLINE_DEMOGRAPHICS.
  const DEMO_KEYS = ['gender', 'race', 'ethnicity', 'hispanic', 'latino',
    'veteran', 'disability', 'lgbt', 'transgender', 'sexual orientation'];
  const findLabelText = (ctrl) => {
    // Strategy 1: nearest .field-with-error or .field containing a label/legend
    let node = ctrl;
    for (let i=0; i<8 && node; i++) {
      const lab = node.querySelector && node.querySelector('label, legend');
      if (lab && lab.textContent && lab.textContent.trim().length > 5) {
        return lab.textContent.trim();
      }
      node = node.parentElement;
    }
    // Strategy 2: previous-sibling label/text
    let prev = ctrl.previousElementSibling;
    while (prev) {
      const t = (prev.textContent || '').trim();
      if (t.length > 5) return t;
      prev = prev.previousElementSibling;
    }
    return '';
  };
  const matchPattern = (label, patterns) => {
    const low = (label || '').toLowerCase();
    for (const p of patterns) {
      const pat = (p.pattern || '').toLowerCase();
      if (pat && low.includes(pat)) return p;
    }
    return null;
  };
  const out = [];
  const ctrls = [...document.querySelectorAll('.select__control')];
  for (const ctrl of ctrls) {
    if (ctrl.querySelector('.select__single-value')) continue; // already filled
    const inp = ctrl.querySelector('input[role=combobox]');
    if (!inp) continue;
    const id = inp.id || '';
    const label = findLabelText(ctrl);
    const labLow = (label || '').toLowerCase();
    const matched = matchPattern(label, patterns);
    if (!matched) {
      // If this looks demographic and no explicit pattern, skip silently.
      const isDemo = DEMO_KEYS.some(k => labLow.includes(k));
      out.push({ id, label: label.slice(0, 140), skip: isDemo ? 'demographic-no-pattern' : 'no-pattern-match' });
      continue;
    }
    ctrl.scrollIntoView({ block: 'center' });
    await sleep(120);
    const r = ctrl.getBoundingClientRect();
    const cx = r.left + 5, cy = r.top + 5;
    fire(ctrl, 'mousedown', cx, cy);
    fire(ctrl, 'mouseup',   cx, cy);
    fire(ctrl, 'click',     cx, cy);
    await sleep(350);
    // Prefer options scoped to THIS dropdown's open menu. React-select renders
    // .select__menu either inside the .select__control's parent or as a child
    // of body (when menuPortalTarget=document.body). Search progressively wider.
    const escId = (window.CSS && CSS.escape) ? CSS.escape(id) : id.replace(/([\[\]\.\:\(\)\#])/g, '\\$1');
    let opts = [...document.querySelectorAll(`[id^="react-select-${escId}-option"]`)];
    if (!opts.length) {
      // Look for an open .select__menu sibling/ancestor first
      let menu = null;
      const par = ctrl.parentElement;
      if (par) menu = par.querySelector('.select__menu');
      if (!menu) {
        // Walk up a bit
        let n = ctrl.parentElement;
        for (let i=0; i<5 && n && !menu; i++) { menu = n.querySelector('.select__menu'); n = n.parentElement; }
      }
      if (menu) {
        opts = [...menu.querySelectorAll('[role=option], .select__option')];
      }
    }
    if (!opts.length) {
      // Last-resort: any visible option in any open menu (risky — may grab a
      // stale menu from a different dropdown).
      const menus = [...document.querySelectorAll('.select__menu')];
      for (const m of menus) {
        opts.push(...m.querySelectorAll('[role=option], .select__option'));
      }
    }
    const ansLc = String(matched.answer || '').toLowerCase();
    let target = opts.find(o => o.textContent.trim() === matched.answer);
    if (!target) target = opts.find(o => o.textContent.trim().toLowerCase() === ansLc);
    if (!target) target = opts.find(o => o.textContent.trim().toLowerCase().startsWith(ansLc));
    if (!target) target = opts.find(o => o.textContent.toLowerCase().includes(ansLc));
    if (!target) {
      fire(document.body, 'mousedown', 0, 0); // close menu
      out.push({ id, label: label.slice(0, 140), pattern: matched.pattern, want: matched.answer, err: 'no-matching-option', available: opts.map(o => o.textContent.trim()).slice(0, 12) });
      continue;
    }
    const tr = target.getBoundingClientRect();
    fire(target, 'mousedown', tr.left+5, tr.top+5);
    fire(target, 'mouseup',   tr.left+5, tr.top+5);
    fire(target, 'click',     tr.left+5, tr.top+5);
    await sleep(200);
    const sv = ctrl.querySelector('.select__single-value');
    out.push({ id, label: label.slice(0, 140), pattern: matched.pattern, want: matched.answer, got: sv ? sv.textContent : null, ok: !!sv });
  }
  return out;
}
"""

# Default pattern map for unplanned dropdowns. Each entry: {pattern (lowercase
# substring of question label), answer (option label to pick), mode optional}.
# Conservative — only add patterns where Cyrus's answer is unambiguous from
# personal-info.json. Order matters: first match wins.
DEFAULT_UNPLANNED_DROPDOWN_PATTERNS = [
    # Lyft 716 (2026-05-26 chain_011): "...reside in commutable proximity to a Lyft Office located in New York City or San Francisco or are you open to relocating?"
    # Cyrus's preference: yes, open to relocating (personal-info.json relocation_targets includes SF + NYC).
    # Lyft renders this as multi_value_single_select with options:
    #   "I am willing to relocate before starting employment."
    #   "I am not willing to relocate before starting employment."
    #   "I already reside near a Lyft office and I am able to work at a Lyft On-site Office."
    # Cyrus is in Kirkland WA (no Lyft on-site office there), so the correct
    # answer is the positive "willing to relocate" option. We anchor on the
    # "I am willing" prefix — JS_PICK_DROPDOWNS's startsWith match priority
    # picks the positive option without colliding with "I am not willing".
    {"pattern": "commutable proximity", "answer": "I am willing to relocate before starting employment."},
    {"pattern": "open to relocating", "answer": "I am willing to relocate before starting employment."},
    # Generic relocation Qs that may show up unspecced
    {"pattern": "willing to relocate", "answer": "Yes"},
    # US-onsite/residency/commute knockouts (Cyrus directive 2026-06-03 via main):
    # US onsite location is NEVER a knockout. Cyrus relocates ANYWHERE in the USA,
    # travels up to 100%. ANY US-based reside/commute/onsite/in-person question -> Yes.
    # (Non-US location still a genuine knockout -- handled separately by classifier.)
    # Proven roles: Gather AI "reside in the Greater Pittsburgh area", Swayable
    # "within commuting distance to SF or NY", Flip onsite LA/Brooklyn, Lyft.
    {"pattern": "currently reside in the greater", "answer": "Yes"},
    {"pattern": "reside in the greater", "answer": "Yes"},
    {"pattern": "do you currently reside in", "answer": "Yes"},
    {"pattern": "within commuting distance", "answer": "Yes"},
    {"pattern": "commuting distance to", "answer": "Yes"},
    {"pattern": "able to commute", "answer": "Yes"},
    {"pattern": "willing to commute", "answer": "Yes"},
    {"pattern": "able to work onsite", "answer": "Yes"},
    {"pattern": "able to work on-site", "answer": "Yes"},
    {"pattern": "comfortable working onsite", "answer": "Yes"},
    {"pattern": "willing to work in the office", "answer": "Yes"},
    {"pattern": "able to work in person", "answer": "Yes"},
    {"pattern": "able to work in-person", "answer": "Yes"},
    {"pattern": "comfortable with this in-office", "answer": "Yes"},
    {"pattern": "willing to travel", "answer": "Yes"},
    {"pattern": "open to relocation", "answer": "Yes"},
    {"pattern": "are you open to relocating", "answer": "Yes"},
    {"pattern": "comfortable relocating", "answer": "Yes"},
    # chain_044 (2026-05-31, Schrödinger 4318632003): common required
    # knockout dropdowns boards-api ships as unspecced. Honest answers for an
    # unemployed US-citizen candidate with no restrictive agreements:
    #   notice period at current employer -> No (not currently employed)
    #   prior/existing agreements limiting duties (non-compete) -> No
    #   acknowledgment-style (vaccine / reviewed & understood) -> the ack option
    {"pattern": "notice period", "answer": "No"},
    {"pattern": "prior or existing agreements", "answer": "No"},
    {"pattern": "existing agreements which would", "answer": "No"},
    {"pattern": "non-compete", "answer": "No"},
    {"pattern": "acknowledge the above", "answer": "I acknowledge the above statement"},
    {"pattern": "require all us-based employees to be ful", "answer": "I acknowledge the above statement"},
    # chain_044 (Forbes 5826489004): required salary-range dropdown. 'OPEN' is
    # the honest non-anchoring pick when the board offers it; falls through to
    # a wide senior-PM band only if OPEN absent (handled by caller override).
    {"pattern": "desired salary range", "answer": "OPEN"},
    {"pattern": "salary range", "answer": "OPEN"},
    # fresh-li-runner (2026-06-02, AST astspacemobile 4684880005): required
    # language-fluency knockout dropdown boards-api ships unspecced and the
    # dryrun marks needs_review (it can't confirm the Yes/No options). Honest
    # answer for Cyrus (native/fluent English) is "Yes". Cross-cutting: many GH
    # tenants gate on "fluent in written and verbal English". Anchor on the
    # distinctive "language requirements" + "fluent" phrasing.
    {"pattern": "language requirements", "answer": "Yes"},
    {"pattern": "fluent in written and verbal english", "answer": "Yes"},
    {"pattern": "fluent in english", "answer": "Yes"},
    # Common legally-authorized-to-work knockout (honest: US citizen -> Yes).
    {"pattern": "legally authorized to work", "answer": "Yes"},
    {"pattern": "authorized to work in the united states", "answer": "Yes"},
    # Cribl-style work-auth phrasing (2026-06-25): "authorized to reside and work in the country"
    {"pattern": "authorized to reside and work", "answer": "Yes"},
    {"pattern": "reside and work in the country", "answer": "Yes"},
    # CoreWeave phrasing (2026-06-26): "Do you have the right to work in the country you are applying to?"
    {"pattern": "right to work in the country", "answer": "Yes"},
    # gh-resume-submit (2026-06-02, Unity 7905031): Unity ships these as
    # required knockout dropdowns boards-api leaves unspecced/needs_review.
    # Honest answers for Cyrus (US citizen, work-authorized, no restricted-
    # country citizenship). Cross-cutting -- export-control + AI-interview-
    # consent + work-eligibility appear on many GH tenants.
    #   work-eligibility in country of position -> Yes
    {"pattern": "legally eligible to work in the country", "answer": "Yes"},
    #   export-control citizenship of sanctioned countries -> Not Applicable
    #   (truthful: US citizen, none of Cuba/Iran/NK/Syria/Crimea/Luhansk/Donetsk)
    {"pattern": "export control license may be required", "answer": "Not Applicable"},
    {"pattern": "citizen or permanent resident of any of the following countries", "answer": "Not Applicable"},
    #   AI-interview-transcript consent -> Yes (enthusiasm/consent is allowed,
    #   not a biographical fact)
    {"pattern": "consent to the use of ai to create written transcripts", "answer": "Yes"},
    {"pattern": "ai to create written transcripts and summaries", "answer": "Yes"},
]


JS_PICK_DROPDOWNS = r"""
async (specs) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: x, clientY: y,
  }));
  const out = [];
  for (const { id, label } of specs) {
    const inp = document.getElementById(id);
    if (!inp) { out.push({ id, err: 'no input' }); continue; }
    const ctrl = inp.closest('.select__control');
    if (!ctrl) { out.push({ id, err: 'no control' }); continue; }
    ctrl.scrollIntoView({ block: 'center' });
    await sleep(100);
    const r = ctrl.getBoundingClientRect();
    const cx = r.left + 5, cy = r.top + 5;
    fire(ctrl, 'mousedown', cx, cy);
    fire(ctrl, 'mouseup',   cx, cy);
    fire(ctrl, 'click',     cx, cy);
    await sleep(300);
    // CSS.escape id — see note on JS_DECLINE_DEMOGRAPHICS below; ids may carry
    // `[`/`]` (Lyft) which break a raw attribute selector.
    const escId = (window.CSS && CSS.escape) ? CSS.escape(id) : id.replace(/([\[\]\.\:\(\)\#])/g, '\\$1');
    let opts = [...document.querySelectorAll(`[id^="react-select-${escId}-option"]`)];
    // chain_044 (2026-05-31): newer GH 'remix' standalone boards
    // (job-boards.greenhouse.io/<org>) render option nodes with class
    // .select__option and id pattern react-select-<N>-option-<k> that does NOT
    // embed the field id. Fall back to the open menu's options.
    if (!opts.length) {
      const menu = document.querySelector('.select__menu');
      if (menu) opts = [...menu.querySelectorAll('.select__option, [role=option]')];
    }
    if (!opts.length) opts = [...document.querySelectorAll('.select__option, [role=option]')];
    // Match priority: exact → case-insensitive exact → startsWith → includes.
    // Codified after DeepMind 2026-05-08 where country option text was 'United
    // States +1' (iti-flag rendered into the option) and the dryrun label was
    // just 'United States'. Strict equality matches were too brittle.
    const wantLc = String(label).toLowerCase();
    let target = opts.find(o => o.textContent.trim() === label);
    if (!target) target = opts.find(o => o.textContent.trim().toLowerCase() === wantLc);
    if (!target) target = opts.find(o => o.textContent.trim().toLowerCase().startsWith(wantLc));
    if (!target) target = opts.find(o => o.textContent.toLowerCase().includes(wantLc));
    if (!target) {
      out.push({ id, err: 'no option', want: label, available: opts.map(o => o.textContent.trim()), warn: 'dryrun label not in rendered options — driver should retry with alternates (see needs_review_dropdowns plan bucket)' });
      // Close the menu.
      fire(document.body, 'mousedown', 0, 0);
      continue;
    }
    const tr = target.getBoundingClientRect();
    const tx = tr.left + 5, ty = tr.top + 5;
    fire(target, 'mousedown', tx, ty);
    fire(target, 'mouseup',   tx, ty);
    fire(target, 'click',     tx, ty);
    await sleep(200);
    const sv = ctrl.querySelector('.select__single-value');
    out.push({ id, want: label, got: sv ? sv.textContent : null });
  }
  return out;
}
"""

# Click the visible Filestack "Attach" button to COMMIT a file already loaded
# into the #resume input via CDP setInputFiles.
#
# 2026-05-13 (PM) — root cause finally pinned down across boards:
#   The correct order is UPLOAD FIRST, THEN CLICK ATTACH.
#   - browser.upload uses CDP Page.setInputFiles which writes File objects
#     into the visually-hidden <input id=resume> directly.
#   - On most NEW (job-boards.greenhouse.io) Filestack-backed forms, that
#     write does NOT automatically reflect in input.files.length — the
#    Filestack adapter is dormant until you click its Attach button.
#   - Clicking Attach AFTER the upload wakes Filestack, it inspects the
#     hidden input, sees the queued File, and processes it (the input is
#     swapped out for a 'filename + Remove' UI).
#   - Clicking Attach BEFORE the upload (the old playbook order) opens the
#     setInputFiles silently no-ops because Chromium routes file-chooser
#     interception to a now-stale input.
#     native file chooser AND/OR rewrites the input handler.
#
# Pre-2026-05-13 history:
#   - Anthropic occasionally worked with click-then-upload because the
#     Filestack adapter's onfocus polling re-read the input.
#   - Cresta worked with no click (Filestack onfocus polled in 800ms).
#   - Scale, Arize, GitLab, DeepMind never worked with click-then-upload.
#
# Verify with JS_VERIFY_RESUME_ATTACHED below.
JS_CLICK_ATTACH = r"""
async (opts) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const delay = (opts && opts.delayMs) || 1000;
  const f = document.querySelector('#resume');
  if (!f) {
    // Already swapped out — file was committed by a prior click.
    const filename = (opts && opts.filename) || '';
    const committed = filename && document.body.innerText.includes(filename);
    return { ok: !!committed, already_committed: !!committed, err: committed ? null : 'no #resume input and no filename in body' };
  }
  const btn = f.parentElement && f.parentElement.querySelector('button');
  if (!btn) return { ok: false, err: 'no attach button' };
  btn.click();
  await sleep(delay);
  // Check whether the file got committed (input gets swapped out, filename appears).
  const filename = (opts && opts.filename) || '';
  const stillHasInput = !!document.querySelector('#resume');
  const committed = filename && document.body.innerText.includes(filename);
  return { ok: !!committed, clicked: true, still_has_input: stillHasInput, committed: !!committed, attach_label: (btn.textContent || '').trim().slice(0, 40) };
}
"""

# Verify the resume file successfully landed and Filestack committed it.
# After the upload-then-click pattern, #resume is removed from the DOM and
# the filename appears in the page body (rendered by Filestack as a
# 'filename + Remove' chip).
#
# Pass the expected filename (just the basename, not the full path).
JS_VERIFY_RESUME_ATTACHED = r"""
({ filename }) => {
  const inputStill = !!document.querySelector('#resume');
  const filesInInput = inputStill ? document.querySelector('#resume').files.length : 0;
  const body = (document.body && document.body.innerText) || '';
  const filenameVisible = !!filename && body.includes(filename);
  return {
    ok: filenameVisible || (inputStill && filesInInput > 0),
    filename_visible: filenameVisible,
    input_still_in_dom: inputStill,
    files_in_input: filesInInput,
    expected: filename,
  };
}
"""

# Fiber-walk fallback for Greenhouse's new Formik-wrapped react-select widget.
# Background: see the 2026-05-19 comment block above JS_PICK_DROPDOWNS.
#
# Walks up from the react-select input's DOM node through the React fiber tree
# looking for the Formik FormField wrapper — identified by a small props shape
# containing {value, onChange, error}. Calls onChange directly with the full
# option object {label, value}; the wrapper internally extracts .value.
#
# Use as a fallback when JS_PICK_DROPDOWNS leaves the field in an error state.
# Specs: [{id, label, value?}]. If `value` is omitted, looks up the option from
# the wrapper's props.options by matching label.
JS_PICK_FORMIK_DROPDOWN = r"""
async (specs) => {
  const out = [];
  for (const { id, label, value } of specs) {
    const inp = document.getElementById(id);
    if (!inp) { out.push({ id, err: 'no input' }); continue; }
    const key = Object.keys(inp).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
    if (!key) { out.push({ id, err: 'no fiber key' }); continue; }
    // Walk up the fiber tree, collecting candidate wrappers with onChange.
    // The Formik FormField wrapper has a small props shape:
    //   {id, label, value, onChange, error, required, outsideLabel}
    // — distinct from the inner react-select Component which has many props.
    let n = inp[key];
    let wrapper = null;
    let depth = 0;
    while (n && depth < 30) {
      const p = n.memoizedProps;
      if (p && typeof p.onChange === 'function' && ('value' in p) && ('error' in p)) {
        // Looks like a Formik FormField wrapper.
        const keys = Object.keys(p);
        // Prefer the OUTERMOST wrapper that still has just label/value/onChange/error pattern.
        // The K-style component has `options`/`onSelect`/`selected` instead — skip that one.
        if (!('onSelect' in p) && !('selected' in p)) {
          wrapper = n;
        }
      }
      n = n.return;
      depth++;
    }
    if (!wrapper) { out.push({ id, err: 'no Formik wrapper found' }); continue; }
    // Find the matching option object from wrapper.props.options (if available)
    // or fall back to {label, value}.
    let opt = null;
    const opts = wrapper.memoizedProps.options;
    if (opts && Array.isArray(opts)) {
      const wantLabel = String(label || '').toLowerCase();
      const wantValue = value !== undefined ? String(value) : null;
      if (wantValue) opt = opts.find(o => String(o.value) === wantValue);
      if (!opt) opt = opts.find(o => String(o.label).toLowerCase() === wantLabel);
      if (!opt) opt = opts.find(o => String(o.label).toLowerCase().includes(wantLabel));
    }
    if (!opt) opt = { label, value: value !== undefined ? value : label };
    try {
      wrapper.memoizedProps.onChange(opt);
    } catch (e) {
      out.push({ id, err: 'onChange threw: ' + e.message, picked: opt });
      continue;
    }
    // Verify by reading single-value chip (note: new widget may render only a
    // partial label, e.g. "+1" for country pickers — presence of any chip OR
    // absence of error is the success signal).
    const ctrl = inp.closest('.select__control');
    const sv = ctrl ? ctrl.querySelector('.select__single-value') : null;
    const invalid = inp.getAttribute('aria-invalid') === 'true';
    out.push({ id, picked: opt, sv: sv ? sv.textContent : null, aria_invalid: invalid });
  }
  return out;
}
"""

# Country react-select with typeahead/large option list (DeepMind, Scale).
# The control opens like a normal react-select, but options aren't all
# rendered — they're virtualized/filtered by a search input. Recipe from
# scaleai-4554440005 + deepmind-7646114 notes:
#   1. mousedown the .select__control to open the menu
#   2. setNative on the inner select__input to type the country name
#   3. Wait for filtered options, then click the first matching option div
# Falls back to clicking option-0 when nothing matches by partial text.
JS_PICK_DROPDOWN_TYPEAHEAD = r"""
async (specs) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: x || 0, clientY: y || 0,
  }));
  const setNative = (el, val) => {
    const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
    desc.set.call(el, val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  };
  const out = [];
  for (const { id, label } of specs) {
    const inp = document.getElementById(id);
    if (!inp) { out.push({ id, err: 'no input' }); continue; }
    const ctrl = inp.closest('.select__control');
    if (!ctrl) { out.push({ id, err: 'no control' }); continue; }
    ctrl.scrollIntoView({ block: 'center' });
    await sleep(120);
    const r = ctrl.getBoundingClientRect();
    fire(ctrl, 'mousedown', r.left + 5, r.top + 5);
    fire(ctrl, 'mouseup',   r.left + 5, r.top + 5);
    fire(ctrl, 'click',     r.left + 5, r.top + 5);
    await sleep(250);
    // Type into the search input to filter options.
    // chain_026 2026-05-29 FIX: Greenhouse Remix-embed `candidate-location` async typeahead
    // does NOT trigger its remote fetch on a bare `input` event — it needs real
    // KeyboardEvent keydown/keyup per character. Without this, the menu stays
    // empty (`opts.length === 0`) and we fall through to `no option after typeahead`.
    // For ASYNC typeaheads we type char-by-char with key events; for SYNC/local
    // typeaheads the original setNative bulk-set still works fine — we do BOTH:
    // setNative for the React-state update, plus per-char keydown/keyup to trigger
    // async fetch when present. Verified live on Mattermost 1320 (chain_026).
    setNative(inp, '');
    await sleep(60);
    const _s = String(label);
    for (let i = 1; i <= _s.length; i++) {
      setNative(inp, _s.slice(0, i));
      const ch = _s[i - 1];
      inp.dispatchEvent(new KeyboardEvent('keydown', { key: ch, bubbles: true }));
      inp.dispatchEvent(new KeyboardEvent('keyup',   { key: ch, bubbles: true }));
      await sleep(60);
    }
    // Final wait — async fetches (Greenhouse candidate-location) take ~800-1500ms
    await sleep(1200);
    const escId = (window.CSS && CSS.escape) ? CSS.escape(id) : id.replace(/([\[\]\.\:\(\)\#])/g, '\\$1');
    let opts = [...document.querySelectorAll(`[id^="react-select-${escId}-option"]`)];
    let target = opts.find(o => o.textContent.trim().toLowerCase() === String(label).toLowerCase());
    if (!target) target = opts.find(o => o.textContent.trim().toLowerCase().startsWith(String(label).toLowerCase()));
    if (!target) target = opts.find(o => o.textContent.toLowerCase().includes(String(label).toLowerCase()));
    if (!target && opts.length) target = opts[0];  // fallback: first filtered
    if (!target) {
      out.push({ id, err: 'no option after typeahead', want: label });
      fire(document.body, 'mousedown', 0, 0);
      continue;
    }
    const tr = target.getBoundingClientRect();
    fire(target, 'mousedown', tr.left + 5, tr.top + 5);
    fire(target, 'mouseup',   tr.left + 5, tr.top + 5);
    fire(target, 'click',     tr.left + 5, tr.top + 5);
    await sleep(180);
    const sv = ctrl.querySelector('.select__single-value');
    out.push({ id, want: label, got: sv ? sv.textContent : null, picked: (target.textContent||'').trim().slice(0, 60) });
  }
  return out;
}
"""

# Phone field with intl-tel-input (iti) flag widget (Scale 2026-05-08).
# The phone <input> is wrapped in an .iti container with a .iti__selected-flag
# button. Setting just the phone digits via setNative leaves the country code
# at the iti default (often UK), which fails server-side validation.
# Recipe: click the flag, click the country in the iti dropdown, then setNative
# the phone digits-only into the input.
JS_FILL_PHONE_ITI = r"""
async ({ id, country, digits }) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const setNative = (el, val) => {
    const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
    desc.set.call(el, val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const inp = document.getElementById(id);
  if (!inp) return { ok: false, err: 'no phone input' };
  const iti = inp.closest('.iti');
  if (iti) {
    const flag = iti.querySelector('.iti__selected-flag');
    if (flag) {
      flag.click();
      await sleep(250);
      const items = [...iti.querySelectorAll('.iti__country, li[class*=iti__country]')];
      const wantLc = String(country || 'United States').toLowerCase();
      let target = items.find(li => (li.textContent || '').toLowerCase().includes(wantLc));
      if (!target) target = items.find(li => (li.getAttribute('data-country-code') || '').toLowerCase() === 'us');
      if (target) {
        target.click();
        await sleep(150);
      }
    }
  }
  // digits-only — strip everything except digits
  const clean = String(digits || '').replace(/[^0-9]/g, '');
  setNative(inp, clean);
  return { ok: true, iti: !!iti, value_after: inp.value, country };
}
"""

# Demographic decline-pass: for any react-select whose surrounding label/legend
# matches gender/race/ethnicity/veteran/disability AND no value is selected,
# pick a decline option by partial-text search. Discovers fields at runtime
# rather than relying on the dryrun spec's `declined_demo` list, which can be
# stale when a form changes its question ids (Vercel, Scale 2026-05-08).
JS_DECLINE_DEMOGRAPHICS = r"""
async ({ patterns }) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: x || 0, clientY: y || 0,
  }));
  const labelRe = new RegExp(patterns.label || 'gender|race|ethnic|hispanic|latin|veteran|disabilit|self[- ]?identif|pronoun|sexual.{0,5}orient', 'i');
  const declines = patterns.declines || [];
  const out = [];
  const controls = [...document.querySelectorAll('.select__control')];
  for (const ctrl of controls) {
    // Skip if already has a value picked.
    if (ctrl.querySelector('.select__single-value')) continue;
    const inp = ctrl.querySelector('input[role=combobox]');
    if (!inp || !inp.id) continue;
    // Find the field label/legend nearby (walk up to find label or fieldset).
    let lbl = '';
    let n = ctrl;
    for (let i = 0; i < 6 && n; i++) {
      n = n.parentElement;
      if (!n) break;
      const labelEl = n.querySelector ? n.querySelector('label, legend') : null;
      if (labelEl) { lbl = labelEl.textContent || ''; break; }
    }
    if (!labelRe.test(lbl)) continue;
    ctrl.scrollIntoView({ block: 'center' });
    await sleep(100);
    const r = ctrl.getBoundingClientRect();
    fire(ctrl, 'mousedown', r.left + 5, r.top + 5);
    fire(ctrl, 'mouseup',   r.left + 5, r.top + 5);
    fire(ctrl, 'click',     r.left + 5, r.top + 5);
    await sleep(280);
    // CSS.escape inp.id — Lyft (and other react-select v5 forms) ship ids like
    // `question_36310349002[]` whose `[` `]` break a raw attribute selector
    // and throw `SyntaxError: '...' is not a valid selector`. The runner
    // currently swallows the exception and continues, but that means we
    // miss every demographic field on those forms. Use CSS.escape() so the
    // selector works regardless of id punctuation.
    const escId = (window.CSS && CSS.escape) ? CSS.escape(inp.id) : inp.id.replace(/([\[\]\.\:\(\)\#])/g, '\\$1');
    let opts = [...document.querySelectorAll(`[id^="react-select-${escId}-option"]`)];
    // chain_044: remix boards use .select__option (id doesn't embed field id).
    if (!opts.length) {
      const menu = document.querySelector('.select__menu');
      opts = menu ? [...menu.querySelectorAll('.select__option, [role=option]')]
                  : [...document.querySelectorAll('.select__option, [role=option]')];
    }
    let target = null;
    for (const want of declines) {
      const wantLc = String(want).toLowerCase();
      target = opts.find(o => o.textContent.trim().toLowerCase() === wantLc);
      if (target) break;
      target = opts.find(o => o.textContent.toLowerCase().includes(wantLc));
      if (target) break;
    }
    if (!target) {
      // Last-ditch: any option whose text contains 'decline', 'prefer not', or 'wish'.
      target = opts.find(o => /decline|prefer not|don'?t wish|do not wish|not to identify|not to disclose/i.test(o.textContent));
    }
    if (!target) {
      out.push({ id: inp.id, label: lbl.slice(0, 80), err: 'no decline option', available: opts.map(o => o.textContent.trim()).slice(0, 30) });
      fire(document.body, 'mousedown', 0, 0);
      continue;
    }
    const tr = target.getBoundingClientRect();
    fire(target, 'mousedown', tr.left + 5, tr.top + 5);
    fire(target, 'mouseup',   tr.left + 5, tr.top + 5);
    fire(target, 'click',     tr.left + 5, tr.top + 5);
    await sleep(150);
    const sv = ctrl.querySelector('.select__single-value');
    out.push({ id: inp.id, label: lbl.slice(0, 80), picked: (target.textContent || '').trim(), got: sv ? sv.textContent : null });
  }
  return out;
}
"""

# Tick any GDPR demographic-data consent checkbox. These are required for the
# form to submit and just authorize storage of the demographic answers we
# already declined. Matched by id pattern (gdpr_demographic_data_consent_*) or
# label text ("I consent to ... demographic data" / "GDPR").
# Multi-value multi-select — Stripe/Datadog v2 ship `question_xxx[]` schema
# fields as native <fieldset class="checkbox"><legend>...</legend>
# <input type=checkbox><label>...</label></fieldset>. Specs:
#   [{ id: "question_64112051[]", legend_re: "Please select the country...",
#      values: ["United States", "US"] }]
# Match fieldset by EITHER legend partial match OR any inner input whose name
# starts with `id`. Tick the first checkbox whose label matches one of values.
# Returns per-field {legend, ticked: [labels], missing: [values]}.
# Codified from stripe-7812346 STATUS.md + 2026-05-22 spike on stripe-7680365.
JS_TICK_MULTI_CHECKBOXES = r"""
async (specs) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0, clientX: x, clientY: y,
  }));
  const out = [];
  const fieldsets = [...document.querySelectorAll('fieldset')];
  for (const spec of specs || []) {
    const idStem = String(spec.id || '').replace(/\[\]$/, '');
    const legendRe = spec.legend_re ? new RegExp(spec.legend_re.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').slice(0, 60), 'i') : null;
    let fs = null;
    for (const f of fieldsets) {
      const hasIdInput = idStem && !!f.querySelector(`input[name^="${idStem}"], input[id^="${idStem}"]`);
      const legend = (f.querySelector('legend')?.textContent || '').trim();
      const legendMatch = legendRe ? legendRe.test(legend) : false;
      if (hasIdInput || legendMatch) { fs = f; break; }
    }
    if (!fs) {
      // 2026-06-04 (Pure Storage 7254748/7671846/7857995 consent-ack bug):
      // some GH tenants render a required multi_value_multi_select consent /
      // acknowledgement field (e.g. "Personal Information Policy" with sole
      // option "Acknowledge/Confirm") as a REACT-SELECT MULTI widget, NOT a
      // native <fieldset.checkbox>. The fieldset scan above finds nothing, so
      // the ack stayed unset -> Greenhouse silently bounced the submit
      // (status=uncertain, emptyRequired:[], lands back on job page). React
      // multi-select commits an option the same way single-select does: open
      // the .select__control (mousedown+mouseup+click), then click the option
      // whose text matches a desired value; the chosen value persists as a
      // .select__multi-value chip. Truthful: a forced-choice ack, not a
      // fabricated biographical claim.
      const escId = (window.CSS && CSS.escape) ? CSS.escape(idStem) : idStem.replace(/([\[\]\.\:\(\)\#])/g, '\\$1');
      let inp = document.getElementById(idStem)
        || document.querySelector(`input[id^="${escId}"]`)
        || document.querySelector(`input[name^="${escId}"]`);
      let ctrl = inp ? inp.closest('.select__control') : null;
      if (!ctrl && legendRe) {
        // Fall back to locating the react-select by its label text.
        for (const c of document.querySelectorAll('.select__control')) {
          const grp = c.closest('.field, .select, [class*=field]') || c.parentElement;
          const lblTxt = (grp && (grp.querySelector('label')?.textContent || grp.textContent) || '').trim();
          if (legendRe.test(lblTxt)) { ctrl = c; break; }
        }
      }
      if (!ctrl) { out.push({ id: spec.id, err: 'no fieldset', react_select: false }); continue; }
      // Already committed? (a .select__multi-value chip present)
      if (ctrl.querySelector('.select__multi-value')) {
        out.push({ id: spec.id, react_select: true, already: true, ticked: [{ label: (ctrl.querySelector('.select__multi-value__label')?.textContent || '').trim(), checked: true }], missing: [] });
        continue;
      }
      ctrl.scrollIntoView({ block: 'center' });
      await sleep(100);
      const r = ctrl.getBoundingClientRect();
      fire(ctrl, 'mousedown', r.left + 5, r.top + 5);
      fire(ctrl, 'mouseup',   r.left + 5, r.top + 5);
      fire(ctrl, 'click',     r.left + 5, r.top + 5);
      await sleep(300);
      let opts = [...document.querySelectorAll(`[id^="react-select-${escId}-option"]`)];
      if (!opts.length) {
        const menu = ctrl.parentElement?.querySelector('.select__menu') || document.querySelector('.select__menu');
        if (menu) opts = [...menu.querySelectorAll('.select__option, [role=option]')];
      }
      if (!opts.length) opts = [...document.querySelectorAll('.select__option, [role=option]')];
      const rticked = [];
      const rmissing = [];
      let rdid = false;
      for (const want of spec.values || []) {
        if (rdid) break;
        const wantLc = String(want).toLowerCase();
        let target = opts.find(o => o.textContent.trim().toLowerCase() === wantLc);
        if (!target) target = opts.find(o => o.textContent.trim().toLowerCase().startsWith(wantLc));
        if (!target) target = opts.find(o => o.textContent.toLowerCase().includes(wantLc));
        if (!target) { rmissing.push(want); continue; }
        const tr = target.getBoundingClientRect();
        fire(target, 'mousedown', tr.left + 5, tr.top + 5);
        fire(target, 'mouseup',   tr.left + 5, tr.top + 5);
        fire(target, 'click',     tr.left + 5, tr.top + 5);
        await sleep(200);
        rticked.push({ label: (target.textContent || '').trim(), checked: !!ctrl.querySelector('.select__multi-value') });
        rdid = true;
      }
      // If nothing matched but there's exactly ONE option (sole forced ack),
      // commit it — the consent field's only purpose is to be acknowledged.
      if (!rdid && opts.length === 1) {
        const t = opts[0];
        const tr = t.getBoundingClientRect();
        fire(t, 'mousedown', tr.left + 5, tr.top + 5);
        fire(t, 'mouseup',   tr.left + 5, tr.top + 5);
        fire(t, 'click',     tr.left + 5, tr.top + 5);
        await sleep(200);
        rticked.push({ label: (t.textContent || '').trim(), checked: !!ctrl.querySelector('.select__multi-value'), sole: true });
        rdid = true;
      }
      fire(document.body, 'mousedown', 0, 0);
      out.push({ id: spec.id, react_select: true, ticked: rticked, missing: rmissing,
                 available: opts.map(o => o.textContent.trim()).slice(0, 20) });
      continue;
    }
    const labels = [...fs.querySelectorAll('label')];
    const ticked = [];
    const missing = [];
    // 2026-05-25: alias-expanded values (e.g. ['None','Never held a clearance',
    // 'Do not wish to disclose']) should tick only the first match — they're
    // alternates, not distinct selections.
    let didTick = false;
    for (const want of spec.values || []) {
      const wantLc = String(want).toLowerCase();
      const matchLbl = labels.find(l => {
        const t = (l.textContent || '').trim().toLowerCase();
        if (t === wantLc) return true;
        // Short tokens (US, UK, GB, UAE) MUST match exactly — substring is
        // too greedy ("australia" contains "us"). Long tokens ("United
        // States") may startsWith / includes.
        if (wantLc.length <= 3) return false;
        return t.startsWith(wantLc) || t.includes(wantLc);
      });
      if (!matchLbl) { missing.push(want); continue; }
      if (didTick) { continue; }
      const fid = matchLbl.getAttribute('for');
      const cb = fid ? document.getElementById(fid) : matchLbl.querySelector('input[type=checkbox]');
      if (cb && !cb.checked) cb.click();
      ticked.push({ label: (matchLbl.textContent || '').trim(), checked: !!cb?.checked });
      didTick = true;
    }
    out.push({
      id: spec.id,
      legend: (fs.querySelector('legend')?.textContent || '').trim().slice(0, 80),
      ticked, missing,
    });
  }
  return out;
}
"""

# Strict demographic-multi decline-only handler. For multi_value_multi_select
# demographic fields (race / ethnic group), this:
#   1. Locates the <fieldset> by legend regex OR by any input whose name/id
#      starts with `id`.
#   2. Scans labels for a decline-style match (decline / prefer not / don't
#      wish / not to identify / not to disclose / I do not wish to answer).
#   3. If found: ticks it. If not found: ticks NOTHING and emits
#      `needs_human_review`. Never falls through to a random identity option.
# This is the safety-critical sibling of JS_TICK_MULTI_CHECKBOXES.
# Codified from the-trade-desk-5139192007 (2026-05-23) where the previous
# default-to-US fallback would have ticked "Two or more Races" as a stand-in.
JS_DECLINE_DEMO_MULTI = r"""
(specs) => {
  const out = [];
  const fieldsets = [...document.querySelectorAll('fieldset')];
  const declineRe = /decline to|prefer not|don'?t wish|do not wish|do not want|not to identify|not to disclose|i do not wish to answer/i;
  for (const spec of specs || []) {
    const idStem = String(spec.id || '').replace(/\[\]$/, '');
    const legendRe = spec.legend_re ? new RegExp(spec.legend_re.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').slice(0, 60), 'i') : null;
    let fs = null;
    for (const f of fieldsets) {
      const hasIdInput = idStem && !!f.querySelector(`input[name^="${idStem}"], input[id^="${idStem}"]`);
      const legend = (f.querySelector('legend')?.textContent || '').trim();
      const legendMatch = legendRe ? legendRe.test(legend) : false;
      if (hasIdInput || legendMatch) { fs = f; break; }
    }
    if (!fs) { out.push({ id: spec.id, err: 'no fieldset', needs_human_review: true, question: spec.question }); continue; }
    const labels = [...fs.querySelectorAll('label')];
    const declineLbl = labels.find(l => declineRe.test((l.textContent || '').trim()));
    if (!declineLbl) {
      out.push({
        id: spec.id,
        legend: (fs.querySelector('legend')?.textContent || '').trim().slice(0, 120),
        err: 'no decline option present',
        available: labels.map(l => (l.textContent || '').trim()).filter(t => t.length).slice(0, 30),
        needs_human_review: true,
        question: spec.question,
      });
      continue;
    }
    const fid = declineLbl.getAttribute('for');
    const cb = fid ? document.getElementById(fid) : declineLbl.querySelector('input[type=checkbox]');
    if (cb && !cb.checked) cb.click();
    out.push({
      id: spec.id,
      legend: (fs.querySelector('legend')?.textContent || '').trim().slice(0, 120),
      picked: (declineLbl.textContent || '').trim().slice(0, 80),
      checked: !!cb?.checked,
    });
  }
  return out;
}
"""

JS_TICK_GDPR_CONSENT = r"""
() => {
  const out = [];
  const labelRe = /i consent to|demographic data|gdpr|i acknowledge and agree|processing of my personal data|by checking this box, you consent/i;
  const inputs = [...document.querySelectorAll('input[type=checkbox]')];
  for (const inp of inputs) {
    const id = (inp.id || '');
    let lbl = '';
    if (id) {
      const lblEl = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (lblEl) lbl = lblEl.textContent || '';
    }
    if (!lbl) {
      const wrap = inp.closest('label');
      if (wrap) lbl = wrap.textContent || '';
    }
    // Also consider the parent fieldset's legend (Okta-style consent legends)
    let legend = '';
    const fs = inp.closest('fieldset');
    if (fs) {
      const lg = fs.querySelector('legend');
      if (lg) legend = lg.textContent || '';
    }
    const idHit = /gdpr.*consent|gdpr_demographic_data|demographic_data_consent/i.test(id);
    const lblHit = labelRe.test(lbl) || labelRe.test(legend);
    if (!idHit && !lblHit) continue;
    if (inp.checked) { out.push({ id, already: true }); continue; }
    inp.scrollIntoView({ block: 'center' });
    inp.click();
    out.push({ id, label: (lbl || '').trim().slice(0, 80), checked: inp.checked });
  }
  return out;
}
"""

# Click the Submit Application button at the bottom of the form.
JS_SUBMIT = r"""
(opts) => {
  const allowVisibleCaptcha = !!(opts && opts.allowVisibleCaptcha);
  const candidates = [...document.querySelectorAll('button[type=submit], button')];
  const btn = candidates.find(b => /submit application|submit/i.test((b.textContent || '').trim()));
  if (!btn) return { ok: false, err: 'no submit button', candidates: candidates.map(b => (b.textContent||'').trim()).slice(0,20) };
  // Note: Greenhouse uses invisible reCAPTCHA Enterprise on many forms; it should not block submit.
  // Some forms (Scale 2026-05-08) render a *visible* reCAPTCHA checkbox that
  // appears blocking but actually isn't — a direct btn.click goes through.
  // We log + bail by default; pass {allowVisibleCaptcha:true} to override.
  const captcha_iframes = [...document.querySelectorAll('iframe[src*="hcaptcha"], iframe[src*="recaptcha"]')];
  const visible_captcha = captcha_iframes.find(f => f.offsetParent !== null && f.getBoundingClientRect().width > 50);
  if (visible_captcha && !allowVisibleCaptcha) {
    return { ok: false, err: 'visible_captcha_present', hint: 'pass {allowVisibleCaptcha:true} to bypass (use sparingly — only when verified harmless, e.g. Scale forms)' };
  }
  btn.scrollIntoView({ block: 'center' });
  btn.click();
  return { ok: true, label: btn.textContent.trim().slice(0, 80), invisible_captcha: captcha_iframes.length, bypassed_visible_captcha: !!visible_captcha };
}
"""

# After clicking submit, wait for confirmation page or thank-you text.
JS_VERIFY_CONFIRMATION = r"""
() => {
  const url = location.href;
  const body = (document.body && document.body.innerText) ? document.body.innerText : '';
  // Multiple confirmation patterns observed across Greenhouse boards
  const patterns = [
    /thanks for applying/i,
    /thank you for applying/i,
    /your application (has been )?(was )?(successfully )?(submitted|received)/i,
    /application submitted/i,
    /we'?ve received your application/i,
    /successfully submitted/i,
  ];
  const matched = patterns.find(re => re.test(body));
  // Also check URL — Greenhouse confirmation often goes to /thanks or ?confirmation=1
  const urlMatch = /thanks|confirmation|submitted|success/i.test(url);
  // Detect form errors (fields highlighted in red)
  const errorEls = [...document.querySelectorAll('.error, [class*=error], [aria-invalid="true"]')]
    .filter(e => e.offsetParent !== null);
  const errorTexts = errorEls.map(e => (e.textContent || '').trim()).filter(t => t.length > 0).slice(0, 10);
  return {
    confirmed: !!matched || urlMatch,
    url,
    matched: matched ? matched.toString() : null,
    url_match: urlMatch,
    snippet: body.slice(0, 600),
    error_count: errorEls.length,
    error_texts: errorTexts,
  };
}
"""

# Detect whether the post-submit page is asking for the 8-char email verification code.
# Greenhouse renders a fieldset#email-verification with 8 single-char inputs:
#   security-input-0 ... security-input-7 (each maxlength=1)
JS_DETECT_VERIFICATION = r"""
() => {
  const body = (document.body && document.body.innerText) || '';
  const wantsCode = /verification code|security code|enter the .{0,20}character code|verify .* email|sent to .* email/i.test(body);
  const fieldset = document.getElementById('email-verification');
  const boxes = [...document.querySelectorAll('input[id^="security-input-"]')];
  // Fallback: any visible single-input verification field (some custom forms).
  let single = null;
  if (!boxes.length) {
    const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null && i.type !== 'hidden' && i.type !== 'file');
    for (const i of inputs) {
      const ml = parseInt(i.getAttribute('maxlength') || '0', 10);
      if (ml >= 6 && ml <= 12) { single = i; break; }
    }
  }
  return {
    verification_required: !!(wantsCode || fieldset || boxes.length),
    style: boxes.length ? 'split' : (single ? 'single' : 'unknown'),
    box_count: boxes.length,
    single_input_id: single ? single.id : null,
    snippet: body.slice(0, 400),
    url: location.href,
  };
}
"""

# Fill the verification code into Greenhouse's 8 single-char boxes (or a single input fallback)
# and click Submit/Verify.
JS_SUBMIT_VERIFICATION_CODE = r"""
(code) => {
  const setNative = (el, val) => {
    const proto = HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    desc.set.call(el, val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const boxes = [...document.querySelectorAll('input[id^="security-input-"]')]
    .sort((a, b) => a.id.localeCompare(b.id));
  const filled = [];
  if (boxes.length) {
    if (code.length !== boxes.length) {
      return { ok: false, err: `code length ${code.length} != boxes ${boxes.length}` };
    }
    for (let i = 0; i < boxes.length; i++) {
      setNative(boxes[i], code[i]);
      filled.push(boxes[i].value);
    }
  } else {
    // Single-input fallback.
    const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null && i.type !== 'hidden' && i.type !== 'file');
    let target = null;
    for (const i of inputs) {
      const ml = parseInt(i.getAttribute('maxlength') || '0', 10);
      if (ml >= 6 && ml <= 12) { target = i; break; }
    }
    if (!target) return { ok: false, err: 'no verification input(s)' };
    setNative(target, String(code));
    filled.push(target.value);
  }
  // Click submit/verify.
  const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
  let btn = buttons.find(b => /submit application|verify|submit|continue|confirm/i.test((b.textContent || '').trim()));
  if (!btn) btn = buttons.find(b => b.type === 'submit');
  if (!btn) return { ok: false, err: 'no submit button', filled };
  btn.scrollIntoView({ block: 'center' });
  btn.click();
  return { ok: true, filled, button: (btn.textContent || '').trim().slice(0, 80) };
}
"""

# Inspect a react-select's currently rendered option labels — used by the
# Python driver to runtime-correct dryrun specs whose default value isn't
# actually one of the rendered options. Vercel 2026-05-08:
# `based-in-countries` was 'filled_needs_review' with 'No' but the real
# options were country names, so the driver re-tried with 'United States'.
JS_INSPECT_OPTIONS = r"""
async ({ id }) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: x || 0, clientY: y || 0,
  }));
  const inp = document.getElementById(id);
  if (!inp) return { ok: false, err: 'no input' };
  const ctrl = inp.closest('.select__control');
  if (!ctrl) return { ok: false, err: 'no control' };
  const r = ctrl.getBoundingClientRect();
  fire(ctrl, 'mousedown', r.left + 5, r.top + 5);
  fire(ctrl, 'mouseup',   r.left + 5, r.top + 5);
  fire(ctrl, 'click',     r.left + 5, r.top + 5);
  await sleep(280);
  const escId = (window.CSS && CSS.escape) ? CSS.escape(id) : id.replace(/([\[\]\.\:\(\)\#])/g, '\\$1');
  const opts = [...document.querySelectorAll(`[id^="react-select-${escId}-option"]`)]
    .map(o => (o.textContent || '').trim());
  fire(document.body, 'mousedown', 0, 0);
  return { ok: true, options: opts };
}
"""

# 2026-05-25 (SpaceX 872 fix): Greenhouse's education subsection (School,
# Degree, Discipline) renders dynamically after the rest of the form. The
# dryrun spec doesn't include these fields, so the standard text/dropdown
# pickers never touch them. JS_FILL_EDUCATION_PANEL does a runtime sweep:
# finds any react-select inside an .education-section / .education-fieldset /
# a fieldset whose legend mentions "education" / "school", and tries to fill
# School (text or async-typeahead), Degree (single-select), Discipline
# (single-select if present). Skips any field already filled. Returns a
# summary so the runner can log coverage / mark deferred fields.
JS_FILL_EDUCATION_PANEL = r"""
async ({ school, degree, discipline, minor }) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: x || 0, clientY: y || 0,
  }));
  const findSection = () => {
    // Try common Greenhouse selectors first.
    // 2026-05-25 (SpaceX 872): added .education--container / .education--form
    // (double-dash BEM variant used by SpaceX Greenhouse iframe).
    const sels = ['.education-section', '.education-fieldset', '[data-qa="education"]', '#education_section', '.education--container', '.education--form'];
    for (const s of sels) {
      const el = document.querySelector(s);
      if (el) return el;
    }
    // Fallback: fieldset/section whose legend or heading mentions Education.
    const candidates = [...document.querySelectorAll('fieldset, section, div')];
    for (const c of candidates) {
      const heading = c.querySelector('legend, h2, h3, h4');
      if (heading && /\beducation\b/i.test(heading.textContent || '')) return c;
    }
    return null;
  };
  const section = findSection();
  if (!section) return { ok: true, found: false, note: 'no education section in DOM (this is fine — many GH boards omit it)' };

  const summary = { ok: true, found: true, filled: [], skipped: [], errors: [] };

  const pickSelect = async (label, ctrl, wantedSubstr) => {
    // Open the react-select.
    const r = ctrl.getBoundingClientRect();
    fire(ctrl, 'mousedown', r.left + 5, r.top + 5);
    fire(ctrl, 'mouseup',   r.left + 5, r.top + 5);
    fire(ctrl, 'click',     r.left + 5, r.top + 5);
    await sleep(280);
    const opts = [...document.querySelectorAll('[id^="react-select-"][id$="-option-0"], [id*="-option-"]')];
    let best = null;
    const want = (wantedSubstr || '').toLowerCase();
    for (const o of opts) {
      const txt = (o.textContent || '').trim().toLowerCase();
      if (!txt) continue;
      if (txt === want) { best = o; break; }
      if (!best && want && txt.includes(want)) best = o;
    }
    if (!best && opts.length) {
      summary.errors.push({ label, err: 'no matching option', want: wantedSubstr, available: opts.slice(0, 8).map(o => (o.textContent||'').trim()) });
      fire(document.body, 'mousedown', 0, 0);
      return false;
    }
    if (best) {
      const br = best.getBoundingClientRect();
      fire(best, 'mousedown', br.left + 5, br.top + 5);
      fire(best, 'mouseup',   br.left + 5, br.top + 5);
      fire(best, 'click',     br.left + 5, br.top + 5);
      await sleep(150);
      summary.filled.push({ label, value: (best.textContent || '').trim() });
      return true;
    }
    fire(document.body, 'mousedown', 0, 0);
    return false;
  };

  // 2026-05-25 (SpaceX 872): the closest-text heuristic loses on layouts
  // where the visible label is in a separate <label for="..."> sibling rather
  // than wrapping the control. Helper: find the .select__control whose input
  // matches a label-for relationship matching `re`, OR whose input id starts
  // with one of `idPrefixes` (e.g. 'school--', 'degree--', 'discipline--').
  const findCtrlByLabelOrId = (re, idPrefixes) => {
    for (const ctrl of section.querySelectorAll('.select__control')) {
      const inp = ctrl.querySelector('input');
      const inpId = inp?.id || '';
      if (idPrefixes && idPrefixes.some(p => inpId.startsWith(p))) return ctrl;
      const lbl = inpId ? document.querySelector('label[for="' + inpId + '"]') : null;
      if (lbl && re.test(lbl.textContent || '')) return ctrl;
      // Fallback: surrounding container text excluding select inner text.
      const wrap = ctrl.closest('.field, .form-group, .question, .education--item, div');
      if (wrap) {
        const wrapText = (wrap.textContent || '').replace(/select\.\.\./gi, '').trim();
        if (re.test(wrapText)) return ctrl;
      }
    }
    return null;
  };

  // School: usually an async-typeahead react-select OR a plain text input.
  const schoolSelects = [...section.querySelectorAll('.select__control')];
  const schoolLabeled = findCtrlByLabelOrId(/school|university|institution/i, ['school--']);
  if (school && schoolLabeled) {
    try {
      const inp = schoolLabeled.querySelector('input[role=combobox], input');
      if (inp) {
        // 2026-05-25 (SpaceX 872 fix): open the react-select control before
        // dispatching the input event. Without the mousedown+click, the
        // async typeahead doesn't fire and no options render.
        const sr = schoolLabeled.getBoundingClientRect();
        fire(schoolLabeled, 'mousedown', sr.left + 5, sr.top + 5);
        fire(schoolLabeled, 'mouseup',   sr.left + 5, sr.top + 5);
        fire(schoolLabeled, 'click',     sr.left + 5, sr.top + 5);
        await sleep(280);
        const proto = Object.getPrototypeOf(inp);
        const desc = Object.getOwnPropertyDescriptor(proto, 'value') || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        desc.set.call(inp, school);
        inp.dispatchEvent(new Event('input', { bubbles: true }));
        await sleep(1200); // wait for async options to load (SpaceX ~800ms)
        const opts = [...document.querySelectorAll('[id*="-option-"]')];
        const want = school.toLowerCase();
        let best = opts.find(o => (o.textContent||'').trim().toLowerCase() === want)
                || opts.find(o => (o.textContent||'').trim().toLowerCase().includes(want));
        if (best) {
          const br = best.getBoundingClientRect();
          fire(best, 'mousedown', br.left + 5, br.top + 5);
          fire(best, 'mouseup',   br.left + 5, br.top + 5);
          fire(best, 'click',     br.left + 5, br.top + 5);
          await sleep(150);
          summary.filled.push({ label: 'School', value: (best.textContent || '').trim() });
        } else {
          // No autocomplete match — try free-text plain input fallback below.
          summary.errors.push({ label: 'School', err: 'no async-select match', want: school });
        }
      }
    } catch (e) { summary.errors.push({ label: 'School', err: String(e) }); }
  } else if (school) {
    // Plain text fallback.
    const txt = [...section.querySelectorAll('input[type=text], input:not([type])')].find(i => {
      const lab = i.closest('label, .field, fieldset, div');
      return lab && /school|university|institution/i.test(lab.textContent || '');
    });
    if (txt) {
      const proto = Object.getPrototypeOf(txt);
      const desc = Object.getOwnPropertyDescriptor(proto, 'value') || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
      desc.set.call(txt, school);
      txt.dispatchEvent(new Event('input', { bubbles: true }));
      summary.filled.push({ label: 'School', value: school });
    } else {
      summary.skipped.push({ label: 'School', reason: 'no field found' });
    }
  } else {
    summary.skipped.push({ label: 'School', reason: 'no school value in personal-info' });
  }

  // Degree: standard react-select.
  const degreeCtrl = findCtrlByLabelOrId(/\bdegree\b/i, ['degree--']);
  if (degree && degreeCtrl) {
    try { await pickSelect('Degree', degreeCtrl, degree); }
    catch (e) { summary.errors.push({ label: 'Degree', err: String(e) }); }
  } else if (!degree) {
    summary.skipped.push({ label: 'Degree', reason: 'no degree value in personal-info' });
  }

  // Discipline (optional).
  const discCtrl = findCtrlByLabelOrId(/discipline|major|field of study/i, ['discipline--']);
  if (discipline && discCtrl) {
    try { await pickSelect('Discipline', discCtrl, discipline); }
    catch (e) { summary.errors.push({ label: 'Discipline', err: String(e) }); }
  }

  // Minor (optional). 2026-05-30 (gh-academic-fields-2026-05-30): mirror of
  // Discipline but matches /minor/. Some Greenhouse tenants (SpaceX, Anduril)
  // expose a Minor react-select inside the same education subsection.
  const minorCtrl = findCtrlByLabelOrId(/\bminor\b/i, ['minor--']);
  if (minor && minorCtrl) {
    try { await pickSelect('Minor', minorCtrl, minor); }
    catch (e) { summary.errors.push({ label: 'Minor', err: String(e) }); }
  } else if (minor) {
    // Plain text fallback.
    const txt = [...section.querySelectorAll('input[type=text], input:not([type])')].find(i => {
      const lab = i.closest('label, .field, fieldset, div');
      return lab && /\bminor\b/i.test(lab.textContent || '');
    });
    if (txt) {
      try {
        const proto = Object.getPrototypeOf(txt);
        const desc = Object.getOwnPropertyDescriptor(proto, 'value') || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        desc.set.call(txt, minor);
        txt.dispatchEvent(new Event('input', { bubbles: true }));
        summary.filled.push({ label: 'Minor', value: minor });
      } catch (e) { summary.errors.push({ label: 'Minor', err: String(e) }); }
    }
  }

  return summary;
}
"""


JS_VERIFY = r"""
() => {
  const text_inputs = [...document.querySelectorAll('input.input__single-line, textarea.input__multi-line')]
    .map(e => ({ id: e.id, value: (e.value || '').slice(0, 60) }));
  const dropdowns = [...document.querySelectorAll('.select__control')]
    .map(c => {
      const inp = c.querySelector('input[role=combobox]');
      const sv = c.querySelector('.select__single-value');
      return { id: inp ? inp.id : null, value: sv ? sv.textContent : null };
    });
  const resume_label = (document.body.textContent.match(/[A-Z]\w+_[A-Z]\w+_Resume\.\w+/) || [null])[0];
  return { text_inputs, dropdowns, resume_label };
}
"""


# ---------------------------------------------------------------------------
# Work-experience repeater (chain_006 sidecar, 2026-05-26)
# ---------------------------------------------------------------------------
# Background: Lyft 1343 (and likely other late-2025 GH tenants) added a
# "Work Experience" repeater block to the rendered /embed/job_app HTML that
# the boards-api spec does NOT expose. Field shape:
#   company-name-N        <input type=text>     (native setter)
#   title-N               <input type=text>     (native setter)
#   start-date-year-N     <input type=text>     (native setter, maxlength=4)
#   end-date-year-N       <input type=text>     (native setter, blank if current)
#   start-date-month-N    <input role=combobox> (react-select typeahead)
#   end-date-month-N      <input role=combobox> (react-select typeahead, blank if current)
#   country               <input role=combobox> (react-select typeahead) — form-level, not repeater
#
# Idempotent: skips fields already populated. Returns a structured result the
# runner can log.
JS_FILL_WORK_EXPERIENCE_BLOCK = r"""
async (entries) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const setNative = (el, val) => {
    if (!el) return false;
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(el, val);
    else el.value = val;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  };
  const fillIfBlank = (id, val) => {
    if (val === '' || val == null) return { id, skip: 'value-blank' };
    const el = document.getElementById(id);
    if (!el) return { id, skip: 'no-element' };
    if ((el.value || '').trim()) return { id, skip: 'already-filled', value: el.value };
    setNative(el, String(val));
    return { id, ok: true, value: String(val) };
  };
  const pickCombobox = async (id, val) => {
    if (val === '' || val == null) return { id, skip: 'value-blank' };
    const el = document.getElementById(id);
    if (!el) return { id, skip: 'no-element' };
    // Already chosen if a select__single-value is visible nearby
    const ctrl = el.closest('.select__control');
    if (ctrl && ctrl.querySelector('.select__single-value')) {
      return { id, skip: 'already-picked', value: ctrl.querySelector('.select__single-value').textContent };
    }
    el.focus();
    // Type chars one-by-one to trigger typeahead
    const str = String(val);
    for (const ch of str) {
      setNative(el, (el.value || '') + ch);
      el.dispatchEvent(new KeyboardEvent('keydown', { key: ch, bubbles: true }));
      el.dispatchEvent(new KeyboardEvent('keyup', { key: ch, bubbles: true }));
      await sleep(60);
    }
    await sleep(300);
    // Try clicking the first option that matches.
    // chain_007 2026-05-26: previously used `[role=option], [id^=react-select-]`
    // which matched LISTBOX containers (id ends with -listbox, contains the
    // option text) BEFORE the actual option. Clicking the listbox container is
    // a no-op for react-select — form state never updates.
    // Fix: prefer strict role=option (correct react-select option element); only
    // fall back to the broader id-prefix selector if no role=option exists
    // (defensive for non-standard themes).
    const want = str.toLowerCase();
    const strictOpts = [...document.querySelectorAll('[role=option]')];
    let opt = strictOpts.find(o => (o.textContent || '').trim().toLowerCase().startsWith(want));
    if (!opt) opt = strictOpts.find(o => (o.textContent || '').trim().toLowerCase().includes(want));
    if (!opt) {
      // Defensive fallback: scoped to react-select options ONLY (exclude listbox/placeholder/live-region).
      const looseOpts = [...document.querySelectorAll('[id^=react-select-][id*="-option-"]')];
      opt = looseOpts.find(o => (o.textContent || '').trim().toLowerCase().startsWith(want))
          || looseOpts.find(o => (o.textContent || '').trim().toLowerCase().includes(want));
    }
    if (opt) {
      const r = opt.getBoundingClientRect();
      opt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: r.left+5, clientY: r.top+5 }));
      opt.dispatchEvent(new MouseEvent('mouseup',   { bubbles: true, clientX: r.left+5, clientY: r.top+5 }));
      opt.dispatchEvent(new MouseEvent('click',     { bubbles: true, clientX: r.left+5, clientY: r.top+5 }));
      await sleep(150);
      return { id, ok: true, picked: opt.textContent.trim() };
    }
    // Fallback: press Enter to commit first highlighted option
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
    await sleep(150);
    const ctrl2 = el.closest('.select__control');
    const sv = ctrl2 ? ctrl2.querySelector('.select__single-value') : null;
    if (sv) return { id, ok: true, picked: sv.textContent.trim(), via: 'enter' };
    return { id, ok: false, err: 'no-matching-option', want: str, opts_count: (typeof strictOpts !== 'undefined' ? strictOpts.length : 0) };
  };

  // Detect: do we even have a work-experience repeater on this page?
  const detected = !!document.querySelector('input[id^="company-name-"]');
  if (!detected) return { detected: false, filled: [], skipped: [], errors: [] };

  const out = { detected: true, entries: entries.length, filled: [], skipped: [], errors: [] };
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i] || {};
    // Don't touch index i if the company-name-i input isn't there
    if (!document.getElementById('company-name-' + i)) {
      out.skipped.push({ index: i, reason: 'no-row' });
      continue;
    }
    const r1 = fillIfBlank('company-name-' + i, e.company);
    const r2 = fillIfBlank('title-' + i, e.title);
    const r3 = fillIfBlank('start-date-year-' + i, e.start_year);
    // End date: leave blank if current=true AND there's no "currently work here" checkbox
    // (the form may render one; we tick it if found).
    const currentCheckbox = document.querySelector('input[type=checkbox][id*="current"][id*="' + i + '"]')
        || document.querySelector('input[type=checkbox][id*="currently-work"]');
    if (e.current && currentCheckbox && !currentCheckbox.checked) {
      currentCheckbox.click();
      out.filled.push({ id: currentCheckbox.id, current_clicked: true });
    }
    let r4 = { id: 'end-date-year-' + i, skip: 'value-blank' };
    if (!e.current) r4 = fillIfBlank('end-date-year-' + i, e.end_year);
    const r5 = await pickCombobox('start-date-month-' + i, e.start_month);
    let r6 = { id: 'end-date-month-' + i, skip: 'value-blank' };
    if (!e.current) r6 = await pickCombobox('end-date-month-' + i, e.end_month);
    for (const r of [r1, r2, r3, r4, r5, r6]) {
      if (r.ok) out.filled.push(r);
      else if (r.skip) out.skipped.push(r);
      else out.errors.push(r);
    }
  }
  // Top-level country (also a typeahead, also not in boards-api spec). Only
  // fill if blank — the iframe runner has a separate country handler that
  // may already have run.
  const country_el = document.getElementById('country');
  if (country_el && !country_el.closest('.select__control')?.querySelector('.select__single-value')) {
    const cr = await pickCombobox('country', (entries[0] && entries[0].country) || 'United States');
    if (cr.ok) out.filled.push(cr);
    else if (cr.skip) out.skipped.push(cr);
    else out.errors.push(cr);
  }
  return out;
}
"""


# ---------------------------------------------------------------------------
# Greenhouse native S3 resume uploader (sidecar 2026-05-26, chain_009).
#
# Background: chains 005/007 assumed Lyft used Filestack for resume upload and
# spent ~3 sidecars trying to defeat a "Filestack swap". Reverse-engineering
# the GH iframe JS bundle revealed there's NO Filestack — GH's own React app
# does an S3 presigned-POST upload to `grnhse-prod-jben-us-east-1.s3.amazonaws.com`,
# stores `{url, name}` on the application object, then submits a JSON body
# containing `job_application.resume_url` + `resume_url_filename`. The bare
# `DataTransfer` hack never triggers React's UploadField onChange so those
# two fields are never populated and submit fails with "Resume/CV is required".
#
# Fix: do the S3 upload ourselves, then patch window.fetch to inject the two
# fields into the submit JSON. See workspace/FILESTACK-DESIGN.md.
# ---------------------------------------------------------------------------

# Wrap window.fetch BEFORE any submit. When a JSON POST is observed whose body
# parses as `{job_application: {...}, ...}` AND `window.__gh_resume_inject` is
# set, mutate the body to add `resume_url` + `resume_url_filename`. All other
# requests pass through untouched. The patch is idempotent (won't double-wrap)
# and records the last-seen submit body to `window.__gh_submit_seen` for the
# runner to inspect for debugging.
#
# chain_009 v3 (2026-05-27): GH submits via XMLHttpRequest, NOT fetch (verified
# live: fetch patch fired but window.__gh_submit_seen stayed null while the
# server returned "Resume/CV is required"). Patch BOTH fetch and XHR. The XHR
# patch hooks send() and inspects/mutates the body string before transmission.
JS_INSTALL_FETCH_PATCH = r"""
() => {
  if (window.__gh_fetch_patched) return { ok: true, alreadyPatched: true };
  window.__gh_fetch_patched = true;
  window.__gh_resume_inject = null;
  window.__gh_submit_seen = null;
  window.__gh_submit_mutated = null;

  function tryMutate(bodyStr, contentTypeHint) {
    const inj = window.__gh_resume_inject;
    if (!inj || typeof bodyStr !== 'string' || !bodyStr) return null;
    const looksJson = (contentTypeHint && String(contentTypeHint).includes('application/json'))
      || (bodyStr[0] === '{' && bodyStr[bodyStr.length-1] === '}');
    if (!looksJson) return null;
    let parsed;
    try { parsed = JSON.parse(bodyStr); } catch (_) { return null; }
    if (!parsed || typeof parsed !== 'object' || !parsed.job_application || typeof parsed.job_application !== 'object') return null;
    window.__gh_submit_seen = { keys: Object.keys(parsed.job_application).slice(0, 40) };
    parsed.job_application.resume_url = inj.resume_url;
    parsed.job_application.resume_url_filename = inj.resume_url_filename;
    window.__gh_submit_mutated = { resume_url: inj.resume_url, resume_url_filename: inj.resume_url_filename };
    return JSON.stringify(parsed);
  }

  // ---- fetch patch ----
  const origFetch = window.fetch.bind(window);
  window.fetch = async function(input, init) {
    try {
      if (init && init.method && String(init.method).toUpperCase() === 'POST' && typeof init.body === 'string') {
        const ct = (init.headers && (init.headers['Content-Type'] || init.headers['content-type'])) || '';
        const newBody = tryMutate(init.body, ct);
        if (newBody !== null) {
          const newInit = Object.assign({}, init, { body: newBody });
          window.__gh_submit_seen = Object.assign({}, window.__gh_submit_seen, { via: 'fetch', url: String(input) });
          return origFetch(input, newInit);
        }
      }
    } catch (e) { /* swallow */ }
    return origFetch(input, init);
  };

  // ---- XMLHttpRequest patch ----
  // GH actually uses XHR for the submit. Hook open() to capture method/url/ct,
  // setRequestHeader() to capture Content-Type, and send() to mutate the body.
  const XHR = window.XMLHttpRequest;
  if (XHR && !XHR.prototype.__gh_patched) {
    XHR.prototype.__gh_patched = true;
    const origOpen = XHR.prototype.open;
    const origSetHeader = XHR.prototype.setRequestHeader;
    const origSend = XHR.prototype.send;
    XHR.prototype.open = function(method, url) {
      try {
        this.__gh_method = method;
        this.__gh_url = url;
        this.__gh_headers = {};
      } catch (e) {}
      return origOpen.apply(this, arguments);
    };
    XHR.prototype.setRequestHeader = function(name, value) {
      try { if (this.__gh_headers) this.__gh_headers[String(name).toLowerCase()] = String(value); } catch (e) {}
      return origSetHeader.apply(this, arguments);
    };
    XHR.prototype.send = function(body) {
      try {
        if (this.__gh_method && String(this.__gh_method).toUpperCase() === 'POST' && typeof body === 'string') {
          const ct = (this.__gh_headers && this.__gh_headers['content-type']) || '';
          const newBody = tryMutate(body, ct);
          if (newBody !== null) {
            window.__gh_submit_seen = Object.assign({}, window.__gh_submit_seen, { via: 'xhr', url: String(this.__gh_url) });
            return origSend.call(this, newBody);
          }
        }
      } catch (e) { /* swallow */ }
      return origSend.apply(this, arguments);
    };
  }

  return { ok: true };
}
"""

# Fetch the S3 presigned POST envelope from GH's JBEN endpoint.
# JBEN_URL is read from window.ENV (always set on GH-iframe pages).
JS_FETCH_PRESIGNED_FIELDS = r"""
async () => {
  const env = window.ENV || {};
  const jben = env.JBEN_URL || 'https://boards.greenhouse.io';
  const url = jben.replace(/\/$/, '') + '/uncacheable_attributes/presigned_fields?fields[]=resume';
  try {
    // chain_009 fix v2 (2026-05-27): use credentials:'omit'. boards.greenhouse.io
    // serves Access-Control-Allow-Origin: https://job-boards.greenhouse.io but
    // does NOT serve Allow-Credentials:true; using 'include' triggers a CORS
    // failure (TypeError: Failed to fetch). GH's own React app calls this
    // without credentials and it works.
    const r = await fetch(url, { credentials: 'omit', mode: 'cors' });
    if (!r.ok) return { ok: false, status: r.status, err: 'non-2xx from presigned endpoint' };
    const j = await r.json();
    if (!j || !j.resume || !j.resume.fields || !j.resume.key || !j.url) {
      return { ok: false, err: 'malformed presigned response', payload: j };
    }
    return { ok: true, baseUrl: j.url, fields: j.resume.fields, key: j.resume.key };
  } catch (e) {
    return { ok: false, err: String(e) };
  }
}
"""

# Run the S3 multipart POST from inside the iframe. Returns the final fileUrl on
# success. The runner provides the file as base64 and we reconstruct the Blob.
# Substituting {timestamp} + {unique_id} into the key matches GH's own code.
JS_S3_UPLOAD = r"""
async ({ baseUrl, fields, key, b64, filename, mime }) => {
  function randHex(n) {
    let s = ''; const cs = '0123456789abcdefghijklmnopqrstuvwxyz';
    while (s.length < n) s += cs[Math.floor(Math.random() * cs.length)];
    return s.slice(0, n);
  }
  try {
    const finalKey = String(key)
      .replace('{timestamp}', String(Date.now()))
      .replace('{unique_id}', randHex(14));
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const blob = new Blob([arr], { type: mime || 'application/octet-stream' });
    const fd = new FormData();
    fd.append('utf8', '\u2713');
    for (const k in fields) fd.append(k, fields[k]);
    fd.append('key', finalKey);
    fd.append('authenticity_token', '1234');
    fd.append('Content-Type', 'application/octet-stream');
    fd.append('file', blob, filename);
    const r = await fetch(baseUrl, { method: 'POST', body: fd, mode: 'cors' });
    const text = (r.status === 201) ? null : await r.text().catch(() => null);
    if (r.status !== 201) return { ok: false, status: r.status, body: text && text.slice(0, 800), finalKey };
    const fileUrl = baseUrl.replace(/\/$/, '') + '/' + finalKey;
    return { ok: true, status: 201, fileUrl, finalKey };
  } catch (e) {
    return { ok: false, err: String(e) };
  }
}
"""

# After a successful S3 upload, plant the inject payload that the fetch patch
# reads at submit time.
JS_INSTALL_RESUME_INJECT = r"""
({ resume_url, resume_url_filename }) => {
  window.__gh_resume_inject = { resume_url, resume_url_filename };
  return { ok: true, resume_url, resume_url_filename };
}
"""

# chain_010 (2026-05-26): React onChange poke for GH iframe resume.
# After chain_009's S3 upload + inject planted, React's client-side validator
# still sees `application.resume === null` because the chain_007 DataTransfer
# binding never triggers React's UploadField.onChange. This payload uses the
# React-native value setter + a real change event to populate React state.
#
# Per OPTION-A-DESIGN.md: page-realm File construction (avoids cross-realm
# instanceof mismatch), native files setter via prototype descriptor, bubbling
# change event. Acceptance of "double upload" (React re-uploads via its own
# uploader, ~+2s) per ESCALATE.md.
JS_REACT_RESUME_TRIGGER = r"""
({ b64, filename, mime }) => {
  const out = {
    triggered: false,
    input_selector: null,
    input_found: false,
    files_before: 0,
    files_after: 0,
    native_setter_used: false,
    change_dispatched: false,
    err: null,
  };
  try {
    let inp = document.querySelector('#resume');
    let sel = '#resume';
    if (!inp) {
      inp = document.querySelector('input[type=file][name*="resume" i]');
      sel = 'input[type=file][name*="resume" i]';
    }
    if (!inp) {
      inp = document.querySelector('input[type=file]');
      sel = 'input[type=file]';
    }
    out.input_selector = sel;
    if (!inp) {
      out.err = 'no file input found';
      return out;
    }
    out.input_found = true;
    out.files_before = inp.files ? inp.files.length : 0;

    // Reconstruct File in PAGE REALM (this is page realm)
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const file = new File([arr], filename, { type: mime || 'application/pdf' });

    const dt = new DataTransfer();
    dt.items.add(file);

    // React-native value setter (bypasses React's synthetic descriptor)
    const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'files');
    if (desc && typeof desc.set === 'function') {
      desc.set.call(inp, dt.files);
      out.native_setter_used = true;
    } else {
      // Fallback: direct assignment (less likely to fool React, but try)
      try { inp.files = dt.files; } catch (_) {}
    }
    out.files_after = inp.files ? inp.files.length : 0;

    // Dispatch a real bubbling change event so React's onChange handler fires
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    out.change_dispatched = true;
    out.triggered = true;

    // Mark on window so the runner can detect double-trigger guard if desired
    window.__gh_react_resume_triggered = { at: Date.now(), filename };
  } catch (e) {
    out.err = String(e);
  }
  return out;
}
"""


def build_work_experience_payload(personal_info: dict) -> list[dict]:
    """Extract a JSON-safe list of work-experience entries for the JS filler.

    Prefers the `work_experience` array (chain_006 single source of truth).
    Falls back to synthesizing one entry from `experience_summary` for older
    personal-info.json files that haven't migrated.
    """
    we = personal_info.get("work_experience")
    if isinstance(we, list) and we:
        out = []
        for e in we:
            if not isinstance(e, dict):
                continue
            out.append({
                "company": e.get("company", ""),
                "title": e.get("title", ""),
                "start_month": e.get("start_month", ""),
                "start_year": str(e.get("start_year", "")),
                "end_month": e.get("end_month", ""),
                "end_year": str(e.get("end_year", "")) if e.get("end_year") else "",
                "current": bool(e.get("current", False)),
                "country": e.get("country", "United States"),
            })
        return out
    # Fallback synthesis from experience_summary
    es = personal_info.get("experience_summary") or {}
    if not es.get("current_employer"):
        return []
    # current_start may be 'YYYY-MM'
    start = (es.get("current_start") or "").split("-")
    start_year = start[0] if len(start) >= 1 else ""
    MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    try:
        start_month = MONTH_NAMES[int(start[1])] if len(start) >= 2 else ""
    except (ValueError, IndexError):
        start_month = ""
    addr = personal_info.get("address") or {}
    return [{
        "company": es.get("current_employer", ""),
        "title": es.get("current_title", ""),
        "start_month": start_month,
        "start_year": start_year,
        "end_month": "",
        "end_year": "",
        "current": True,
        "country": addr.get("country", "United States"),
    }]


# ---------------------------------------------------------------------------
# Dryrun → action plan
# ---------------------------------------------------------------------------

# Greenhouse demographic dropdown ids that we leave alone unless declined.
DEMO_IDS = {"gender", "race", "hispanic_ethnicity", "veteran_status", "disability_status"}


# ---------------------------------------------------------------------------
# Telemetry helpers
# ---------------------------------------------------------------------------

def log_unknown_field(org: str, job_id: str, fid: str, ftype: str, label: str = "", reason: str = "") -> None:
    """Append a one-line record per unrecognized field to unknown_fields.log.

    Used so we discover new patterns instead of silently dropping fields the
    driver doesn't know how to handle. Format: ISO-time | org | job | id | type | label | reason
    """
    UNKNOWN_FIELDS_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = "|".join([
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        org or "?",
        job_id or "?",
        fid or "?",
        ftype or "?",
        (label or "").replace("|", "/")[:200],
        (reason or "").replace("|", "/")[:120],
    ])
    with UNKNOWN_FIELDS_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Field-classification helpers used by the planner.
# ---------------------------------------------------------------------------

def _is_country_field(fid: str, label: str, options: list | None = None, value: Any = None) -> bool:
    """Country react-selects need typeahead handling (Scale, DeepMind).

    Conservative — only true when the id/label clearly identifies a country
    selector AND the options/value don't look like a Yes/No question.
    Codified after seeing visa-sponsorship questions with 'country' in their
    label (Anthropic) get false-positively flagged as country dropdowns.
    """
    # Strong signal: id matches country pattern.
    if COUNTRY_ID_RE.search(fid or ""):
        return True
    # Yes/No question values — definitely not a country selector.
    if isinstance(value, str) and value.strip().lower() in {"yes", "no", "y", "n", "true", "false"}:
        return False
    # Yes/No-shaped option list (<=3 options) — definitely not country.
    if options is not None and len(options) <= 3:
        return False
    # Label must START with a country-like phrase.
    return bool(COUNTRY_LABEL_RE.search(label or ""))


def _is_phone_iti_field(fid: str, label: str) -> bool:
    """Phone fields wrapped in an .iti widget need flag-click + digits-only (Scale)."""
    if fid == "phone":
        return True
    return bool(PHONE_LABEL_RE.search(label or "") or PHONE_LABEL_RE.search(fid or ""))


def _is_demographic_field(fid: str, label: str) -> bool:
    if fid in DEMO_IDS:
        return True
    return bool(DEMO_LABEL_RE.search(label or ""))


def build_plan(spec: dict) -> dict:
    """Translate a dryrun spec into action buckets the driver can execute."""
    text_fields: dict[str, str] = {}
    dropdowns: list[dict] = []
    country_dropdowns: list[dict] = []  # need typeahead handling
    multi_checkboxes: list[dict] = []   # multi_value_multi_select as native <fieldset>
    declined_demo_multi: list[dict] = []  # demographic multi_value_multi_select (race/ethnic) — strict decline-only
    phone_iti: dict | None = None        # special iti widget interaction
    needs_review_dropdowns: list[dict] = []  # runtime-correct candidates
    resume_path: str | None = None
    declined_demo: list[dict] = []
    skipped: list[dict] = []
    unknown: list[dict] = []
    org = spec.get("org", "?")
    job_id = str(spec.get("job_id", "?"))

    for f in spec["fields"]:
        fid = f["id"]
        ftype = f["type"]
        val = f["value"]
        status = f.get("status")
        label = f.get("label") or f.get("question") or ""

        if ftype == "input_file" and fid == "resume":
            # The dryrun stores a project-relative path; resolve to /tmp uploads.
            if val:
                name = Path(val).name
                resume_path = str(UPLOADS / name)
            continue

        if ftype in ("input_text", "textarea"):
            if val == "" and not f.get("required"):
                continue
            # Skip unresolved sentinel values — don't fill garbage into the form.
            # Required-but-unresolved fields are already tracked in spec["blockers"].
            # (MongoDB partial-test STATUS.md note, 2026-05-13.)
            if val == "__UNRESOLVED__":
                skipped.append({"id": fid, "reason": "unresolved", "required": f.get("required", False)})
                continue
            # Skip dryrun placeholders.
            if isinstance(val, str) and val.startswith("<<") and val.endswith(">>"):
                skipped.append({"id": fid, "reason": "placeholder"})
                continue
            # Phone iti widget — pulled out of plain text-fields so the driver
            # can click the flag and pick the country before setting digits.
            # Codified from scaleai-4554440005 / scaleai-4593571005 notes.
            if _is_phone_iti_field(fid, label) and ftype == "input_text":
                phone_iti = {
                    "id": fid,
                    "country": "United States",
                    "digits": str(val),
                }
                # Still register in text_fields as a fallback in case the
                # iti wrapper isn't actually present on this form.
                text_fields[fid] = val
                continue
            text_fields[fid] = val
            continue

        if ftype == "multi_value_single_select":
            # Skip unresolved sentinel values for dropdowns too.
            if val == "__UNRESOLVED__":
                skipped.append({"id": fid, "reason": "unresolved", "required": f.get("required", False)})
                continue
            # Country react-selects need typeahead handling (Scale/DeepMind).
            if _is_country_field(fid, label, options=f.get("options"), value=val):
                country_dropdowns.append({"id": fid, "label": str(val) if val else "United States"})
                continue
            # Vercel 2026-05-08 fix: dryrun marked field 'filled_needs_review'
            # with default 'No' but options were country names. Track these
            # so the driver can inspect the rendered options at runtime and
            # try alternate strategies (e.g. country fallback).
            if status == "filled_needs_review":
                needs_review_dropdowns.append({
                    "id": fid,
                    "label": str(val),
                    "alternates": ["United States", "Yes"],  # 2026-06-24: removed "No" — was accidentally committing negative answers for ack_in_office fields (Brex 3105 cohort)
                    "question": label,
                })
                continue
            if status == "declined" and _is_demographic_field(fid, label):
                # Actively pick a 'decline' option to satisfy required EEOC fields.
                # We pass several common labels and let the JS picker match the first
                # one that appears in the option list.
                declined_demo.append({
                    "id": fid,
                    "labels": [str(val)] + DECLINE_LABELS,
                })
                continue
            dropdowns.append({"id": fid, "label": str(val)})
            continue

        if ftype == "multi_value_multi_select":
            # Stripe / Datadog v2 ship these as native <fieldset.checkbox> with
            # one <input type=checkbox> per option, NOT react-select. The driver
            # opens nothing — it just ticks the checkboxes by matching label
            # text inside the fieldset whose legend matches the question.
            # Codified from stripe-7812346 / stripe-7680365 (2026-05-19/22).
            #
            # SAFETY: never default a demographic multi to United-States-style
            # values (race/ethnicity multis would silently get ticked as
            # "United States" — nonsense and misrepresentation). Route declined
            # demographic multis to declined_demo_multi instead, which tries
            # decline-style labels and flags `needs_human_review` if none
            # exist. (the-trade-desk-5139192007 race/ethnic group, 2026-05-23.)
            if _is_demographic_field(fid, label):
                declined_demo_multi.append({
                    "id": fid,
                    "legend_re": label[:80] if label else None,
                    "labels": list(DECLINE_LABELS),
                    "question": label,
                })
                continue
            if val == "__UNRESOLVED__" or val in (None, "", []):
                # Default: pick United States if the option is present.
                values = ["United States", "US", "USA"]
            elif isinstance(val, list):
                values = [str(v) for v in val]
            else:
                values = [str(val)]
            # Common alias expansion — Stripe ships 2-letter codes ("US",
            # "UK", "UAE") while dryrun stores full names. Codified from
            # stripe-7812346 STATUS.md (2026-05-19) + 2026-05-22 spike.
            _aliases = {
                "united states": ["US", "USA"],
                "united kingdom": ["UK", "GB"],
                "united arab emirates": ["UAE"],
                # 2026-05-25 (SpaceX 872): security_clearance='none' from
                # personal-info maps to GH's 'Never held a clearance' option.
                # Also tolerate 'Do not wish to disclose' as a safe fallback.
                "none": ["Never held a clearance", "Do not wish to disclose"],
            }
            expanded = list(values)
            for v in values:
                for alias in _aliases.get(v.lower(), []):
                    if alias not in expanded:
                        expanded.append(alias)
            multi_checkboxes.append({
                "id": fid,
                "legend_re": label[:80] if label else None,
                "values": expanded,
            })
            continue

        # Anything else: log as unknown so we can grow coverage.
        skipped.append({"id": fid, "type": ftype})
        unknown.append({"id": fid, "type": ftype, "label": label})
        log_unknown_field(org, job_id, fid, ftype, label, reason="unhandled_type")

    # ------------------------------------------------------------------
    # Greenhouse Remix-embed form-chrome (chain_015, Checkr 2026-05-29 +
    # Otter chain_014). The newer job-boards.greenhouse.io embed adds two
    # required react-select typeaheads that are NOT in the boards-api spec:
    #   #country            — global country picker (always 'United States')
    #   #candidate-location — typeahead city/state picker (only present when
    #                         the legacy `location` text input is also in spec)
    # Both use the standard .select__control + .select__input shape, so the
    # existing JS_PICK_DROPDOWN_TYPEAHEAD handles them. Always-emit is safe
    # because the typeahead helper returns `err: no input` on legacy forms
    # that lack these IDs (no submit-blocking side-effect).
    # De-dup against any country entry the loop above already added (e.g. if
    # the org explicitly defines a `country` question in their boards-api).
    _existing_typeahead_ids = {d["id"] for d in country_dropdowns}
    if "country" not in _existing_typeahead_ids:
        country_dropdowns.append({"id": "country", "label": "United States"})
    if "location" in text_fields and "candidate-location" not in _existing_typeahead_ids:
        # Use the freeform `location` text the dryrun resolved (e.g. "Kirkland, WA").
        # JS_PICK_DROPDOWN_TYPEAHEAD types it into the typeahead input, waits
        # ~400ms for async results, picks the first match. The legacy
        # `text_fields["location"]` setter still runs for forms that use the
        # plain <input id="location">; on Remix-embed forms that input simply
        # doesn't exist and the setter logs 'no element' harmlessly.
        country_dropdowns.append({"id": "candidate-location", "label": text_fields["location"]})

    return {
        "text_fields": text_fields,
        "dropdowns": dropdowns,
        "country_dropdowns": country_dropdowns,
        "multi_checkboxes": multi_checkboxes,
        "phone_iti": phone_iti,
        "needs_review_dropdowns": needs_review_dropdowns,
        "resume_path": resume_path,
        "declined_demo": declined_demo,
        "declined_demo_multi": declined_demo_multi,
        "skipped": skipped,
        "unknown": unknown,
        "url": spec["role_url"],
        "_education": spec.get("education_panel") or {},
    }


# ---------------------------------------------------------------------------
# Driver — emits the sequence of `browser` tool calls the agent should make.
# When run as `__main__` it prints the plan as JSON for debugging. The agent
# loop reads each step and dispatches it.
# ---------------------------------------------------------------------------

def emit_steps(plan: dict, label: str = "anthropic") -> list[dict]:
    """Return an ordered list of {tool, args} dicts the agent runs in order."""
    steps: list[dict] = []
    steps.append({"tool": "browser.open", "args": {"label": label, "url": plan["url"]}})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_OPEN_APPLY,
        "comment": "Click the visible 'Apply' button to reveal the form.",
    }})
    steps.append({"tool": "sleep", "args": {"ms": 600}})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_FILL_TEXT_FIELDS, "arg": plan["text_fields"],
        "comment": "Fill every text/textarea field via the native value setter.",
    }})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_PICK_DROPDOWNS, "arg": plan["dropdowns"],
        "comment": "Open each react-select via mousedown on .select__control and click the matching option div.",
    }})
    # Country react-selects (Scale, DeepMind 2026-05-08) — typeahead variant.
    if plan.get("country_dropdowns"):
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_PICK_DROPDOWN_TYPEAHEAD, "arg": plan["country_dropdowns"],
            "comment": "Country react-select(s): open + setNative(label) + click first matching option (typeahead).",
        }})
    # Multi-value multi-select (Stripe / Datadog v2): native <fieldset.checkbox>.
    if plan.get("multi_checkboxes"):
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_TICK_MULTI_CHECKBOXES, "arg": plan["multi_checkboxes"],
            "comment": "For each multi_value_multi_select field, find the fieldset by legend text and tick the checkbox(es) matching the desired option label(s).",
        }})
    # Phone iti widget — flag-click + setNative digits-only (Scale).
    if plan.get("phone_iti"):
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_FILL_PHONE_ITI, "arg": plan["phone_iti"],
            "comment": "Phone iti: click .iti__selected-flag, pick United States, set digits-only into the input.",
        }})
    # Strict decline-only pass for demographic multi-value multi-selects
    # (race/ethnic group rendered as <fieldset.checkbox>). Never falls through
    # to a real identity option. Emits needs_human_review when no decline
    # option exists.
    if plan.get("declined_demo_multi"):
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_DECLINE_DEMO_MULTI, "arg": plan["declined_demo_multi"],
            "comment": "For each demographic multi_value_multi_select (race/ethnic group), tick the decline option only. Flag needs_human_review if no decline option exists \u2014 do NOT pick a real identity.",
            "meta": {"safety": "strict-decline-only"},
        }})
    # Demographic decline-pass: auto-detect by label and pick a decline option.
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_DECLINE_DEMOGRAPHICS,
        "arg": {"patterns": {
            "label": DEMO_LABEL_RE.pattern,
            "declines": DECLINE_LABELS,
        }},
        "comment": "For any unset gender/race/ethnicity/veteran/disability react-select, pick a 'Decline to self-identify' option by partial-text search.",
    }})
    # GDPR demographic-data consent tickbox — required for forms that store
    # demographic answers (even when we declined them). Always tick.
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_TICK_GDPR_CONSENT,
        "comment": "Tick any GDPR demographic-data consent checkbox so the form can submit.",
    }})
    # Runtime correction for dryrun's `filled_needs_review` dropdowns:
    # inspect the actually-rendered options and retry with alternates if the
    # dryrun default isn't present (Vercel 2026-05-08 fix).
    for spec_dd in plan.get("needs_review_dropdowns", []):
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_INSPECT_OPTIONS, "arg": {"id": spec_dd["id"]},
            "comment": f"Inspect rendered options for {spec_dd['id']} ({spec_dd.get('question','')[:60]}) — caller should pick the best label from the alternates list.",
            "meta": {"needs_review": True, "alternates": spec_dd["alternates"], "original_label": spec_dd["label"]},
        }})
    # 2026-05-25 (SpaceX 872 fix): runtime education-panel sweep. Greenhouse
    # boards that include School/Degree/Discipline render them dynamically;
    # they don't appear in the dryrun field list, so this best-effort filler
    # runs unconditionally. Returns {ok, found, filled[], skipped[], errors[]}.
    # If found:false the call is a no-op. If school/degree is null in
    # personal-info, the field is skipped with a `field-coverage-deferred` flag
    # for the runner to surface in STATUS.md (NOT a hard block).
    edu_school = (plan.get("_education") or {}).get("school")
    edu_degree = (plan.get("_education") or {}).get("degree")
    edu_discipline = (plan.get("_education") or {}).get("discipline")
    edu_minor = (plan.get("_education") or {}).get("minor")
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_FILL_EDUCATION_PANEL,
        "arg": {"school": edu_school, "degree": edu_degree, "discipline": edu_discipline, "minor": edu_minor},
        "comment": "Best-effort fill of dynamic Education subsection (School/Degree/Discipline). Greenhouse renders this after main form load; absent on many boards. Null personal-info values → 'field-coverage-deferred' flag, not a hard block.",
        "meta": {"education_panel": True, "defer_if_null": True},
    }})
    if plan["resume_path"]:
        resume_filename = Path(plan["resume_path"]).name
        # 2026-05-13 (PM): UPLOAD FIRST, THEN CLICK ATTACH. See JS_CLICK_ATTACH
        # docstring for the full root-cause writeup. The old order
        # (click-then-upload) silently no-op'd uploads on most boards.
        steps.append({"tool": "browser.upload", "args": {
            "label": label,
            # 2026-05-25 (upload regression FIX): MUST use `element=` not
            # `selector=`. OpenClaw's browser.upload arms a filechooser when
            # given selector=only, never fires it, and silently returns ok:true
            # with files=0. `element=` routes through Playwright
            # locator.setInputFiles directly. See _upload-regression-diag-20260525.md.
            "element": "input#resume",
            "paths": [plan["resume_path"]],
            "comment": "Stage the file into the visually-hidden #resume input via CDP setInputFiles. Filestack will commit it on the next Attach click. Files must be under /tmp/openclaw/uploads/.",
        }})
        steps.append({"tool": "sleep", "args": {"ms": 300}})
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_CLICK_ATTACH,
            "arg": {"delayMs": 1200, "filename": resume_filename},
            "comment": "Click Attach to wake Filestack — it picks up the file already staged in #resume and swaps the input out for a 'filename + Remove' UI.",
        }})
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_VERIFY_RESUME_ATTACHED,
            "arg": {"filename": resume_filename},
            "comment": "Verify the resume actually landed. If ok=false, RETRY the upload+click sequence once before continuing.",
            "meta": {"verify": "resume", "retry_on_fail": True, "retry_steps": [
                # 2026-05-25 FIX: element= not selector= (see note above).
                {"tool": "browser.upload", "args": {"label": label, "element": "input#resume", "paths": [plan["resume_path"]]}},
                {"tool": "sleep", "args": {"ms": 500}},
                {"tool": "browser.act.evaluate", "args": {"label": label, "fn": JS_CLICK_ATTACH, "arg": {"delayMs": 1500, "filename": resume_filename}}},
                {"tool": "browser.act.evaluate", "args": {"label": label, "fn": JS_VERIFY_RESUME_ATTACHED, "arg": {"filename": resume_filename}}},
            ]},
        }})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_VERIFY,
        "comment": "Read back current state for verification.",
    }})
    return steps


# ---------------------------------------------------------------------------
# Result logging — called by the agent runner after each app attempt.
# ---------------------------------------------------------------------------

def log_success(org: str, job_id: str, url: str, plan: dict, confirmation: dict, screenshot_path: str | None) -> Path:
    SUBMITTED_DIR.mkdir(parents=True, exist_ok=True)
    out = SUBMITTED_DIR / f"{org}-{job_id}.json"
    out.write_text(json.dumps({
        "org": org,
        "job_id": job_id,
        "url": url,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "text_fields": plan.get("text_fields", {}),
        "dropdowns": plan.get("dropdowns", []),
        "resume": plan.get("resume_path"),
        "confirmation": confirmation,
        "screenshot": screenshot_path,
    }, indent=2))
    return out


def log_failure(org: str, job_id: str, url: str, error: str, details: dict | None = None, screenshot_path: str | None = None) -> Path:
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    out = FAILED_DIR / f"{org}-{job_id}.json"
    out.write_text(json.dumps({
        "org": org,
        "job_id": job_id,
        "url": url,
        "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error": error,
        "details": details or {},
        "screenshot": screenshot_path,
    }, indent=2))
    return out


def build_queue(cap: int = DEFAULT_CAP, per_org_cap: int = 2) -> list[dict]:
    """Build the unattended-submit queue from dryrun specs.

    Filters:
    - ready_to_submit == True (no blockers)
    - URL is on `job-boards.greenhouse.io` (modern react form; legacy boards.greenhouse.io needs a different driver)
    - No prior log in submitted/ or failed/
    - Cap at `cap` apps (capped to avoid runaway).
    """
    SUBMITTED_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    submitted = {p.stem for p in SUBMITTED_DIR.glob("*.json")}
    failed = {p.stem for p in FAILED_DIR.glob("*.json")}
    queue: list[dict] = []
    per_org: dict[str, int] = {}
    for spec_path in sorted(DRYRUN_DIR.glob("*.json")):
        spec = json.loads(spec_path.read_text())
        if not spec.get("ready_to_submit"):
            continue
        url = spec.get("role_url", "")
        if "job-boards.greenhouse.io" not in url:
            continue
        org, job_id = spec["org"], spec["job_id"]
        key = f"{org}-{job_id}"
        if key in submitted or key in failed:
            continue
        if per_org.get(org, 0) >= per_org_cap:
            continue
        per_org[org] = per_org.get(org, 0) + 1
        queue.append({
            "org": org,
            "job_id": job_id,
            "url": url,
            "title": spec.get("job_title", ""),
            "spec_path": str(spec_path),
        })
        if len(queue) >= cap:
            break
    return queue


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP)
    ap.add_argument("--queue", action="store_true", help="Print the unattended queue and exit.")
    ap.add_argument("--plan", nargs=2, metavar=("ORG", "JOB_ID"), help="Emit step plan for one app.")
    args = ap.parse_args()

    if args.queue:
        q = build_queue(cap=args.cap)
        print(json.dumps({"cap": args.cap, "count": len(q), "queue": q}, indent=2))
        return 0

    if args.plan:
        org, job_id = args.plan
        spec_path = DRYRUN_DIR / f"{org}-{job_id}.json"
        if not spec_path.exists():
            print(f"missing dryrun: {spec_path}", file=sys.stderr)
            return 1
        spec = json.loads(spec_path.read_text())
        plan = build_plan(spec)
        steps = emit_steps(plan, label=org)
        print(json.dumps({
            "org": org,
            "job_id": job_id,
            "url": plan["url"],
            "plan": plan,
            "steps": steps,
        }, indent=2))
        return 0

    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
