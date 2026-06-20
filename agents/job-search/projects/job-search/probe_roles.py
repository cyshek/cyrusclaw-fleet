from playwright.sync_api import sync_playwright
import time, sqlite3

role_checks = [
    (1394, "https://explore.jobs.netflix.net/careers/job/790294851634"),
    (2874, "https://explore.jobs.netflix.net/careers/job/790313893634"),
    (2875, "https://explore.jobs.netflix.net/careers/job/790313892634"),
    (2870, "https://explore.jobs.netflix.net/careers/job/790313870634"),
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
            closed = "may have closed" in body or "no longer available" in body
            print(f"Role {role_id}: URL={page.url} closed={closed}")
        except Exception as e:
            print(f"Role {role_id}: error={e}")
    page.close()
