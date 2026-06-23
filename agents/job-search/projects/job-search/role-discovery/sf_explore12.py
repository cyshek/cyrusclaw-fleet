#!/usr/bin/env python3
"""Try the direct SF apply URL via talentcommunity/applyOnline pattern"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore12]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    sf_urls = [
        "https://career8.successfactors.com/careers?company=aosmith",
        "https://career8.successfactors.com/career?company=aosmith&career_ns=job_listing",
    ]

    for url in sf_urls:
        page = ctx.new_page()
        log(f"\nTrying: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(3)
        final_url = page.url
        title = page.title()
        body = page.locator("body").inner_text()[:200]
        log(f"  Final: {final_url}")
        log(f"  Title: {title}")
        log(f"  Body: {body}")
        page.close()

    # Now try the actual J2W apply URL pattern
    page = ctx.new_page()
    log("\nLoading job page to inspect apply button attrs...")
    page.goto("https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Accept cookies
    page.evaluate("() => { var b = document.querySelector('#cookie-accept'); if (b) b.click(); }")
    time.sleep(1)

    apply_js = page.evaluate("""
    () => {
        var applyBtn = document.querySelector('a.dialogApplyBtn');
        if (!applyBtn) applyBtn = document.querySelector('a[href*="talentcommunity"]');
        if (!applyBtn) return 'no apply button';
        return {
            href: applyBtn.href,
            onclick: applyBtn.getAttribute('onclick'),
            'data-apply-url': applyBtn.getAttribute('data-apply-url'),
            'all-attrs': Object.fromEntries([...applyBtn.attributes].map(a => [a.name, a.value]))
        };
    }
    """)
    log(f"Apply button attrs: {json.dumps(apply_js, indent=2)}")

    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
