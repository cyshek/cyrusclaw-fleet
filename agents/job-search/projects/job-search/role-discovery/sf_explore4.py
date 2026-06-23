#!/usr/bin/env python3
"""Explore the SF apply form for A.O. Smith - click through from job page"""
from playwright.sync_api import sync_playwright
import json, time, sys, os, re

CDP_URL = "http://127.0.0.1:18800"
JOB_URL = "https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore4]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    
    page = ctx.new_page()
    
    # Set up request interception to log redirects
    navigations = []
    page.on("response", lambda r: navigations.append(f"{r.status} {r.url[:100]}"))
    
    log(f"Opening job page: {JOB_URL}")
    page.goto(JOB_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    
    log(f"Current URL: {page.url}")
    
    # Accept cookies if present
    try:
        btn = page.locator("button:has-text('Accept All Cookies')").first
        if btn.is_visible(timeout=2000):
            btn.click()
            log("Accepted cookies")
            time.sleep(1)
    except:
        pass
    
    page.screenshot(path=f"{DEBUG_DIR}/06-job-detail.png")
    
    # Click "Apply now" link with talentcommunity
    log("Clicking Apply now link...")
    apply_link = page.locator("a[href*='talentcommunity/apply']").first
    apply_link.click()
    time.sleep(6)
    
    log(f"After click URL: {page.url}")
    log(f"Title: {page.title()}")
    
    page.screenshot(path=f"{DEBUG_DIR}/07-after-apply-click.png")
    
    # Check if we're on a real apply form
    fields = page.locator("input[name*='fbclc'], input[name*='tor__'], input[name*='fbjq']").all()
    log(f"SF-specific fields found: {len(fields)}")
    for f in fields[:20]:
        name = f.get_attribute("name") or ""
        fid = f.get_attribute("id") or ""
        ftype = f.get_attribute("type") or ""
        log(f"  {ftype} name='{name}' id='{fid}'")
    
    # All form fields
    all_fields = page.locator("input, select, textarea").all()
    log(f"\nAll {len(all_fields)} form fields:")
    for f in all_fields[:80]:
        try:
            name = f.get_attribute("name") or ""
            fid = f.get_attribute("id") or ""
            ftype = f.get_attribute("type") or f.evaluate("el => el.tagName")
            if name or (fid and fid not in ("", ":")):
                log(f"  {ftype} name='{name}' id='{fid}'")
        except:
            pass
    
    # Labels
    labels = page.locator("label").all()
    log(f"\nLabels ({len(labels)}):")
    for lbl in labels[:40]:
        try:
            txt = lbl.inner_text().strip()[:100]
            for_attr = lbl.get_attribute("for") or ""
            if txt:
                log(f"  [{for_attr}]: {txt}")
        except:
            pass
    
    body_text = page.locator("body").inner_text()[:5000]
    log(f"\nBody text:\n{body_text}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
