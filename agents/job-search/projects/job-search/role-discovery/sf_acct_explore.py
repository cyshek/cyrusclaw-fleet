#!/usr/bin/env python3
"""Explore the full SF account creation + apply form flow"""
from playwright.sync_api import sync_playwright
import json, time, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

def log(*a):
    print("[sf-acct]", *a, flush=True)

def set_input_native(page, selector, value):
    """Fill input via native value-setter + events"""
    page.evaluate("""
    ([sel, val]) => {
        var el = document.querySelector(sel);
        if (!el) return false;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeInputValueSetter.call(el, val);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        el.dispatchEvent(new Event('blur', {bubbles: true}));
        return true;
    }
    """, [selector, value])

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()    
    # Navigate to sign-in page (the landing after apply click)
    signin_url = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_save&career_job_req_id=27523&navBarLevel=JOB_SEARCH&career_os=job_listing&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected"
    log(f"Loading sign-in page: {signin_url}")
    page.goto(signin_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    log(f"URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/32-signin-page.png")
    
    body = page.locator("body").inner_text()[:1000]
    log(f"Body: {body}")
    
    # Look for "Create account" link
    create_link = page.evaluate("""
    () => {
        var links = document.querySelectorAll('a');
        for (var l of links) {
            if (/create|account|sign.*up|new.*user|register/i.test(l.innerText + l.href)) {
                return {text: l.innerText.trim(), href: l.href, id: l.id};
            }
        }
        return null;
    }
    """)
    log(f"Create account link: {create_link}")
    
    # Look for newMemberSignup or similar
    signup_btn = page.evaluate("""
    () => {
        var els = document.querySelectorAll('[id*=signup], [id*=register], [id*=newMember], [class*=signup]');
        return Array.from(els).map(e => ({id: e.id, text: e.innerText?.trim()?.substring(0,50), href: e.href}));
    }
    """)
    log(f"Signup elements: {signup_btn[:5]}")
    
    # Try navigating to the "Create account" page directly
    # The classic SF create-account URL pattern
    create_url = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_create_account&career_job_req_id=27523"
    log(f"\nNavigating to create account URL: {create_url}")
    page.goto(create_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    log(f"URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/33-create-account.png")
    body = page.locator("body").inner_text()[:1500]
    log(f"Body: {body}")
    
    # Check for classic SF account fields
    fields = page.evaluate("""
    () => {
        var inputs = document.querySelectorAll('input[name], select[name], textarea[name]');
        var result = [];
        for (var i=0; i<Math.min(inputs.length, 80); i++) {
            var el = inputs[i];
            if (el.type !== 'hidden' || el.name.startsWith('fb') || el.name.startsWith('tor')) {
                result.push({tag: el.tagName, name: el.name, id: el.id, type: el.type || 'N/A', value: (el.value || '').substring(0,20)});
            }
        }
        return result;
    }
    """)
    log(f"\nForm fields ({len(fields)}):")
    for f in fields:
        log(f"  {f}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
