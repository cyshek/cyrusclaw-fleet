#!/usr/bin/env python3
"""Check if signing in opens a new CDP target."""
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
        if "uber.com/careers" in p.url:
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
print(f"At form URL: {page.url}")
print(f"Pages before sign-in click: {len(ctx.pages)}")
for p2 in ctx.pages:
    try:
        print(f"  - {p2.url[:80]}")
    except:
        print("  - (closed)")

# Listen for new pages
new_pages = []
def on_page(new_page):
    new_pages.append(new_page)
    print(f"NEW PAGE OPENED: {new_page.url}")
ctx.on("page", on_page)

# Click Sign in button on account card
print("\nClicking Sign in on account card...")
btn = page.locator("button:has-text('Sign in')").first
btn.click(timeout=8000)
time.sleep(2)

print(f"\nPages after click: {len(ctx.pages)}")
for p2 in ctx.pages:
    try:
        print(f"  - {p2.url[:80]}")
    except:
        print("  - (closed)")

print(f"New pages opened: {len(new_pages)}")

# Try to fill on same page
has_email = page.locator("input[name=email], input[type=email]").count()
print(f"Has email on original page: {has_email}")

# Check if any new page has email
for np in new_pages:
    try:
        ne = np.locator("input[name=email], input[type=email]").count()
        print(f"New page {np.url[:60]} has email: {ne}")
    except:
        print("New page closed")

page.screenshot(path="/tmp/uber_after_acct_click.png")
print("Screenshot: /tmp/uber_after_acct_click.png")
