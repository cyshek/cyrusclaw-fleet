#!/usr/bin/env python3
"""Explore SF apply form - force click the apply link"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
JOB_URL = "https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore5]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    
    page = ctx.new_page()
    log(f"Opening job page: {JOB_URL}")
    page.goto(JOB_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    
    # Accept cookies
    try:
        btn = page.locator("button:has-text('Accept All Cookies')").first
        if btn.is_visible(timeout=2000):
            btn.click(timeout=3000)
            time.sleep(1)
    except:
        pass
    
    # Navigate directly to apply URL to avoid the cookie/session redirect issue
    apply_url = "https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US"
    log(f"Navigating to: {apply_url}")
    page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    log(f"URL: {page.url}")
    log(f"Title: {page.title()}")
    
    page.screenshot(path=f"{DEBUG_DIR}/08-apply-after-cookie.png")
    
    body = page.locator("body").inner_text()[:5000]
    log(f"Body:\n{body}")
    
    # All form fields
    all_fields = page.locator("input, select, textarea").all()
    log(f"\nAll {len(all_fields)} form fields:")
    for f in all_fields[:80]:
        try:
            name = f.get_attribute("name") or ""
            fid = f.get_attribute("id") or ""
            ftype = f.get_attribute("type") or f.evaluate("el => el.tagName")
            if name or (fid and len(fid) > 2):
                log(f"  {ftype} name='{name}' id='{fid}'")
        except:
            pass
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
