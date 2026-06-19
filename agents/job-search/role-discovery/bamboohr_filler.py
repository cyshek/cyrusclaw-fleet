"""bamboohr_filler.py — Submit applications to BambooHR-hosted job boards
(<tenant>.bamboohr.com/careers/<id>, <tenant>.bamboohr.com/jobs/view.php?id=<n>,
<tenant>.bamboohr.com/jobs/embed2.php?id=<n>).

Architecture (chain_034a 2026-05-30):
    BambooHR's hosted careers form is a React SPA built on the "Fabric" UI
    framework (BambooHR's design system). All field interaction goes through
    DOM-level steps (no public submit API).

Form anatomy:
    - Text fields: native <input type=text|email|tel|url> / <textarea> with
      stable React-controlled state. We use the React native value setter
      trick (`HTMLInputElement.prototype.value` setter) + input event to
      propagate.

    - State / Country dropdown: Fabric MenuVessel pattern.
        <button aria-label="State, ...">Select...</button>
      Clicking opens a portal-mounted `<div class="fab-MenuVessel__list">`
      somewhere on the page (NOT a child of the button). The options live
      inside as `<div role="menuitem">` / `<button>` elements. We MUST
      scope the option lookup to the open MenuVessel container — page-
      scoped queries collide with hidden overlays (chain_033 lost Uphold
      1023 to a Washington div elsewhere on the page).

    - Yes/No (customQuestionAnswers): rendered as visible <button> pairs
      backed by hidden inputs. Click the button by text.

    - Resume + Cover Letter: `<input type=file required>`. There are two;
      the FIRST (DOM order) is coverLetterFileId, the SECOND is
      resumeFileId. Direct `set_input_files` works; no need to click the
      upload button.

    - reCAPTCHA v2 visible checkbox: `<div class="g-recaptcha"
      data-sitekey="...">`. Solve via CapSolver `ReCaptchaV2TaskProxyless`
      and inject token into `#g-recaptcha-response` textarea (+ dispatch
      change event).

    - Submit: visible button (text "Submit Application").

This module emits a STEP PLAN (same convention as ashby_filler / 
greenhouse_filler) which the browser-driver subagent consumes. There's no
direct-API HTTP submit pipeline like rippling_filler — BambooHR doesn't
expose one publicly.

Usage:
    from bamboohr_filler import build_plan, emit_steps
    plan = build_plan(spec)
    steps = emit_steps(plan, label="uphold-839")

CLI:
    python3 bamboohr_filler.py --plan <tenant> <job_id>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
DRYRUN_DIR = HERE.parent / "applications" / "dryrun"

# ---- Personal info loader --------------------------------------------------
_INFO_PATH = HERE.parent / "personal-info.json"
def _info():
    try:
        return json.loads(_INFO_PATH.read_text())
    except Exception:
        return {"identity": {}, "address": {}}

# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

_BAMBOO_HOST_RX = re.compile(r"^([a-z0-9-]+)\.bamboohr\.com$", re.I)
_BAMBOO_CAREERS_PATH_RX = re.compile(r"/careers/(\d+)(?:/|$|\?)")
_BAMBOO_VIEWPHP_RX = re.compile(r"/jobs/(?:view|embed2)\.php")


def parse_bamboohr_url(url: str) -> Optional[tuple[str, str]]:
    """Return (tenant, job_id) or None.

    Accepts:
      https://<tenant>.bamboohr.com/careers/<id>
      https://<tenant>.bamboohr.com/jobs/view.php?id=<n>
      https://<tenant>.bamboohr.com/jobs/embed2.php?id=<n>
    """
    if not url:
        return None
    try:
        p = urlparse(url)
    except Exception:
        return None
    host = (p.hostname or "").lower()
    m = _BAMBOO_HOST_RX.match(host)
    if not m:
        return None
    tenant = m.group(1)
    # /careers/<id>
    m2 = _BAMBOO_CAREERS_PATH_RX.search(p.path or "")
    if m2:
        return tenant, m2.group(1)
    # /jobs/view.php?id=<n> or /jobs/embed2.php?id=<n>
    if _BAMBOO_VIEWPHP_RX.search(p.path or ""):
        q = parse_qs(p.query or "")
        ids = q.get("id") or []
        if ids and ids[0].isdigit():
            return tenant, ids[0]
    return None


def canonical_apply_url(tenant: str, job_id: str) -> str:
    return f"https://{tenant}.bamboohr.com/careers/{job_id}"


# ---------------------------------------------------------------------------
# JS snippets (shipped to browser.act.evaluate)
# ---------------------------------------------------------------------------

# Native value setter for React-controlled inputs/textareas.
# Returns {filled: [{id, dom_id, len}], missing: [...], errors: [...]}.
JS_FILL_TEXT_FIELDS = r"""
(textFields) => {
  const out = {filled: [], missing: [], errors: []};
  const setNativeValue = (el, value) => {
    const proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    el.dispatchEvent(new Event('blur', {bubbles: true}));
  };
  // Resolve a field id to a DOM element. BambooHR uses simple id= names
  // (firstName, lastName, email, phone, addressStreet1, addressCity,
  // addressZip, desiredPay, linkedinUrl), but also sometimes name= with
  // a prefix. Try id first, then name, then [data-field=].
  const resolve = (fid) => {
    let el = document.getElementById(fid);
    if (el) return el;
    el = document.querySelector(`[name="${fid}"]`);
    if (el) return el;
    el = document.querySelector(`[data-field="${fid}"] input, [data-field="${fid}"] textarea`);
    return el;
  };
  for (const [fid, value] of Object.entries(textFields || {})) {
    try {
      const el = resolve(fid);
      if (!el) { out.missing.push(fid); continue; }
      if (el.tagName === 'INPUT' && ['radio','checkbox','file','submit','button'].includes(el.type)) {
        out.missing.push({id: fid, reason: 'wrong-type:'+el.type});
        continue;
      }
      setNativeValue(el, value ?? '');
      out.filled.push({id: fid, dom_id: el.id || el.name || '', len: String(value || '').length});
    } catch (e) {
      out.errors.push({id: fid, error: String(e)});
    }
  }
  return out;
}
"""

# Fabric MenuVessel dropdown opener + option clicker. Async (returns a Promise).
# Input: list of {label_prefix, option_text} entries
#   label_prefix matches button[aria-label^=...] (e.g. "State")
#   option_text matches the visible text of an option within the open
#                MenuVessel list container (e.g. "Washington")
#
# Returns {picked: [{label_prefix, picked_text}], missing: [...], errors: [...]}.
#
# CRITICAL: option click is scoped to .fab-MenuVessel__list — chain_033 lost
# Uphold 1023 because a page-scoped `>> text=Washington` click hit a hidden
# overlay div that collapsed the page.
JS_PICK_MENUVESSEL_OPTIONS = r"""
(picks) => {
  const out = {picked: [], missing: [], errors: []};
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, maxMs=3000, stepMs=50) => {
    const t0 = Date.now();
    while (Date.now() - t0 < maxMs) {
      const v = fn();
      if (v) return v;
      await sleep(stepMs);
    }
    return null;
  };
  const findOpenList = () => {
    // The MenuVessel list is appended to a portal; query the WHOLE page.
    // Prefer the one that is actually visible (offsetParent != null).
    const candidates = Array.from(document.querySelectorAll('.fab-MenuVessel__list, [class*="fab-MenuVessel__list"]'));
    for (const el of candidates) {
      if (el.offsetParent !== null) return el;
    }
    return candidates[0] || null;
  };
  const findButton = (prefix) => {
    // Try aria-label^= first, then look for trigger buttons inside
    // a [data-field=...] container labeled with the prefix.
    const escPrefix = prefix.replace(/"/g, '\\"');
    let b = document.querySelector(`button[aria-label^="${escPrefix}"]`);
    if (b) return b;
    b = document.querySelector(`button[aria-label*="${escPrefix}"]`);
    return b;
  };
  return (async () => {
    for (const pick of (picks || [])) {
      try {
        const btn = findButton(pick.label_prefix);
        if (!btn) {
          out.missing.push({label_prefix: pick.label_prefix, reason: 'no-trigger'});
          continue;
        }
        btn.scrollIntoView({block: 'center', behavior: 'instant'});
        btn.click();
        const list = await waitFor(findOpenList, 2000);
        if (!list) {
          out.missing.push({label_prefix: pick.label_prefix, reason: 'list-did-not-open'});
          continue;
        }
        // Find option whose visible text matches option_text (case-insensitive
        // exact match preferred; substring fallback).
        const want = String(pick.option_text || '').trim().toLowerCase();
        const items = Array.from(list.querySelectorAll(
          '[role="menuitem"], [role="option"], button, li, div'
        )).filter(e => (e.textContent || '').trim().length > 0);
        let chosen = null;
        for (const it of items) {
          const t = (it.textContent || '').trim().toLowerCase();
          if (t === want) { chosen = it; break; }
        }
        if (!chosen) {
          for (const it of items) {
            const t = (it.textContent || '').trim().toLowerCase();
            if (t.includes(want) && want.length >= 2) { chosen = it; break; }
          }
        }
        if (!chosen) {
          out.missing.push({label_prefix: pick.label_prefix, reason: 'option-not-found',
                            sample: items.slice(0, 10).map(e => (e.textContent || '').trim())});
          // Close the menu by clicking the trigger again so subsequent picks work.
          try { btn.click(); } catch(e) {}
          continue;
        }
        chosen.scrollIntoView({block: 'center', behavior: 'instant'});
        chosen.click();
        out.picked.push({label_prefix: pick.label_prefix,
                         picked_text: (chosen.textContent || '').trim()});
        // Give the menu a moment to close before the next pick.
        await sleep(120);
      } catch (e) {
        out.errors.push({label_prefix: pick.label_prefix, error: String(e)});
      }
    }
    return out;
  })();
}
"""

# Yes/No (customQuestionAnswers) button clicker.
# Input: list of {question_text, answer} where answer in {"Yes","No"} (or
#   any visible button text). Strategy: find a container whose text contains
#   `question_text`, then click the button matching `answer` within it.
# Returns {picked: [...], missing: [...]}.
JS_CLICK_YESNO_QUESTIONS = r"""
(questions) => {
  const out = {picked: [], missing: [], errors: []};
  const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  for (const q of (questions || [])) {
    try {
      const wantQ = norm(q.question_text);
      const wantA = norm(q.answer);
      if (!wantQ || !wantA) {
        out.missing.push({question_text: q.question_text, reason: 'bad-input'});
        continue;
      }
      // Find candidate containers: walk all elements whose direct text
      // includes the question, then ascend to the nearest container that
      // also has buttons inside.
      let container = null;
      const all = Array.from(document.querySelectorAll('label, legend, fieldset, div, p, span'));
      for (const el of all) {
        const t = norm(el.textContent);
        if (!t.includes(wantQ)) continue;
        // Walk up to find a node holding buttons.
        let node = el;
        for (let i = 0; i < 6 && node; i++) {
          if (node.querySelectorAll('button').length >= 2) {
            container = node; break;
          }
          node = node.parentElement;
        }
        if (container) break;
      }
      if (!container) {
        out.missing.push({question_text: q.question_text, reason: 'no-container'});
        continue;
      }
      const buttons = Array.from(container.querySelectorAll('button'));
      let chosen = null;
      for (const b of buttons) {
        if (norm(b.textContent) === wantA) { chosen = b; break; }
      }
      if (!chosen) {
        for (const b of buttons) {
          if (norm(b.textContent).includes(wantA)) { chosen = b; break; }
        }
      }
      if (!chosen) {
        out.missing.push({question_text: q.question_text, reason: 'no-button',
                          buttons: buttons.map(b => (b.textContent || '').trim())});
        continue;
      }
      chosen.scrollIntoView({block: 'center', behavior: 'instant'});
      chosen.click();
      out.picked.push({question_text: q.question_text,
                       picked_text: (chosen.textContent || '').trim()});
    } catch (e) {
      out.errors.push({question_text: q.question_text, error: String(e)});
    }
  }
  return out;
}
"""

# Detect captcha sitekey on the page (v2 visible checkbox).
# Returns {sitekey, has_v2, has_v3, scripts: [...]}.
JS_DETECT_CAPTCHA = r"""
() => {
  const out = {sitekey: null, has_v2: false, has_v3: false, scripts: []};
  out.scripts = Array.from(document.scripts).map(s => s.src).filter(s =>
    /recaptcha|hcaptcha|turnstile/i.test(s));
  out.has_v3 = out.scripts.some(s => /\?render=/.test(s));
  const el = document.querySelector('.g-recaptcha[data-sitekey], [data-sitekey]');
  if (el) {
    out.sitekey = el.getAttribute('data-sitekey');
    out.has_v2 = el.classList.contains('g-recaptcha') ||
                 !!document.querySelector('iframe[src*="recaptcha/api2"]');
  }
  return out;
}
"""

# Inject v2 token into the response textarea.
# Input: {token: "..."}
# Returns {injected: bool, ids: [...]}.
JS_INJECT_V2_TOKEN = r"""
(arg) => {
  const out = {injected: false, ids: []};
  const token = (arg && arg.token) || '';
  if (!token) return out;
  // The standard slot id is `g-recaptcha-response`. BambooHR pages have
  // exactly one v2 widget so the unsuffixed id is the right one. Inject
  // into all matching textareas to be safe.
  const eles = Array.from(document.querySelectorAll(
    'textarea[id^="g-recaptcha-response"], textarea[name^="g-recaptcha-response"]'
  ));
  if (eles.length === 0) {
    // No existing slot — create one (some pages defer the textarea until
    // after the user clicks the checkbox).
    const ta = document.createElement('textarea');
    ta.id = 'g-recaptcha-response';
    ta.name = 'g-recaptcha-response';
    ta.style.display = 'none';
    document.body.appendChild(ta);
    eles.push(ta);
  }
  for (const ta of eles) {
    ta.value = token;
    ta.dispatchEvent(new Event('change', {bubbles: true}));
    out.ids.push(ta.id || ta.name);
  }
  out.injected = true;
  return out;
}
"""

# Verify form state pre-submit.
# Returns {filled_text_inputs, picked_buttons, attached_files, has_submit,
#          recaptcha_token_len, missing_required}.
JS_VERIFY = r"""
() => {
  const out = {};
  out.filled_text_inputs = Array.from(document.querySelectorAll(
    'input[type=text], input[type=email], input[type=tel], input[type=url], input[type=number], textarea'
  )).filter(e => (e.value || '').length > 0).length;
  out.attached_files = Array.from(document.querySelectorAll(
    'input[type=file]'
  )).filter(e => (e.files || []).length > 0).length;
  out.required_files = Array.from(document.querySelectorAll(
    'input[type=file][required]'
  )).length;
  const submitBtn = Array.from(document.querySelectorAll('button')).find(b =>
    /submit application|submit/i.test((b.textContent || '').trim()));
  out.has_submit = !!submitBtn;
  const v2 = document.querySelector('#g-recaptcha-response');
  out.recaptcha_token_len = (v2 && v2.value || '').length;
  // Try to identify obvious missing-required markers in the React form.
  out.missing_required = Array.from(document.querySelectorAll(
    '[aria-invalid="true"], .fab-FormError, .fab-FormField--error'
  )).length;
  return out;
}
"""

# Click submit. Returns {clicked: bool, button_text: str}.
JS_CLICK_SUBMIT = r"""
() => {
  const buttons = Array.from(document.querySelectorAll('button'));
  let btn = buttons.find(b => /submit application/i.test((b.textContent || '').trim()));
  if (!btn) btn = buttons.find(b => /^submit$/i.test((b.textContent || '').trim()));
  if (!btn) return {clicked: false, button_text: ''};
  btn.scrollIntoView({block: 'center', behavior: 'instant'});
  btn.click();
  return {clicked: true, button_text: (btn.textContent || '').trim()};
}
"""


# ---------------------------------------------------------------------------
# Field-name conventions
# ---------------------------------------------------------------------------

# Default BambooHR text-field IDs. Spec authors can override by passing a
# `text_fields` dict directly mapping our canonical answer keys (first_name,
# last_name, email, phone, street, city, zip, desired_pay, linkedin) to the
# raw BambooHR DOM ids the page actually uses.
_DEFAULT_BAMBOO_FIELD_IDS = {
    "first_name": "firstName",
    "last_name": "lastName",
    "email": "email",
    "phone": "phone",
    "street": "addressStreet1",
    "city": "addressCity",
    "zip": "addressZip",
    "desired_pay": "desiredPay",
    "linkedin": "linkedinUrl",
}

# Canonical answers shape:
#   {
#     "first_name": "Cyrus",
#     "last_name": "Yari",
#     "email": "...",
#     "phone": "+1 415 555 1234",
#     "street": "...",
#     "city": "Kirkland",
#     "state": "Washington",   # MenuVessel option text
#     "country": "United States",  # optional MenuVessel
#     "zip": "98033",
#     "desired_pay": "150000",
#     "linkedin": "https://linkedin.com/in/cyrusyari",
#     "resume_path": "/abs/path/resume.pdf",
#     "cover_letter_path": null,   # optional
#     "yesno_questions": [
#       {"question_text": "Are you authorized to work in the US?", "answer": "Yes"},
#       ...
#     ],
#     "extra_text_fields": {"<raw_id>": "<value>"},   # for tenant-specific fields
#     "dropdowns": [
#       {"label_prefix": "State", "option_text": "Washington"},
#       ...
#     ],
#   }


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------

def build_plan(spec: dict) -> dict:
    """Build a structured plan dict from an answers spec.

    Required spec keys:
        role_url: str — BambooHR apply URL (any of the 3 supported shapes)
        answers: dict — canonical answers (see shape above)

    Optional:
        field_ids: dict — override _DEFAULT_BAMBOO_FIELD_IDS for tenants
                          that use non-standard ids
    """
    role_url = spec["role_url"]
    parsed = parse_bamboohr_url(role_url)
    if not parsed:
        raise ValueError(f"not a recognized BambooHR URL: {role_url}")
    tenant, job_id = parsed
    canonical_url = canonical_apply_url(tenant, job_id)

    answers = dict(spec.get("answers") or {})
    field_ids = dict(_DEFAULT_BAMBOO_FIELD_IDS)
    field_ids.update(spec.get("field_ids") or {})

    text_fields: dict[str, str] = {}
    for k, dom_id in field_ids.items():
        v = answers.get(k)
        if v is None or v == "":
            continue
        text_fields[dom_id] = str(v)
    # Pass-through extra fields.
    for raw_id, v in (answers.get("extra_text_fields") or {}).items():
        if v is None or v == "":
            continue
        text_fields[raw_id] = str(v)

    # Dropdowns — explicit list first, then auto-add state/country from
    # top-level answers.
    dropdowns: list[dict] = []
    for d in (answers.get("dropdowns") or []):
        if d.get("label_prefix") and d.get("option_text"):
            dropdowns.append({
                "label_prefix": d["label_prefix"],
                "option_text": d["option_text"],
            })
    seen_prefixes = {d["label_prefix"].lower() for d in dropdowns}
    if answers.get("state") and "state" not in seen_prefixes:
        dropdowns.append({"label_prefix": "State", "option_text": str(answers["state"])})
    if answers.get("country") and "country" not in seen_prefixes:
        dropdowns.append({"label_prefix": "Country", "option_text": str(answers["country"])})

    # Yes/No questions
    yesno: list[dict] = []
    for q in (answers.get("yesno_questions") or []):
        if not q.get("question_text") or not q.get("answer"):
            continue
        yesno.append({"question_text": q["question_text"], "answer": q["answer"]})

    return {
        "url": canonical_url,
        "tenant": tenant,
        "job_id": job_id,
        "text_fields": text_fields,
        "dropdowns": dropdowns,
        "yesno_questions": yesno,
        "resume_path": answers.get("resume_path"),
        "cover_letter_path": answers.get("cover_letter_path"),
    }


# ---------------------------------------------------------------------------
# emit_steps
# ---------------------------------------------------------------------------

def _wrap(js_fn: str, payload: Any) -> str:
    """Wrap a JS arrow fn into a zero-arg closure with payload baked in."""
    return ("() => { const __payload = " + json.dumps(payload) +
            "; return (" + js_fn.strip() + ")(__payload); }")


def emit_steps(plan: dict, label: str = "bamboohr") -> list[dict]:
    """Emit an ordered list of {tool, args} steps for the browser driver."""
    steps: list[dict] = []
    steps.append({"tool": "browser.open", "args": {
        "label": label,
        "url": plan["url"],
    }})
    # Generous initial wait — BambooHR SPA hydration is slow.
    steps.append({"tool": "sleep", "args": {"ms": 2000}})

    # 1. Text fields (React native-value-setter fast path).
    if plan["text_fields"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label,
            "fn": _wrap(JS_FILL_TEXT_FIELDS, plan["text_fields"]),
            "comment": (
                "Fill all native text/email/tel/url/textarea inputs by id|name|\n"
                "[data-field=...]. Uses React native-value-setter + input/change/blur\n"
                "events. Verify post-condition by reading back input.value; any\n"
                "field where post_value != requested should fall back to per-key\n"
                "CDP keystrokes (driver responsibility — same pattern as Ashby chain_005)."
            ),
            "meta": {"verify_required": True},
        }})

    # 2. Resume / cover letter upload.
    #    BambooHR renders two `<input type=file required>` inputs in DOM
    #    order; the first is COVER LETTER, the second is RESUME. To avoid
    #    coupling to selector position, we drive both via a single
    #    `bamboohr.upload_files` step with explicit roles.
    if plan["resume_path"] or plan["cover_letter_path"]:
        steps.append({"tool": "bamboohr.upload_files", "args": {
            "label": label,
            "resume_path": plan["resume_path"],
            "cover_letter_path": plan["cover_letter_path"],
            "comment": (
                "Drive both <input type=file required> inputs in DOM order.\n"
                "Position 1 = cover_letter (coverLetterFileId backing), position 2 = resume\n"
                "(resumeFileId backing). Driver MUST use set_input_files on the input\n"
                "elements directly — do NOT click the visible Upload button. Verify:\n"
                "evaluate () => Array.from(document.querySelectorAll('input[type=file]'))\n"
                "                    .map(e => (e.files || []).length)\n"
                "Both positions should report >=1 file. If a slot is unused, pass null."
            ),
            "meta": {"file_count_expected_min": int(bool(plan["resume_path"])) +
                                                  int(bool(plan["cover_letter_path"]))},
        }})
        steps.append({"tool": "sleep", "args": {"ms": 600}})

    # 3. Fabric MenuVessel dropdowns (State, Country, etc).
    if plan["dropdowns"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label,
            "fn": _wrap(JS_PICK_MENUVESSEL_OPTIONS, plan["dropdowns"]),
            "comment": (
                "Open each Fabric MenuVessel dropdown (button[aria-label^=<prefix>])\n"
                "and click the option matching option_text WITHIN the open\n"
                ".fab-MenuVessel__list container. SCOPED match — chain_033 lost\n"
                "Uphold 1023 because a page-scoped >> text=Washington click hit a\n"
                "hidden overlay div elsewhere. Returns {picked, missing, errors}.\n"
                "Driver: any required dropdown in `missing` -> BLOCKED."
            ),
            "meta": {"async": True},
        }})

    # 4. Yes/No questions (customQuestionAnswers).
    if plan["yesno_questions"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label,
            "fn": _wrap(JS_CLICK_YESNO_QUESTIONS, plan["yesno_questions"]),
            "comment": (
                "For each {question_text, answer}: find the nearest container\n"
                "whose text includes question_text AND which holds >=2 buttons,\n"
                "then click the button whose text == answer. BambooHR Yes/No\n"
                "groups are <button> pairs backed by hidden inputs (chain_033)."
            ),
        }})

    # 5. Detect + solve reCAPTCHA v2 (visible checkbox).
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label,
        "fn": JS_DETECT_CAPTCHA,
        "comment": (
            "Detect captcha presence + sitekey. BambooHR uses reCAPTCHA v2\n"
            "(visible checkbox). Driver: if has_v2 and sitekey, call\n"
            "  capsolver_client.CapSolverClient().recaptcha_v2(sitekey, page_url)\n"
            "  then run bamboohr.inject_v2_token with the returned token.\n"
            "If has_v3 instead (some legacy tenants), use recaptcha_v3 path\n"
            "(injection slot is still #g-recaptcha-response)."
        ),
        "meta": {"resolve_only": True, "captcha_kind": "recaptcha_v2"},
    }})
    steps.append({"tool": "bamboohr.solve_recaptcha_v2", "args": {
        "label": label,
        "page_url": plan["url"],
        "comment": (
            "Driver-resolved step: read sitekey from the previous detect step,\n"
            "solve via CapSolver v2 (~$0.002/solve), then inject token via\n"
            "JS_INJECT_V2_TOKEN. Skip cleanly if has_v2 is false."
        ),
        "driver_exec": {
            "module": "capsolver_client",
            "function": "recaptcha_v2",
            "kwargs": {"page_url": plan["url"]},
            "gate_env": "ENABLE_CAPSOLVER",
            "gate_value": "1",
        },
        "inject_fn": JS_INJECT_V2_TOKEN.strip(),
    }})

    # 6. Verify pre-submit.
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label,
        "fn": JS_VERIFY,
        "comment": (
            "Pre-submit verify: counts of filled text inputs, attached files,\n"
            "has_submit button, recaptcha_token_len, missing_required\n"
            "([aria-invalid] / .fab-FormField--error). Driver: if\n"
            "missing_required > 0, log + BLOCKED."
        ),
    }})

    # 7. Click submit.
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label,
        "fn": JS_CLICK_SUBMIT,
        "comment": "FINAL: click 'Submit Application'. Run only after VERIFY passes.",
        "meta": {"final_submit": True},
    }})
    return steps


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _smoke_spec_for(tenant: str, job_id: str) -> dict:
    """Build a minimal placeholder spec for smoke-testing build_plan + emit_steps
    without a real dryrun resolver. Uses dummy answers; only field shape matters.
    """
        _pi = _info()
    _id = _pi.get("identity", {}); _ad = _pi.get("address", {})
    import re as _re
    def _digs(p): return _re.sub(r'[^0-9]','',p or '')
    return {
        "role_url": canonical_apply_url(tenant, job_id),
        "answers": {
            "first_name": _id.get("first_name", ""),
            "last_name": _id.get("last_name", ""),
            "email": _id.get("email", ""),
            "phone": _digs(_id.get("phone", "")),
            "street": _ad.get("street", ""),
            "city": _ad.get("city", ""),
            "state": _ad.get("state_label", _ad.get("state", "")),
            "zip": _ad.get("zip", ""),
            "desired_pay": "150000",
            "linkedin": _id.get("linkedin_url", ""),
            "resume_path": "/tmp/resume.pdf",
            "cover_letter_path": None,
            "yesno_questions": [
                {"question_text": "Are you authorized to work in the United States?",
                 "answer": "Yes"},
                {"question_text": "Will you now or in the future require sponsorship?",
                 "answer": "No"},
                {"question_text": "Are you able to commute to a hybrid location?",
                 "answer": "Yes"},
            ],
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Emit BambooHR fill-step plan.")
    ap.add_argument("--plan", nargs=2, metavar=("TENANT", "JOB_ID"),
                    help="Emit step plan for one BambooHR app.")
    ap.add_argument("--smoke", action="store_true",
                    help="Use the built-in placeholder answers spec (no dryrun needed).")
    args = ap.parse_args(argv)
    if not args.plan:
        print(__doc__, file=sys.stderr)
        return 2
    tenant, job_id = args.plan
    if args.smoke:
        spec = _smoke_spec_for(tenant, job_id)
    else:
        spec_path = DRYRUN_DIR / f"bamboohr-{tenant}-{job_id}.json"
        if not spec_path.exists():
            print(f"missing spec: {spec_path} (use --smoke for placeholder)", file=sys.stderr)
            return 1
        spec = json.loads(spec_path.read_text())
    plan = build_plan(spec)
    steps = emit_steps(plan, label=f"{tenant}-{job_id}")
    print(json.dumps({"plan": plan, "steps": steps}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
