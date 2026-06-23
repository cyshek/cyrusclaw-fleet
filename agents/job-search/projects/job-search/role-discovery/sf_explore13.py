#!/usr/bin/env python3
"""Navigate SF careers portal to find the Product Manager job and apply form"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore13]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    page = ctx.new_page()
    # Go to SF career portal directly
    sf_career_url = "https://career8.successfactors.com/careers?company=aosmith"
    log(f"Loading SF career portal: {sf_career_url}")
    page.goto(sf_career_url, wait_until="networkidle", timeout=30000)
    time.sleep(5)

    log(f"URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/18-sf-career-portal.png")

    # Get body text
    body = page.locator("body").inner_text()[:3000]
    log(f"Body:\n{body}")

    # Look for job search / job links
    links = page.eval_on_selector_all("a", "els => els.map(e => ({text: e.innerText.trim().substring(0,80), href: e.href}))")
    log(f"\nLinks ({len(links)}):")
    for l in links[:30]:
        if l.get("text") or l.get("href"):
            log(f"  {l}")

    # Try direct job URL: /career?company=aosmith&career_ns=job_listing&career_job_req_id=1395242700
    job_detail_url = "https://career8.successfactors.com/career?company=aosmith&career_ns=job_listing&career_job_req_id=1395242700"
    log(f"\nNavigating to job detail: {job_detail_url}")
    page.goto(job_detail_url, wait_until="networkidle", timeout=30000)
    time.sleep(5)

    log(f"Job detail URL: {page.url}")
    log(f"Title: {page.title()}")
    page.screenshot(path=f"{DEBUG_DIR}/19-sf-job-detail.png")

    body2 = page.locator("body").inner_text()[:3000]
    log(f"Body:\n{body2}")

    # Look for Apply button
    apply_links = page.eval_on_selector_all("a, button", "els => els.map(e => ({text: e.innerText.trim().substring(0,80), href: e.href || '', id: e.id}))")
    log(f"\nApply items:")
    for l in apply_links:
        if "apply" in (l.get("text","") + l.get("id","") + l.get("href","")).lower() and l.get("text"):
            log(f"  {l}")

    page.close()
    browser.close()
finally:
    pw.stop()
log("Done.")
