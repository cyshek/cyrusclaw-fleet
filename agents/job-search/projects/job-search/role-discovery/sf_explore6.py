#!/usr/bin/env python3
"""Navigate to AO Smith job page, accept cookies, then click Apply"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
JOB_URL = "https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore6]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    
    page = ctx.new_page()
    log(f"Opening job page: {JOB_URL}")
    page.goto(JOB_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    
    log(f"URL after load: {page.url}")
    page.screenshot(path=f"{DEBUG_DIR}/09-job-page-fresh.png")
    
    # Accept cookies - try multiple selectors
    accepted = False
    for btn_sel in [
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept all')",
        "button[id*='accept']",
        "#CybotCookiebotDialogBodyButtonAccept",
        ".cookie-accept",
        "button:has-text('Accept')",
    ]:
        try:
            btn = page.locator(btn_sel).first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=2000)
                log(f"Accepted cookies via: {btn_sel}")
                accepted = True
                time.sleep(2)
                break
        except:
            pass
    
    if not accepted:
        log("No cookie banner found, proceeding")
    
    # Check what buttons/links are now visible
    all_links = page.eval_on_selector_all("a, button", "els => els.map(e => ({tag: e.tagName, text: e.innerText.trim().substring(0,80), href: e.href || '', vis: e.offsetParent !== null}))")
    apply_items = [x for x in all_links if "apply" in (x.get("text","") + x.get("href","")).lower()]
    log(f"\nApply items ({len(apply_items)}):")
    for a in apply_items:
        log(f"  {a}")
    
    # Try force-navigate to apply URL  
    apply_url = "https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US"
    log(f"\nForce navigating to: {apply_url}")
    page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(6)
    
    log(f"URL after navigate: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/10-after-forced-apply.png")
    
    body = page.locator("body").inner_text()[:3000]
    log(f"Body:\n{body}")
    
    # If we're on the right form, enumerate fields
    fields = page.locator("input, select, textarea").all()
    log(f"\n{len(fields)} form fields:")
    for f in fields[:50]:
        try:
            name = f.get_attribute("name") or ""
            fid = f.get_attribute("id") or ""
            ftype = f.get_attribute("type") or f.evaluate("el => el.tagName")
            if name.startswith("fbclc") or name.startswith("tor__") or name.startswith("fbjq") or "email" in name.lower():
                log(f"  SF-FIELD: {ftype} name='{name}' id='{fid}'")
        except:
            pass
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
