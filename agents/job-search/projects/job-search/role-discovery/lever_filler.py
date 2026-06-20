#!/usr/bin/env python3
"""
lever_filler.py — Build the ordered browser action plan that will fill (NOT
submit) a Lever application form.

Inputs:  a dryrun spec from lever_dryrun.py (../applications/dryrun/lever-*.json)
Outputs: a dict with text_fields, dropdowns, radios, checkboxes, eeo, etc.,
         plus an `emit_steps()` function returning the browser tool calls.

Differences vs Greenhouse:
- Lever forms use NATIVE <input>, <select>, real HTML radios/checkboxes.
  No react-select. No Filestack. The resume <input type=file> is directly
  uploadable via the standard browser file-input path.
- Field naming convention:
    Standard: name, email, phone, location, org, urls[LinkedIn], urls[GitHub],
              urls[Portfolio], resume
    Custom:   cards[<cardId>][field<idx>]  (text/textarea/select/radio/checkbox)
    EEO:      eeo[gender], eeo[race], eeo[veteran], eeo[disability], ...
- Submit is an <a data-qa="btn-submit">  (we DO NOT click it).

Keep this in sync with greenhouse_filler.py's plan-keys so inline_submit can
share most code paths.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Captcha helpers — JS payloads + solver class. Importing the JS strings is
# free (no network, no key required). Constructing CaptchaSolver() is the
# only thing that touches the API key, and we only do that at *submit time*
# (inside the runner agent), not at plan-build time.
from captcha_inject import (
    JS_DETECT_HCAPTCHA,
    JS_INJECT_HCAPTCHA,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
UPLOADS = Path("/tmp/openclaw/uploads")

DECLINE_LABELS = [
    "Decline to self identify", "Decline to self-identify",
    "Decline to identify", "Prefer not to say", "Prefer not to disclose",
    "I do not wish to answer", "I don't wish to answer",
    "Choose not to disclose", "I don't wish to self-identify",
    "Decline To Self Identify",
]


def is_eeo_field(fid: str) -> bool:
    return fid.startswith("eeo[")


def build_plan(spec: dict) -> dict:
    text_fields: dict[str, str] = {}      # native text inputs / textareas
    selects: list[dict] = []               # {name, value} for <select>
    radios: list[dict] = []                # {name, value} for radio groups (multiple-choice)
    checkboxes: list[dict] = []            # {name, values: [...]} for multi-select
    eeo: list[dict] = []                   # {name, decline_labels: [...]}
    resume_path: str | None = None
    skipped: list[dict] = []
    unknown: list[dict] = []

    org = spec.get("org", "?")
    job_id = str(spec.get("job_id", "?"))

    for f in spec["fields"]:
        fid = f["id"]
        ftype = f["type"]
        lever_type = f.get("lever_type")
        val = f["value"]
        status = f.get("status")
        label = f.get("label") or ""

        # Resume
        if ftype == "input_file" and fid == "resume":
            if val and not (isinstance(val, str) and val.startswith("<<")):
                name = Path(val).name
                resume_path = str(UPLOADS / name)
            continue

        # EEO bucket — handled via decline-by-text-search at runtime.
        if is_eeo_field(fid) or lever_type == "eeo":
            eeo.append({"name": fid, "label": label, "decline_labels": DECLINE_LABELS})
            continue

        # Text / textarea
        if ftype in ("input_text", "textarea") or lever_type in ("text", "textarea"):
            if val == "" and not f.get("required"):
                continue
            if status in ("filled", "filled_needs_review", "declined"):
                # Placeholders are kept in text_fields so _merge_cover_lever can
                # overwrite them with real essay answers. After merge, any
                # remaining placeholders are moved to `skipped`.
                text_fields[fid] = str(val)
            continue

        # Multi-select (checkboxes) — value is a label or list of labels.
        if lever_type == "multiple-select" or ftype == "multi_value_multi_select":
            if status not in ("filled", "filled_needs_review", "declined"):
                if f.get("required"):
                    skipped.append({"id": fid, "reason": "unresolved-required-multiselect"})
                continue
            vals = val if isinstance(val, list) else [val]
            checkboxes.append({"name": fid, "values": [str(v) for v in vals],
                                "options": f.get("options") or []})
            continue

        # Single-select: <select> for "dropdown"; radio buttons for "multiple-choice".
        if lever_type == "dropdown" or ftype == "multi_value_single_select" and lever_type != "multiple-choice":
            if status in ("filled", "filled_needs_review", "declined") and val:
                selects.append({"name": fid, "value": str(val),
                                 "options": f.get("options") or []})
            elif f.get("required"):
                skipped.append({"id": fid, "reason": "unresolved-required-select"})
            continue

        if lever_type == "multiple-choice":
            if status in ("filled", "filled_needs_review", "declined") and val:
                radios.append({"name": fid, "value": str(val),
                                "options": f.get("options") or []})
            elif f.get("required"):
                skipped.append({"id": fid, "reason": "unresolved-required-radio"})
            continue

        # Fallback bucket
        skipped.append({"id": fid, "type": ftype, "lever_type": lever_type})
        unknown.append({"id": fid, "type": ftype, "lever_type": lever_type, "label": label})

    return {
        "ats": "lever",
        "url": spec.get("apply_url") or spec.get("role_url"),
        "org": org,
        "job_id": job_id,
        "text_fields": text_fields,
        "selects": selects,
        "radios": radios,
        "checkboxes": checkboxes,
        "eeo": eeo,
        "resume_path": resume_path,
        "skipped": skipped,
        "unknown": unknown,
    }


# ---------------------------------------------------------------------------
# JS payloads — executed via browser.act.evaluate
# ---------------------------------------------------------------------------

# Generic helper: native React-friendly setter for inputs/textareas/selects.
JS_FILL_TEXT_FIELDS = r"""
(fields) => {
  const set = (el, val) => {
    const proto = Object.getPrototypeOf(el);
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
  };
  const results = {};
  for (const [name, value] of Object.entries(fields)) {
    const els = document.querySelectorAll(`[name="${CSS.escape(name)}"]`);
    if (!els.length) { results[name] = 'NOT_FOUND'; continue; }
    set(els[0], value);
    results[name] = 'OK:' + (value+'').slice(0, 40);
  }
  return results;
}
"""

# Location-typeahead bypass (added 2026-05-26 per Palantir 96a0ce26 diagnosis).
#
# Lever's location field (`#location-input`) is a jQuery typeahead backed by
# `retrieveLocations.js`. The blur handler WIPES both #location-input and the
# hidden #selected-location if no dropdown item was clicked. Setting values via
# the generic JS_FILL_TEXT_FIELDS path (which dispatches a blur event) therefore
# fails: input goes empty and submit is rejected with "Please select a location".
#
# Bypass: query the unauthenticated `/searchLocations?text=<X>&hcaptchaResponse=`
# endpoint directly via fetch. On the FIRST call per page-load it accepts an empty
# hcaptchaResponse and returns `[{name, id}, ...]`. We pick the first hit (or an
# exact-name match if found), set both #location-input and #selected-location
# (the latter as JSON-stringified object), then `.off('blur')` so the typeahead
# blur-wipe can't undo us.
#
# Validated end-to-end on Palantir 96a0ce26 — form passed JS_VERIFY (unset=0).
# (Captcha was the wall, not the location.)
JS_FILL_LOCATION_TYPEAHEAD = r"""
async (loc) => {
  if (!loc) return {skipped: 'no-location'};
  const inp = document.querySelector('#location-input, input.location-input');
  const sel = document.querySelector('#selected-location, input[name="selectedLocation"]');
  if (!inp || !sel) return {skipped: 'no-typeahead-on-page'};
  // First try the unauthenticated /searchLocations endpoint.
  try {
    const $ = window.jQuery || window.$;
    const hcap = ($ && $('#hcaptchaResponseInput').val()) || '';
    const res = await fetch('/searchLocations?text=' + encodeURIComponent(loc) + '&hcaptchaResponse=' + encodeURIComponent(hcap));
    const txt = await res.text();
    let locs = null;
    try { locs = JSON.parse(txt); } catch (_e) {}
    if (!locs || !locs.length) {
      // Fallback: stuff a synthetic object so the form has SOMETHING; Lever may
      // still reject server-side but we want submit to attempt rather than
      // silently no-op on blur-wipe.
      const proto = Object.getPrototypeOf(inp);
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(inp, loc);
      sel.value = JSON.stringify({name: loc});
      if ($) { $('input.location-input').off('blur'); }
      return {status: 'no-results-fallback', http: res.status, sample: txt.slice(0, 120)};
    }
    const lower = loc.toLowerCase();
    const target = locs.find(l => (l.name || '').toLowerCase() === lower)
                 || locs.find(l => (l.name || '').toLowerCase().startsWith(lower))
                 || locs[0];
    window.searchedLocations = locs;
    const proto = Object.getPrototypeOf(inp);
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(inp, target.name);
    sel.value = JSON.stringify(target);
    inp.dispatchEvent(new Event('input', {bubbles: true}));
    inp.dispatchEvent(new Event('change', {bubbles: true}));
    // Crucially: kill the blur-wipe handler so subsequent focus shifts don't
    // clear our values.
    if ($) { $('input.location-input').off('blur'); }
    return {status: 'OK', picked: target.name, id: target.id};
  } catch (e) {
    return {status: 'error', err: String(e).slice(0, 200)};
  }
}
"""

# Native <select> by visible option text.
JS_PICK_SELECTS = r"""
(items) => {
  const results = [];
  for (const it of items) {
    const sel = document.querySelector(`select[name="${CSS.escape(it.name)}"]`);
    if (!sel) { results.push({name: it.name, status: 'NOT_FOUND'}); continue; }
    const want = (it.value+'').trim().toLowerCase();
    let chosen = null;
    for (const opt of sel.options) {
      const t = (opt.textContent || opt.value || '').trim().toLowerCase();
      if (t === want) { chosen = opt; break; }
    }
    if (!chosen) {
      for (const opt of sel.options) {
        const t = (opt.textContent || opt.value || '').trim().toLowerCase();
        if (t.includes(want) || want.includes(t)) { chosen = opt; break; }
      }
    }
    if (!chosen) { results.push({name: it.name, status: 'NO_MATCH', want: it.value}); continue; }
    sel.value = chosen.value;
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    results.push({name: it.name, status: 'OK', picked: chosen.textContent.trim().slice(0,40)});
  }
  return results;
}
"""

# Radio buttons (lever multiple-choice) — pick by visible label.
JS_PICK_RADIOS = r"""
(items) => {
  const results = [];
  for (const it of items) {
    const radios = document.querySelectorAll(`input[type="radio"][name="${CSS.escape(it.name)}"]`);
    if (!radios.length) { results.push({name: it.name, status: 'NOT_FOUND'}); continue; }
    const want = (it.value+'').trim().toLowerCase();
    let picked = null;
    for (const r of radios) {
      // Find label text — prefer wrapping label, else aria-label, else value.
      let txt = '';
      let p = r.parentElement;
      while (p && !txt) { txt = (p.textContent || '').trim(); p = p.parentElement; if (txt.length > 200) break; }
      txt = txt.toLowerCase();
      const v = (r.value || '').toLowerCase();
      if (txt === want || v === want || txt.includes(want)) { picked = r; break; }
    }
    if (!picked) { picked = radios[0]; }  // fallback
    picked.click();
    picked.dispatchEvent(new Event('change', { bubbles: true }));
    results.push({name: it.name, status: 'OK', picked: picked.value});
  }
  return results;
}
"""

# Checkboxes (lever multiple-select) — check items by visible label.
JS_PICK_CHECKBOXES = r"""
(items) => {
  const results = [];
  for (const it of items) {
    const boxes = document.querySelectorAll(`input[type="checkbox"][name="${CSS.escape(it.name)}"]`);
    if (!boxes.length) { results.push({name: it.name, status: 'NOT_FOUND'}); continue; }
    const wants = (it.values || []).map(v => (v+'').trim().toLowerCase());
    let n = 0;
    for (const b of boxes) {
      let txt = '';
      let p = b.parentElement;
      while (p && !txt) { txt = (p.textContent || '').trim(); p = p.parentElement; if (txt.length > 200) break; }
      txt = txt.toLowerCase();
      if (wants.some(w => txt === w || txt.includes(w))) {
        if (!b.checked) { b.click(); }
        n++;
      }
    }
    results.push({name: it.name, status: 'OK', checked: n});
  }
  return results;
}
"""

# EEO decline-pass: for each eeo[*] field, find the option containing
# 'decline'/'prefer not'/'do not wish' and pick it (select or radio).
JS_DECLINE_EEO = r"""
(items) => {
  const declines = (items.declines || []).map(s => s.toLowerCase());
  const results = [];
  // Process all eeo[*] fields automatically — covers anything we missed.
  const sels = document.querySelectorAll('select[name^="eeo["]');
  for (const sel of sels) {
    if (sel.value && sel.value !== '' && sel.value !== 'null') {
      results.push({name: sel.name, status: 'ALREADY_SET'}); continue;
    }
    let chosen = null;
    for (const opt of sel.options) {
      const t = (opt.textContent || '').trim().toLowerCase();
      if (declines.some(d => t.includes(d))) { chosen = opt; break; }
    }
    if (chosen) {
      sel.value = chosen.value;
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      results.push({name: sel.name, status: 'OK', picked: chosen.textContent.trim()});
    } else {
      results.push({name: sel.name, status: 'NO_DECLINE_OPTION'});
    }
  }
  // Radio EEO fields: group by name.
  const allRadios = document.querySelectorAll('input[type="radio"][name^="eeo["]');
  const groups = {};
  for (const r of allRadios) { (groups[r.name] = groups[r.name] || []).push(r); }
  for (const [name, rs] of Object.entries(groups)) {
    if (rs.some(r => r.checked)) { results.push({name, status: 'ALREADY_SET'}); continue; }
    let picked = null;
    for (const r of rs) {
      let txt = '';
      let p = r.parentElement;
      while (p && !txt) { txt = (p.textContent || '').trim(); p = p.parentElement; if (txt.length > 200) break; }
      txt = txt.toLowerCase();
      if (declines.some(d => txt.includes(d))) { picked = r; break; }
    }
    if (picked) { picked.click(); results.push({name, status: 'OK', picked: picked.value}); }
    else { results.push({name, status: 'NO_DECLINE_OPTION'}); }
  }
  return results;
}
"""

# Verify — scrape filled state.
JS_VERIFY = r"""
() => {
  const data = {};
  const inputs = document.querySelectorAll('#application-form input, #application-form textarea, #application-form select');
  for (const el of inputs) {
    if (!el.name) continue;
    if (el.type === 'file') { data[el.name] = el.files && el.files.length ? `FILE:${el.files[0].name}` : ''; continue; }
    if (el.type === 'checkbox' || el.type === 'radio') {
      if (el.checked) { data[el.name] = (data[el.name]||'') + '|' + el.value; }
      continue;
    }
    data[el.name] = (el.value || '').slice(0, 80);
  }
  return data;
}
"""


# ---------------------------------------------------------------------------
# Step emission (mirrors greenhouse_filler.emit_steps)
# ---------------------------------------------------------------------------

def emit_steps(plan: dict, label: str = "lever") -> list[dict]:
    steps: list[dict] = []
    steps.append({"tool": "browser.open", "args": {"label": label, "url": plan["url"]}})
    steps.append({"tool": "sleep", "args": {"ms": 800}})
    if plan["text_fields"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_FILL_TEXT_FIELDS, "arg": plan["text_fields"],
            "comment": "Fill all text/textarea fields via native value setter.",
        }})
        # Location-typeahead bypass — runs ONLY if 'location' is in text_fields.
        # Lever's blur handler wipes location-input + selected-location whenever
        # the user didn't pick from the dropdown. The generic JS_FILL_TEXT_FIELDS
        # path dispatches `blur` so it always loses. We re-fill via the
        # /searchLocations API and unbind blur. Added 2026-05-26 per Palantir
        # 96a0ce26 diagnosis.
        loc = (plan["text_fields"] or {}).get("location")
        if loc:
            steps.append({"tool": "browser.act.evaluate", "args": {
                "label": label, "fn": JS_FILL_LOCATION_TYPEAHEAD, "arg": loc,
                "comment": "Lever location-typeahead bypass via /searchLocations API.",
            }})
    if plan["selects"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_PICK_SELECTS,
            "arg": [{"name": s["name"], "value": s["value"]} for s in plan["selects"]],
            "comment": "Pick native <select> options by visible text.",
        }})
    if plan["radios"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_PICK_RADIOS,
            "arg": [{"name": r["name"], "value": r["value"]} for r in plan["radios"]],
            "comment": "Click matching radio buttons (multiple-choice cards).",
        }})
    if plan["checkboxes"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label, "fn": JS_PICK_CHECKBOXES,
            "arg": [{"name": c["name"], "values": c["values"]} for c in plan["checkboxes"]],
            "comment": "Tick matching checkboxes (multiple-select cards).",
        }})
    # EEO decline-pass — runs for ALL eeo[*] fields on the page automatically.
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_DECLINE_EEO,
        "arg": {"declines": DECLINE_LABELS},
        "comment": "For each eeo[*] field, pick the 'Decline to self-identify' option.",
    }})
    if plan["resume_path"]:
        steps.append({"tool": "browser.upload", "args": {
            "label": label,
            # 2026-05-25 (upload regression FIX): MUST use `element=` not
            # `selector=`. selector= falls into the arm-only filechooser branch
            # and silently no-ops (ok:true, files=0). element= goes through
            # Playwright locator.setInputFiles directly.
            # See _upload-regression-diag-20260525.md.
            "element": "input#resume-upload-input, input[name='resume']",
            "paths": [plan["resume_path"]],
            "comment": "Upload resume PDF to the standard <input type=file name=resume>.",
        }})
        steps.append({"tool": "sleep", "args": {"ms": 1500}})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_VERIFY,
        "comment": "Verify filled state for human review.",
    }})

    # ------------------------------------------------------------------
    # Submit + captcha handshake
    # ------------------------------------------------------------------
    # Per STEALTH-TEST-RESULT.md: Lever ships a hidden helper button
    # `<button type="submit" id="hcaptchaSubmitBtn" class="hidden">` that
    # MUST NOT be the click target. Always select the visible "Submit
    # application" button explicitly.
    steps.append({
        "tool": "browser.act.click",
        "args": {
            "label": label,
            "selector": "button:has-text('Submit application'):visible",
            "comment": "Click the visible 'Submit application' button (NOT the hidden hcaptchaSubmitBtn helper).",
        },
        "meta": {"final_submit": True, "may_trigger_captcha": True},
    })
    # Give Lever a beat to mount the visible hCaptcha enclave if it's going to.
    steps.append({"tool": "sleep", "args": {"ms": 2500}})
    # Captcha-handling phase. The runner executes this as a single logical
    # block: detect → solve → inject → re-click submit. If CAPSOLVER_API_KEY
    # is unset the runner MUST treat this block as a single-role failure with
    # reason "CAPTCHA-NOT-CONFIGURED, see CAPTCHA-SOLVER-DECISION.md" — DO NOT
    # crash the batch.
    steps.append({
        "tool": "captcha.handle",
        "args": {
            "label": label,
            "detect_fn": JS_DETECT_HCAPTCHA,
            "inject_fn": JS_INJECT_HCAPTCHA,
            "solver_kind": "hcaptcha",
            "resubmit_selector": "button:has-text('Submit application'):visible",
            "on_not_configured": "fail-role",  # do NOT crash batch
            "failure_reason": "CAPTCHA-NOT-CONFIGURED, see CAPTCHA-SOLVER-DECISION.md",
            "comment": (
                "If a visible hCaptcha enclave is present, run CaptchaSolver().solve_hcaptcha(...)"
                " with the detected sitekey, inject the token, then re-click Submit. If no key"
                " is configured, fail this role only and continue the batch."
            ),
        },
        "meta": {"captcha_phase": True, "vendor_default": "capsolver"},
    })
    # Final verify after submit + (maybe) captcha solve.
    steps.append({"tool": "sleep", "args": {"ms": 2000}})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_VERIFY,
        "comment": "Final post-submit verify (look for confirmation page or error banner).",
    }})
    return steps


# ---------------------------------------------------------------------------
# Logging helpers (mirror greenhouse_filler signature so inline_submit code paths line up)
# ---------------------------------------------------------------------------

def log_success(org: str, job_id: str, url: str, plan: dict, confirmation: dict,
                screenshot_path: str | None) -> Path:
    out = PROJECT_ROOT / "applications" / "submissions" / "lever"
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{org}-{job_id}-success.json"
    p.write_text(json.dumps({
        "org": org, "job_id": job_id, "url": url,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "confirmation": confirmation,
        "screenshot": screenshot_path,
        "plan_summary": {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in plan.items() if k != "skipped"},
    }, indent=2) + "\n")
    return p


def log_failure(org: str, job_id: str, url: str, error: str,
                details: dict | None = None, screenshot_path: str | None = None) -> Path:
    out = PROJECT_ROOT / "applications" / "submissions" / "lever"
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{org}-{job_id}-failure.json"
    p.write_text(json.dumps({
        "org": org, "job_id": job_id, "url": url,
        "failed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "error": error, "details": details, "screenshot": screenshot_path,
    }, indent=2) + "\n")
    return p


# ---------------------------------------------------------------------------
# CLI: print plan as JSON for debugging
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="Path to a lever-*.json dryrun spec.")
    ap.add_argument("--print-steps", action="store_true")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    plan = build_plan(spec)
    if args.print_steps:
        steps = emit_steps(plan, label=f"lever-{plan['org']}-{plan['job_id'][:8]}")
        print(json.dumps({"plan": plan, "steps": steps}, indent=2, default=str))
    else:
        print(json.dumps(plan, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
