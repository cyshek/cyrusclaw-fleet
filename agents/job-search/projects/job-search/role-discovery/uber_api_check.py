#!/usr/bin/env python3
"""
Check Uber sign-in API responses.
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

for p in list(ctx.pages):
    try:
        if "uber.com" in p.url:
            p.close()
    except:
        pass
time.sleep(0.5)

page = ctx.new_page()

# Intercept ALL requests/responses
api_calls = []
def on_response(resp):
    try:
        u = resp.url
        if "uber.com" in u and ("auth" in u.lower() or "account" in u.lower() or "login" in u.lower() or "signin" in u.lower()):
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                body = resp.text()
                api_calls.append({"url": u[:100], "status": resp.status, "body": body[:500]})
    except:
        pass

page.on("response", on_response)

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

# Click Sign in
btn = page.locator("button:has-text('Sign in')").first
btn.click(timeout=8000)
time.sleep(1.5)

# Fill
page.fill("input[name=email], input[type=email]", EMAIL)
time.sleep(0.3)
page.fill("input[name=password], input[type=password]", PASSWORD)
time.sleep(0.3)

# Monitor API calls during submit
print("API calls before submit:", len(api_calls))
for c in api_calls:
    print(f"  {c['status']} {c['url']}")
    print(f"  {c['body'][:200]}")

api_calls.clear()

# Click submit
page.locator("button[type=submit]:has-text('Sign in')").last.click(timeout=8000)

# Wait and monitor
for i in range(15):
    time.sleep(1)
    if page.locator("input[name=firstName]").count():
        print(f"SUCCESS at t={i}s")
        break

print(f"\nAPI calls during submit: {len(api_calls)}")
for c in api_calls:
    print(f"  {c['status']} {c['url']}")
    print(f"  {c['body'][:400]}")
    print()

# Check network logs more broadly
page2 = ctx.new_page()
all_calls = []
def on_resp2(resp):
    try:
        all_calls.append({"url": resp.url[:120], "status": resp.status})
    except:
        pass
page2.on("response", on_resp2)
page2.goto("about:blank")
