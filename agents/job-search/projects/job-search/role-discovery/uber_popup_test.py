#!/usr/bin/env python3
"""
Sign in by capturing the popup that opens when clicking Sign in.
"""
import time, json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"

creds = json.loads(open(f"{RDIR}/.uber-creds.json").read())["account"]
EMAIL = creds["email"]
PASSWORD = creds["password"]

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]

# Close all Uber tabs
for p in list(ctx.pages):
    try:
        if "uber.com" in p.url:
            p.close()
    except:
        pass
time.sleep(0.5)

page = ctx.new_page()
page.goto("https://www.uber.com/careers/list/156921/", wait_until="domcontentloaded", timeout=45000)
time.sleep(2)

sel = "a[href*='/careers/apply/interstitial/156921']"
link = page.locator(sel).first
if link.count():
    link.click(timeout=8000)
else:
    page.goto("https://www.uber.com/careers/apply/interstitial/156921", wait_until="domcontentloaded", timeout=30000)

for _ in range(12):
    time.sleep(1.2)
    if "/careers/apply/form/156921" in page.url:
        break

time.sleep(2)
print(f"At: {page.url}")

# Capture the popup
print("Clicking Sign in with expect_page...")
with ctx.expect_page(timeout=10000) as new_page_info:
    btn = page.locator("button:has-text('Sign in')").first
    btn.click(timeout=8000)

new_page = new_page_info.value
print(f"New page: {new_page.url}")
new_page.wait_for_load_state("domcontentloaded", timeout=15000)
time.sleep(2)
print(f"New page after load: {new_page.url}")

new_page.screenshot(path="/tmp/uber_popup.png")
print("Screenshot: /tmp/uber_popup.png")

# Check state of both pages
print(f"Original page still open: {not page.is_closed()}")
for p2 in ctx.pages:
    try:
        print(f"  Page: {p2.url[:80]}")
    except:
        print(f"  Page: (closed)")

# Try to fill sign-in on new page
has_email = new_page.locator("input[name=email], input[type=email]").count()
print(f"New page has email input: {has_email}")

body = new_page.inner_text("body").lower() if not new_page.is_closed() else ""
print(f"New page body preview: {body[:300]}")
