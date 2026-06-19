from playwright.sync_api import sync_playwright
import time

role_checks = [
    (1394, "https://explore.jobs.netflix.net/careers/job/790315659551"),
    (2870, "https://explore.jobs.netflix.net/careers/job/790313094223"),
    (2874, "https://explore.jobs.netflix.net/careers/job/790314668577"),
    (2875, "https://explore.jobs.netflix.net/careers/job/790315885533"),
]

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    for role_id, url in role_checks:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)
            body = page.inner_text("body", timeout=3000)
            closed = "may have closed" in body.lower() or "no longer available" in body.lower()
            print(f"Role {role_id}: closed={closed} url={page.url[:80]}")
            if not closed:
                print(f"  Body: {body[:200]}")
        except Exception as e:
            print(f"Role {role_id}: error={e}")
    page.close()
