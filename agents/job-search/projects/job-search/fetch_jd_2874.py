from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.goto("https://explore.jobs.netflix.net/careers/job/790314668577", wait_until="domcontentloaded", timeout=20000)
    time.sleep(2)
    body = page.inner_text("body", timeout=5000)
    # Write to JD.md
    with open("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/netflix-2874/JD.md", "w") as f:
        f.write(body)
    print("JD.md written, length:", len(body))
    print("Snippet:", body[:400])
    page.close()
