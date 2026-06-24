#!/usr/bin/env python3
"""
Sign in by detecting the new page that opens after clicking Sign in.
The original page closes, but a new page opens - we need to capture that.
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

# Set up new page listener BEFORE clicking
new_pages = []
def on_page(new_page):
    new_pages.append(new_page)
    print(f"NEW PAGE: {new_page.url}")
ctx.on("page", on_page)

pages_before = set(id(p) for p in ctx.pages)
print(f"Pages before: {len(ctx.pages)}")

# Click Sign in - expect it to close original page
print("Clicking Sign in...")
try:
    btn = page.locator("button:has-text('Sign in')").first
    btn.click(timeout=8000)
    print("Click succeeded (no error)")
except Exception as exc:
    print(f"Click error (expected): {type(exc).__name__}: {str(exc)[:100]}")

# Wait a moment for new page to appear
time.sleep(2)
print(f"New pages captured: {len(new_pages)}")
print(f"All ctx pages now: {len(ctx.pages)}")
for p2 in ctx.pages:
    try:
        print(f"  - {p2.url[:100]}")
    except:
        print(f"  - (error)")

# Find the new Uber page
uber_pages = []
for p2 in ctx.pages:
    try:
        if "uber.com" in p2.url:
            uber_pages.append(p2)
    except:
        pass

if uber_pages:
    sign_page = uber_pages[0]
    print(f"Uber page: {sign_page.url}")
    sign_page.wait_for_load_state("domcontentloaded", timeout=15000)
    time.sleep(2)
    print(f"After load: {sign_page.url}")
    sign_page.screenshot(path="/tmp/uber_sign_page.png")
    has_email = sign_page.locator("input[name=email], input[type=email]").count()
    print(f"Has email: {has_email}")
    body = sign_page.inner_text("body").lower()[:400]
    print(f"Body: {body}")
elif new_pages:
    for np in new_pages:
        try:
            np.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(2)
            print(f"New page final URL: {np.url}")
            np.screenshot(path="/tmp/uber_new_page.png")
        except Exception as e:
            print(f"New page error: {e}")
else:
    print("No Uber pages found!")
    # Check all pages
    for p2 in ctx.pages:
        try:
            p2.screenshot(path="/tmp/uber_remaining_page.png")
            print(f"Saved screenshot of: {p2.url[:80]}")
            break
        except:
            pass
