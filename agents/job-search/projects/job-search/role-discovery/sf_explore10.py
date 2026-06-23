#!/usr/bin/env python3
"""Analyze the redirect chain for talentcommunity/apply URL"""
from playwright.sync_api import sync_playwright
import json, time, sys, os

CDP_URL = "http://127.0.0.1:18800"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug"

def log(*a):
    print("[sf-explore10]", *a, flush=True)

os.makedirs(DEBUG_DIR, exist_ok=True)

pw = sync_playwright().start()
try:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    # Keep track of ALL responses for the talentcommunity URL
    resp_details = []

    page = ctx.new_page()

    def on_response(resp):
        if "talentcommunity" in resp.url or "successfactors" in resp.url or "apply" in resp.url.lower():
            try:
                headers = {k: v for k, v in resp.headers.items() if k.lower() in ("location", "set-cookie", "content-type", "x-redirect")}
                resp_details.append({"status": resp.status, "url": resp.url, "headers": headers})
            except Exception:
                pass

    page.on("response", on_response)

    # First, use requests/curl to see raw response
    import subprocess
    result = subprocess.run(
        ["curl", "-I", "-L", "-b", "JSESSIONID=144A1D080A6F3B72CE74CD2324F898E1.pc70bcar1010",
         "https://jobs.aosmith.com/talentcommunity/apply/1395242700/?locale=en_US"],
        capture_output=True, text=True, timeout=15
    )
    log(f"Curl output:\n{result.stdout[:2000]}")

    # Also try with requests
    log("\nDone.")
    page.close()
    browser.close()
finally:
    pw.stop()
