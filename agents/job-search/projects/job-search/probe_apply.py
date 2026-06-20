from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    
    apply_url = "https://explore.jobs.netflix.net/careers/apply?pid=790314061634"
    print(f"Navigating to: {apply_url}")
    
    try:
        page.goto(apply_url, wait_until="networkidle", timeout=20000)
    except Exception as e:\n        print(f"networkidle timeout: {e}")
        try:
            page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e2:
            print(f"Navigation failed: {e2}")
    
    time.sleep(2)
    
    current_url = page.url
    print(f"Current URL: {current_url}")
    title = page.title()
    print(f"Page title: {title}")
    
    has_form = page.locator("#Contact_Information_email").count()
    print(f"Email field present: {has_form}")
    
    try:
        body = page.inner_text("body", timeout=5000)
        print(f"Body snippet: {body[:500]}")
    except Exception as e:\n        print(f"Body read error: {e}")
    
    page.close()
