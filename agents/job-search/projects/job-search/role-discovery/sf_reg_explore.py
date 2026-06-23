#!/usr/bin/env python3
"""Explore the SF register/create-account form"""
from playwright.sync_api import sync_playwright
import json, time, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

def log(*a):
    print("[sf-reg]", *a, flush=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    # First go to the sign-in page to establish session + get cookies
    log("Step 1: Loading sign-in page...")
    signin_url = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_save&career_job_req_id=27523&navBarLevel=JOB_SEARCH&career_os=job_listing&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected"
    page.goto(signin_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)
    page.screenshot(path=f"{DEBUG_DIR}/40-signin.png")
    log(f"Title: {page.title()}, URL: {page.url}")
    
    # Look for "Create account" link and click it
    log("Step 2: Finding and clicking Create Account link...")
    create_link = page.evaluate("""
    () => {
        var links = document.querySelectorAll('a[href*="register"]');
        if (links.length) return links[0].href;
        
        // Try text match
        var all = document.querySelectorAll('a');
        for (var l of all) {
            if (/create.*account|not.*registered|new.*user/i.test(l.innerText)) {
                return l.href;
            }
        }
        return null;
    }
    """)
    log(f"Create account link: {create_link}")
    
    if create_link:
        page.goto(create_link, wait_until="domcontentloaded", timeout=30000)
    else:
        # Navigate directly to register URL
        register_url = "https://career8.successfactors.com/career?company=aosmith&login_ns=register&career_ns=job_save&career_os=job_listing&career_job_req_id=27523&navBarLevel=JOB_SEARCH"
        log(f"Navigating directly to: {register_url}")
        page.goto(register_url, wait_until="domcontentloaded", timeout=30000)
    
    time.sleep(5)
    log(f"Register page URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/41-register-page.png")
    
    body = page.locator("body").inner_text()[:2000]
    log(f"Body:\n{body}")
    
    # Enumerate all form fields
    fields = page.evaluate("""
    () => {
        var inputs = document.querySelectorAll('input, select, textarea');
        var result = [];
        for (var i=0; i<Math.min(inputs.length, 100); i++) {
            var el = inputs[i];
            var label = '';
            // Try to find label
            if (el.id) {
                var lbl = document.querySelector('label[for="' + el.id + '"]');
                if (lbl) label = lbl.innerText.trim().substring(0,50);
            }
            result.push({
                tag: el.tagName,
                name: el.name || '',
                id: el.id || '',
                type: el.type || 'N/A',
                value: (el.value || '').substring(0,30),
                label: label
            });
        }
        return result;
    }
    """)
    log(f"\nAll form fields ({len(fields)}):")
    for f in fields:
        if f.get('type') not in ('hidden',) or any(f.get('name','').startswith(x) for x in ('fb', 'tor', 'fbjq', '_s', 'career')):
            log(f"  {f}")
    
    # Check page source for fbclc_ fields
    src = page.content()
    fb_fields = [l for l in src.split('\n') if 'fbclc_' in l or 'tor__' in l or 'fbqa_' in l]
    log(f"\nLines with fb/tor/fbqa:")
    for l in fb_fields[:20]:
        log(f"  {l.strip()[:120]}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
