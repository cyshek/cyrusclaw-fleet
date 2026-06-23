#!/usr/bin/env python3
"""Explore the SF CX Apply form for AO Smith"""
from playwright.sync_api import sync_playwright
import json, time, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

def log(*a):
    print("[cx-explore]", *a, flush=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()    
    # Navigate to job detail page
    job_url = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_listing&career_job_req_id=27523"
    log(f"Loading job detail: {job_url}")
    page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    page.screenshot(path=f"{DEBUG_DIR}/30-sf-job-detail.png")
    log(f"Title: {page.title()}")
    
    # Extract secKey from the page
    sec_key = page.evaluate("""
    () => {
        var btn = document.querySelector('#applyButton_top');
        if (!btn) return null;
        var onclick = btn.getAttribute('onclick');
        var m = onclick.match(/jobSecKey:\\s*'([^']+)'/);
        return m ? m[1] : null;
    }
    """)
    log(f"secKey: {(sec_key or 'NOT FOUND')[:30]}...")
    
    if not sec_key:
        log("ERROR: Could not find secKey - checking page state")
        log(f"URL: {page.url}")
        body_txt = page.locator("body").inner_text()[:1000]
        log(f"Body: {body_txt}")
        page.close()
        browser.close()
        pw.stop()
        exit(1)
    
    # Use JavaScript to simulate what applyJobReq does for guest user
    log("Simulating Apply button click for guest...")
    page.evaluate("""
    (secKey) => {
        function setField(id, val) {
            var el = document.getElementById(id);
            if (el) el.value = val;
        }
        setField('joblist_jobApplyRedirect', 'applyRedirected');
        setField('career_job_req_sec_key', secKey);
        setField('career_job_req_id', '27523');
        setField('navBarLevel', 'JOB_SEARCH');
        setField('career_os', 'job_listing');
        setField('isApplyWithLinkedIn', 'false');
        setField('career_ns', 'job_save');
    }
    """, sec_key)
    
    # Submit the form
    log("Submitting form to navigate to apply flow...")
    with page.expect_navigation(timeout=20000):
        page.evaluate("() => document.querySelector('form#careerform').submit()")
    
    time.sleep(5)
    
    log(f"After Apply - URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/31-sf-after-apply-click.png")
    
    body = page.locator("body").inner_text()[:2000]
    log(f"Body: {body}")
    
    # Look for form fields - especially the classic fbclc_ fields
    fields = page.evaluate("""
    () => {
        var inputs = document.querySelectorAll('input[name], select[name], textarea[name]');
        var result = [];
        for (var i=0; i<Math.min(inputs.length, 60); i++) {
            var el = inputs[i];
            result.push({tag: el.tagName, name: el.name, id: el.id, type: el.type || 'N/A', value: (el.value || '').substring(0,30)});
        }
        return result;
    }
    """)
    log(f"\nForm fields ({len(fields)}):")
    for f in fields:
        if f.get('type') not in ('hidden',) or f.get('name','').startswith(('fb', 'tor', 'fbjq')):
            log(f"  {f}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
