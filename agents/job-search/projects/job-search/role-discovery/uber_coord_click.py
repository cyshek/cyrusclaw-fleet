#!/usr/bin/env python3
"""
Test sign-in with coordinate-based click and proper button identification.
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

# Monitor responses
resps = []
def on_r(r):
    try:
        resps.append(f"{r.status} {r.url[:100]}")
    except:
        pass
page.on("response", on_r)

page.goto("https://www.uber.com/careers/list/156921/", wait_until="domcontentloaded", timeout=45000)
time.sleep(2)
link = page.locator("a[href*='/careers/apply/interstitial/156921']").first
if link.count():
    link.click(timeout=8000)
else:
    page.goto("https://www.uber.com/careers/apply/interstitial/156921", wait_until="domcontentloaded", timeout=30000)
for _ in range(12):
    time.sleep(1.2)
    if "/careers/apply/form/156921" in page.url:
        break
time.sleep(2)

# Click Sign in button
btn = page.locator("button:has-text('Sign in')").first
btn.click(timeout=8000)
time.sleep(1.5)

# Fill credentials
page.fill("input[name=email], input[type=email]", EMAIL)
time.sleep(0.3)
page.fill("input[name=password], input[type=password]", PASSWORD)
time.sleep(0.5)

# Identify all submit buttons precisely
btn_details = page.evaluate("""() => {
    const btns = [...document.querySelectorAll('button[type=submit]')];
    return btns.map((b, i) => {
        const rect = b.getBoundingClientRect();
        return {
            idx: i,
            text: (b.innerText||'').trim().slice(0,40),
            disabled: b.disabled,
            x: Math.round(rect.x + rect.width/2),
            y: Math.round(rect.y + rect.height/2),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            visible: rect.width > 0 && rect.height > 0
        };
    });
}""")
print("Submit buttons:")
for b in btn_details:
    print(f"  {b}")

# Find the visible Sign in button INSIDE the dialog
# The dialog should be inside a modal/dialog element
dialog_btn = page.evaluate("""() => {
    const dialogs = document.querySelectorAll('[role=dialog], [aria-modal=true], .modal, [class*=modal], [class*=Modal], [class*=dialog]');
    for (const d of dialogs) {
        const btn = d.querySelector('button[type=submit]');
        if (btn) {
            const rect = btn.getBoundingClientRect();
            return {
                found: true,
                text: btn.innerText.trim(),
                x: Math.round(rect.x + rect.width/2),
                y: Math.round(rect.y + rect.height/2),
                dialogClass: d.className.slice(0,60)
            };
        }
    }
    return {found: false};
}""")
print(f"Dialog button: {dialog_btn}")

page.screenshot(path="/tmp/uber_before_click.png")
resps_before = len(resps)

# Try clicking via JS form submit
js_submit = page.evaluate("""() => {
    const forms = document.querySelectorAll('form');
    for (const form of forms) {
        const email = form.querySelector('input[name=email], input[type=email]');
        if (email) {
            console.log('Found form with email input');
            return {found: true, action: form.action, method: form.method};
        }
    }
    return {found: false};
}""")
print(f"Form info: {js_submit}")

if js_submit.get("found"):
    print("Submitting via form.submit()...")
    page.evaluate("""() => {
        const forms = document.querySelectorAll('form');
        for (const form of forms) {
            if (form.querySelector('input[name=email], input[type=email]')) {
                form.submit();
                return;
            }
        }
    }""")
    time.sleep(3)
    print(f"New responses: {resps[resps_before:]}")
    print(f"Has form: {page.locator('input[name=firstName]').count()}")
else:
    # Try clicking using coordinates
    if btn_details:
        # Use the LAST visible submit button (should be modal's Sign In)
        visible = [b for b in btn_details if b['visible'] and b['text'] and 'sign' in b['text'].lower()]
        if visible:
            target = visible[-1]  # last = modal submit
            print(f"Clicking by coordinates: ({target['x']}, {target['y']})")
            page.mouse.click(target['x'], target['y'])
            time.sleep(5)
            print(f"New responses: {resps[resps_before:]}")
            print(f"Has form: {page.locator('input[name=firstName]').count()}")

page.screenshot(path="/tmp/uber_after_click.png")
print("Done. Screenshots in /tmp/uber_*.png")
