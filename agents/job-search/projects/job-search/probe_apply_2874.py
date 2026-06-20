from playwright.sync_api import sync_playwright
import time

# Try the apply page for 2874 (TPM)
pid = "790314668577"
apply_url = f"https://explore.jobs.netflix.net/careers/apply?pid={pid}"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    print("Navigating:", apply_url)
    try:
        page.goto(apply_url, wait_until="networkidle", timeout=20000)
    except:
        page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(3)
    print("URL:", page.url)
    has_form = page.locator("#Contact_Information_email").count()
    print("Email field:", has_form)
    try:
        body = page.inner_text("body", timeout=5000)
        print("Body:", body[:400])
    except Exception as e:
        print("err:", e)
    page.close()
