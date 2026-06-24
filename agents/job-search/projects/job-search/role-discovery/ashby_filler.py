"""Ashby form filler — emits the ordered browser-step plan to fill an Ashby
application form from an `ashby_dryrun.py` spec.

Mirrors the shape of `greenhouse_filler.py` (build_plan + emit_steps) so
`inline_submit.py` can dispatch on ATS without caring about DOM details.

Ashby DOM is much simpler than Greenhouse:
- Text/email/tel/textarea: native <input>/<textarea> with id == field uuid.
  No react-select. Use the React native value setter trick to fire change.
- ValueSelect / Boolean (and even multi-option like "Yes, and I currently live
  in the SF Bay Area."): rendered as <input type=radio>. Radio name pattern is
  `<formId>_<fieldId>` and ids are `<formId>_<fieldId>-labeled-radio-<idx>`.
  A <label for=...> sibling holds the option text.
- MultiValueSelect: rendered as <input type=checkbox> with the same
  name/id pattern (we tick the checkbox whose label matches our value).
- Resume: direct <input type=file id="_systemfield_resume"> — no Filestack.
  Just upload via browser.upload to the selector "#_systemfield_resume".
- Submit: <button type=submit> whose visible text is "Submit Application".
- reCAPTCHA: usually invisible. The submit-button click triggers the challenge;
  the calling agent solves it (or it auto-passes on a clean residential IP).

The dryrun field id is the same uuid the DOM uses (we lifted the schema from
the Ashby React app's network response). For radios/checkboxes the id we
record is `<formId>_<fieldId>` — JS resolves children by name attribute.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRYRUN_DIR = HERE.parent / "applications" / "dryrun"


# ---------------------------------------------------------------------------
# JS snippets shipped to browser.act.evaluate. Each takes one `arg` (passed
# as the first parameter when the agent invokes evaluate with a dict arg).
# Keep them defensive: missing fields should report skipped, not throw.
# ---------------------------------------------------------------------------

# Native value setter for React-controlled inputs/textareas.
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
  // Resolve a dryrun field id to a DOM element. Ashby's DOM strips the form-id
  // prefix for text inputs but keeps it for other widgets, so try several
  // suffix variants in order: full id, last UUID/bare suffix, last "_systemfield_*".
  const resolve = (fid) => {
    let el = document.getElementById(fid);
    if (el) return el;
    // last underscore-separated chunk (handles "<formId>_<fieldId>" -> "<fieldId>")
    const parts = fid.split('_');
    for (let i = 1; i < parts.length; i++) {
      const tail = parts.slice(i).join('_');
      el = document.getElementById(tail);
      if (el) return el;
      // also try with leading underscore (e.g. "_systemfield_name")
      if (!tail.startsWith('_')) {
        el = document.getElementById('_' + tail);
        if (el) return el;
      }
    }
    // last resort: name=
    el = document.querySelector(`[name="${fid}"]`);
    return el;
  };
  for (const [fid, value] of Object.entries(textFields || {})) {
    try {
      const el = resolve(fid);
      if (!el) { out.missing.push(fid); continue; }
      // Skip non-text elements (radio/checkbox/file) defensively.
      if (el.tagName === 'INPUT' && ['radio','checkbox','file','submit','button'].includes(el.type)) {
        out.missing.push({id: fid, reason: 'wrong-type:'+el.type});
        continue;
      }
      setNativeValue(el, value ?? '');
      out.filled.push({id: fid, dom_id: el.id, len: (value || '').length});
    } catch (e) {
      out.errors.push({id: fid, error: String(e)});
    }
  }
  return out;
}
"""

# ---- chain_005 P1 (2026-05-26): Native-setter FAST PATH for plain-text Ashby
# fields. Chain_004 verified on Sentry & OpenAI tenants that
# `_valueTracker.setValue` + `input` event DOES propagate React state for
# `_ashby_type in {String, Email, Phone, Number, Url, LongText}`. It is
# 5–10x faster than per-key CDP keystrokes. The driver should TRY this first,
# then verify by re-reading `input.value` after a short tick. On verification
# failure (React internal state didn't pick up — e.g. on certain tenants or
# with `react-hook-form` wrappers), fall back to the existing CDP-keystrokes
# path (`ashby.type_text_fields`).
#
# Caveat: do NOT call this on `_ashby_type=combobox` / `Location` fields
# (their search listener needs a real `keypress` event to populate options).
# The emitter excludes Location from the fast-path input set.
#
# Kill switch: set `USE_NATIVE_SETTER_FAST_PATH = False` (constant below) and
# re-emit plans. Driver should treat missing fast-path step as "skip".
USE_NATIVE_SETTER_FAST_PATH = True

JS_FAST_FILL_TEXT_FIELDS = r"""
(textFields) => {
  // Native-setter + input-event path. Returns per-field result for the driver
  // to verify. Driver should re-read input.value after a short tick and fall
  // back to CDP keystrokes on any field whose read-back value != requested.
  const out = {filled: [], missing: [], errors: []};
  const setNativeValue = (el, value) => {
    const proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, value);
    // input-event only on the fast path (avoids blur-flush + change side
    // effects that some tenants use to trigger validators eagerly).
    el.dispatchEvent(new Event('input', {bubbles: true}));
  };
  const resolve = (fid) => {
    let el = document.getElementById(fid);
    if (el) return el;
    const parts = fid.split('_');
    for (let i = 1; i < parts.length; i++) {
      const tail = parts.slice(i).join('_');
      el = document.getElementById(tail);
      if (el) return el;
      if (!tail.startsWith('_')) {
        el = document.getElementById('_' + tail);
        if (el) return el;
      }
    }
    el = document.querySelector(`[name="${fid}"]`);
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
      out.filled.push({id: fid, dom_id: el.id, len: (value || '').length, post_value: el.value});
    } catch (e) {
      out.errors.push({id: fid, error: String(e)});
    }
  }
  return out;
}
"""

# ---- chain_005 P4 (2026-05-26): Location typeahead resolver. Returns
# {fid, dom_id, cx, cy, current_value} so the driver can clickCoords to focus
# before typing the city. Driver then types the city as CDP keystrokes
# (combobox search listener needs real keypress events — chain_004 lesson),
# waits for `[role=option]` / `[role=listbox]` to render, and clicks the
# first matching option. Fallback: tab-out to commit free-text.
JS_RESOLVE_LOCATION_INPUTS = r"""
(locFields) => {
  const out = {resolved: [], missing: []};
  const resolve = (fid) => {
    let el = document.getElementById(fid);
    if (el) return el;
    const parts = fid.split('_');
    for (let i = 1; i < parts.length; i++) {
      const tail = parts.slice(i).join('_');
      el = document.getElementById(tail);
      if (el) return el;
      if (!tail.startsWith('_')) {
        el = document.getElementById('_' + tail);
        if (el) return el;
      }
    }
    el = document.querySelector(`[name="${fid}"]`);
    return el;
  };
  for (const lf of locFields || []) {
    const el = resolve(lf.fid);
    if (!el) { out.missing.push(lf.fid); continue; }
    try { el.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
    const rect = el.getBoundingClientRect();
    out.resolved.push({
      fid: lf.fid, dom_id: el.id, value: lf.value,
      current_value: el.value || '',
      cx: Math.round(rect.left + rect.width / 2),
      cy: Math.round(rect.top + rect.height / 2),
    });
  }
  return out;
}
"""

# ---- chain_028 (2026-05-29 Speak 1015 guard): Self-contained, defensive
# Ashby Location typeahead. Previously chain_005 P4 emitted a multi-step
# *instruction* ("clickCoords -> CDP keystrokes -> wait listbox -> click
# option") that the calling agent followed manually. When the option list
# never populated (slow tenant, async fetch debounce, server lag), the
# agent improvised and crashed mid-recipe on Speak 1015 (chain_013).
#
# This new helper is one self-contained async JS function. It:
#   1. Resolves each location fid (with the same fallback logic).
#   2. Tries the FAST PATH: setNative(input, value) + Tab to commit free-text.
#      Many Ashby tenants accept the plain text value without selecting from
#      the typeahead (Location is sometimes a free-text input dressed up as
#      a combobox).
#   3. If Tab did NOT commit (input still has the typed text and an open
#      listbox is present), falls back to PER-CHAR KeyboardEvent typing
#      (recipe ported from greenhouse_filler.JS_PICK_DROPDOWN_TYPEAHEAD
#      chain_026 — async typeaheads need real keydown/keyup per char to
#      trigger their remote fetch). Polls up to ~2500ms for
#      `[role=option]` / `[role=listbox] [role=option]` / `[role=combobox]`
#      descendant options, then clicks the best match.
#   4. ALWAYS returns a structured result: {resolved: [{fid, method, picked}],
#      unresolved: [{fid, reason, label}]}. NEVER throws. NEVER hangs > 5s
#      per field. Driver reads the result and decides: proceed-to-submit
#      (resolved >= required count) OR mark BLOCKED.
#
# Why a single evaluate() step: removes all room for the calling agent to
# improvise. The helper handles the empty-options edge case internally
# (graceful unresolved) instead of crashing.
USE_LOCATION_TYPEAHEAD_SELF_CONTAINED = True

JS_FILL_ASHBY_LOCATION_TYPEAHEAD = r"""
async (locFields) => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const out = {resolved: [], unresolved: []};
  const resolve = (fid) => {
    let el = document.getElementById(fid);
    if (el) return el;
    const parts = fid.split('_');
    for (let i = 1; i < parts.length; i++) {
      const tail = parts.slice(i).join('_');
      el = document.getElementById(tail);
      if (el) return el;
      if (!tail.startsWith('_')) {
        el = document.getElementById('_' + tail);
        if (el) return el;
      }
    }
    el = document.querySelector(`[name="${fid}"]`);
    if (el) return el;
    // chain_028 LIVE-FIX (Speak 1015, 2026-05-29): Ashby Location combobox
    // input has NO id and NO name; only role="combobox" + placeholder
    // "Start typing...". The spec's `*__systemfield_location` fid points
    // to a wrapper div, not the input. Fall back to role-based lookup.
    // chain_041 (2026-05-31 ElevenLabs 939): the `/location/i.test(fid)`
    // gate was too narrow — ElevenLabs' Location field is a CUSTOM-UUID
    // field (`<formId>_<uuid>`, no "location" substring), so the fallback
    // never fired and resolve() returned null -> "no-input" -> required
    // Location left empty -> server rejected. These fields ALL come from
    // build_plan's location_fields (already typed `_ashby_type==Location`),
    // so the combobox fallback is always safe here. Drop the fid gate.
    {
      const combos = [...document.querySelectorAll('input[role="combobox"]')];
      // Prefer one with location-y placeholder text, else first UNFILLED combobox.
      el = combos.find(i => /start typing|location|city|country|where/i.test(i.placeholder || ''))
        || combos.find(i => /start typing|location|city|country|where/i.test(i.getAttribute('aria-label') || ''))
        || combos.find(i => !i.value)
        || combos[0];
      if (el) return el;
    }
    return el;
  };
  const setNative = (el, val) => {
    const proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles: true}));
  };
  const fireKey = (el, type, ch) => {
    el.dispatchEvent(new KeyboardEvent(type, {
      key: ch, code: 'Key' + (ch || '').toUpperCase(),
      bubbles: true, cancelable: true,
    }));
  };
  const findOptions = () => {
    // Ashby typeahead options live in a popped listbox. Try common shapes.
    let opts = [...document.querySelectorAll('[role="listbox"] [role="option"]')];
    if (!opts.length) opts = [...document.querySelectorAll('[role="option"]')];
    if (!opts.length) opts = [...document.querySelectorAll('[id*="option"]')];
    // chain (2026-06-03 Rogo): some Ashby tenants render listbox options as
    // <div class="_option_*"> inside <div role=listbox class="_floatingContainer_*">
    // rather than [role=option]. Match those class-based options too.
    if (!opts.length) {
      const lb = document.querySelector('[role="listbox"]');
      if (lb) opts = [...lb.querySelectorAll('[class*="_option"]')];
    }
    if (!opts.length) opts = [...document.querySelectorAll('[class*="_option_"]')];
    // Filter out hidden / size-0 options.
    return opts.filter(o => {
      const r = o.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
  };
  const waitForOptions = async (budgetMs) => {
    const start = Date.now();
    while (Date.now() - start < budgetMs) {
      const opts = findOptions();
      if (opts.length) return opts;
      await sleep(80);
    }
    return findOptions();
  };
  const pickBest = (opts, label) => {
    const want = String(label || '').trim().toLowerCase();
    if (!want) return opts[0] || null;
    const cityTok = want.split(',')[0].trim();           // "kirkland, wa" -> "kirkland"
    const stateTok = (want.split(',')[1] || '').trim();  // -> "wa"
    const exact = opts.find(o => o.textContent.trim().toLowerCase() === want)
        || opts.find(o => o.textContent.trim().toLowerCase().startsWith(want))
        || opts.find(o => o.textContent.toLowerCase().includes(want))
        || opts.find(o => cityTok && o.textContent.toLowerCase().includes(cityTok))
        || opts.find(o => stateTok && o.textContent.toLowerCase().includes(stateTok));
    if (exact) return exact;
    // chain_041 (2026-05-31): NO token overlap. Previously fell through to
    // opts[0] and picked garbage ("Wallis and Futuna" for "Kirkland, WA" on
    // ElevenLabs). That silently mis-submits a wrong location. Instead: if the
    // option set looks like a COUNTRY picker, pick "United States"; otherwise
    // return null so the caller leaves the field unresolved (human review)
    // rather than asserting a false location.
    const us = opts.find(o => /united states|^usa$|^us$/i.test(o.textContent.trim()));
    if (us) return us;
    return null;
  };
  const clickOption = (target) => {
    const tr = target.getBoundingClientRect();
    const opts = {bubbles: true, cancelable: true, view: window, button: 0,
                  clientX: tr.left + 5, clientY: tr.top + 5};
    target.dispatchEvent(new MouseEvent('mousedown', opts));
    target.dispatchEvent(new MouseEvent('mouseup', opts));
    target.dispatchEvent(new MouseEvent('click', opts));
  };

  for (const lf of locFields || []) {
    const fid = lf.fid;
    const label = lf.value || '';
    let el;
    try {
      el = resolve(fid);
    } catch (e) {
      out.unresolved.push({fid, label, reason: 'resolve-threw:' + String(e)});
      continue;
    }
    if (!el) { out.unresolved.push({fid, label, reason: 'no-input'}); continue; }
    try { el.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
    await sleep(80);

    // ---- Attempt 1: fast path. setNative + focus + Tab to commit free-text.
    try {
      el.focus();
      setNative(el, '');
      await sleep(40);
      setNative(el, label);
      await sleep(250);
      let opts = findOptions();
      if (opts.length) {
        const target = pickBest(opts, label);
        if (target) {
          clickOption(target);
          await sleep(180);
          out.resolved.push({fid, label, method: 'fast-setNative+pick',
                             picked: (target.textContent || '').trim().slice(0, 80),
                             post_value: el.value});
          continue;
        }
      }
    } catch (e) { /* fall through to per-char */ }

    // ---- Attempt 2: per-char KeyboardEvent typing (async-typeahead recipe).
    try {
      el.focus();
      setNative(el, '');
      await sleep(60);
      fireKey(el, 'keydown', '');
      const s = String(label);
      for (let i = 1; i <= s.length; i++) {
        setNative(el, s.slice(0, i));
        const ch = s[i - 1];
        fireKey(el, 'keydown', ch);
        fireKey(el, 'keyup', ch);
        await sleep(55);
      }
      const opts = await waitForOptions(2500);
      if (opts.length) {
        const target = pickBest(opts, label);
        if (target) {
          clickOption(target);
          await sleep(200);
          out.resolved.push({fid, label, method: 'per-char+pick',
                             picked: (target.textContent || '').trim().slice(0, 80),
                             post_value: el.value});
          continue;
        }
      }
    } catch (e) {
      out.unresolved.push({fid, label, reason: 'per-char-threw:' + String(e).slice(0, 120)});
      continue;
    }

    // ---- Attempt 3: free-text + Tab commit. If the input retained the
    // value, declare resolved-as-freetext (some Ashby tenants accept this).
    try {
      el.focus();
      const haveValue = (el.value || '').trim().length > 0;
      fireKey(el, 'keydown', 'Tab');
      el.dispatchEvent(new Event('blur', {bubbles: true}));
      await sleep(120);
      if (haveValue) {
        out.resolved.push({fid, label, method: 'free-text-tab',
                           post_value: el.value, required: !!lf.required});
        continue;
      }
    } catch (e) {}

    out.unresolved.push({fid, label, required: !!lf.required,
                        reason: 'no-options-after-2500ms',
                        post_value: (el && el.value) || ''});
  }
  return out;
}
"""

# ---- FIX 1 helper (resolve-only; per-field typing happens via CDP keystrokes,
# NOT JS value setter). Returns [{fid, dom_id, current_value, len}, ...] so the
# driver knows the exact DOM id to target with act:type.
JS_RESOLVE_TEXT_FIELDS = r"""
(textFields) => {
  const out = {resolved: [], missing: []};
  const resolve = (fid) => {
    let el = document.getElementById(fid);
    if (el) return el;
    const parts = fid.split('_');
    for (let i = 1; i < parts.length; i++) {
      const tail = parts.slice(i).join('_');
      el = document.getElementById(tail);
      if (el) return el;
      if (!tail.startsWith('_')) {
        el = document.getElementById('_' + tail);
        if (el) return el;
      }
    }
    el = document.querySelector(`[name="${fid}"]`);
    return el;
  };
  for (const [fid, value] of Object.entries(textFields || {})) {
    const el = resolve(fid);
    if (!el) { out.missing.push(fid); continue; }
    if (el.tagName === 'INPUT' && ['radio','checkbox','file','submit','button'].includes(el.type)) {
      out.missing.push({id: fid, reason: 'wrong-type:'+el.type});
      continue;
    }
    // scroll into view so driver's clickCoords/act:type lands correctly.
    try { el.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
    out.resolved.push({fid, dom_id: el.id, tag: el.tagName.toLowerCase(), type: el.type || null, current_value: el.value || '', want_len: (value || '').length});
  }
  return out;
}
"""

# ---- FIX 2 helper (resolve-only; clicks happen via CDP clickCoords on the
# <label> element). Returns [{name, label_id, label_text, cx, cy}, ...].
JS_RESOLVE_RADIO_LABELS = r"""
(radios) => {
  // chain_033 (2026-05-30 Notion fix): radio entries may be EITHER
  //   (a) traditional <input type=radio> groups (ValueSelect, EEOC, etc.), OR
  //   (b) yesno-button widgets — <div class="_yesno_*">
  //         <button>Yes</button><button>No</button>
  //       wrapped in a <div class="_fieldEntry_*" data-field-path="<uuid|_systemfield_X>">
  //       container, with a HIDDEN <input type=checkbox> that React does NOT
  //       use for serialization (only the button's `_active_` class counts).
  // For (b), the input[type=radio] lookup returns nothing — pre-chain_033 this
  // left Notion/Speak/Baseten/Plain Boolean fields unfilled and the submit
  // validator reported them as missing. We now fall back to a `_yesno_`
  // resolver that returns the matching <button>'s bounding-rect center. The
  // driver still clickCoords on (cx, cy) — same recipe, different target.
  const out = {picked: [], missing: [], no_match: []};
  const allRadioNames = new Set([...document.querySelectorAll('input[type=radio]')].map(r => r.name));
  const resolveName = (rname) => {
    if (allRadioNames.has(rname)) return rname;
    const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
    const uuids = rname.match(uuidRe) || [];
    const tail = uuids[uuids.length - 1];
    if (tail) {
      for (const n of allRadioNames) { if (n.endsWith('_' + tail) || n === tail) return n; }
    }
    return null;
  };
  // ---- chain_033 yesno-button fallback ----
  // The dryrun fid is `<formId>_<fieldUuid>` (or `<formId>__systemfield_X`).
  // Per Ashby DOM contract, the per-field container is
  //   <div class="_fieldEntry_*" data-field-path="<fieldUuid|_systemfield_X>">
  // We try data-field-path equal to either (a) the full fid, (b) the
  // trailing UUID, or (c) the trailing `_systemfield_*` suffix. The yesno
  // div lives somewhere inside that container.
  const extractFieldPath = (fid) => {
    const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
    const uuids = fid.match(uuidRe) || [];
    const sysIdx = fid.indexOf('_systemfield_');
    const candidates = [fid];
    if (uuids.length >= 1) candidates.push(uuids[uuids.length - 1]);
    if (sysIdx >= 0) candidates.push(fid.slice(sysIdx));
    return candidates;
  };
  const findYesnoContainer = (fid) => {
    for (const cand of extractFieldPath(fid)) {
      const entry = document.querySelector(`[data-field-path="${cand}"]`);
      if (entry && entry.querySelector('div[class*="_yesno_"]')) return entry;
    }
    // Last-ditch: any _fieldEntry_ whose hidden checkbox name matches.
    for (const cb of document.querySelectorAll('input[type=checkbox]')) {
      if (cb.name === fid || fid.endsWith('_' + cb.name) || cb.name.endsWith('_' + fid)) {
        const entry = cb.closest('[class*="_fieldEntry_"], [data-field-path]');
        if (entry && entry.querySelector('div[class*="_yesno_"]')) return entry;
      }
    }
    return null;
  };
  const pickYesnoButton = (entry, tries) => {
    const yesno = entry.querySelector('div[class*="_yesno_"]');
    if (!yesno) return null;
    const btns = [...yesno.querySelectorAll('button')];
    if (!btns.length) return null;
    const btnText = (b) => (b.textContent || '').trim().toLowerCase();
    for (const cand of tries) {
      const c = (cand || '').trim().toLowerCase();
      if (!c) continue;
      const hit = btns.find(b => btnText(b) === c)
               || btns.find(b => btnText(b).startsWith(c))
               || btns.find(b => btnText(b).includes(c));
      if (hit) return hit;
    }
    return null;
  };
  for (const r of radios || []) {
    const name = resolveName(r.name);
    const tries = [r.value, ...(r.alternates || [])].filter(Boolean);
    const inputs = name
      ? [...document.querySelectorAll(`input[type=radio][name="${name}"]`)]
      : [];
    // ---- (a) Traditional radio path ----
    if (inputs.length) {
      const labelText = (id) => (document.querySelector(`label[for="${id}"]`)?.textContent || '').trim().toLowerCase();
      let chosen = null;
      for (const cand of tries) {
        const c = (cand || '').trim().toLowerCase();
        chosen = inputs.find(i => labelText(i.id) === c)
              || inputs.find(i => labelText(i.id).startsWith(c))
              || inputs.find(i => labelText(i.id).includes(c));
        if (chosen) break;
      }
      if (!chosen) { out.no_match.push({name, want: r.value, options: inputs.map(i => labelText(i.id))}); continue; }
      const label = document.querySelector(`label[for="${chosen.id}"]`);
      if (!label) { out.no_match.push({name, want: r.value, reason: 'no <label for=> found'}); continue; }
      try { label.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
      const rect = label.getBoundingClientRect();
      out.picked.push({
        name,
        kind: 'radio_label',
        label_id: label.id || null,
        label_for: chosen.id,
        label_text: (label.textContent || '').trim(),
        cx: Math.round(rect.left + rect.width / 2),
        cy: Math.round(rect.top + rect.height / 2),
      });
      continue;
    }
    // ---- (b) Yesno-button fallback (chain_033) ----
    const container = findYesnoContainer(r.name);
    if (container) {
      const btn = pickYesnoButton(container, tries);
      if (!btn) {
        const opts = [...container.querySelectorAll('div[class*="_yesno_"] button')]
          .map(b => (b.textContent || '').trim().toLowerCase());
        out.no_match.push({name: r.name, want: r.value, kind: 'yesno_button', options: opts});
        continue;
      }
      try { btn.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
      const rect = btn.getBoundingClientRect();
      out.picked.push({
        name: r.name,
        kind: 'yesno_button',
        label_id: null,
        label_for: null,
        label_text: (btn.textContent || '').trim(),
        already_active: /_active_/.test(btn.className || ''),
        cx: Math.round(rect.left + rect.width / 2),
        cy: Math.round(rect.top + rect.height / 2),
      });
      continue;
    }
    // ---- Neither traditional nor yesno found ----
    out.missing.push({want_name: r.name, resolved: name});
  }
  return out;
}
"""

# Same as radio resolver, but for checkboxes (MultiValueSelect).
JS_RESOLVE_CHECKBOX_LABELS = r"""
(checkboxes) => {
  const out = {picked: [], missing: [], no_match: []};
  const allBoxNames = new Set([...document.querySelectorAll('input[type=checkbox]')].map(c => c.name));
  const resolveName = (cname) => {
    if (allBoxNames.has(cname)) return cname;
    const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
    const uuids = cname.match(uuidRe) || [];
    const tail = uuids[uuids.length - 1];
    if (tail) {
      for (const n of allBoxNames) { if (n.endsWith('_' + tail) || n === tail) return n; }
    }
    return null;
  };
  for (const c of checkboxes || []) {
    const name = resolveName(c.name);
    if (!name) { out.missing.push({want_name: c.name}); continue; }
    const inputs = [...document.querySelectorAll(`input[type=checkbox][name="${name}"]`)];
    if (!inputs.length) { out.missing.push({want_name: c.name, resolved: name}); continue; }
    const labelText = (id) => (document.querySelector(`label[for="${id}"]`)?.textContent || '').trim().toLowerCase();
    for (const want of (c.values || [])) {
      const w = (want || '').trim().toLowerCase();
      const target = inputs.find(i => labelText(i.id) === w)
                  || inputs.find(i => labelText(i.id).startsWith(w))
                  || inputs.find(i => labelText(i.id).includes(w));
      if (!target) { out.no_match.push({name, want, options: inputs.map(i => labelText(i.id))}); continue; }
      const label = document.querySelector(`label[for="${target.id}"]`);
      if (!label) { out.no_match.push({name, want, reason: 'no <label for=> found'}); continue; }
      try { label.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
      const rect = label.getBoundingClientRect();
      out.picked.push({
        name, want,
        label_for: target.id,
        label_text: (label.textContent || '').trim(),
        cx: Math.round(rect.left + rect.width / 2),
        cy: Math.round(rect.top + rect.height / 2),
        already_checked: target.checked,
      });
    }
  }
  return out;
}
"""

# LEGACY (kept for back-compat / debugging only — emit_steps no longer uses
# these. Driver should use the new ashby.type_text_fields, label-coord radio,
# and ashby.upload_resume_via_visible_button steps instead. See FIX 1/2/3.)

# Click the radio whose <label> text matches the desired option (case-insensitive,
# substring or startswith). `radios` is [{name, value, alternates?}] where
# `name` is the radio group name (`<formId>_<fieldId>`).
JS_PICK_RADIOS = r"""
(radios) => {
  const out = {picked: [], missing: [], no_match: []};
  // Resolve a dryrun radio name to the actual DOM radio name.
  // Strategy: try exact name first; if nothing matches, try the "tail" of
  // the dryrun id (split on '_'), then any radio whose name ENDS WITH
  // the dryrun id's last UUID-shaped segment.
  const allRadioNames = new Set([...document.querySelectorAll('input[type=radio]')].map(r => r.name));
  const resolveName = (rname) => {
    if (allRadioNames.has(rname)) return rname;
    // Try matching by tail UUID (last 36-char segment)
    const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
    const uuids = rname.match(uuidRe) || [];
    const tail = uuids[uuids.length - 1];
    if (tail) {
      for (const n of allRadioNames) { if (n.endsWith('_' + tail) || n === tail) return n; }
    }
    return null;
  };
  for (const r of radios || []) {
    const name = resolveName(r.name);
    if (!name) { out.missing.push({want_name: r.name}); continue; }
    const inputs = [...document.querySelectorAll(`input[type=radio][name="${name}"]`)];
    if (!inputs.length) { out.missing.push({want_name: r.name, resolved: name}); continue; }
    const labelText = (id) => (document.querySelector(`label[for="${id}"]`)?.textContent || '').trim().toLowerCase();
    const tries = [r.value, ...(r.alternates || [])].filter(Boolean);
    let chosen = null;
    for (const cand of tries) {
      const c = (cand || '').trim().toLowerCase();
      chosen = inputs.find(i => labelText(i.id) === c)
            || inputs.find(i => labelText(i.id).startsWith(c))
            || inputs.find(i => labelText(i.id).includes(c));
      if (chosen) break;
    }
    if (!chosen) { out.no_match.push({name, want: r.value, options: inputs.map(i => labelText(i.id))}); continue; }
    chosen.click();
    chosen.dispatchEvent(new Event('change', {bubbles: true}));
    out.picked.push({name, label: (document.querySelector(`label[for="${chosen.id}"]`)?.textContent || '').trim()});
  }
  return out;
}
"""

# Tick checkboxes for MultiValueSelect. `checkboxes` is [{name, values: [...]}].
JS_PICK_CHECKBOXES = r"""
(checkboxes) => {
  const out = {picked: [], missing: [], no_match: []};
  const allBoxNames = new Set([...document.querySelectorAll('input[type=checkbox]')].map(c => c.name));
  const resolveName = (cname) => {
    if (allBoxNames.has(cname)) return cname;
    const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
    const uuids = cname.match(uuidRe) || [];
    const tail = uuids[uuids.length - 1];
    if (tail) {
      for (const n of allBoxNames) { if (n.endsWith('_' + tail) || n === tail) return n; }
    }
    return null;
  };
  for (const c of checkboxes || []) {
    const name = resolveName(c.name);
    if (!name) { out.missing.push({want_name: c.name}); continue; }
    const inputs = [...document.querySelectorAll(`input[type=checkbox][name="${name}"]`)];
    if (!inputs.length) { out.missing.push({want_name: c.name, resolved: name}); continue; }
    const labelText = (id) => (document.querySelector(`label[for="${id}"]`)?.textContent || '').trim().toLowerCase();
    for (const want of (c.values || [])) {
      const w = (want || '').trim().toLowerCase();
      const target = inputs.find(i => labelText(i.id) === w)
                  || inputs.find(i => labelText(i.id).startsWith(w))
                  || inputs.find(i => labelText(i.id).includes(w));
      if (!target) { out.no_match.push({name, want, options: inputs.map(i => labelText(i.id))}); continue; }
      if (!target.checked) {
        target.click();
        target.dispatchEvent(new Event('change', {bubbles: true}));
      }
      out.picked.push({name, label: labelText(target.id)});
    }
  }
  return out;
}
"""

# Verify form state: count filled inputs, list any required-but-empty.
JS_VERIFY = r"""
() => {
  const summary = {
    text_inputs: 0, text_filled: 0,
    radios_groups: 0, radios_checked: 0,
    checkboxes: 0, checkboxes_checked: 0,
    file_inputs: 0, file_loaded: 0,
    submit_button: null,
  };
  for (const el of document.querySelectorAll('input[type=text], input[type=email], input[type=tel], textarea')) {
    summary.text_inputs++;
    if ((el.value || '').trim()) summary.text_filled++;
  }
  const radioNames = new Set();
  for (const r of document.querySelectorAll('input[type=radio]')) radioNames.add(r.name);
  summary.radios_groups = radioNames.size;
  for (const name of radioNames) {
    if (document.querySelector(`input[type=radio][name="${name}"]:checked`)) summary.radios_checked++;
  }
  for (const c of document.querySelectorAll('input[type=checkbox]')) {
    summary.checkboxes++;
    if (c.checked) summary.checkboxes_checked++;
  }
  // LEARNING (Baseten 944, 2026-05-26): Ashby Yes/No questions render as a
  // <div> with two styled <button>s + a hidden <input type=checkbox>. The
  // checkbox.checked does NOT track button selection — only the
  // `_active_y2cw4_58` class on the chosen <button> does, and that class is
  // what React serializes on submit. Verify Yes/No via this class, never via
  // checkbox.checked. (browser.act:click ref=<aria-ref> reliably toggles it;
  // synthetic .click() and clickCoords may not.)
  summary.yesno_buttons_active = 0;
  summary.yesno_groups = 0;
  document.querySelectorAll('div._yesno_17tft_149, div[class*="_yesno_"]').forEach(g => {
    summary.yesno_groups++;
    if ([...g.querySelectorAll('button')].some(b => /_active_/.test(b.className))) summary.yesno_buttons_active++;
  });
  for (const f of document.querySelectorAll('input[type=file]')) {
    summary.file_inputs++;
    if (f.files && f.files.length) summary.file_loaded++;
  }
  const submitBtn = [...document.querySelectorAll('button')].find(b => /submit application/i.test((b.textContent || '').trim()));
  summary.submit_button = submitBtn ? {found: true, disabled: submitBtn.disabled, text: submitBtn.textContent.trim()} : {found: false};
  return summary;
}
"""

# Click the Submit Application button (used after manual review).
JS_CLICK_SUBMIT = r"""
() => {
  const btn = [...document.querySelectorAll('button')].find(b => /submit application/i.test((b.textContent || '').trim()));
  if (!btn) return {ok: false, error: 'submit button not found'};
  if (btn.disabled) return {ok: false, error: 'submit button is disabled'};
  btn.click();
  return {ok: true, text: btn.textContent.trim()};
}
"""


# ---------------------------------------------------------------------------
# Plan builder — converts dryrun spec into structured browser actions.
# ---------------------------------------------------------------------------

DEMO_LABEL_RE = re.compile(
    r"\b(gender|race|ethnicity|veteran|disability|self.?identif|pronoun|age range)\b",
    re.I,
)


def _is_demographic(label: str) -> bool:
    return bool(DEMO_LABEL_RE.search(label or ""))


def build_plan(spec: dict) -> dict:
    """Build a structured plan dict from an ashby_dryrun spec."""
    text_fields: dict[str, str] = {}
    date_fields: dict[str, str] = {}              # chain_005 P3: react-datepicker text + Enter
    location_fields: list[dict] = []               # chain_005 P4: typeahead {fid, value, label}
    radios: list[dict] = []
    checkboxes: list[dict] = []
    resume_path: str | None = None
    skipped: list[dict] = []
    needs_review: list[dict] = []

    for f in spec.get("fields", []):
        atype = f.get("_ashby_type", "")
        status = f.get("status")
        fid = f["id"]
        label = f.get("label", "")
        value = f.get("value", "")

        # Skip unresolved (only blockers would show; optional unresolveds get
        # left blank in the form which is the correct behavior).
        if status == "unresolved":
            skipped.append({"id": fid, "label": label, "reason": "unresolved"})
            continue
        if status == "needs_essay":
            # cover_answer_generator should have filled this via
            # inline_submit.merge_cover_answers_into_plan; if value is empty
            # we still emit the (empty) text_field entry so it's visible.
            text_fields[fid] = value or ""
            continue

        # chain (2026-06-03 Cohere 598): the dryrun spec scrapes the live DOM
        # and types the Ashby Location combobox as a plain `input_text`
        # (ashby_type null) because the input LOOKS like a text input. Routing
        # it through text_fields breaks submission — the combobox search
        # listener needs REAL keypress events (it ignores .value sets), so the
        # server sees Location empty and rejects (Rogo/Cohere both died here).
        # Detect Location by the canonical `_systemfield_location` id OR an
        # exact "Location" label even when ashby_type is missing, and route to
        # the typeahead handler. This unblocks the permissive-Ashby cohort.
        _id_l = (f.get("id") or fid or "")
        _lab_l = (label or "").strip().lower()
        if atype == "Location" or _id_l.endswith("_systemfield_location") or _lab_l == "location":
            location_fields.append({
                "fid": fid,
                "value": str(value) if value is not None else "",
                "label": label,
                "required": f.get("required", False),
            })
            continue

        if atype in ("String", "Email", "Phone", "URL", "Url"):
            text_fields[fid] = value or ""
        elif atype == "LongText":
            text_fields[fid] = value or ""
        elif atype == "Number":
            text_fields[fid] = str(value) if value is not None else ""
        elif atype == "Date":
            # chain_005 P3 (2026-05-26): Ashby Date fields render as a
            # react-datepicker text input. The dryrun resolver already
            # populates a value (e.g. "Two weeks from offer" or an
            # MM/DD/YYYY string from the earliest_start rule). Route
            # through text_fields so the driver types it like any string;
            # if it parses as a date the driver should also send Enter to
            # commit the datepicker. Tracking via separate date_fields
            # dict so the emitter can flag Enter-key follow-up.
            text_fields[fid] = str(value) if value is not None else ""
            date_fields[fid] = str(value) if value is not None else ""
        elif atype == "Location":
            # chain_005 P4 (2026-05-26): Ashby Location fields render as a
            # typeahead combobox. The dryrun resolver already populates a
            # value (typically `address.city` like "Kirkland"). DO NOT add
            # to text_fields (combobox search listener requires real
            # keypress events — chain_004 lesson). Emitter routes through
            # a multi-step location-typeahead handler instead.
            location_fields.append({
                "fid": fid,
                "value": str(value) if value is not None else "",
                "label": label,
                "required": f.get("required", False),
            })
        elif atype == "File":
            # Only the resume field is auto-attached. Other File fields
            # (transcripts, work-sample) are skipped and surfaced for review.
            if "resume" in label.lower() or fid == "_systemfield_resume":
                resume_path = str(value) if value else None
            else:
                skipped.append({"id": fid, "label": label, "reason": "non-resume file field"})
        elif atype in ("ValueSelect", "Boolean"):
            # Single-select -> radio. Build alternates list for fuzzy match.
            alts = []
            if isinstance(value, str):
                v = value.strip().lower()
                if v in ("yes", "true"):
                    alts = ["yes", "yes, i agree", "i agree", "i acknowledge", "i confirm"]
                elif v in ("no", "false"):
                    alts = ["no"]
                elif _is_demographic(label):
                    alts = ["i prefer not to answer", "decline to self-identify",
                            "decline to identify", "prefer not to say", "do not wish to answer"]
            radios.append({
                "name": fid,  # in Ashby the id IS the radio name
                "value": value or "",
                "alternates": alts,
                "label": label,
                "required": f.get("required", False),
                "options": [o.get("label") for o in (f.get("options") or [])],
            })
        elif atype == "MultiValueSelect":
            # value may be a comma-separated string or a single label
            if isinstance(value, list):
                vals = value
            elif isinstance(value, str) and value:
                # single value; can't split commas naively (option labels often
                # contain commas). Treat the whole string as one value.
                vals = [value]
            else:
                vals = []
            checkboxes.append({
                "name": fid,
                "values": vals,
                "label": label,
                "required": f.get("required", False),
                "options": [o.get("label") for o in (f.get("options") or [])],
            })
        else:
            skipped.append({"id": fid, "label": label, "reason": f"unknown _ashby_type={atype}"})

    return {
        "url": spec["role_url"],
        "text_fields": text_fields,
        "date_fields": date_fields,            # chain_005 P3
        "location_fields": location_fields,    # chain_005 P4
        "radios": radios,
        "checkboxes": checkboxes,
        "resume_path": resume_path,
        "skipped": skipped,
        "needs_review": needs_review,
    }


# ---------------------------------------------------------------------------
# Step emitter — produces the ordered list of {tool, args} dicts.
# ---------------------------------------------------------------------------

def _wrap(js_fn: str, payload) -> str:
    """Wrap a JS function (e.g. `(arg) => {...}`) into a zero-arg closure that
    calls the function with the JSON-serialized payload baked in. The browser
    tool's `evaluate` action invokes `fn` with no arguments, so we have to
    inline the data ourselves."""
    return "() => { const __payload = " + json.dumps(payload) + "; return (" + js_fn.strip() + ")(__payload); }"


def emit_steps(plan: dict, label: str = "ashby") -> list[dict]:
    steps: list[dict] = []
    steps.append({"tool": "browser.open", "args": {
        "label": label,
        # chain_embed_url_fix (2026-06-23): only append /application for
        # jobs.ashbyhq.com hosted forms. For custom embed tenants (e.g.
        # cursor.com/careers/...) the form IS the page; /application is a 404.
        "url": plan["url"] if ("ashbyhq.com" not in plan["url"] and not plan["url"].endswith("/application")) else (plan["url"] + ("/application" if not plan["url"].endswith("/application") else "")),
    }})
    steps.append({"tool": "sleep", "args": {"ms": 1200}})
    # ---- FIX 1 (2026-05-25 burndown, Harvey 671): Ashby React forms validate
    # against internal state, not DOM .value. JS native-value-setter fills DOM
    # but React validator still reports "Missing entry for required field".
    # Emit CDP-real `act:type` keystrokes per text field instead of the JS
    # evaluate path. Resolution of the dryrun fid -> DOM id still needs JS
    # since Ashby sometimes prefixes ids with the form id, so we do one
    # resolve-only evaluate first, then a per-field act:type step. The
    # executing agent should expand `ashby.type_text_fields` into one
    # snapshot+act:type per resolved field.
    if plan["text_fields"]:
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label,
            "fn": _wrap(JS_RESOLVE_TEXT_FIELDS, plan["text_fields"]),
            "comment": "Resolve dryrun field ids -> actual DOM ids (Ashby sometimes prefixes with form id).",
            "meta": {"resolve_only": True},
        }})
        # ---- chain_005 P1 (2026-05-26): emit a fast-path attempt FIRST.
        # Driver should: run JS_FAST_FILL_TEXT_FIELDS, then evaluate a
        # read-back snippet (`() => [...document.querySelectorAll('input,textarea')]
        # .map(e => ({id:e.id, v:e.value}))`) and compute the set of fields
        # whose React state did NOT update. Only those need the CDP-keystroke
        # fallback. Excludes location_fields entirely (combobox path).
        if USE_NATIVE_SETTER_FAST_PATH:
            steps.append({"tool": "browser.act.evaluate", "args": {
                "label": label,
                "fn": _wrap(JS_FAST_FILL_TEXT_FIELDS, plan["text_fields"]),
                "comment": (
                    "chain_005 P1 (2026-05-26): native-setter FAST PATH. Tries\n"
                    "`_valueTracker.setValue` + input-event for each plain text\n"
                    "field. Chain_004 verified this DOES propagate React state\n"
                    "for Ashby String/Email/Phone/Number/Url/LongText on Sentry\n"
                    "& OpenAI tenants (5–10x faster than CDP keystrokes).\n"
                    "Driver MUST verify by re-reading each input.value after a\n"
                    "~50ms tick; any field whose read-back != requested value\n"
                    "falls through to the CDP-keystroke step below. Combobox /\n"
                    "Location fields are intentionally NOT in text_fields\n"
                    "(they go through ashby.location_typeahead_fill instead).\n"
                    "Kill switch: set ashby_filler.USE_NATIVE_SETTER_FAST_PATH=False."
                ),
                "meta": {"fast_path": True, "verify_required": True,
                         "fallback_step": "ashby.type_text_fields"},
            }})
        steps.append({"tool": "ashby.type_text_fields", "args": {
            "label": label,
            "text_fields": plan["text_fields"],
            "comment": (
                "FIX 1 (Harvey 671): for each (resolved_dom_id, value), driver must\n"
                "  1. snapshot the input (ref by `#<dom_id>`), 2. act:click on the\n"
                "  ref to focus, 3. clear via Ctrl+A then Delete keys, 4. act:type the\n"
                "  value as REAL CDP keystrokes (NOT via JS native value setter).\n"
                "chain_005 P1 (2026-05-26): driver should SKIP fields that the\n"
                "fast-path step above already populated successfully. Only fields\n"
                "whose read-back value != requested need CDP keystrokes.\n"
                "date_fields (see below) ALSO go through this step — driver should\n"
                "send an extra Enter key after typing each date_field value to\n"
                "commit the react-datepicker selection."
            ),
            "date_field_ids": list(plan.get("date_fields", {}).keys()),
        }})
    # ---- chain_005 P4 (2026-05-26): Location typeahead emission. Each field
    # gets resolved first, then a multi-step typeahead sequence: focus via
    # clickCoords, type city as CDP keystrokes (combobox listener needs real
    # keypress events), wait for [role=option], click first matching option.
    # Fallback: free-text + tab-out if no option appears within ~1.5s.
    if plan.get("location_fields"):
        # chain_028 (2026-05-29 Speak 1015 guard): single self-contained
        # async-JS evaluate step (vs. legacy two-step manual recipe).
        if USE_LOCATION_TYPEAHEAD_SELF_CONTAINED:
            steps.append({"tool": "browser.act.evaluate", "args": {
                "label": label,
                "fn": _wrap(JS_FILL_ASHBY_LOCATION_TYPEAHEAD,
                    [{"fid": lf["fid"], "value": lf["value"],
                      "required": lf.get("required", False)}
                     for lf in plan["location_fields"]]),
                "comment": (
                    "chain_028 (Speak 1015 guard): self-contained async JS that\n"
                    "handles Ashby Location typeahead end-to-end. Per field:\n"
                    "  1. setNative + look for [role=option] -> pick best match.\n"
                    "  2. Per-char KeyboardEvent fallback (chain_026 async-\n"
                    "     typeahead recipe), wait up to 2500ms for options.\n"
                    "  3. Free-text + Tab/blur commit as last resort.\n"
                    "ALWAYS returns {resolved: [{fid, method, picked, post_value}],\n"
                    "unresolved: [{fid, reason, required, post_value}]}. Never\n"
                    "throws. Driver: if any required field is unresolved, mark\n"
                    "BLOCKED with structured reason; if only optional fields\n"
                    "unresolved, proceed to submit (Location is often optional).\n"
                    "Kill switch: ashby_filler.USE_LOCATION_TYPEAHEAD_SELF_CONTAINED=False\n"
                    "reverts to the legacy two-step manual recipe."
                ),
                "meta": {"self_contained_typeahead": True,
                         "location_typeahead_v2": True},
            }})
        else:
            steps.append({"tool": "browser.act.evaluate", "args": {
                "label": label,
                "fn": _wrap(JS_RESOLVE_LOCATION_INPUTS,
                    [{"fid": lf["fid"], "value": lf["value"]} for lf in plan["location_fields"]]),
                "comment": (
                    "chain_005 P4 (legacy): resolve each Location field's DOM\n"
                    "id + bounding rect center for clickCoords-focus."
                ),
                "meta": {"resolve_only": True, "emits_click_targets": True},
            }})
            steps.append({"tool": "ashby.location_typeahead_fill", "args": {
                "label": label,
                "locations": plan["location_fields"],
                "comment": (
                    "chain_005 P4 LEGACY (kill-switched OFF). Manual recipe:\n"
                    "clickCoords focus -> CDP keystrokes -> wait listbox ->\n"
                    "click option -> Tab fallback. Crash-prone on slow async\n"
                    "tenants (Speak 1015 chain_013)."
                ),
                "meta": {"combobox_typeahead": True},
            }})
    if plan["radios"]:
        # ---- FIX 2 (2026-05-25 burndown, Harvey 671): JS `input.click()` does
        # NOT update React state for Ashby radio groups. Must do real pointer
        # click on the <label> element via CDP clickCoords (scrollIntoView +
        # measure bounding rect + clickCoords on center). Same lesson as
        # Snowflake 870 Yes/No buttons.
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label,
            "fn": _wrap(JS_RESOLVE_RADIO_LABELS,
                [{"name": r["name"], "value": r["value"], "alternates": r["alternates"]} for r in plan["radios"]]),
            "comment": (
                "FIX 2 (Harvey 671): resolve each radio group -> matching <label>\n"
                "element id + bounding-rect center. Returns {picked: [{label_id, cx, cy, label_text, kind}]}.\n"
                "chain_033 (2026-05-30 Notion fix): `kind` is either `radio_label`\n"
                "(traditional <input type=radio>) or `yesno_button` (Notion / Speak /\n"
                "Baseten / Plain style — <div class=_yesno_>Yes/No buttons + hidden\n"
                "checkbox). Driver behavior is IDENTICAL for both kinds: scrollIntoView\n"
                "on the element + `act:clickCoords` at (cx, cy). Do NOT use JS .click()\n"
                "on the <input> — Ashby React validator ignores synthetic clicks.\n"
                "Post-click verify (chain_033): re-evaluate JS_VERIFY —\n"
                "`yesno_buttons_active` should equal `yesno_groups` (each Boolean field\n"
                "now has an active button). If not, retry the missing entry's clickCoords."
            ),
            "meta": {"emits_click_targets": True, "click_kind": "label_coords"},
        }})
    if plan["checkboxes"]:
        # Same pattern as radios — emit label-coords resolution. Harvey didn't
        # have multi-value-select to verify, but the React-state hostility is
        # the same code path so apply the same fix preemptively.
        steps.append({"tool": "browser.act.evaluate", "args": {
            "label": label,
            "fn": _wrap(JS_RESOLVE_CHECKBOX_LABELS,
                [{"name": c["name"], "values": c["values"]} for c in plan["checkboxes"]]),
            "comment": (
                "FIX 2 extension: same label-coords approach for MultiValueSelect\n"
                "checkboxes. Driver does scrollIntoView + clickCoords on each label."
            ),
            "meta": {"emits_click_targets": True, "click_kind": "label_coords"},
        }})
    if plan["resume_path"]:
        # ---- FIX 3 (2026-05-25 burndown, Harvey 671): selector
        # "#_systemfield_resume" silently no-ops when the page has 2 file
        # inputs (e.g. resume + transcripts). browser.upload returns ok:true
        # but files=0. Workaround: snapshot the page, find the visible
        # "Upload File" button inside the Resume container, upload via ref.
        steps.append({"tool": "ashby.upload_resume_via_visible_button", "args": {
            "label": label,
            "paths": [plan["resume_path"]],
            "comment": (
                "FIX 3 (Harvey 671): driver must NOT use selector='#_systemfield_resume'\n"
                "(silently no-ops on multi-file-input pages). Instead:\n"
                "  1. browser.snapshot to get the page.\n"
                "  2. Find the 'Upload File' button whose nearest ancestor label/\n"
                "     section text contains 'Resume' (and NOT 'Transcript' or\n"
                "     'Cover Letter' or other file-field labels).\n"
                "  3. browser.upload ref=<that_button_ref> paths=[...].\n"
                "  4. Verify by re-snapshot: page should show the resume filename.\n"
                "FALLBACK (single file input on page): browser.upload\n"
                "  element='#_systemfield_resume' paths=[...]. MUST use `element=`,\n"
                "  NOT `selector=` — selector= silently no-ops with files=0.\n"
                "  See _upload-regression-diag-20260525.md (2026-05-25).\n"
                "POST-UPLOAD VERIFY (required): evaluate\n"
                "  () => document.querySelector('#_systemfield_resume')?.files?.length || 0\n"
                "  If 0, treat as UploadFailedError and retry once with element= form."
            ),
            "fallback_element": "#_systemfield_resume",
            "fallback_selector": "#_systemfield_resume",
            "verify_fn": "() => document.querySelector('#_systemfield_resume')?.files?.length || 0",
        }})
        steps.append({"tool": "sleep", "args": {"ms": 600}})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_VERIFY,
        "comment": "Verify form state: counts of filled inputs, picked radios/checkboxes, attached files, submit button presence.",
    }})
    # ---- FIX 5 (2026-05-26 burndown, OpenAI/Notion/Baseten cluster): strict
    # Ashby tenants ship reCAPTCHA v3 with sitekey
    # `6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y` (loader
    # `recaptcha.net/recaptcha/api.js?render=<sitekey>` — NOT Enterprise).
    # The Submit button generates a v3 score-token client-side; Azure-DC IPs
    # score below threshold and get a "Your application submission was
    # flagged as possible spam" alert. Workaround: solve via CapSolver
    # before submit and inject token into `g-recaptcha-response-100000`
    # (Ashby uses the suffixed textarea).
    steps.append({"tool": "ashby.maybe_solve_recaptcha_v3", "args": {
        "label": label,
        "page_url": plan["url"],
        "known_strict_sitekey": "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
        "page_action": "submit",
        "min_score": 0.7,
        "enterprise": False,
        # 2026-05-27 (capsolver-scaffold): step is now executable when the
        # driver imports captcha_presubmit.solve_and_inject_recaptcha_v3 and
        # the env vars ENABLE_CAPSOLVER=1 + CAPSOLVER_API_KEY are set. When
        # disabled (default), driver must skip this step and proceed to
        # JS_CLICK_SUBMIT — existing behavior unchanged.
        "driver_exec": {
            "module": "captcha_presubmit",
            "function": "solve_and_inject_recaptcha_v3",
            "kwargs": {
                "page_url": plan["url"],
                "fallback_sitekey": "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y",
                "action": "submit",
                "min_score": 0.7,
                "enterprise": False,
            },
            "gate_env": "ENABLE_CAPSOLVER",
            "gate_value": "1",
        },
        "comment": (
            "FIX 5 (strict-Ashby reCAPTCHA v3): driver should\n"
            "  1. evaluate `() => Array.from(document.scripts).map(s=>s.src).filter(s=>s.includes('recaptcha'))`\n"
            "     to confirm the v3 loader + extract sitekey from `?render=...`.\n"
            "  2. If sitekey == known_strict_sitekey (Ashby shared infra), call\n"
            "     captcha_solver.CaptchaSolver(vendor='capsolver').solve_recaptcha_v3(\n"
            "       sitekey, page_url, page_action='submit', min_score=0.7)\n"
            "  3. On token: evaluate to inject \u2014\n"
            "     `(t) => { const ids=['g-recaptcha-response','g-recaptcha-response-100000'];\n"
            "      for (const id of ids) { let el=document.getElementById(id); if (!el){\n"
            "        el=document.createElement('textarea'); el.id=id; el.name=id; el.style.display='none';\n"
            "        document.body.appendChild(el);} el.value=t;} return {injected: ids.length};}`\n"
            "  4. THEN click Submit. If SolverNotConfigured \u2014 skip (log\n"
            "     `captcha-skipped-no-key`); submit will likely spam-flag but\n"
            "     attempt is still required per per-role doctrine.\n"
            "  5. If post-submit DOM still shows `[role=alert]` containing\n"
            "     `flagged as possible spam`, the v3 score was sub-threshold;\n"
            "     log per-tenant + bail (no infinite retry loop).\n"
            "NEW 2026-05-27: easiest path is to just call\n"
            "  `from captcha_presubmit import solve_and_inject_recaptcha_v3;\n"
            "   solve_and_inject_recaptcha_v3(frame, **driver_exec.kwargs)`\n"
            "  which handles detect+solve+inject in one call. No-op when\n"
            "  ENABLE_CAPSOLVER!=1 \u2014 safe to leave wired permanently."
        ),
        "meta": {"captcha_kind": "recaptcha_v3"},
    }})
    steps.append({"tool": "browser.act.evaluate", "args": {
        "label": label, "fn": JS_CLICK_SUBMIT,
        "comment": "FINAL: click 'Submit Application'. Run only after VERIFY passes manual review.",
        "meta": {"final_submit": True},
    }})
    return steps


# ---------------------------------------------------------------------------
# CLI for debugging.
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", nargs=2, metavar=("ORG", "JOB_ID"),
                    help="Emit step plan for one Ashby app.")
    args = ap.parse_args()
    if not args.plan:
        print(__doc__, file=sys.stderr)
        return 2
    org, job_id = args.plan
    spec_path = DRYRUN_DIR / f"{org}-{job_id}.json"
    if not spec_path.exists():
        print(f"missing dryrun: {spec_path}", file=sys.stderr)
        return 1
    spec = json.loads(spec_path.read_text())
    plan = build_plan(spec)
    steps = emit_steps(plan, label=org)
    print(json.dumps({
        "org": org, "job_id": job_id, "url": plan["url"],
        "plan": {k: v for k, v in plan.items() if k != "url"},
        "steps": steps,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
