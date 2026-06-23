#!/usr/bin/env python3
"""Intercept network to find real apply redirect destination"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore8]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

requests_log = []
responses_log = []

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    page = ctx.new_page()

    def on_request(req):
        if "talentcommunity" in req.url or "successfactors" in req.url or "apply" in req.url.lower():
            requests_log.append(f"REQ {req.method} {req.url[:150]}")

    def on_response(resp):
        if "talentcommunity" in resp.url or "successfactors" in resp.url or resp.status in (301, 302, 303, 307, 308):
            responses_log.append(f"RESP {resp.status} {resp.url[:150]}")

    page.on("request", on_request)
    page.on("response", on_response)

    log("Loading job page...")
    page.goto("https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Accept cookies
    result = page.evaluate("""
    () => {
        var btns = document.querySelectorAll('button');
        for (var b of btns) {
            if (b.innerText.toLowerCase().includes('accept all cookies')) {
                b.click();
                return 'clicked';
            }
        }
        return 'no button';
    }
    """)
    log(f"Cookie: {result}")
    time.sleep(2)

    # Navigate to apply URL
    page.goto("https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)

    log(f"\nFinal URL: {page.url}")

    log("\nAll logged requests/responses:")
    for r in requests_log:
        log(f"  {r}")
    for r in responses_log:
        log(f"  {r}")

    # Check cookies - what consent cookies exist?
    cookies = ctx.cookies()
    log(f"\nAll cookies for aosmith.com domain:")
    for c in cookies:
        if "aosmith" in c.get("domain", "") or "successfactors" in c.get("domain", ""):
            log(f"  {c['name']}={c['value'][:50]} (domain={c['domain']})")

    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
