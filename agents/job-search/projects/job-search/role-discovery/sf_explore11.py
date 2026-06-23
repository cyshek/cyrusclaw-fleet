#!/usr/bin/env python3
"""Try fetching apply form from within browser context"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore11]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    page = ctx.new_page()

    # Load the job page first
    log("Loading job page...")
    page.goto("https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/", wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Accept cookies via button
    page.evaluate("""
    () => {
        var btns = document.querySelectorAll('button');
        for (var b of btns) {
            if (b.innerText.toLowerCase().includes('accept all cookies')) { b.click(); return 'clicked'; }
        }
        return 'not found';
    }
    """)
    time.sleep(2)

    # Check what session cookies we have
    cookies = ctx.cookies(["https://jobs.aosmith.com"])
    log(f"AO Smith cookies: {[(c['name'], c['value'][:30]) for c in cookies]}")

    # Now try to fetch the apply URL from within the browser (carries cookies)
    log("\nFetching apply URL from within browser...")
    result = page.evaluate("""
    async () => {
        const resp = await fetch('https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US', {
            method: 'GET',
            redirect: 'manual',
            credentials: 'include'
        });
        return {
            status: resp.status,
            type: resp.type,
            url: resp.url,
            headers: Object.fromEntries(resp.headers.entries())
        };
    }
    """)
    log(f"Fetch result: {json.dumps(result, indent=2)}")

    # Try setting cookies manually and navigating
    # The JSESSIONID from career8.successfactors.com is the key
    # Use the SF direct URL
    sf_url = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_listing&navBarLevel=JOB_DETAIL&rcm_site_locale=en_GB&career_job_req_id=1395242700&selected_lang=en_US&jobPipeline=LinkedIn&src=LinkedIn&site=&company=aosmith&lang=en_US"
    log(f"\nTrying SF direct URL: {sf_url[:100]}")
    page.goto(sf_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    log(f"URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/17-sf-direct.png")

    body = page.locator("body").inner_text()[:3000]
    log(f"Body: {body}")

    # If on SF, look for Apply button  
    links = page.eval_on_selector_all("a, button", "els => els.map(e => ({text: e.innerText.trim().substring(0,60), href: e.href || ''}))")
    for l in links:
        if "apply" in (l.get("text","") + l.get("href","")).lower() and l.get("text"):
            log(f"Apply: {l}")

    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
