from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # Try the job page first
    job_url = "https://explore.jobs.netflix.net/careers/job/790314061634"
    print("Navigating to job page:", job_url)
    try:
        page.goto(job_url, wait_until="networkidle", timeout=20000)
    except:
        page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(2)
    print("Job page URL:", page.url)
    print("Job page title:", page.title())
    try:
        body = page.inner_text("body", timeout=5000)
        print("Body snippet:", body[:400])
    except Exception as e:
        print("err:", e)

    # Check if there is an Apply button
    apply_btn = page.locator("text=Apply")
    print("Apply button count:", apply_btn.count())

    page.close()
