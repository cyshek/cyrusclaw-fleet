#!/usr/bin/env python3
"""Full exploration: account creation -> apply form for AO Smith SF"""
from playwright.sync_api import sync_playwright
import json, time, os, random, string

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

def log(*a):
    print("[sf-full]", *a, flush=True)

def fill_input(page, selector, value):
    page.evaluate("""
    ([sel, val]) => {
        var el = typeof sel === 'string' ? document.querySelector(sel) : sel;
        if (!el) return false;
        var nativeSet = Object.getOwnPropertyDescriptor(
            el.tagName === 'INPUT' ? window.HTMLInputElement.prototype : window.HTMLTextAreaElement.prototype, 'value'
        ).set;
        nativeSet.call(el, val);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        el.dispatchEvent(new Event('blur', {bubbles: true}));
        return true;
    }
    """, [selector, value])

def select_option(page, name, value):
    page.evaluate("""
    ([name, val]) => {
        var sel = document.querySelector('select[name="' + name + '"]');
        if (!sel) return false;
        var nativeSet = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
        nativeSet.call(sel, val);
        sel.dispatchEvent(new Event('change', {bubbles: true}));
        return true;
    }
    """, [name, value])

# Generate unique email
UNIQUE = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
EMAIL = f"cyshekari+aosmith2280test{UNIQUE}@gmail.com"
PWD = "Cyrus2026!Apply"

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()    
    # Step 1: Navigate to Create Account page
    log("Step 1: Navigate to Create Account page...")
    # First load sign-in page to get a valid session
    signin_page = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_save&career_job_req_id=27523&navBarLevel=JOB_SEARCH&career_os=job_listing&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected"
    page.goto(signin_page, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    
    # Find and click Create Account link
    create_link = page.evaluate("""
    () => {
        var links = document.querySelectorAll('a[href*="register"]');
        return links.length ? links[0].href : null;
    }
    """)
    log(f"Create link: {create_link[:80] if create_link else 'NOT FOUND'}")
    
    if create_link:
        page.goto(create_link, wait_until="domcontentloaded", timeout=30000)
    else:
        page.goto("https://career8.successfactors.com/career?company=aosmith&login_ns=register&career_ns=job_save&career_os=job_listing&career_job_req_id=27523&navBarLevel=JOB_SEARCH", wait_until="domcontentloaded", timeout=30000)
    
    time.sleep(4)
    log(f"Create Account page: {page.url}")
    page.screenshot(path=f"{DEBUG_DIR}/50-create-account.png")
    
    # Fill account creation form
    log("Step 2: Filling create account form...")
    fill_input(page, '#fbclc_userName', EMAIL)
    fill_input(page, '#fbclc_emailConf', EMAIL)
    fill_input(page, '#fbclc_pwd', PWD)
    fill_input(page, '#fbclc_pwdConf', PWD)
    fill_input(page, '#fbclc_fName', 'Cyrus')
    fill_input(page, '#fbclc_lName', 'Shekari')
    
    # Country select - find US value
    country_val = page.evaluate("""
    () => {
        var sel = document.querySelector('select[name="fbclc_country"]');
        if (!sel) return null;
        for (var o of sel.options) {
            if (/united states/i.test(o.text)) return o.value;
        }
        return null;
    }
    """)
    log(f"US country value: {country_val}")
    if country_val:
        select_option(page, 'fbclc_country', country_val)
    
    time.sleep(1)
    page.screenshot(path=f"{DEBUG_DIR}/51-create-account-filled.png")
    log("Fields filled. Screenshotted.")
    
    # Check all visible required fields
    required = page.evaluate("""
    () => {
        var result = [];
        var req = document.querySelectorAll('[aria-required="true"], [required]');
        for (var el of req) {
            if (el.type !== 'hidden') {
                result.push({id: el.id, name: el.name, type: el.type, value: (el.value || '').substring(0, 30)});
            }
        }
        return result;
    }
    """)
    log(f"Required fields: {required}")
    
    # Click the Create Account button
    log("Step 3: Submitting Create Account...")
    create_btn = page.evaluate("() => document.querySelector('#fbclc_createAccountButton')?.id")
    log(f"Create button id: {create_btn}")
    
    page.evaluate("() => { var btn = document.querySelector('#fbclc_createAccountButton'); if (btn) btn.click(); }")
    
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except:
        pass
    time.sleep(5)
    
    log(f"After Create Account - URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/52-after-create-account.png")
    body = page.locator("body").inner_text()[:2000]
    log(f"Body:\n{body}")
    
    # Enumerate form fields if we're now on apply form
    fields = page.evaluate("""
    () => {
        var inputs = document.querySelectorAll('input[name], select[name], textarea[name]');
        var result = [];
        for (var i=0; i<Math.min(inputs.length, 100); i++) {
            var el = inputs[i];
            var label = '';
            if (el.id) {
                var lbl = document.querySelector('label[for="' + el.id + '"]');
                if (lbl) label = lbl.innerText.trim().substring(0,60);
            }
            result.push({tag: el.tagName, name: el.name, id: el.id, type: el.type || 'N/A', value: (el.value || '').substring(0,30), label: label});
        }
        return result;
    }
    """)
    log(f"\nForm fields after Create Account ({len(fields)}):")
    for f in fields:
        if f.get('type') not in ('hidden',) or any(f.get('name','').startswith(x) for x in ('fb', 'tor', 'fbjq', '_s', 'career')):
            log(f"  {f}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
