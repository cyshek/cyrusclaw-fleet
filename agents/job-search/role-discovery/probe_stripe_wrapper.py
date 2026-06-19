#!/usr/bin/env python3
"""
probe_stripe_wrapper.py — lightweight, no-packet captcha-presence probe.

For each (stripe-wrapper apply URL, direct GH embed URL) pair:
  * Load the URL with Playwright.
  * If wrapper: wait for iframe#grnhse_iframe, capture its src (looking for
    validityToken=).
  * Wait for the form to load inside the frame.
  * Capture initial state: .grecaptcha-error present? recaptcha iframe present?
    submit button disabled?
  * Do NOT fill or submit.

Output: JSON report.

Usage:
    python probe_stripe_wrapper.py --gh-jid 7176530 --slug product-manager-payments
    python probe_stripe_wrapper.py --gh-jid 7176530 --slug product-manager-payments --json-out report.json

You can also pass --probes wrapper,direct to limit which URL shapes are tested.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


def log(msg: str) -> None:
    print(f"[stripe-probe] {msg}", file=sys.stderr, flush=True)


def probe_wrapper(playwright, url: str, timeout_ms: int = 45000) -> dict:
    out: dict = {"shape": "stripe-wrapper", "url": url, "events": []}
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
    )
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="load", timeout=timeout_ms)
        out["final_url"] = page.url
        try:
            page.wait_for_selector("iframe#grnhse_iframe", timeout=20000)
        except PWTimeout:
            try:
                page.wait_for_selector('iframe[src*="job-boards.greenhouse.io"]', timeout=10000)
            except PWTimeout:
                out["error"] = "no greenhouse iframe appeared on wrapper page"
                browser.close()
                return out
        iframe_el = page.query_selector("iframe#grnhse_iframe") or page.query_selector(
            'iframe[src*="job-boards.greenhouse.io"]'
        )
        iframe_src = iframe_el.get_attribute("src") if iframe_el else None
        out["iframe_src"] = iframe_src
        out["has_validity_token"] = bool(iframe_src and "validityToken=" in iframe_src)

        # Find the frame object
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
            out["error"] = "no GH frame object"
            out["frame_urls"] = [f.url for f in page.frames]
            browser.close()
            return out

        try:
            frame.wait_for_selector("form", timeout=20000)
        except PWTimeout:
            out["error"] = "form did not load inside GH frame"

        # Inspect captcha state
        state = frame.evaluate(
            """() => ({
                hasGrecaptchaError: !!document.querySelector('.grecaptcha-error'),
                recaptchaIframes: Array.from(document.querySelectorAll('iframe[src*="recaptcha"], iframe[src*="hcaptcha"]')).map(f => f.src),
                submitButton: (() => {
                    const b = document.querySelector('button[type="submit"], input[type="submit"]');
                    if (!b) return null;
                    return {tag: b.tagName, disabled: b.disabled, ariaDisabled: b.getAttribute('aria-disabled'), classes: b.className};
                })(),
                formAction: (document.querySelector('form') || {}).action || null,
                hasGrecaptchaScript: !!document.querySelector('script[src*="recaptcha/enterprise"]'),
                bodyTextHead: (document.body && document.body.innerText || '').slice(0, 200),
            })"""
        )
        out["form_state"] = state
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            browser.close()
        except Exception:
            pass
    return out


def probe_direct(playwright, gh_jid: str, timeout_ms: int = 45000) -> dict:
    url = f"https://job-boards.greenhouse.io/embed/job_app?for=stripe&token={gh_jid}"
    out: dict = {"shape": "direct-embed", "url": url, "events": []}
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
    )
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="load", timeout=timeout_ms)
        out["final_url"] = page.url
        try:
            page.wait_for_selector("form", timeout=20000)
        except PWTimeout:
            out["error"] = "form did not load on direct embed"
        state = page.evaluate(
            """() => ({
                hasGrecaptchaError: !!document.querySelector('.grecaptcha-error'),
                recaptchaIframes: Array.from(document.querySelectorAll('iframe[src*="recaptcha"], iframe[src*="hcaptcha"]')).map(f => f.src),
                submitButton: (() => {
                    const b = document.querySelector('button[type="submit"], input[type="submit"]');
                    if (!b) return null;
                    return {tag: b.tagName, disabled: b.disabled, ariaDisabled: b.getAttribute('aria-disabled'), classes: b.className};
                })(),
                formAction: (document.querySelector('form') || {}).action || null,
                hasGrecaptchaScript: !!document.querySelector('script[src*="recaptcha/enterprise"]'),
                bodyTextHead: (document.body && document.body.innerText || '').slice(0, 200),
            })"""
        )
        out["form_state"] = state
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            browser.close()
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gh-jid", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--probes", default="wrapper,direct")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    wrapper_url = f"https://stripe.com/jobs/listing/{args.slug}/{args.gh_jid}/apply"
    probes = [p.strip() for p in args.probes.split(",")]

    results = []
    with sync_playwright() as pw:
        if "wrapper" in probes:
            log(f"probe wrapper: {wrapper_url}")
            results.append(probe_wrapper(pw, wrapper_url))
        if "direct" in probes:
            log(f"probe direct embed for jid {args.gh_jid}")
            results.append(probe_direct(pw, args.gh_jid))

    out = {"gh_jid": args.gh_jid, "slug": args.slug, "probes": results}
    payload = json.dumps(out, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(payload)
        log(f"wrote {args.json_out}")
    print(payload)


if __name__ == "__main__":
    main()
