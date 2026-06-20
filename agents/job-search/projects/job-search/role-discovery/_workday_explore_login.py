#!/usr/bin/env python3
"""Explore Adobe Workday sign-in / create-account page."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DBG = HERE.parent / ".workday-debug"
DBG.mkdir(exist_ok=True)

# Direct create-account / login URL
URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/login"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / "adobe"),
        headless=True,
        viewport={"width": 1400, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)
    print("URL:", page.url)
    print("TITLE:", page.title())
    page.screenshot(path=str(DBG / "02-login.png"), full_page=True)
    btns = page.locator("button, a[role=button], [role=button]").all()
    print(f"\n--- {len(btns)} buttons/links ---")
    for b in btns[:30]:
        try:
            txt = (b.text_content() or "").strip()[:80]
            aid = b.get_attribute("data-automation-id") or ""
            if txt or aid:
                print(f"  [{aid}] {txt!r}")
        except Exception: pass
    print("\n--- inputs ---")
    for i in page.locator("input").all()[:20]:
        try:
            print(f"  id={i.get_attribute('id')!r} name={i.get_attribute('name')!r} type={i.get_attribute('type')!r} aid={i.get_attribute('data-automation-id')!r}")
        except Exception: pass
    print("\n--- body[:1500] ---")
    print((page.locator("body").text_content() or "")[:1500])
    ctx.close()
