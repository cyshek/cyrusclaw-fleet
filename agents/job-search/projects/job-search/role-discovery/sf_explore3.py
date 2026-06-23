#!/usr/bin/env python3
"""Explore the actual SF apply form for A.O. Smith"""
from playwright.sync_api import sync_playwright
import json, time, sys, os, re

CDP_URL = "http://127.0.0.1:18800"
APPLY_URL = "https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US"

DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore3]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    
    page = ctx.new_page()
    log(f"Opening apply URL: {APPLY_URL}")
    page.goto(APPLY_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    log(f"Final URL: {page.url}")
    log(f"Title: {page.title()}")
    
    page.screenshot(path=f"{DEBUG_DIR}/05-apply-form.png")
    log("Screenshot: 05-apply-form.png")
    
    # All form fields
    fields = page.locator("input, select, textarea").all()
    log(f"\nFound {len(fields)} form fields:")
    for f in fields:
        try:
            name = f.get_attribute("name") or ""
            fid = f.get_attribute("id") or ""
            ftype = f.get_attribute("type") or f.evaluate("el => el.tagName")
            fval = ""
            try:
                fval = f.input_value(timeout=500) or ""
            except:
                pass
            if name or fid:
                log(f"  {ftype} name='{name}' id='{fid}' val='{fval[:50]}'")
        except:
            pass
    
    # All labels
    labels = page.locator("label").all()
    log(f"\nLabels ({len(labels)}):")
    for lbl in labels[:30]:
        try:
            txt = lbl.inner_text().strip()
            for_attr = lbl.get_attribute("for") or ""
            if txt:
                log(f"  label for='{for_attr}': {txt[:80]}")
        except:
            pass
    
    # Body text
    body_text = page.locator("body").inner_text()[:5000]
    log(f"\nFull page body:\n{body_text}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
