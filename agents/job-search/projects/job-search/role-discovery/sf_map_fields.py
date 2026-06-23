#!/usr/bin/env python3
"""Map all fields on the AO Smith SF registration+apply form"""
from playwright.sync_api import sync_playwright
import json, time, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

def log(*a):
    print("[sf-map]", *a, flush=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()    
    # Navigate to register page via sign-in redirect
    log("Loading register page...")
    page.goto("https://career8.successfactors.com/career?company=aosmith&career_ns=job_save&career_job_req_id=27523&navBarLevel=JOB_SEARCH&career_os=job_listing&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    
    create_link = page.evaluate("() => { var l = document.querySelector('a[href*=\"register\"]'); return l ? l.href : null; }")
    if create_link:
        page.goto(create_link, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)
    log(f"Register page: {page.url}")
    
    # Get ALL form fields including hidden ones for understanding state
    all_fields = page.evaluate("""
    () => {
        var inputs = document.querySelectorAll('input, select, textarea');
        var result = [];
        for (var i=0; i<inputs.length; i++) {
            var el = inputs[i];
            var label = '';
            if (el.id) {
                var lbl = document.querySelector('label[for="' + el.id + '"]');
                if (lbl) label = lbl.innerText.trim().substring(0,80);
            }
            result.push({
                tag: el.tagName,
                name: el.name || '',
                id: el.id || '',
                type: el.type || 'N/A',
                value: (el.value || '').substring(0,40),
                checked: el.checked,
                label: label
            });
        }
        return result;
    }
    """)
    log(f"\nAll form fields ({len(all_fields)}):")
    for f in all_fields:
        # Show all non-standard-hidden fields
        if f.get('type') not in ('hidden',) or any(x in f.get('name','') for x in ('fbclc', 'tor__', 'fbjq', 'searPref', 'privacy', 'fbqa', 'career')):
            log(f"  {f}")
    
    # Look specifically for profile visibility and privacy fields
    log("\nLooking for fbclc_searPref and privacy fields...")
    priv_fields = page.evaluate("""
    () => {
        var result = {};
        
        // Profile visibility
        var searPref = document.querySelectorAll('[name="fbclc_searPref"]');
        result.searPref = Array.from(searPref).map(el => ({id: el.id, value: el.value, checked: el.checked}));
        
        // Privacy 
        var privacyLink = document.querySelector('#dataPrivacyId');
        result.privacyLink = privacyLink ? {id: privacyLink.id, href: privacyLink.href, text: privacyLink.innerText.substring(0,50)} : null;
        
        // Get page HTML around privacy
        var privacySection = document.querySelector('[id*=privacy], [class*=privacy]');
        result.privacySection = privacySection ? privacySection.outerHTML.substring(0,300) : null;
        
        return result;
    }
    """)
    log(f"Privacy fields: {json.dumps(priv_fields, indent=2)}")
    
    # Look for tor__ fields
    log("\nLooking for tor__ fields...")
    tor_fields = page.evaluate("""
    () => {
        var inputs = document.querySelectorAll('[name^="tor__"]');
        return Array.from(inputs).map(el => {
            var label = '';
            if (el.id) {
                var lbl = document.querySelector('label[for="' + el.id + '"]');
                if (lbl) label = lbl.innerText.trim().substring(0,80);
            }
            return {tag: el.tagName, name: el.name, id: el.id, type: el.type || 'select', value: el.value || '', label: label};
        });
    }
    """)
    log(f"tor__ fields: {json.dumps(tor_fields, indent=2)}")
    
    # Look for fbjq_ fields (screening questions)
    log("\nLooking for fbjq_ fields...")
    fbjq_fields = page.evaluate("""
    () => {
        var inputs = document.querySelectorAll('[name^="fbjq_"]');
        return Array.from(inputs).map(el => ({tag: el.tagName, name: el.name, id: el.id, type: el.type, value: el.value || ''}));
    }
    """)
    log(f"fbjq_ fields: {json.dumps(fbjq_fields[:10], indent=2)}")
    
    # Look for file upload (resume)
    log("\nLooking for file upload / resume field...")
    file_fields = page.evaluate("""
    () => {
        var files = document.querySelectorAll('input[type="file"]');
        return Array.from(files).map(el => ({id: el.id, name: el.name, accept: el.accept}));
    }
    """)
    log(f"File fields: {file_fields}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
