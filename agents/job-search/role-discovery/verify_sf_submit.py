"""Verify the Salesforce submission landed in Candidate Home."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

CREDS = json.loads(Path(__file__).resolve().parent.parent.joinpath('.workday-creds.json').read_text())
EMAIL = CREDS['tenants']['salesforce']['email']
PASS = CREDS['shared_password']

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(Path(__file__).resolve().parent.parent / ".workday-browser-data" / "salesforce"),
        headless=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://salesforce.wd12.myworkdayjobs.com/External_Career_Site/userHome", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    print("URL:", page.url)
    if 'login' in page.url:
        try:
            page.fill('[data-automation-id="email"]', EMAIL)
            page.fill('[data-automation-id="password"]', PASS)
            page.locator('[data-automation-id="click_filter"][aria-label="Sign In"]').first.click()
            page.wait_for_timeout(5000)
            print("after signin URL:", page.url)
        except Exception as e:
            print("signin err:", e)
    page.wait_for_timeout(3000)
    body = page.evaluate("() => document.body.innerText.slice(0, 3000)")
    print("BODY:")
    print(body)
    page.screenshot(path='/tmp/sf-userhome.png', full_page=True)
    ctx.close()
