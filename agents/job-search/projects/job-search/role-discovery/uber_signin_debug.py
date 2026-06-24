#!/usr/bin/env python3
"""
Try Uber sign-in and capture the exact state after sign-in attempt.
Check for error messages and network errors.
"""
import time, json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery"

creds = json.loads(open(f"{RDIR}/.uber-creds.json").read())["account"]
EMAIL = creds["email"]
PASSWORD = creds["password"]
print(f"Attempting sign-in with: {EMAIL}")

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

# Capture console errors
console_msgs = []
page.on("console", lambda msg: console_msgs.append(f"{msg.type}: {msg.text[:100]}"))
page.on("pageerror", lambda err: console_msgs.append(f"PAGEERROR: {str(err)[:100]}"))

# Capture ALL network
network = []
def on_r(r):
    try:
        network.append({"status": r.status, "url": r.url[:120]})
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

# Click Sign in
page.locator("button:has-text('Sign in')").first.click(timeout=8000)
time.sleep(1.5)

# Fill credentials
page.fill("input[name=email], input[type=email]", EMAIL)
time.sleep(0.3)
page.fill("input[name=password], input[type=password]", PASSWORD)
time.sleep(0.5)

network_before = len(network)

# Click the dialog's Sign in button (use JS click to trigger React handler)
clicked = page.evaluate("""() => {
    // Find the Sign in button inside the modal/dialog
    const allBtns = [...document.querySelectorAll('button[type=submit]')];
    const visible = allBtns.filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && b.innerText.includes('Sign');
    });
    if (visible.length > 0) {
        // Use React's synthetic event
        const btn = visible[visible.length - 1];  // last visible sign in btn
        btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        return {clicked: true, btn_text: btn.innerText, x: btn.getBoundingClientRect().x, y: btn.getBoundingClientRect().y};
    }
    return {clicked: false};
}""")
print(f"Click result: {clicked}")

# Wait and check
for i in range(12):
    time.sleep(1)
    # Check for errors  
    err_text = page.evaluate("""() => {
        const errs = [...document.querySelectorAll('[role=alert], [aria-live=polite], [class*=error], [class*=Error]')];
        return errs.map(e => e.innerText.trim().slice(0, 100)).filter(t => t);
    }""")
    if err_text:
        print(f"  t={i}s ERRORS: {err_text}")
    
    has_form = page.locator("input[name=firstName]").count()
    if has_form:
        print(f"  t={i}s SUCCESS - form visible!")
        break
    
    # Show new network calls
    new_net = network[network_before:]
    if new_net:
        print(f"  t={i}s network: {[r['url'] for r in new_net[-3:]]}")
        network_before = len(network)

print(f"\nConsole messages:")
for m in console_msgs[-10:]:
    print(f"  {m}")

print(f"\nAll network calls during signin (non-static):")
for r in network[network_before-20:]:
    if any(x in r['url'] for x in ['uber.com', 'auth', 'login']):
        print(f"  {r['status']} {r['url']}")

page.screenshot(path="/tmp/uber_signin_result.png")
