#!/usr/bin/env python3
"""Capture ALL responses during sign-in."""
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

# Capture ALL responses
all_responses = []
def on_response(resp):
    try:
        all_responses.append({"url": resp.url[:120], "status": resp.status})
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

before_count = len(all_responses)
print(f"Responses so far: {before_count}")

# Click Sign in
btn = page.locator("button:has-text('Sign in')").first
btn.click(timeout=8000)
time.sleep(1.5)

# Fill
page.fill("input[name=email], input[type=email]", EMAIL)
time.sleep(0.3)
page.fill("input[name=password], input[type=password]", PASSWORD)
time.sleep(0.3)

# Clear before submit
new_responses = []
def on_response2(resp):
    try:
        new_responses.append({"url": resp.url[:120], "status": resp.status})
    except:
        pass
page.on("response", on_response2)

# Click submit
page.locator("button[type=submit]:has-text('Sign in')").last.click(timeout=8000)
time.sleep(8)

print(f"Responses after submit: {len(new_responses)}")
for r in new_responses:
    print(f"  {r['status']} {r['url']}")

# Check page state
state = page.evaluate("""() => {
    const form = document.querySelector('input[name=firstName]');
    const signin = document.querySelector('button:contains("Sign in")');
    const err = [...document.querySelectorAll('[class*=error],[class*=Error],[role=alert]')].map(e=>e.innerText.slice(0,60));
    const body = document.body.innerText.slice(0, 300);
    return {has_form: !!form, body_preview: body, errors: err};
}""")
print(f"\nPage state: form={state.get('has_form')}")
print(f"Errors: {state.get('errors')}")
print(f"Body: {state.get('body_preview','')[:200]}")
