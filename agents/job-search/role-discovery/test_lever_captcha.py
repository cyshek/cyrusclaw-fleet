#!/usr/bin/env python3
"""Test whether tf-playwright-stealth defeats Lever's hCaptcha visible-challenge.

Tests 3 Lever apply pages in 4 modes:
  1. headless, no stealth  (baseline)
  2. headless, with stealth
  3. headed,   no stealth
  4. headed,   with stealth

For each: detect hCaptcha presence/visibility.

Does NOT submit anything.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

# Try the stealth import (tf-playwright-stealth installs as `playwright_stealth`)
try:
    from playwright_stealth import stealth_async  # type: ignore
    STEALTH_AVAILABLE = True
    STEALTH_ERR = None
except Exception as e:
    STEALTH_AVAILABLE = False
    STEALTH_ERR = str(e)
    stealth_async = None  # type: ignore

URLS = [
    ("Outreach",  "https://jobs.lever.co/outreach/810b13b3-8338-44fd-99dd-94d24cfe078c/apply"),
    ("Spotify",   "https://jobs.lever.co/spotify/a4a933ce-ab44-4a13-b8ca-8575c97ea40a/apply"),
    ("Palantir",  "https://jobs.lever.co/palantir/96a0ce26-cf84-4fa8-934b-acc4363620b2/apply"),
]


async def detect_captcha(page: Page) -> dict:
    """Probe DOM for hCaptcha and reCAPTCHA fingerprints. Returns a dict."""
    # Allow network/JS to settle a bit so widgets can render.
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    await page.wait_for_timeout(2500)

    js = r"""
    () => {
      const out = { hcaptcha_iframes: [], hcaptcha_div: null, recaptcha_iframes: [], sitekey_attrs: [], page_title: document.title };
      // hCaptcha iframes
      for (const f of document.querySelectorAll("iframe")) {
        const src = f.getAttribute("src") || "";
        if (src.includes("hcaptcha.com")) {
          const r = f.getBoundingClientRect();
          out.hcaptcha_iframes.push({
            src,
            w: r.width, h: r.height,
            visible: r.width > 5 && r.height > 5 && getComputedStyle(f).visibility !== "hidden" && getComputedStyle(f).display !== "none",
          });
        }
        if (src.includes("recaptcha")) {
          const r = f.getBoundingClientRect();
          out.recaptcha_iframes.push({ src, w: r.width, h: r.height });
        }
      }
      // .h-captcha containers (Lever's standard mount point)
      const hc = document.querySelector(".h-captcha, [class*='h-captcha']");
      if (hc) {
        const r = hc.getBoundingClientRect();
        out.hcaptcha_div = { w: r.width, h: r.height, sitekey: hc.getAttribute("data-sitekey") || null };
      }
      // any data-sitekey attrs
      for (const el of document.querySelectorAll("[data-sitekey]")) {
        out.sitekey_attrs.push({ tag: el.tagName, sitekey: el.getAttribute("data-sitekey") });
      }
      return out;
    }
    """
    return await page.evaluate(js)


def classify(probe: dict) -> str:
    iframes = probe.get("hcaptcha_iframes", [])
    div = probe.get("hcaptcha_div")
    if not iframes and not div and not probe.get("sitekey_attrs"):
        return "absent"
    # If any visible (>30px tall) hcaptcha iframe present, it's a visible challenge / checkbox.
    visible_iframe = any(f.get("visible") and f.get("h", 0) > 30 for f in iframes)
    if visible_iframe:
        return "present-visible"
    # Otherwise widget present but checkbox not rendered = invisible challenge mode
    return "present-invisible"


async def run_one(playwright, name: str, url: str, headless: bool, use_stealth: bool) -> dict:
    browser = await playwright.chromium.launch(headless=headless, args=["--no-sandbox"])
    ctx = await browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    page = await ctx.new_page()
    err = None
    if use_stealth and STEALTH_AVAILABLE:
        try:
            await stealth_async(page)
        except Exception as e:
            err = f"stealth_async failed: {e}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        probe = await detect_captcha(page)
    except Exception as e:
        probe = {"error": str(e)}
    verdict = classify(probe) if "error" not in probe else "error"
    await ctx.close()
    await browser.close()
    return {
        "site": name,
        "url": url,
        "headless": headless,
        "stealth": use_stealth,
        "verdict": verdict,
        "probe": probe,
        "err": err,
    }


async def main():
    if not STEALTH_AVAILABLE:
        print(f"WARNING: stealth library not available: {STEALTH_ERR}", file=sys.stderr)

    results = []
    async with async_playwright() as p:
        for name, url in URLS:
            for headless in (True, False):
                for use_stealth in (False, True):
                    print(f"-> {name:10s} headless={headless} stealth={use_stealth}", flush=True)
                    try:
                        r = await run_one(p, name, url, headless, use_stealth)
                    except Exception as e:
                        r = {"site": name, "url": url, "headless": headless, "stealth": use_stealth,
                             "verdict": "launch_error", "err": str(e)}
                    print(f"   {r['verdict']}", flush=True)
                    results.append(r)

    out = Path(__file__).parent / "test_lever_captcha_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {out}")

    # Summary table
    print("\n=== SUMMARY ===")
    print(f"{'site':10s}  {'mode':24s}  verdict")
    for r in results:
        mode = f"headless={r['headless']!s:5s} stealth={r['stealth']!s:5s}"
        print(f"{r['site']:10s}  {mode}  {r['verdict']}")


if __name__ == "__main__":
    asyncio.run(main())
