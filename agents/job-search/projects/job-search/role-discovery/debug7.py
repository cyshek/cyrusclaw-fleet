from playwright.sync_api import sync_playwright
import json

CDP_URL = "http://127.0.0.1:19223"
APPLY_URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315885533"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.goto(APPLY_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    # Check efUserInteractionHistory
    ef_hist = page.evaluate("() => localStorage.getItem(\"efUserInteractionHistory\")")
    print("efUserInteractionHistory:", ef_hist)
    # Check if there is an already applied cookie or similar
    cookies = ctx.cookies()
    print("Cookie count:", len(cookies))
    for c in cookies[:10]:
        print(" ", c.get("name"), "=", str(c.get("value",""))[:40])
    page.close()
