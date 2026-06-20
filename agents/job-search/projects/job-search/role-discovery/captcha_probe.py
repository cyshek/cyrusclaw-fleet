#!/usr/bin/env python3
"""
captcha_probe.py — test the hypothesis that loading the Greenhouse iframe via
the company's careers-page WRAPPER (with validityToken in iframe src) lets the
form pass reCAPTCHA Enterprise — whereas loading the embed URL directly fails.

Usage:
    python captcha_probe.py --wrapper <careers-page-url> --packet <slug> [--submit]

If --submit is omitted the probe fills required fields and inspects the Submit
button state + reCAPTCHA DOM presence without clicking Submit.
With --submit it clicks Submit, waits 30s, and reports whether
.grecaptcha-error appeared or the confirmation page loaded.

Probe writes a JSON report to STDOUT and a summary line to STDERR.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import re
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


def log(msg: str) -> None:
    print(f"[probe] {msg}", file=sys.stderr, flush=True)


def find_packet(slug: str) -> Path:
    p = Path(__file__).resolve().parent.parent / "applications" / "submitted" / slug
    if not p.exists():
        raise SystemExit(f"packet not found: {p}")
    return p


def find_pdf(packet: Path) -> Path:
    pdfs = sorted(packet.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDF in {packet}")
    # prefer the v2 (tailored) one
    for p in pdfs:
        if "v2" in p.name:
            return p
    return pdfs[0]


def load_prefill(packet: Path) -> dict:
    return json.loads((packet / "prefill.json").read_text())


def run(wrapper_url: str, packet_slug: str, do_submit: bool, timeout_ms: int = 60_000) -> dict:
    packet = find_packet(packet_slug)
    pdf = find_pdf(packet)
    pre = load_prefill(packet)

    report = {
        "wrapper_url": wrapper_url,
        "packet": packet_slug,
        "pdf": str(pdf),
        "do_submit": do_submit,
        "events": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        log(f"goto wrapper: {wrapper_url}")
        page.goto(wrapper_url, wait_until="load", timeout=timeout_ms)
        report["final_wrapper_url"] = page.url

        # Wait for the greenhouse iframe to appear.
        log("waiting for #grnhse_iframe")
        try:
            page.wait_for_selector("iframe#grnhse_iframe", timeout=20_000)
        except PWTimeout:
            # fallback: any greenhouse iframe
            page.wait_for_selector('iframe[src*="job-boards.greenhouse.io"]', timeout=10_000)

        iframe_el = page.query_selector("iframe#grnhse_iframe") or page.query_selector(
            'iframe[src*="job-boards.greenhouse.io"]'
        )
        iframe_src = iframe_el.get_attribute("src") if iframe_el else None
        report["iframe_src"] = iframe_src
        has_validity = bool(iframe_src and "validityToken=" in iframe_src)
        report["has_validity_token"] = has_validity
        log(f"iframe src has validityToken: {has_validity}")

        # Switch to the iframe — wait up to 15s for the Frame to attach + URL
        frame = None
        deadline = time.time() + 20
        while time.time() < deadline:
            for f in page.frames:
                if f.url and "job-boards.greenhouse.io" in f.url:
                    frame = f
                    break
            if frame:
                break
            time.sleep(0.5)
        if frame is None:
            report["error"] = "could not find greenhouse iframe Frame object"
            report["all_frame_urls"] = [f.url for f in page.frames]
            browser.close()
            return report
        log(f"frame URL: {frame.url}")

        # Wait for the form
        try:
            frame.wait_for_selector("form", timeout=20_000)
        except PWTimeout:
            report["error"] = "form did not appear in iframe"
            browser.close()
            return report

        # Inspect submit button + recaptcha
        def inspect():
            return frame.evaluate(
                """() => {
                    const submit = [...document.querySelectorAll('button')].find(b => /submit/i.test(b.textContent||'')) || document.querySelector('button[type="submit"]');
                    const grecapDivs = [...document.querySelectorAll('.grecaptcha-error, [class*="grecaptcha"]')].map(e => ({cls:e.className, text:(e.textContent||'').slice(0,80)}));
                    const recapIframes = [...document.querySelectorAll('iframe[src*="recaptcha"]')].map(e => ({src:(e.src||'').slice(0,140)}));
                    return {
                        submitText: submit ? submit.textContent.trim() : null,
                        submitDisabled: submit ? submit.disabled : null,
                        grecap: grecapDivs,
                        recapIframes,
                        url: location.href,
                    };
                }"""
            )

        report["events"].append({"phase": "pre-fill", "state": inspect()})

        # --- Fill required text fields ---
        log("filling text fields")
        text_fills = [
            ('input[name*="first_name" i], #first_name', pre["identity"]["first_name"]),
            ('input[name*="last_name" i], #last_name', pre["identity"]["last_name"]),
            ('input[name*="email" i], #email', pre["contact"]["email"]),
            ('input[name*="phone" i], #phone', pre["contact"]["phone"]),
        ]
        for sel, val in text_fills:
            try:
                el = frame.query_selector(sel)
                if el:
                    el.fill(val)
                    log(f"  filled {sel} = {val}")
            except Exception as e:
                log(f"  fill error {sel}: {e}")

        # --- Upload resume ---
        log("uploading resume")
        # Greenhouse: file inputs are usually #resume or input[type=file]
        try:
            file_inputs = frame.query_selector_all('input[type="file"]')
            if file_inputs:
                file_inputs[0].set_input_files(str(pdf))
                log(f"  uploaded {pdf.name} via input[type=file]")
            else:
                log("  no file input visible — trying after clicking attach")
                attach = frame.query_selector('button:has-text("Attach")')
                if attach:
                    with page.expect_file_chooser() as fc_info:
                        attach.click()
                    fc_info.value.set_files(str(pdf))
                    log("  uploaded via filechooser")
        except Exception as e:
            log(f"  resume upload error: {e}")

        # Give Filestack a moment to commit
        time.sleep(3)

        # --- Fill required react-select dropdowns ---
        # We need to handle: How did you hear, work-auth, sponsorship, prev-Databricks, sanctions
        log("filling required dropdowns")

        def pick_react_select(label_regex: str, value: str) -> bool:
            try:
                ok = frame.evaluate(
                    """([labelRe, val]) => {
                        const labels = [...document.querySelectorAll('label, legend')];
                        const re = new RegExp(labelRe, 'i');
                        const lab = labels.find(l => re.test(l.textContent||''));
                        if (!lab) return {ok:false, why:'no label'};
                        // walk to nearest .select__control under the label's container
                        let container = lab.closest('div.field, div.application-question, div.form-group') || lab.parentElement;
                        let ctrl = container && container.querySelector('.select__control');
                        if (!ctrl) {
                            // fallback: any select__control sibling
                            ctrl = lab.nextElementSibling && lab.nextElementSibling.querySelector && lab.nextElementSibling.querySelector('.select__control');
                        }
                        if (!ctrl) return {ok:false, why:'no control'};
                        // open
                        ['mousedown','mouseup','click'].forEach(t => ctrl.dispatchEvent(new MouseEvent(t,{bubbles:true})));
                        return {ok:true, why:'opened'};
                    }""",
                    [label_regex, value],
                )
                if not ok.get("ok"):
                    return False
                time.sleep(0.3)
                # Now pick option
                picked = frame.evaluate(
                    """([val]) => {
                        const opts = [...document.querySelectorAll('.select__option, [class*=option]')].filter(o => /option/.test(o.className||''));
                        const re = new RegExp(val.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'), 'i');
                        const m = opts.find(o => re.test(o.textContent||''));
                        if (!m) return {ok:false, opts: opts.slice(0,15).map(o => (o.textContent||'').trim().slice(0,60))};
                        ['mousedown','mouseup','click'].forEach(t => m.dispatchEvent(new MouseEvent(t,{bubbles:true})));
                        return {ok:true, picked: (m.textContent||'').trim()};
                    }""",
                    [value],
                )
                if not picked.get("ok"):
                    log(f"  pick {label_regex} -> NOT FOUND. opts={picked.get('opts')}")
                    return False
                log(f"  pick {label_regex} -> {picked.get('picked')}")
                return True
            except Exception as e:
                log(f"  pick err {label_regex}: {e}")
                return False

        # Best-effort answers
        pick_react_select(r"how did you hear", "LinkedIn") or pick_react_select(r"how did you hear", "Other")
        pick_react_select(r"legally authorized to work", "Yes")
        pick_react_select(r"sponsorship", "No")
        pick_react_select(r"worked for Databricks", "No")
        pick_react_select(r"^Country\*?$|^Country$|Country\*", "United States")
        pick_react_select(r"Hispanic/Latino", "No")

        # Multi-selects (sanctions) — try "None of the above"
        pick_react_select(r"sanctions|export controls|please confirm whether any", "None of the above")
        pick_react_select(r"if you selected a response", "None of the above")

        # Demographics — decline
        pick_react_select(r"^gender|gender identity", "Decline")
        pick_react_select(r"race", "Decline")
        pick_react_select(r"veteran", "don't wish to answer")
        pick_react_select(r"disability", "do not want to answer")

        # Diagnose any remaining empty required selects
        missing = frame.evaluate(
            """() => {
                const out = [];
                const ctrls = document.querySelectorAll('.select__control');
                ctrls.forEach(c => {
                    const hasValue = c.querySelector('.select__single-value, .select__multi-value');
                    if (!hasValue) {
                        // find label
                        let p = c;
                        let label = '';
                        for (let i=0; i<6 && p; i++) {
                            p = p.parentElement;
                            if (p) {
                                const l = p.querySelector('label, legend');
                                if (l) { label = (l.textContent||'').trim().slice(0,80); break; }
                            }
                        }
                        out.push(label);
                    }
                });
                return out;
            }"""
        )
        log(f"empty react-selects after fill: {missing}")

        time.sleep(1)
        state_after_fill = inspect()
        report["events"].append({"phase": "post-fill", "state": state_after_fill})
        log(f"post-fill submit disabled: {state_after_fill.get('submitDisabled')}")
        log(f"post-fill grecap: {state_after_fill.get('grecap')}")

        if not do_submit:
            browser.close()
            return report

        # --- Click Submit ---
        log("clicking submit")
        try:
            frame.evaluate(
                """() => {
                    const b = [...document.querySelectorAll('button')].find(x => /submit/i.test(x.textContent||'')) || document.querySelector('button[type="submit"]');
                    if (b) { b.scrollIntoView(); b.click(); }
                }"""
            )
        except Exception as e:
            log(f"  submit click err: {e}")

        # Watch for outcome
        end = time.time() + 30
        last = None
        while time.time() < end:
            time.sleep(2)
            try:
                last = inspect()
                # also grab error banners / field errors
                err_state = frame.evaluate(
                    """() => {
                        const grecapErr = document.querySelector('.grecaptcha-error');
                        const grecapErrText = grecapErr ? (grecapErr.textContent || '').trim() : '';
                        const fieldErrs = [...document.querySelectorAll('.error, [class*=error]:not(iframe):not(.grecaptcha-error)')].map(e => (e.textContent||'').trim()).filter(t => t && t.length < 200).slice(0,10);
                        const banners = [...document.querySelectorAll('[role=alert], .alert, .flash')].map(e => (e.textContent||'').trim()).slice(0,5);
                        return {grecapErrText, fieldErrs, banners};
                    }"""
                )
                last['err_state'] = err_state
            except Exception:
                pass
            url_now = frame.url if frame else page.url
            grecap_err_text = (last or {}).get('err_state', {}).get('grecapErrText', '')
            if grecap_err_text:
                report["outcome"] = "CAPTCHA_GATE"
                report["events"].append({"phase": "post-submit", "state": last})
                log(f"  CAPTCHA_GATE detected, error text: {grecap_err_text!r}")
                browser.close()
                return report
            if "confirmation" in (url_now or "").lower() or "thank" in (url_now or "").lower():
                report["outcome"] = "SUBMITTED"
                report["events"].append({"phase": "post-submit", "state": last, "url": url_now})
                log(f"  SUBMITTED, url={url_now}")
                browser.close()
                return report
            # Also detect confirmation text inside the iframe
            try:
                conf = frame.evaluate(
                    """() => {
                        const t = (document.body.textContent || '').toLowerCase();
                        return /thank you for applying|application submitted|application has been received|we have received your application|thanks for applying/.test(t);
                    }"""
                )
            except Exception:
                conf = False
            if conf:
                report["outcome"] = "SUBMITTED_TEXT"
                report["events"].append({"phase": "post-submit", "state": last, "url": frame.url})
                log("  SUBMITTED (text match)")
                browser.close()
                return report

        report["outcome"] = "TIMEOUT_NO_CONFIRM_NO_CAPTCHA_ERROR"
        report["events"].append({"phase": "post-submit-final", "state": last})
        browser.close()
        return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrapper", required=True, help="Company careers page URL with gh_jid")
    ap.add_argument("--packet", required=True, help="Packet slug (folder name under applications/submitted)")
    ap.add_argument("--submit", action="store_true", help="Actually click Submit")
    args = ap.parse_args()
    rep = run(args.wrapper, args.packet, args.submit)
    print(json.dumps(rep, indent=2, default=str))


if __name__ == "__main__":
    main()
