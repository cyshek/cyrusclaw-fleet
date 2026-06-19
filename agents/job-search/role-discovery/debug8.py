from playwright.sync_api import sync_playwright
import json, time

CDP_URL = "http://127.0.0.1:19223"
APPLY_URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315885533"

captured = []

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    
    def on_request(req):
        if any(x in req.url for x in ["submit", "apply", "api/", "application", "eightfold"]):
            captured.append({"type": "request", "url": req.url[:150], "method": req.method})
            print("REQ:", req.method, req.url[:120])
    
    def on_response(resp):
        if any(x in resp.url for x in ["submit", "apply", "api/", "application", "eightfold"]):
            captured.append({"type": "response", "url": resp.url[:150], "status": resp.status})
            print("RESP:", resp.status, resp.url[:120])
    
    page.on("request", on_request)
    page.on("response", on_response)
    page.goto(APPLY_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    try: page.evaluate("() => { var s = document.getElementById(\"onetrust-consent-sdk\"); if (s) s.remove(); }")
    except: pass
    # Dismiss any existing form state by pressing Submit and watching
    btn = page.locator("button:has-text(\"Submit application\")").first
    print("Button disabled:", btn.is_disabled())
    print("Clicking...")
    btn.click(timeout=5000)
    time.sleep(10)
    print("Captured events:", captured)
    page.close()
