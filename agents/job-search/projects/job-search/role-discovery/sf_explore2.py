#!/usr/bin/env python3
"""Find the actual apply URL and form for A.O. Smith SF"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
JOB_URL = "https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/"

def log(*a):
    print("[sf-explore2]", *a, flush=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    
    page = ctx.new_page()
    log(f"Opening job page: {JOB_URL}")
    page.goto(JOB_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)
    
    log(f"URL: {page.url}")
    log(f"Title: {page.title()}")
    
    os.makedirs("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug", exist_ok=True)
    page.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug/03-job-page.png")
    
    # Accept cookies if present
    try:
        btn = page.locator("button:has-text('Accept All Cookies')").first
        if btn.is_visible(timeout=2000):
            btn.click()
            log("Accepted cookies")
            time.sleep(1)
    except:
        pass
    
    # Look for Apply button  
    page.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug/04-job-page-noncookies.png")
    
    body_text = page.locator("body").inner_text()[:3000]
    log(f"Page body:\n{body_text}")
    
    # Find apply links
    hrefs = page.eval_on_selector_all("a", "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))")
    for h in hrefs:
        if "apply" in (h.get("text","") + h.get("href","")).lower():
            log(f"Apply link: {h}")
    
    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
