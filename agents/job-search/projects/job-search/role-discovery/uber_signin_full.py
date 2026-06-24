#!/usr/bin/env python3
"""
Full sign-in flow test - carefully fill and submit credentials.
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
print(f"Form URL: {page.url}")

# Check current state
state = page.evaluate("""() => {
    const btns = [...document.querySelectorAll('button')].map(b => ({text: (b.innerText||'').trim().slice(0,40), type: b.type}));
    const inputs = [...document.querySelectorAll('input')].map(i => ({name: i.name, type: i.type, id: i.id}));
    return {btns, inputs};
}""")
print(f"Buttons: {[b for b in state['btns'] if b['text']][:10]}")
print(f"Inputs: {state['inputs'][:10]}")

# Click Sign in button
print("\nStep 1: Click Sign in on account card")
btn = page.locator("button:has-text('Sign in')").first
btn.click(timeout=8000)
time.sleep(1.5)
page.screenshot(path="/tmp/s1_after_click.png")

state2 = page.evaluate("""() => {
    const inputs = [...document.querySelectorAll('input')].map(i => ({name:i.name, type:i.type, id:i.id, visible: window.getComputedStyle(i).display !== 'none'}));
    const btns = [...document.querySelectorAll('button')].filter(b=>(b.innerText||'').trim()).map(b => ({text:(b.innerText||'').trim().slice(0,40), type:b.type, disabled:b.disabled}));
    return {inputs, btns};
}""")
print(f"After click - inputs: {[i for i in state2['inputs'] if i['visible']]}")
print(f"After click - buttons: {state2['btns'][:10]}")

# Fill email
email_inp = page.locator("input[name=email], input[type=email]").first
if email_inp.count():
    print(f"\nStep 2: Fill email ({EMAIL})")
    email_inp.fill(EMAIL, timeout=5000)
    time.sleep(0.5)
    val = email_inp.input_value()
    print(f"Email value after fill: {val[:30]}")

# Fill password  
pw_inp = page.locator("input[name=password], input[type=password]").first
if pw_inp.count():
    print(f"Step 3: Fill password")
    pw_inp.fill(PASSWORD, timeout=5000)
    time.sleep(0.5)

page.screenshot(path="/tmp/s2_filled.png")

# Find the submit button
submit_info = page.evaluate("""() => {
    const btns = [...document.querySelectorAll('button')];
    return btns.filter(b=>(b.innerText||'').includes('Sign in') || b.type==='submit').map(b=>({
        text:(b.innerText||'').trim(), type:b.type, disabled:b.disabled,
        visible: window.getComputedStyle(b).display !== 'none'
    }));
}""")
print(f"Submit candidates: {submit_info}")

# Click submit
print("\nStep 4: Click submit")
submit = page.locator("button[type=submit]:has-text('Sign in'), dialog button:has-text('Sign in'), [role=dialog] button:has-text('Sign in')").last
if not submit.count():
    submit = page.locator("button:has-text('Sign in')").last

print(f"Submit button count: {submit.count()}")
submit.click(timeout=8000)
page.screenshot(path="/tmp/s3_after_submit.png")

# Poll for form
print("\nPolling for form...")
for i in range(20):
    time.sleep(1.5)
    has_form = page.locator("input[name=firstName]").count()
    if has_form:
        print(f"SUCCESS at t={i*1.5}s - form visible!")
        break
    try:
        body = page.inner_text("body").lower()[:200]
        print(f"  t={i*1.5}s: form={has_form} body={body[:80]}")
    except Exception as exc:
        print(f"  t={i*1.5}s: page error {exc}")
        break

page.screenshot(path="/tmp/s4_final.png")
print("Done. Screenshots in /tmp/s*.png")
