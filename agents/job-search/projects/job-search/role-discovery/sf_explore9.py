#!/usr/bin/env python3
"""Try giving all cookie consents and then navigate to apply form"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore9]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    page = ctx.new_page()
    log("Loading job page...")
    page.goto("https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Find and click all cookie consent buttons - look for the cookie settings first
    page.screenshot(path=f"{DEBUG_DIR}/14-before-cookies.png")

    # List all buttons
    btns = page.eval_on_selector_all("button", "els => els.map(e => ({id: e.id, text: e.innerText.trim(), cls: e.className.substring(0,60), vis: e.offsetParent !== null}))")
    log(f"Buttons found: {len(btns)}")
    for b in btns:
        if any(w in b.get("text","").lower() + b.get("id","").lower() for w in ["cookie", "accept", "privacy", "consent", "modify"]):
            log(f"  {b}")

    # Click "Accept All Cookies" button
    result = page.evaluate("""
    () => {
        // First look for the main accept button
        var btns = document.querySelectorAll('button');
        for (var b of btns) {
            if (b.innerText.toLowerCase().includes('accept all cookies')) {
                b.click();
                return 'clicked: ' + b.innerText.trim();
            }
        }
        return 'not found';
    }
    """)
    log(f"Cookie click: {result}")
    time.sleep(2)
    page.screenshot(path=f"{DEBUG_DIR}/15-after-accept-cookies.png")

    # Navigate to apply URL
    log("Navigating to apply URL...")
    page.goto("https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US", wait_until="domcontentloaded", timeout=20000)
    time.sleep(6)

    final_url = page.url
    log(f"URL: {final_url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/16-apply-url.png")

    if "1395242700" in final_url or "apply" in final_url.lower() or "career" in final_url:
        log("SUCCESS - we reached the apply form or a related page!")
        body = page.locator("body").inner_text()[:3000]
        log(f"Body: {body}")
    else:
        # The cookie consent for SAPasserviceprovider is a required cookie - check the checkbox
        log("Still redirected, checking consent modal...")
        # Go back to job page and look for the cookie modal structure
        page.goto("https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Check cookie modal HTML
        modal_html = page.evaluate("""
        () => {
            var modal = document.querySelector('#cookieConsentModal, .cookie-modal, [id*="cookie"], [class*="cookie"]');
            return modal ? modal.outerHTML.substring(0, 2000) : 'no modal found';
        }
        """)
        log(f"Cookie modal HTML: {modal_html}")

        # Check the SAPasserviceprovider checkbox
        sap_check_result = page.evaluate("""
        () => {
            var inputs = document.querySelectorAll('input[type=checkbox]');
            var results = [];
            for (var inp of inputs) {
                results.push({id: inp.id, name: inp.name, checked: inp.checked});
            }
            return results;
        }
        """)
        log(f"Checkboxes: {sap_check_result}")

        # All page body text
        body = page.locator("body").inner_text()[:5000]
        log(f"Body: {body}")

    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
