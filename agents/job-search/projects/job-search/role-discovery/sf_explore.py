#!/usr/bin/env python3
"""Explore the SF apply form for A.O. Smith"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
SF_APPLY_URL = "https://career8.successfactors.com/career?company=aosmith&jobId=1395242700"

def log(*a):
    print("[sf-explore]", *a, flush=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    
    page = ctx.new_page()
    log("Opening SF apply form directly...")
    page.goto(SF_APPLY_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    log(f"URL: {page.url}")
    log(f"Title: {page.title()}")
    
    os.makedirs("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug", exist_ok=True)
    page.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug/02-sf-apply-page.png")
    log("Screenshot saved")
    
    # Look for the form fields
    fields = page.locator("input, select, textarea").all()
    log(f"\nFound {len(fields)} form fields:")
    for f in fields[:80]:
        try:
            name = f.get_attribute("name") or ""
            fid = f.get_attribute("id") or ""
            ftype = f.get_attribute("type") or f.evaluate("el => el.tagName")
            log(f"  name='{name}' id='{fid}' type='{ftype}'")
        except:
            pass
    
    # Page content snippet
    body_text = page.locator("body").inner_text()[:3000]
    log(f"\nPage body snippet:\n{body_text}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
