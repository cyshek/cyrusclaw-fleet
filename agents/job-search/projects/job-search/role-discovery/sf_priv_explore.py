#!/usr/bin/env python3
"""Explore the privacy modal and check post-account-creation apply form"""
from playwright.sync_api import sync_playwright
import json, time, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

def log(*a):
    print("[sf-priv]", *a, flush=True)

def fill_input(page, sel, val):
    page.evaluate("""
    ([sel, val]) => {
        var el = document.querySelector(sel);
        if (!el) return;
        var ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        ns.call(el, val);
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur', {bubbles:true}));
    }
    """, [sel, val])

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()    
    # Navigate to register page
    log("Loading register page...")
    page.goto("https://career8.successfactors.com/career?company=aosmith&career_ns=job_save&career_job_req_id=27523&navBarLevel=JOB_SEARCH&career_os=job_listing&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    create_link = page.evaluate("() => { var l = document.querySelector('a[href*=\"register\"]'); return l ? l.href : null; }")
    if create_link:
        page.goto(create_link, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)
    
    # Look for privacy link in the page source
    privacy_html = page.evaluate("""
    () => {
        // Look for dataPrivacy link
        var link = document.querySelector('#dataPrivacyId, a[id*="privacy"], a[class*="privacy"], .privacyPolicy a');
        
        // Look in the full page for any "data privacy" text
        var body = document.body.innerHTML;
        var idx = body.toLowerCase().indexOf('dataprivacy');
        if (idx < 0) idx = body.toLowerCase().indexOf('data privacy');
        
        var snippet = idx >= 0 ? body.substring(Math.max(0, idx-200), Math.min(body.length, idx+500)) : 'NOT FOUND';
        
        return {
            link: link ? {id: link.id, href: link.href, text: link.innerText, outerHTML: link.outerHTML} : null,
            snippet: snippet
        };
    }
    """)
    log(f"Privacy link info:")
    log(f"  link: {privacy_html.get('link')}")
    log(f"  snippet: {privacy_html.get('snippet', '')[:400]}")
    
    # Look for all links that might be privacy-related
    all_links = page.evaluate("""
    () => {
        var result = [];
        var links = document.querySelectorAll('a');
        for (var l of links) {
            var text = (l.innerText || '').toLowerCase();
            var href = l.href || '';
            if (/privacy|terms|data|agreement/i.test(text + href)) {
                result.push({text: l.innerText.trim().substring(0,60), href: href, id: l.id});
            }
        }
        return result;
    }
    """)
    log(f"\nPrivacy/terms links: {all_links}")
    
    # Now let's fill the form and check what appears when we try to open the privacy modal
    # Fill the form first
    log("\nFilling form...")
    fill_input(page, '#fbclc_userName', 'cyshekari+test99@gmail.com')
    fill_input(page, '#fbclc_emailConf', 'cyshekari+test99@gmail.com')
    fill_input(page, '#fbclc_pwd', 'Cyrus2026!Apply')
    fill_input(page, '#fbclc_pwdConf', 'Cyrus2026!Apply')
    fill_input(page, '#fbclc_fName', 'Cyrus')
    fill_input(page, '#fbclc_lName', 'Shekari')
    page.evaluate("""
    () => {
        var sel = document.querySelector('select[name="fbclc_country"]');
        if (sel) { sel.value = 'US'; sel.dispatchEvent(new Event('change', {bubbles:true})); }
    }
    """)
    
    # Click profile visibility value=2
    page.evaluate("""
    () => {
        var radios = document.querySelectorAll('[name="fbclc_searPref"]');
        for (var r of radios) {
            if (r.value === '2') { r.click(); break; }
        }
    }
    """)
    
    time.sleep(1)
    page.screenshot(path=f"{DEBUG_DIR}/60-before-privacy.png")
    
    # Look for privacy-related content after filling
    privacy_after = page.evaluate("""
    () => {
        // Check body text for privacy-related elements
        var allText = document.body.innerText;
        var privIdx = allText.toLowerCase().indexOf('privacy');
        return {
            bodyPrivacy: privIdx >= 0 ? allText.substring(Math.max(0, privIdx-100), Math.min(allText.length, privIdx+300)) : 'NOT IN BODY',
            // Check for links in the page
            links: Array.from(document.querySelectorAll('a')).map(l => ({id:l.id, text:l.innerText.trim().substring(0,60), href:(l.href||'').substring(0,80)}))
        };
    }
    """)
    log(f"\nBody privacy context: {privacy_after.get('bodyPrivacy', '')[:300]}")
    log(f"\nAll links:")
    for l in privacy_after.get('links', [])[:20]:
        log(f"  {l}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
