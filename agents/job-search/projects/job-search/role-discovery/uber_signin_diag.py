#!/usr/bin/env python3
"""
Deep diagnostic: what happens after Uber sign-in submit?
"""
import time, json, sys
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"

creds = json.loads(open(f"{RDIR}/.uber-creds.json").read())["account"]
EMAIL = creds["email"]
PASSWORD = creds["password"]

print(f"Email: {EMAIL[:30]}")

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

# Open fresh page
page = ctx.new_page()
job_id = "156921"

print(f"Navigating to job {job_id}...")
page.goto(f"https://www.uber.com/careers/list/{job_id}/", wait_until="domcontentloaded", timeout=45000)
time.sleep(2)

# Click apply
sel = f"a[href*='/careers/apply/interstitial/{job_id}']"
link = page.locator(sel).first
if link.count():
    link.click(timeout=8000)
else:
    page.goto(f"https://www.uber.com/careers/apply/interstitial/{job_id}", wait_until="domcontentloaded", timeout=30000)

# Wait for form URL
for _ in range(12):
    time.sleep(1.2)
    if f"/careers/apply/form/{job_id}" in page.url:
        break

time.sleep(2)
print(f"URL: {page.url}")
print(f"Has form: {page.locator('input[name=firstName]').count()}")
si_btn = page.locator("button:has-text('Sign in')").first
print(f"Has Sign in: {si_btn.count()}")

# Click sign in
page.screenshot(path="/tmp/uber_before_signin.png")
btn = page.locator("button:has-text('Sign in')").first
if not btn.count():
    print("No Sign in button!")
    sys.exit(1)

print("Clicking Sign in...")
btn.click(timeout=8000)
time.sleep(2)

print(f"After click URL: {page.url}")
page.screenshot(path="/tmp/uber_after_signin_click.png")

# Check what's visible
info = page.evaluate("""() => {
    const email = document.querySelector('input[name=email], input[type=email]');
    const pw = document.querySelector('input[name=password], input[type=password]');
    const firstName = document.querySelector('input[name=firstName]');
    const body = document.body.innerText.slice(0, 300);
    return {
        has_email: !!email,
        has_pw: !!pw,
        has_firstName: !!firstName,
        body_preview: body,
        url: window.location.href
    };
}""")
print(f"State: {json.dumps(info, indent=2)}")

if not info.get("has_email"):
    print("No email input! Exiting.")
    sys.exit(1)

# Fill credentials
print("Filling email...")
page.fill("input[name=email], input[type=email]", EMAIL)
time.sleep(0.5)
print("Filling password...")
page.fill("input[name=password], input[type=password]", PASSWORD)
time.sleep(0.5)
page.screenshot(path="/tmp/uber_filled_creds.png")

# Submit
for sel in ["button[type=submit]:has-text('Sign in')", "button:has-text('Sign in')"]:
    loc = page.locator(sel).last
    if loc.count():
        print(f"Clicking submit: {sel}")
        loc.click(timeout=8000)
        break

# Now poll carefully
for i in range(30):
    time.sleep(1.5)
    try:
        url = page.url
        has_form = page.locator("input[name=firstName]").count()
        body = page.inner_text("body").lower() if page.locator("body").count() else ""
        print(f"  t={i*1.5:.1f}s form={has_form} url={url[:60]}")
        if has_form:
            print("SUCCESS - form visible!")
            break
        if "verification code" in body or "enter the code" in body or "we sent" in body:
            print("VERIFICATION REQUIRED!")
            print(f"  body: {body[:200]}")
            page.screenshot(path="/tmp/uber_verification.png")
            break
        if "captcha" in body or "are you a robot" in body:
            print("CAPTCHA!")
            break
        if "invalid" in body and "password" in body:
            print("INVALID PASSWORD!")
            print(f"  body: {body[:200]}")
            break
        if i % 5 == 0:
            page.screenshot(path=f"/tmp/uber_poll_{i}.png")
    except Exception as exc:
        print(f"  t={i*1.5:.1f}s page error: {exc}")
        break

print("Final URL:", page.url)
page.screenshot(path="/tmp/uber_final.png")
print("Screenshots saved to /tmp/uber_*.png")
