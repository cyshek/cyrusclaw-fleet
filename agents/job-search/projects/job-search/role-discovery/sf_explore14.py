#!/usr/bin/env python3
"""Wait for SF SPA to render and then navigate to apply form"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore14]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    page = ctx.new_page()
    # Go to job detail URL on SF
    job_url = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_listing&career_job_req_id=1395242700"
    log(f"Loading: {job_url}")
    page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
    
    # Wait for the SPA to render - look for specific elements
    log("Waiting for SPA to render...")
    for i in range(10):
        time.sleep(2)
        body = page.locator("body").inner_text()
        if len(body.strip()) > 100:
            log(f"SPA rendered after {(i+1)*2}s, body length: {len(body)}")
            break
        log(f"  Waiting... ({i+1})")
    
    log(f"URL: {page.url}")
    page.screenshot(path=f"{DEBUG_DIR}/20-sf-spa-rendered.png")
    
    body = page.locator("body").inner_text()[:4000]
    log(f"Body:\n{body}")
    
    # Wait for apply button
    try:
        page.wait_for_selector("#fbqa_apply, a[id*='apply'], button[id*='apply'], #apply", timeout=10000)
        log("Found apply button!")
    except:
        log("No apply button found by id")
    
    # Look for all form elements
    fields = page.locator("input, select, textarea, a, button").all()
    log(f"\n{len(fields)} interactive elements:")
    for f in fields[:30]:
        try:
            name = f.get_attribute("name") or ""
            fid = f.get_attribute("id") or ""
            ftype = f.get_attribute("type") or f.evaluate("el => el.tagName")
            txt = f.inner_text().strip()[:40] if f.evaluate("el => el.tagName") in ("A","BUTTON") else ""
            log(f"  {ftype} id='{fid}' name='{name}' text='{txt}'")
        except:
            pass
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
