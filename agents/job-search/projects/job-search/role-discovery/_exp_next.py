#!/usr/bin/env python3
"""Fill experience page, click Next, see what errors come back."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from workday_playwright import (
    fill_my_information, fill_my_experience, click_next, load_personal_info, detect_step, check_errors, screenshot
)

URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"
info = load_personal_info()

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / "adobe-exp-next"),
        headless=True, viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    page.click("[data-automation-id=applyManually]")
    page.wait_for_timeout(4000)
    fill_my_information(page, info, "exp-next")
    click_next(page, "exp-next", "p1")
    page.wait_for_timeout(6000)
    fill_my_experience(page, info, "exp-next")
    page.wait_for_timeout(2000)
    # Just click Next regardless of fill status
    click_next(page, "exp-next", "p2")
    page.wait_for_timeout(6000)
    print("STEP after next:", detect_step(page))
    print("ERRORS:", check_errors(page))
    # Dump every error message
    errs2 = page.evaluate("""
        () => {
          const out = [];
          // Workday error: each invalid field has an error-msg sibling
          document.querySelectorAll('[role=alert], [data-automation-id*="error" i], .Error, .errorMessage').forEach(e => {
            const t = (e.textContent || '').trim();
            if (t) out.push({id: e.id, text: t.slice(0,200)});
          });
          return out;
        }
    """)
    print(f"\n--- {len(errs2)} error-like elements ---")
    for e in errs2[:20]:
        print(f"  {e}")
    # Also: text labeled "Errors Found" or similar at top of page
    body = page.locator('body').text_content() or ""
    if "Errors Found" in body or "Error" in body:
        # Find the error block
        idx = body.find("Errors Found")
        if idx >= 0:
            print(f"\nERRORS BLOCK:\n{body[idx:idx+1500]}")
    DBG = HERE.parent / ".workday-debug" / "exp-next-state"
    DBG.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(DBG / "after-next.png"), full_page=True)
    ctx.close()
