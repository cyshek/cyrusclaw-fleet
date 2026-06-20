#!/usr/bin/env python3
"""
greenhouse_iframe_runner.py — Playwright runner for Greenhouse forms that are
embedded as cross-origin iframes in company careers pages.

Why this exists:
    As of 2026-05-23 the direct `job-boards.greenhouse.io/embed/job_app?for=X&token=Y`
    URL silently fails reCAPTCHA Enterprise on Azure datacenter IPs (silent
    blocked-submit, button disabled forever). Loading the form via the company's
    careers-page wrapper URL (e.g. databricks.com/company/careers/...?gh_jid=Y)
    surfaces an iframe src that includes `validityToken=...` — and that warmed
    request passes the recaptcha gate.

    Validated 2026-05-24: Databricks 8243219002 wrapper-URL load resulted in real
    form-validation errors instead of `.grecaptcha-error`, confirming captcha
    passed.

How it works:
    1. Navigate top-level page to wrapper_url (the company careers page).
    2. Wait for #grnhse_iframe (Greenhouse iframe with validityToken).
    3. Locate the iframe Frame object.
    4. Replay the steps emitted by greenhouse_filler.emit_steps inside the
       iframe via frame.evaluate / file_chooser.
    5. Click Submit (JS_SUBMIT). Watch for `.grecaptcha-error` (real captcha
       failure) vs. field validation errors vs. confirmation page.

Usage:
    python greenhouse_iframe_runner.py --slug <packet-slug> [--dry-run]
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# import the filler (same dir)
sys.path.insert(0, str(Path(__file__).resolve().parent))
gf = importlib.import_module("greenhouse_filler")

ROOT = Path(__file__).resolve().parent.parent
SUBMITTED = ROOT / "applications" / "submitted"
DRYRUN = ROOT / "applications" / "dryrun"


def log(msg: str) -> None:
    print(f"[gh-iframe] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Greenhouse native S3 resume uploader (sidecar 2026-05-26, chain_009)
# ---------------------------------------------------------------------------
# Kill switch for the S3-uploader + submit-JSON-injection path. When True
# (default), after standard resume binding attempts, we ALSO:
#   1. GET ${JBEN_URL}/uncacheable_attributes/presigned_fields?fields[]=resume
#   2. POST the resume to S3 with the presigned envelope (returns 201)
#   3. Patch window.fetch so the submit JSON gets `resume_url` +
#      `resume_url_filename` injected into `job_application.*` at send time.
# This is what unblocks Lyft/careerpuck (Lyft 1343 / 716, Hume 1379) which
# have NO Filestack despite chain_007's hypothesis: GH itself does the S3
# upload via React, and the existing DataTransfer binding never triggers it.
# See workspace/FILESTACK-DESIGN.md for full reverse-engineering notes.
USE_GH_S3_UPLOADER = True

# chain_010 (2026-05-26): React-onChange trigger. After chain_009 proved the
# S3 upload works but React's client-side validator still blocks submit
# because application.resume state stays null, we additionally fire the
# React-native files setter + a bubbling change event on #resume so
# React's UploadField.onChange handler runs and populates state. See
# OPTION-A-DESIGN.md. Only runs when USE_GH_S3_UPLOADER is also True.
USE_REACT_RESUME_TRIGGER = True


def _debug_filestack_log(report: dict, debug: bool, label: str, payload) -> None:
    """Helper for --debug-filestack: dump uploader-related events to stderr
    in addition to the normal report['gh_s3_upload'] capture."""
    if debug:
        try:
            print(f"[gh-s3] {label}: {json.dumps(payload, default=str)[:1000]}", file=sys.stderr, flush=True)
        except Exception:
            print(f"[gh-s3] {label}: <unserializable>", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Honest-verify helper (chain_006 sidecar, 2026-05-26)
# ---------------------------------------------------------------------------
# Background: chain_005 (Lyft 1343) the runner reported `step:submit, result:{ok:True}`
# AND `verify_resume.strict_bound=True` DURING the run. Post-submit page state showed
# 8 unfilled required fields including Resume. Operator (Cyrus + me) was misled into
# treating the role as "submit_ok" rather than BLOCKED. Fix: any post-submit
# fieldErrs list non-empty without `conf` = honest BLOCKED state. Downgrade the
# submit-step result and set a distinct outcome so downstream graders don't
# mistake field-error responses for successful submits.
#
# Pure function (no Playwright deps) so it's unit-testable without a browser.
def honest_verify_post_submit(report: dict, last: dict | None) -> dict:
    """Downgrade misleading submit:ok signals when post_submit shows fieldErrs.

    Mutates and returns `report`. Idempotent — safe to call multiple times.

    Rules:
    - If `last['conf']` truthy AND `fieldErrs` empty → no change. (Real submit.)
    - If `fieldErrs` non-empty:
        * Walk `report['events']`, find any `step == 'submit'` entries, and
          downgrade `result.ok` from True → False; tag
          `result.downgraded_from_clicked=True` and attach `field_errors`.
        * Set `report['outcome'] = 'BLOCKED_FIELD_ERRORS'` unless already a
          terminal blocker (CAPTCHA_GATE, VERIFICATION_FAIL — those are more
          specific and stay).
        * Set `report['honest_verify'] = {downgraded: True, field_errors:[...],
          reason: 'post_submit.fieldErrs non-empty'}`.
    - If `fieldErrs` empty but `conf` falsy and outcome would be TIMEOUT, leave
      outcome alone (genuine timeout case).
    """
    if not isinstance(report, dict):
        return report
    last = last or {}
    field_errs = list(last.get("fieldErrs") or [])
    conf = bool(last.get("conf"))

    # Defense in depth: even if conf=True, having required-field errors is
    # suspicious. We DO trust conf when fieldErrs empty (the normal case).
    if not field_errs:
        return report

    # Don't override terminal blockers more specific than this.
    terminal_blockers = {"CAPTCHA_GATE", "VERIFICATION_FAIL"}
    if report.get("outcome") not in terminal_blockers:
        report["outcome"] = "BLOCKED_FIELD_ERRORS"

    # Downgrade the submit event(s).
    events = report.get("events") or []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("step") != "submit":
            continue
        res = ev.get("result")
        if not isinstance(res, dict):
            continue
        if res.get("ok") is True and not res.get("downgraded_from_clicked"):
            res["ok"] = False
            res["downgraded_from_clicked"] = True
            res["field_errors"] = field_errs
            res["downgrade_reason"] = "post_submit.fieldErrs non-empty"

    report["honest_verify"] = {
        "downgraded": True,
        "field_errors": field_errs,
        "conf_was": conf,
        "reason": "post_submit.fieldErrs non-empty",
    }
    return report


def _pw_pick_dropdowns(frame, specs, log) -> list:
    """chain_044: Playwright real-click+type+Enter fallback for remix GH
    react-select v5 dropdowns whose menus don't open via synthetic MouseEvents.
    Mirrors the country-picker recipe (input.click -> type label -> Enter).
    Each spec = {id, label}. Returns [{id, want, got}]."""
    out = []
    for spec in specs:
        fid = spec.get("id"); want = spec.get("label")
        rec = {"id": fid, "want": want, "got": None}
        try:
            inp = frame.locator(f'#{fid}').first
            if inp.count() == 0:
                # react-select hidden combobox lives at input[id=<fid>] inside .select__control
                inp = frame.locator(f'input#{fid}').first
            if inp.count() == 0:
                rec["err"] = "no input"; out.append(rec); continue
            try:
                inp.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            inp.click()
            time.sleep(0.2)
            try:
                inp.fill("")
            except Exception:
                pass
            inp.type(str(want), delay=35)
            time.sleep(0.5)
            inp.press("Enter")
            time.sleep(0.3)
            chk = frame.evaluate(
                """(fid) => {
                    const inp = document.getElementById(fid);
                    const ctrl = inp ? inp.closest('.select__control, [class*=select__control]') : null;
                    const sv = ctrl ? ctrl.querySelector('.select__single-value, [class*=select__single-value]') : null;
                    return sv ? sv.textContent.trim() : null;
                }""", fid)
            rec["got"] = chk
            if not chk:
                # fallback: click matching option in open menu
                fb = frame.evaluate(
                    """(want) => {
                        const opts = [...document.querySelectorAll('.select__menu .select__option, [role=option]')];
                        const wl = String(want).toLowerCase();
                        let m = opts.find(o => o.textContent.trim().toLowerCase() === wl)
                              || opts.find(o => o.textContent.trim().toLowerCase().startsWith(wl))
                              || opts.find(o => o.textContent.toLowerCase().includes(wl));
                        if (m) { m.click(); return m.textContent.trim(); }
                        return null;
                    }""", want)
                if fb:
                    rec["got"] = fb
        except Exception as e:
            rec["err"] = f"{type(e).__name__}: {e}"
        out.append(rec)
    return out


def find_packet(slug: str) -> Path:
    p = SUBMITTED / slug
    if not p.exists():
        raise SystemExit(f"packet not found: {p}")
    return p


def load_plan(packet: Path) -> dict:
    meta = json.loads((packet / "meta.json").read_text())
    org = meta["gh_org"]
    jid = meta["gh_jid"]
    spec_path = DRYRUN / f"{org}-{jid}.json"
    spec = json.loads(spec_path.read_text())
    plan = gf.build_plan(spec)
    pdfs = sorted(packet.glob("*v2.pdf")) or sorted(packet.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDF in {packet}")
    plan["resume_path"] = str(pdfs[0])
    # Merge cover answers if present
    cover = packet / "cover_answers.md"
    if cover.exists():
        try:
            from inline_submit import merge_cover_answers_into_plan  # type: ignore
            plan = merge_cover_answers_into_plan(plan, spec, cover)
        except Exception as e:
            log(f"cover merge failed (continuing): {e}")
    return {"plan": plan, "meta": meta, "spec": spec}


def get_iframe_frame(page, timeout_s: int = 40):
    # Wait for the iframe element to appear in DOM (parent page CSS selector).
    # NOTE: when wrappers are SPA shells (careerpuck), the <iframe> may exist
    # with an empty/late-set src; we need a second wait that watches the Frame
    # objects in page.frames for a job-boards.greenhouse.io URL.
    try:
        page.wait_for_selector(
            'iframe#grnhse_iframe, iframe[src*="job-boards.greenhouse.io"]',
            timeout=timeout_s * 1000,
        )
    except Exception:
        pass  # not fatal; some wrappers don't use #grnhse_iframe id
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for f in page.frames:
            if f.url and "job-boards.greenhouse.io" in f.url:
                return f
        time.sleep(0.5)
    urls = [f.url for f in page.frames]
    raise RuntimeError(f"greenhouse iframe Frame not found. frame urls={urls}")


def run(slug: str, *, dry_run: bool = False, headless: bool = True, debug_filestack: bool = False) -> dict:
    pkt = find_packet(slug)
    bundle = load_plan(pkt)
    plan = bundle["plan"]
    meta = bundle["meta"]
    wrapper = meta.get("wrapper_url") or meta.get("apply_url")
    if not wrapper:
        raise SystemExit("no wrapper_url in meta.json")

    report = {"slug": slug, "wrapper_url": wrapper, "dry_run": dry_run, "events": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        log(f"goto wrapper: {wrapper}")
        page.goto(wrapper, wait_until="load", timeout=60_000)
        report["final_url"] = page.url

        # SPA wrappers (e.g. app.careerpuck.com) lazy-load the Greenhouse iframe
        # via IntersectionObserver — without a scroll, the iframe is never
        # injected and we fall back to the reCAPTCHA-gated direct embed URL.
        # Mouse-move + scroll + small wait reliably triggers the load.
        # (chain_007 2026-05-26: validated on app.careerpuck.com/lyft.)
        try:
            page.mouse.move(400, 400)
            page.mouse.move(640, 500)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(0.5)
        except Exception as _e:
            log(f"scroll-warmup non-fatal err: {_e}")

        frame = None
        try:
            frame = get_iframe_frame(page)
        except Exception as e:
            log(f"wrapper iframe load failed ({e}); falling back to direct embed URL")
            report["wrapper_iframe_error"] = str(e)
            # Fallback: navigate page directly to the embed URL and use the
            # top-level page as the form context. Validity-token gating may
            # still permit submit in this path; the runner will surface any
            # token-related error during the submit step.
            embed_url = meta.get("embed_url") or plan.get("url")
            if not embed_url:
                report["error"] = f"iframe wait failed and no embed_url to fall back to: {e}"
                browser.close()
                return report
            log(f"goto embed direct: {embed_url}")
            page.goto(embed_url, wait_until="load", timeout=60_000)
            import time as _t; _t.sleep(2.0)
            report["final_url"] = page.url
            frame = page.main_frame
            report["direct_embed_fallback"] = True
        log(f"iframe frame URL: {frame.url[:140]}")
        report["iframe_url"] = frame.url
        report["has_validity_token"] = "validityToken=" in (frame.url or "")

        # Wait for the form to render
        try:
            frame.wait_for_selector("form", timeout=20_000)
        except PWTimeout:
            report["error"] = "form not rendered in iframe"
            browser.close()
            return report

        # --- Replay steps inside iframe ---
        def evalfn(js: str, arg=None):
            if arg is None:
                return frame.evaluate(js)
            return frame.evaluate(js, arg)

        # --- chain_009: install fetch patch BEFORE any submit can fire ---
        # The patch wraps window.fetch and, if window.__gh_resume_inject is set
        # later (after our S3 upload completes), mutates the JSON submit body to
        # include resume_url + resume_url_filename. Idempotent + harmless when
        # USE_GH_S3_UPLOADER=False (we just never plant the inject payload).
        report["gh_s3_upload"] = {"enabled": USE_GH_S3_UPLOADER, "fetch_patched": False}
        if USE_GH_S3_UPLOADER:
            try:
                fp = evalfn(gf.JS_INSTALL_FETCH_PATCH)
                report["gh_s3_upload"]["fetch_patched"] = bool(fp and fp.get("ok"))
                report["gh_s3_upload"]["fetch_patch_result"] = fp
                _debug_filestack_log(report, debug_filestack, "fetch_patch_install", fp)
            except Exception as e:
                report["gh_s3_upload"]["fetch_patch_err"] = f"{type(e).__name__}: {e}"
                log(f"gh-s3 fetch patch install err: {e}")

        # JS_OPEN_APPLY — click the visible Apply button (some pages need this)
        try:
            r = evalfn(gf.JS_OPEN_APPLY)
            log(f"JS_OPEN_APPLY: {r}")
        except Exception as e:
            log(f"JS_OPEN_APPLY err: {e}")
        time.sleep(0.6)

        # Text fields
        if plan.get("text_fields"):
            r = evalfn(gf.JS_FILL_TEXT_FIELDS, plan["text_fields"])
            report["events"].append({"step": "text_fields", "result": r})
            log(f"text_fields filled: {sum(1 for v in r.values() if v.get('ok'))} / {len(r)}")

        # Dropdowns
        if plan.get("dropdowns"):
            r = evalfn(gf.JS_PICK_DROPDOWNS, plan["dropdowns"])
            report["events"].append({"step": "dropdowns", "result": r})
            picked_ct = sum(1 for v in r if v.get('got'))
            log(f"dropdowns picked: {picked_ct} / {len(r)}")
            # chain_044: remix GH boards (job-boards.greenhouse.io/<org>) ship
            # react-select v5 whose menus do NOT open via synthetic MouseEvents.
            # Fall back to Playwright real-click+type+Enter (same recipe the
            # country picker uses, which DOES work on these boards). Only for
            # dropdowns left unpicked by the JS pass.
            unpicked = [spec for spec, res in zip(plan["dropdowns"], r) if not res.get('got')]
            if unpicked:
                pw_res = _pw_pick_dropdowns(frame, unpicked, log)
                report["events"].append({"step": "dropdowns_pw_fallback", "result": pw_res})
                log(f"dropdowns PW fallback: {sum(1 for x in pw_res if x.get('got'))} / {len(unpicked)}")

        # Country typeahead
        if plan.get("country_dropdowns"):
            r = evalfn(gf.JS_PICK_DROPDOWN_TYPEAHEAD, plan["country_dropdowns"])
            report["events"].append({"step": "country_dropdowns", "result": r})

        # Stripe-specific: candidate-location typeahead
        # The greenhouse 'location' text_field id doesn't exist on Stripe forms;
        # they use a #candidate-location react-select typeahead instead. Inline
        # the stripe_filler.js logic for that one widget.
        try:
            STRIPE_CAND_LOC_JS = r"""
            async ({ query }) => {
              const sleep = ms => new Promise(r => setTimeout(r, ms));
              const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window, button: 0, clientX: x||0, clientY: y||0}));
              const setNative = (el, val) => {
                const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, val);
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
              };
              const cl = document.getElementById('candidate-location');
              if (!cl) return { ok: false, err: 'no candidate-location field' };
              const clCtrl = cl.closest('.select__control');
              if (clCtrl.querySelector('.select__single-value')) {
                return { ok: true, already: clCtrl.querySelector('.select__single-value').textContent };
              }
              const r = clCtrl.getBoundingClientRect();
              fire(clCtrl, 'mousedown', r.left+5, r.top+5);
              fire(clCtrl, 'mouseup', r.left+5, r.top+5);
              fire(clCtrl, 'click', r.left+5, r.top+5);
              await sleep(300);
              setNative(cl, query);
              await sleep(1100);
              const opts = [...document.querySelectorAll("[id^='react-select-candidate-location-option']")];
              if (!opts.length) return { ok: false, err: 'no options', query };
              const tr = opts[0].getBoundingClientRect();
              fire(opts[0], 'mousedown', tr.left+5, tr.top+5);
              fire(opts[0], 'mouseup', tr.left+5, tr.top+5);
              fire(opts[0], 'click', tr.left+5, tr.top+5);
              await sleep(300);
              return { ok: true, picked: clCtrl.querySelector('.select__single-value')?.textContent };
            }
            """
            r = evalfn(STRIPE_CAND_LOC_JS, {"query": "Kirkland"})
            report["events"].append({"step": "candidate_location", "result": r})
            log(f"candidate_location: {r}")
        except Exception as e:
            log(f"candidate_location err: {e}")
            report["events"].append({"step": "candidate_location", "error": str(e)})

        # Multi-checkboxes
        if plan.get("multi_checkboxes"):
            r = evalfn(gf.JS_TICK_MULTI_CHECKBOXES, plan["multi_checkboxes"])
            report["events"].append({"step": "multi_checkboxes", "result": r})
            log(f"multi_checkboxes: {r}")
            # 2026-05-25 (SpaceX 872): fallback for fields the API typed as
            # multi_value_multi_select but the tenant actually rendered as a
            # react-select-multi (no <fieldset>). Re-attempt those via the
            # react-select interface using the same values list.
            fallback_specs = [s for s, res in zip(plan["multi_checkboxes"], r) if isinstance(res, dict) and res.get("err") == "no fieldset"]
            if fallback_specs:
                JS_TICK_REACT_SELECT_MULTI = r"""
                async (specs) => {
                  const sleep = ms => new Promise(r => setTimeout(r, ms));
                  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));
                  const out = [];
                  for (const spec of specs || []) {
                    const idStem = String(spec.id || '').replace(/\[\]$/, '');
                    const inp = document.getElementById(spec.id) || document.querySelector(`input[id^="${idStem}"]`);
                    if (!inp) { out.push({id: spec.id, err: 'no input'}); continue; }
                    const ctrl = inp.closest('.select__control');
                    if (!ctrl) { out.push({id: spec.id, err: 'no select__control'}); continue; }
                    const picked = [];
                    const missing = [];
                    let pickedAny = false;
                    for (const want of spec.values || []) {
                      if (pickedAny) continue;
                      const cr = ctrl.getBoundingClientRect();
                      fire(ctrl, 'mousedown', cr.left+5, cr.top+5);
                      fire(ctrl, 'mouseup',   cr.left+5, cr.top+5);
                      fire(ctrl, 'click',     cr.left+5, cr.top+5);
                      await sleep(280);
                      const opts = [...document.querySelectorAll('[id*="-option-"]')];
                      const wantLc = String(want).toLowerCase();
                      let target = opts.find(o => (o.textContent||'').trim().toLowerCase() === wantLc);
                      if (!target) target = opts.find(o => (o.textContent||'').trim().toLowerCase().includes(wantLc));
                      if (!target) { missing.push(want); fire(document.body,'mousedown',0,0); continue; }
                      const tr = target.getBoundingClientRect();
                      fire(target, 'mousedown', tr.left+5, tr.top+5);
                      fire(target, 'mouseup',   tr.left+5, tr.top+5);
                      fire(target, 'click',     tr.left+5, tr.top+5);
                      await sleep(150);
                      picked.push(want);
                      pickedAny = true;
                    }
                    out.push({id: spec.id, picked, missing});
                  }
                  return out;
                }
                """
                try:
                    rf = evalfn(JS_TICK_REACT_SELECT_MULTI, fallback_specs)
                    report["events"].append({"step": "multi_checkboxes_react_fallback", "result": rf})
                    log(f"multi_checkboxes_react_fallback: {rf}")
                except Exception as e:
                    log(f"multi_checkboxes_react_fallback err: {e}")
                    report["events"].append({"step": "multi_checkboxes_react_fallback", "error": str(e)})

        # Education subsection (School/Degree/Discipline) — 2026-05-25 patch.
        # Greenhouse may render an Education panel dynamically that's NOT in
        # the dryrun field list. Runtime sweep; no-op if section absent.
        if plan.get("_education"):
            try:
                r = evalfn(gf.JS_FILL_EDUCATION_PANEL, plan["_education"])
                report["events"].append({"step": "education_panel", "result": r})
                log(f"education_panel: {r}")
            except Exception as e:
                log(f"education_panel err (continuing): {e}")
                report["events"].append({"step": "education_panel", "error": str(e)})

        # Phone ITI
        if plan.get("phone_iti"):
            r = evalfn(gf.JS_FILL_PHONE_ITI, plan["phone_iti"])
            report["events"].append({"step": "phone_iti", "result": r})

        # Declined demo multi (race/ethnic)
        if plan.get("declined_demo_multi"):
            r = evalfn(gf.JS_DECLINE_DEMO_MULTI, plan["declined_demo_multi"])
            report["events"].append({"step": "declined_demo_multi", "result": r})

        # Decline demographics single-select pass
        decline_arg = {"patterns": {
            "label": gf.DEMO_LABEL_RE.pattern,
            "declines": gf.DECLINE_LABELS,
        }}
        try:
            r = evalfn(gf.JS_DECLINE_DEMOGRAPHICS, decline_arg)
            report["events"].append({"step": "decline_demographics", "result": r})
        except Exception as e:
            log(f"JS_DECLINE_DEMOGRAPHICS err (continuing): {e}")
            report["events"].append({"step": "decline_demographics", "error": str(e)})

        # chain_044: PW real-click fallback for remix-board demographic
        # react-selects (synthetic events don't open their menus). Discover
        # unfilled demographic controls, then real-click+pick a decline option.
        try:
            demo_unfilled = frame.evaluate(
                """(re) => {
                    const labelRe = new RegExp(re, 'i');
                    const out = [];
                    for (const ctrl of document.querySelectorAll('.select__control')) {
                        if (ctrl.querySelector('.select__single-value')) continue;
                        const inp = ctrl.querySelector('input[role=combobox], input[id]');
                        if (!inp || !inp.id) continue;
                        let lbl = '', n = ctrl;
                        for (let i=0;i<6&&n;i++){ n=n.parentElement; if(!n)break;
                            const le=n.querySelector?n.querySelector('label,legend'):null;
                            if(le){lbl=le.textContent||'';break;} }
                        if (labelRe.test(lbl)) out.push({id: inp.id, label: lbl.slice(0,80)});
                    }
                    return out;
                }""", gf.DEMO_LABEL_RE.pattern)
            for d in demo_unfilled or []:
                try:
                    inp = frame.locator(f'#{d["id"]}').first
                    if inp.count() == 0:
                        continue
                    inp.scroll_into_view_if_needed(timeout=2000)
                    inp.click()
                    time.sleep(0.3)
                    pick = frame.evaluate(
                        """() => {
                            const opts=[...document.querySelectorAll('.select__menu .select__option,[role=option]')];
                            let m=opts.find(o=>/decline|prefer not|don'?t wish|do not wish|not to identify|not to disclose|i don'?t/i.test(o.textContent));
                            if(m){m.click();return m.textContent.trim();}
                            return null;
                        }""")
                    report["events"].append({"step": "decline_demographics_pw", "id": d["id"], "picked": pick})
                except Exception:
                    pass
        except Exception as e:
            log(f"decline_demographics PW fallback err (continuing): {e}")

        # GDPR
        r = evalfn(gf.JS_TICK_GDPR_CONSENT)
        report["events"].append({"step": "gdpr", "result": r})

        # Iframe-form-chrome Country react-select (NOT in spec; required by v2 GH iframe)
        try:
            # Use Playwright locator to focus then type — react-select needs real keyboard events
            country_inp = frame.locator('input#country').first
            if country_inp.count() > 0:
                try:
                    country_inp.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass
                country_inp.click()
                time.sleep(0.2)
                country_inp.type('United States', delay=40)
                time.sleep(0.6)
                # Press Enter to commit first highlighted option
                country_inp.press('Enter')
                time.sleep(0.3)
                check = frame.evaluate(
                    """() => {
                        const inp = document.querySelector('input#country');
                        const container = inp ? inp.closest('.select__control, [class*=select__control]') : null;
                        const sv = container ? container.querySelector('.select__single-value, [class*=select__single-value]') : null;
                        return {selected: sv ? sv.textContent.trim() : null};
                    }"""
                )
                report["events"].append({"step": "country_select", "result": check})
                log(f"country_select: {check}")
                if not check.get('selected'):
                    # Fallback: click first menu option
                    fb = frame.evaluate(
                        """() => {
                            const opts = [...document.querySelectorAll('[role=option], [id^=react-select-country-option]')];
                            const m = opts.find(o => /^united states/i.test((o.textContent||'').trim())) || opts[0];
                            if (m) { m.click(); return {clicked: m.textContent.trim()}; }
                            return {err: 'no menu opts', count: opts.length};
                        }"""
                    )
                    report["events"].append({"step": "country_select_fb", "result": fb})
                    log(f"country_select_fb: {fb}")
            else:
                report["events"].append({"step": "country_select", "result": {"skip": "no-input"}})
        except Exception as e:
            log(f"country select err (continuing): {e}")
            report["events"].append({"step": "country_select", "error": str(e)})

        # Work-experience repeater block (chain_006 sidecar, 2026-05-26).
        # Lyft and likely other late-2025 GH tenants embed a repeater
        # (company-name-N, title-N, start/end-date-month/year-N, top-level country)
        # that the boards-api spec does NOT expose. Runtime fill from
        # personal-info.json.work_experience. No-op if the block isn't present.
        try:
            import json as _json
            pinfo_path = Path(__file__).resolve().parent.parent / "personal-info.json"
            pinfo = _json.loads(pinfo_path.read_text())
            entries = gf.build_work_experience_payload(pinfo)
            if entries:
                wr = evalfn(gf.JS_FILL_WORK_EXPERIENCE_BLOCK, entries)
                report["events"].append({"step": "work_experience_block", "result": wr})
                log(f"work_experience_block: {wr}")
            else:
                report["events"].append({"step": "work_experience_block", "result": {"skip": "no entries in personal-info"}})
        except Exception as e:
            log(f"work_experience_block err (continuing): {e}")
            report["events"].append({"step": "work_experience_block", "error": str(e)})

        # Needs-review dropdowns are NOT auto-resolved here — caller should
        # already have spec-correct labels. Log them for transparency.
        for ndd in plan.get("needs_review_dropdowns", []) or []:
            try:
                r = evalfn(gf.JS_INSPECT_OPTIONS, {"id": ndd["id"]})
                report["events"].append({"step": "needs_review_inspect", "id": ndd["id"], "result": r})
            except Exception:
                pass

        # Unplanned-required-dropdown filler (chain_011, 2026-05-26).
        # Some GH tenants (Lyft 716) ship required dropdowns that boards-api
        # doesn't expose in the dryrun spec. Strategy: scan via JS_FILL_UNPLANNED_DROPDOWNS
        # to discover (id, label, matched_answer) for unfilled non-demographic
        # dropdowns; then delegate each (id, answer) pair to the proven
        # JS_PICK_DROPDOWNS recipe (same path the planned dropdowns use).
        # Idempotent; demographic labels are skipped unless explicitly patterned.
        try:
            scan = evalfn(gf.JS_FILL_UNPLANNED_DROPDOWNS, {"patterns": gf.DEFAULT_UNPLANNED_DROPDOWN_PATTERNS})
            report["events"].append({"step": "unplanned_dropdowns_scan", "result": scan})
            # Collect candidates where we matched a pattern (even if our inline
            # pick failed). We'll retry these with JS_PICK_DROPDOWNS.
            retry_specs = [
                {"id": x["id"], "label": x["want"]}
                for x in (scan or [])
                if x.get("want") and x.get("id")
            ]
            if retry_specs:
                retry = evalfn(gf.JS_PICK_DROPDOWNS, retry_specs)
                report["events"].append({"step": "unplanned_dropdowns_retry", "result": retry})
                picked = sum(1 for v in (retry or []) if v.get("got"))
                log(f"unplanned_dropdowns_retry: picked={picked} / {len(retry_specs)}")
                # chain_044: PW real-click fallback for remix react-select.
                still = [s for s, res in zip(retry_specs, retry or []) if not (res or {}).get("got")]
                if still:
                    pw = _pw_pick_dropdowns(frame, still, log)
                    report["events"].append({"step": "unplanned_dropdowns_pw", "result": pw})
                    log(f"unplanned_dropdowns PW fallback: {sum(1 for x in pw if x.get('got'))} / {len(still)}")
            else:
                picked = sum(1 for x in (scan or []) if x.get("ok"))
                log(f"unplanned_dropdowns: picked={picked}, total_scanned={len(scan or [])}")
        except Exception as e:
            log(f"unplanned_dropdowns err (continuing): {e}")
            report["events"].append({"step": "unplanned_dropdowns", "error": str(e)})

        # Resume upload — Filestack via #resume input
        #
        # CHANGELOG 2026-05-25 (lyft-8525086002 regression fix):
        # ------------------------------------------------------
        # Symptom on Lyft (and likely other newer GH-Filestack tenants):
        #   set_input_files(#resume) returns ok, JS_CLICK_ATTACH clicks the
        #   parent button, JS_VERIFY_RESUME_ATTACHED says filename_visible=true
        #   BUT #resume.files.length === 0. After Submit, GH backend rejects
        #   with empty Work-Experience block (resume-parser never fired).
        #
        # Root cause hypothesis: Filestack swaps out the native click handler
        #   on the visible Attach button (intercepts before the GH page handler
        #   binds the file). When we call Playwright's set_input_files() on the
        #   visually-hidden #resume input AND THEN click Attach, Filestack runs
        #   its OWN file-picker handler (opens its widget showing the preview)
        #   instead of reading the file we already staged. Result: #resume.files
        #   stays empty even though Filestack's preview chip renders.
        #
        # Asana (which worked yesterday on the same code) uses an older
        #   Filestack config where the Attach-button handler reads #resume.files
        #   first — so the staged file got picked up. Lyft's tenant skips that.
        #
        # Fix strategy — three layered attempts, verify by
        #   #resume.files.length > 0 (strict; filename_visible alone is NOT
        #   enough — it's a UI artifact, not a backend binding):
        #
        #   A) PRIMARY: expect_file_chooser + click Attach. Lets Filestack's
        #      own onclick fire, then we feed the file into the chooser it
        #      opens — same path a real user takes. Works on Filestack-managed
        #      and native widgets alike.
        #   B) FALLBACK: set_input_files on #resume + dispatch synthetic
        #      change/input events on the input AND its parent (some Filestack
        #      adapters poll the parent for child-input mutations).
        #   C) LAST RESORT: JS DataTransfer injection — read the file via
        #      Playwright, base64 it into the frame, build a File object, set
        #      #resume.files via DataTransfer, and dispatch change. This
        #      bypasses Filestack entirely; the GH submit handler reads
        #      formData from #resume.files directly so this is sufficient.
        resume_path = plan.get("resume_path")
        if resume_path:
            try:
                resume_name = Path(resume_path).name

                def _resume_bound() -> bool:
                    """STRICT bind check (tightened 2026-05-25 after Lyft 716):
                    ONLY <file input>.files.length > 0 counts as a real backend bind.
                    The old 'Filestack swap + filename visible' branch was a false
                    positive — Lyft hit it (input detached, cosmetic chip rendered)
                    but Greenhouse backend got NO file → post-submit fieldErrs
                    demanded Company/Title/Start-date (the resume-parse path).
                    A detached input is a SIGNAL to try the next binding layer,
                    not evidence of success.

                    Updated 2026-05-26 (chain worker): when #resume is gone
                    (Filestack detached + replaced with anonymous input), fall
                    back to ANY input[type=file] in the form. Mirror logic to
                    Attempt C's re-query — otherwise an Attempt-C success on the
                    swapped input would still report unbound."""
                    state = evalfn(
                        r"""({ filename }) => {
                            let inp = document.querySelector('#resume');
                            if (!inp) {
                                const all = Array.from(document.querySelectorAll('input[type=file]'));
                                inp = all.find(el => /resume|cv/i.test((el.name||'') + ' ' + (el.id||'') + ' ' + (el.getAttribute('aria-label')||''))) || all[0];
                            }
                            const inputStill = !!inp;
                            const filesInInput = inp ? inp.files.length : 0;
                            const body = (document.body && document.body.innerText) || '';
                            const filenameVisible = !!filename && body.includes(filename);
                            // Strict: only real bind is files.length>0 on the live input.
                            const bound = filesInInput > 0;
                            return { bound, inputStill, filesInInput, filenameVisible };
                        }""",
                        {"filename": resume_name},
                    )
                    return bool(state.get("bound"))

                # --- Attempt 0: DataTransfer on the ORIGINAL #resume BEFORE A fires ---
                # 2026-05-26 chain_009 — Lyft 716 retrospective: on careerpuck/Lyft-style
                # Filestack tenants, Attempt A's file_chooser click triggers Filestack to
                # DETACH #resume entirely AND not render a replacement input. By the time
                # Attempt B/C run, there is no file input in the DOM at all. The fix is
                # to try DataTransfer FIRST against the still-live #resume, then only fall
                # back to A if no #resume existed in the first place. DataTransfer cannot
                # trigger a Filestack picker dialog (no user gesture), so it doesn't cause
                # the swap; if it binds and submit is accepted, we win without A's risk.
                attempt_0 = {"ok": False, "err": None}
                try:
                    import base64, mimetypes
                    with open(resume_path, "rb") as fh:
                        _b64_0 = base64.b64encode(fh.read()).decode("ascii")
                    _mime_0 = mimetypes.guess_type(resume_path)[0] or "application/pdf"
                    inj0 = frame.evaluate(
                        r"""async ({ b64, filename, mime }) => {
                            const inp = document.querySelector('#resume');
                            if (!inp) return { ok: false, err: 'no #resume on first paint' };
                            const bin = atob(b64);
                            const arr = new Uint8Array(bin.length);
                            for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                            const file = new File([arr], filename, { type: mime });
                            const dt = new DataTransfer();
                            dt.items.add(file);
                            inp.files = dt.files;
                            // NOTE 2026-05-26 chain_009 v2: do NOT dispatch change/input.
                            // Filestack's change listener tries to upload via its picker
                            // protocol and FAILS (DataTransfer isn't a real user gesture),
                            // then detaches #resume entirely. By not firing change, we
                            // leave inp.files populated and avoid Filestack's reaction.
                            // GH server reads inp.files at submit-time so binding still wins.
                            return { ok: true, files_after: inp.files.length, name_after: inp.files[0] ? inp.files[0].name : null };
                        }""",
                        {"b64": _b64_0, "filename": resume_name, "mime": _mime_0},
                    )
                    time.sleep(1.5)
                    attempt_0["ok"] = _resume_bound()
                    attempt_0["injected"] = inj0
                except Exception as e:
                    attempt_0["err"] = f"{type(e).__name__}: {e}"
                report["events"].append({"step": "resume_attempt_0_datatransfer_first", "result": attempt_0})
                log(f"resume attempt-0 (DataTransfer-first): {attempt_0}")

                # --- Attempt A: file-chooser via Attach-button click ---
                attempt_a = {"ok": False, "err": None}
                # Only run A if Attempt 0 did NOT bind. A's file_chooser is known to
                # trigger irreversible Filestack swap on Lyft-class tenants.
                if attempt_0["ok"]:
                    attempt_a["ok"] = True
                    attempt_a["err"] = "skipped (attempt-0 already bound)"
                    report["events"].append({"step": "resume_attempt_a_filechooser", "result": attempt_a})
                    log("resume attempt-A: skipped (attempt-0 already bound)")
                else:
                    try:
                        # Locate the Attach button (Filestack's pickup CTA next to #resume).
                        # In the iframe DOM it's the first <button> sibling/cousin of #resume.
                        attach_handle = frame.evaluate_handle(
                            r"""() => {
                                const f = document.querySelector('#resume');
                                if (!f) return null;
                                // Filestack's Attach button is typically in the same wrapper div
                                let scope = f.parentElement;
                                for (let i = 0; i < 3 && scope; i++) {
                                    const btn = scope.querySelector('button');
                                    if (btn) return btn;
                                    scope = scope.parentElement;
                                }
                                return null;
                            }"""
                        )
                        attach_el = attach_handle.as_element()
                        if attach_el:
                            with page.expect_file_chooser(timeout=5000) as fc_info:
                                attach_el.click()
                            fc = fc_info.value
                            fc.set_files(resume_path)
                            log(f"attempt-A: file_chooser fed {resume_name}")
                            time.sleep(2.0)
                            attempt_a["ok"] = _resume_bound()
                        else:
                            attempt_a["err"] = "no attach button found"
                    except PWTimeout:
                        attempt_a["err"] = "file_chooser never opened (Filestack consumed click)"
                    except Exception as e:
                        attempt_a["err"] = f"{type(e).__name__}: {e}"
                    report["events"].append({"step": "resume_attempt_a_filechooser", "result": attempt_a})
                    log(f"resume attempt-A (file_chooser): {attempt_a}")

                # --- Attempt B: set_input_files + force-dispatch events ---
                if not attempt_a["ok"]:
                    attempt_b = {"ok": False, "err": None}
                    try:
                        file_inputs = frame.query_selector_all("input#resume, input[type=file]")
                        if file_inputs:
                            file_inputs[0].set_input_files(resume_path)
                            time.sleep(0.3)
                            # Force-dispatch change/input on the input AND its parents.
                            evalfn(
                                r"""() => {
                                    const inp = document.querySelector('#resume');
                                    if (!inp) return false;
                                    const evtChange = new Event('change', { bubbles: true });
                                    const evtInput = new Event('input', { bubbles: true });
                                    inp.dispatchEvent(evtChange);
                                    inp.dispatchEvent(evtInput);
                                    // Also fire on parent (Filestack adapter sometimes binds on wrapper).
                                    if (inp.parentElement) {
                                        inp.parentElement.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                    return true;
                                }"""
                            )
                            # Then click Attach to nudge Filestack.
                            evalfn(gf.JS_CLICK_ATTACH, {"delayMs": 1200, "filename": resume_name})
                            time.sleep(2.0)
                            attempt_b["ok"] = _resume_bound()
                        else:
                            attempt_b["err"] = "no #resume input"
                    except Exception as e:
                        attempt_b["err"] = f"{type(e).__name__}: {e}"
                    report["events"].append({"step": "resume_attempt_b_dispatch", "result": attempt_b})
                    log(f"resume attempt-B (dispatch events): {attempt_b}")

                # --- Attempt C: JS DataTransfer injection (bypass Filestack) ---
                if not _resume_bound():
                    attempt_c = {"ok": False, "err": None}
                    try:
                        import base64, mimetypes
                        with open(resume_path, "rb") as fh:
                            b64 = base64.b64encode(fh.read()).decode("ascii")
                        mime = mimetypes.guess_type(resume_path)[0] or "application/pdf"
                        injected = frame.evaluate(
                            r"""async ({ b64, filename, mime }) => {
                                // Re-query: Filestack often DETACHES the original #resume
                                // input after Attempt A's file_chooser fires, then renders
                                // a fresh, anonymous <input type=file> elsewhere (no #resume
                                // id). Cross-cutting fix (2026-05-26, chain worker, learning
                                // from Lyft 716 careerpuck failures): try #resume first,
                                // then fall back to ANY input[type=file] in the form, prefer
                                // the visible one. Without this fallback, Attempt C errors
                                // with 'no #resume after prior attempts' and the whole
                                // 3-layer chain reports BLOCKED for a fixable case.
                                let inp = document.querySelector('#resume');
                                if (!inp) {
                                    const all = Array.from(document.querySelectorAll('input[type=file]'));
                                    // Prefer ones that look like resume inputs by name/id hint.
                                    inp = all.find(el => /resume|cv/i.test((el.name||'') + ' ' + (el.id||'') + ' ' + (el.getAttribute('aria-label')||''))) || all[0];
                                }
                                if (!inp) return { ok: false, err: 'no file input found in DOM (Filestack swap with no replacement?)' };
                                // Decode base64 → Uint8Array → Blob → File.
                                const bin = atob(b64);
                                const arr = new Uint8Array(bin.length);
                                for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                                const file = new File([arr], filename, { type: mime });
                                const dt = new DataTransfer();
                                dt.items.add(file);
                                inp.files = dt.files;
                                inp.dispatchEvent(new Event('change', { bubbles: true }));
                                inp.dispatchEvent(new Event('input', { bubbles: true }));
                                return { ok: true, files_after: inp.files.length, name_after: inp.files[0] ? inp.files[0].name : null, used_selector: inp.id ? ('#'+inp.id) : (inp.name ? ('[name='+inp.name+']') : 'input[type=file] (anonymous)') };
                            }""",
                            {"b64": b64, "filename": resume_name, "mime": mime},
                        )
                        time.sleep(1.5)
                        attempt_c["ok"] = _resume_bound()
                        attempt_c["injected"] = injected
                    except Exception as e:
                        attempt_c["err"] = f"{type(e).__name__}: {e}"
                    report["events"].append({"step": "resume_attempt_c_datatransfer", "result": attempt_c})
                    log(f"resume attempt-C (DataTransfer): {attempt_c}")

                # Final verify — keep using the legacy JS for report parity
                v = evalfn(gf.JS_VERIFY_RESUME_ATTACHED, {"filename": resume_name})
                v["strict_bound"] = _resume_bound()
                report["events"].append({"step": "verify_resume", "result": v})
                if not v.get("strict_bound"):
                    log(f"RESUME BIND FAILED after all attempts: {v}")
                    report["resume_bind_failed"] = True
                else:
                    log(f"resume bound OK: {v}")
            except Exception as e:
                log(f"resume upload err: {e}")
                report["events"].append({"step": "resume_upload", "error": str(e)})

        # --- chain_009: GH native S3 uploader + JSON inject ---
        # Independent of all DataTransfer attempts above. We do our own S3
        # presigned-POST upload from inside the iframe and plant the resulting
        # {url, name} into window.__gh_resume_inject so the fetch patch wires
        # it into job_application.resume_url / resume_url_filename at submit.
        # Safe even when DataTransfer also bound the file (server only reads
        # resume_url from the JSON body anyway; the multipart file in inp.files
        # is never sent because submit is JSON, not multipart form).
        if USE_GH_S3_UPLOADER and resume_path and report["gh_s3_upload"].get("fetch_patched"):
            s3rep = {"presigned": None, "upload": None, "inject": None}
            try:
                import base64 as _b64m, mimetypes as _mimm
                with open(resume_path, "rb") as fh:
                    _b64s = _b64m.b64encode(fh.read()).decode("ascii")
                _mimes = _mimm.guess_type(resume_path)[0] or "application/pdf"
                _fnames = Path(resume_path).name

                pres = evalfn(gf.JS_FETCH_PRESIGNED_FIELDS)
                s3rep["presigned"] = {"ok": bool(pres and pres.get("ok")),
                                       "baseUrl": (pres or {}).get("baseUrl"),
                                       "key": (pres or {}).get("key")}
                _debug_filestack_log(report, debug_filestack, "presigned", pres)
                if not (pres and pres.get("ok")):
                    s3rep["presigned"]["err"] = (pres or {}).get("err") or "unknown"
                    report["gh_s3_upload"].update(s3rep)
                    log(f"gh-s3 presigned FAILED: {pres}")
                else:
                    up = evalfn(gf.JS_S3_UPLOAD, {
                        "baseUrl": pres["baseUrl"],
                        "fields": pres["fields"],
                        "key": pres["key"],
                        "b64": _b64s,
                        "filename": _fnames,
                        "mime": _mimes,
                    })
                    s3rep["upload"] = up
                    _debug_filestack_log(report, debug_filestack, "s3_upload", up)
                    if up and up.get("ok"):
                        inj = evalfn(gf.JS_INSTALL_RESUME_INJECT, {
                            "resume_url": up["fileUrl"],
                            "resume_url_filename": _fnames,
                        })
                        s3rep["inject"] = inj
                        _debug_filestack_log(report, debug_filestack, "inject", inj)
                        log(f"gh-s3 upload OK: {up.get('fileUrl')[:80] if up.get('fileUrl') else None}")

                        # --- chain_010: React-onChange trigger ---
                        # Even though S3 upload + fetch patch are in place, GH's
                        # client-side React validator inspects application.resume
                        # state, not the DOM. Without an onChange event the
                        # state stays null and submit short-circuits with
                        # "Resume/CV is required". Use the React-native value
                        # setter + bubbling change event on #resume so React's
                        # UploadField.onChange fires (which may also trigger a
                        # second upload via React's own uploader — acceptable
                        # per OPTION-A-DESIGN.md, ~+2s).
                        if USE_REACT_RESUME_TRIGGER:
                            try:
                                trig = evalfn(gf.JS_REACT_RESUME_TRIGGER, {
                                    "b64": _b64s,
                                    "filename": _fnames,
                                    "mime": _mimes,
                                })
                                s3rep["react_trigger"] = trig
                                _debug_filestack_log(report, debug_filestack, "react_trigger", trig)
                                log(f"gh-s3 react trigger: {trig}")
                                # Give React's own uploader / state update time
                                # to settle before we click Submit. ~6s is enough
                                # for a double-upload to complete on typical PDFs.
                                try:
                                    time.sleep(6)
                                    post_trig = evalfn(
                                        r"""() => {
                                            const inp = document.querySelector('#resume');
                                            const chip = (document.body.textContent||'').match(/[A-Z]\w+_[A-Z]\w+_Resume\.\w+/);
                                            return {
                                                input_present: !!inp,
                                                files_in_input: inp && inp.files ? inp.files.length : 0,
                                                filename_chip_visible: !!chip,
                                                chip_text: chip ? chip[0] : null,
                                                react_marker: window.__gh_react_resume_triggered || null,
                                            };
                                        }"""
                                    )
                                    s3rep["react_trigger_post"] = post_trig
                                    _debug_filestack_log(report, debug_filestack, "react_trigger_post", post_trig)
                                    log(f"gh-s3 react trigger post-state: {post_trig}")
                                except Exception as e:
                                    s3rep["react_trigger_post_err"] = f"{type(e).__name__}: {e}"
                            except Exception as e:
                                s3rep["react_trigger_err"] = f"{type(e).__name__}: {e}"
                                log(f"gh-s3 react trigger err: {e}")
                    else:
                        log(f"gh-s3 upload FAILED: {up}")
                report["gh_s3_upload"].update(s3rep)
            except Exception as e:
                report["gh_s3_upload"]["err"] = f"{type(e).__name__}: {e}"
                log(f"gh-s3 sidecar err: {e}")

        # State right before submit
        pre_state = evalfn(
            """() => {
                const sub = [...document.querySelectorAll('button')].find(b => /submit/i.test(b.textContent||''));
                const grecap = document.querySelector('.grecaptcha-error');
                return {submitDisabled: sub ? sub.disabled : null, submitText: sub ? sub.textContent.trim() : null, grecapErrText: grecap ? (grecap.textContent||'').trim() : ''};
            }"""
        )
        report["pre_submit"] = pre_state
        log(f"pre-submit: {pre_state}")

        if dry_run:
            log("--dry-run: stopping before Submit click")
            report["outcome"] = "DRY_RUN"
            browser.close()
            return report

        # ---- CapSolver pre-submit (env-gated, default OFF) ----
        # If ENABLE_CAPSOLVER=1 AND CAPSOLVER_API_KEY set, attempt to solve
        # reCAPTCHA v3 and inject the token into the iframe before clicking
        # Submit. When disabled (default), this is a no-op and the existing
        # behavior is unchanged. See projects/job-search/role-discovery/
        # captcha_presubmit.py + capsolver_client.py.
        try:
            from captcha_presubmit import (
                solve_and_inject_recaptcha_v3,
                is_enabled as _capsolver_enabled,
            )
            if _capsolver_enabled():
                log("capsolver pre-submit ENABLED; attempting recaptcha v3")
                presubmit = solve_and_inject_recaptcha_v3(
                    frame,
                    page_url=page.url,  # top-level URL; v3 token is bound
                                        # to the parent page origin not the iframe
                )
                report["captcha_presubmit"] = presubmit
                log(f"capsolver pre-submit result: "
                    f"injected={presubmit.get('injected')} "
                    f"reason={presubmit.get('reason')}")
            else:
                report["captcha_presubmit"] = {
                    "enabled": False,
                    "reason": "ENABLE_CAPSOLVER!=1 or key unset",
                }
        except Exception as e:
            # Defensive: presubmit must never crash the submit flow.
            log(f"capsolver pre-submit raised (non-fatal): {e}")
            report["captcha_presubmit"] = {
                "enabled": False,
                "reason": f"unexpected error: {type(e).__name__}: {e}",
            }

        # SUBMIT
        log("clicking Submit")
        try:
            sr = evalfn(gf.JS_SUBMIT, {"allowVisibleCaptcha": True})
            report["events"].append({"step": "submit", "result": sr})
            log(f"submit click: {sr}")
        except Exception as e:
            log(f"submit click err: {e}")
            report["error"] = f"submit click: {e}"
            browser.close()
            return report

        # --- chain_009: capture fetch-patch observability ---
        if USE_GH_S3_UPLOADER:
            try:
                seen = evalfn("() => ({ seen: window.__gh_submit_seen, mutated: window.__gh_submit_mutated })")
                if seen:
                    report["gh_s3_upload"]["submit_seen"] = seen.get("seen")
                    report["gh_s3_upload"]["submit_mutated"] = seen.get("mutated")
                    _debug_filestack_log(report, debug_filestack, "post_submit_capture", seen)
            except Exception as e:
                report["gh_s3_upload"]["capture_err"] = f"{type(e).__name__}: {e}"

        # Watch for outcome — also handles Stripe's email-verification-code
        # interstitial. After the first submit click, the form transitions to a
        # page with 8 `input[id^=security-input-]` boxes; we poll Gmail for the
        # code and fill/submit again.
        end = time.time() + 30
        last = None
        verification_handled = False
        submit_epoch = int(time.time())
        while time.time() < end:
            time.sleep(2)
            try:
                last = evalfn(
                    r"""() => {
                        const grecap = document.querySelector('.grecaptcha-error');
                        const grecapErrText = grecap ? (grecap.textContent||'').trim() : '';
                        const fieldErrs = [...document.querySelectorAll('.error, [class*=error]:not(iframe):not(.grecaptcha-error)')].map(e => (e.textContent||'').trim()).filter(t => t && t.length < 250).slice(0,10);
                        const sub = [...document.querySelectorAll('button')].find(b => /submit/i.test(b.textContent||''));
                        const bodyText = (document.body.textContent||'').toLowerCase();
                        const conf = /thank you for applying|thank you for submitting|application submitted|thanks for applying|application has been received|we have received your application/.test(bodyText) || /\/(confirmation|thanks|submitted)(\b|\?|\/|$)/i.test(location.href || '') || /\/job_app\/confirmation/i.test(location.href || '');
                        const secBoxes = document.querySelectorAll('input[id^="security-input-"]').length;
                        return {grecapErrText, fieldErrs, submitDisabled: sub ? sub.disabled : null, conf, url: location.href, secBoxes};
                    }"""
                )
            except Exception:
                pass
            if last and last.get("grecapErrText"):
                report["outcome"] = "CAPTCHA_GATE"
                report["post_submit"] = last
                log(f"CAPTCHA_GATE: {last['grecapErrText']!r}")
                browser.close()
                return report
            if last and last.get("conf"):
                report["outcome"] = "SUBMITTED"
                report["post_submit"] = last
                log(f"SUBMITTED, url={last.get('url')}")
                # Defense in depth: even on conf=True, if fieldErrs non-empty,
                # honest_verify will downgrade. (Real submits clear errors.)
                honest_verify_post_submit(report, last)
                browser.close()
                return report
            if last and last.get("secBoxes") and not verification_handled:
                verification_handled = True
                log(f"security-code interstitial detected ({last['secBoxes']} boxes); polling Gmail")
                try:
                    from gmail_imap import wait_for_verification_code
                    payload = wait_for_verification_code(timeout_seconds=180, poll_seconds=5, since_epoch=submit_epoch)
                    code = payload.get("code") if isinstance(payload, dict) else payload
                    log(f"verification code received: {code}")
                    report["verification_code_used"] = code
                    fr = evalfn(gf.JS_SUBMIT_VERIFICATION_CODE, code)
                    report["events"].append({"step": "verification_code_submit", "result": fr})
                    log(f"verification submit: {fr}")
                    # Extend the deadline to give the confirmation page time to render
                    end = time.time() + 30
                except Exception as e:
                    log(f"verification code flow failed: {e}")
                    report["outcome"] = "VERIFICATION_FAIL"
                    report["verification_error"] = str(e)
                    report["post_submit"] = last
                    browser.close()
                    return report

        report["outcome"] = "TIMEOUT"
        report["post_submit"] = last
        log(f"TIMEOUT, last state: {last}")
        # If we timed out but the form actually surfaced required-field errors,
        # promote that to a BLOCKED_FIELD_ERRORS verdict and downgrade the
        # misleading `step:submit, result:{ok:True}` event so downstream graders
        # don't treat the role as submitted. Chain_006 sidecar fix.
        honest_verify_post_submit(report, last)
        browser.close()
        return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--debug-filestack", action="store_true",
                    help="verbose dump of GH S3-uploader sidecar events (chain_009)")
    args = ap.parse_args()
    rep = run(args.slug, dry_run=args.dry_run, headless=not args.headed,
              debug_filestack=args.debug_filestack)
    print(json.dumps(rep, indent=2, default=str))


if __name__ == "__main__":
    main()
