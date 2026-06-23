#!/usr/bin/env python3
"""Try direct SF URL forms and figure out how to reach the apply form"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore7]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    # Step 1: Load job page and accept cookies
    page = ctx.new_page()
    log("Loading job page...")
    page.goto("https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/", wait_until="networkidle", timeout=30000)
    time.sleep(3)
    page.screenshot(path=f"{DEBUG_DIR}/11a-job-page.png")

    # Accept the cookie consent
    result = page.evaluate("""
    () => {
        var btns = document.querySelectorAll('button');
        for (var b of btns) {
            if (b.innerText.toLowerCase().includes('accept all cookies')) {
                b.click();
                return 'clicked: ' + b.innerText;
            }
        }
        return 'no accept-all-cookies button';
    }
    """)
    log(f"Cookie result: {result}")
    time.sleep(2)

    # Check URL now
    log(f"After cookie: {page.url}")

    # Navigate to apply URL
    log("Navigating to apply URL...")
    resp = page.goto("https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)

    log(f"Final URL: {page.url}")
    log(f"Title: {page.title()}")
    body = page.locator("body").inner_text()[:500]
    log(f"Body: {body}")
    page.screenshot(path=f"{DEBUG_DIR}/12-apply-after-cookie.png")

    # If still redirected, try the JS redirect via apply button
    if "1395242700" not in page.url and "apply" not in page.url.lower():
        log("Still redirected - trying JS click approach")
        page.goto("https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Force execute the apply link's JS/navigation
        result2 = page.evaluate("""
        () => {
            var links = document.querySelectorAll('a');
            for (var l of links) {
                if (l.href && l.href.includes('talentcommunity/apply')) {
                    return {href: l.href, text: l.innerText.trim(), visible: l.offsetParent !== null, display: getComputedStyle(l).display};
                }
            }
            return null;
        }
        """)
        log(f"Apply link info: {result2}")

        # Try force navigate
        if result2 and result2.get("href"):
            apply_href = result2["href"]
            log(f"Force navigating to: {apply_href}")
            page.goto(apply_href, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            log(f"After force nav: {page.url}")
            log(f"Title: {page.title()}")
            page.screenshot(path=f"{DEBUG_DIR}/13-force-nav-apply.png")
            body2 = page.locator("body").inner_text()[:1000]
            log(f"Body: {body2}")

    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
