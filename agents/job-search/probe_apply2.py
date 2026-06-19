from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    apply_url = "https://explore.jobs.netflix.net/careers/apply?pid=790314061634"
    print("Navigating:", apply_url)
    try:
        page.goto(apply_url, wait_until="networkidle", timeout=20000)
    except Exception as e:
        print("networkidle timeout, trying domcontentloaded")
        try:
            page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e2:
            print("navigation failed:", e2)
    time.sleep(3)
    print("URL:", page.url)
    print("Title:", page.title())
    has_form = page.locator("#Contact_Information_email").count()
    print("Email field:", has_form)
    try:
        body = page.inner_text("body", timeout=5000)
        print("Body:", body[:500])
    except Exception as e:
        print("Body err:", e)
    page.close()
