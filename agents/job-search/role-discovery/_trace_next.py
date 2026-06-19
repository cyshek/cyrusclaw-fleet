#!/usr/bin/env python3
"""After filling page 1, click Next, observe what comes next over time."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"
sys.path.insert(0, str(HERE))
from workday_playwright import fill_page1_my_information, load_personal_info

info = load_personal_info()

DBG = HERE.parent / ".workday-debug" / "p1-next-trace"
DBG.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / "adobe-trace"),
        headless=True, viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    page.click("[data-automation-id=applyManually]")
    page.wait_for_timeout(4000)
    fill_page1_my_information(page, info, "trace")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(DBG / "01-p1-filled.png"), full_page=True)
    # Click Next
    page.click('[data-automation-id="pageFooterNextButton"]')
    print("Clicked Next at", page.url)
    # Trace
    for i in range(8):
        page.wait_for_timeout(2000)
        body = (page.locator("body").text_content() or "")[:1500]
        url = page.url
        title = page.title()
        print(f"\n--- T+{(i+1)*2}s URL={url}")
        print(f"TITLE: {title}")
        print(f"BODY:\n{body}")
        page.screenshot(path=str(DBG / f"t{(i+1)*2:02d}s.png"), full_page=True)
        # Detect step indicator
        step = page.evaluate("""
            () => {
              const cur = document.querySelector('[data-automation-id="progressBarActiveStep"]');
              return cur ? cur.textContent.trim() : 'N/A';
            }
        """)
        print(f"STEP: {step}")
    ctx.close()
