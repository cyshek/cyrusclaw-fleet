#!/usr/bin/env python3
"""Quick exploration: visit Adobe apply URL with Playwright headless, dump initial page state."""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DBG = HERE.parent / ".workday-debug"
DBG.mkdir(exist_ok=True)

URL = sys.argv[1] if len(sys.argv) > 1 else "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"

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
    # Take a screenshot
    page.screenshot(path=str(DBG / "01-initial.png"), full_page=True)
    # Dump button/link text
    btns = page.locator("button, a[role=button], [role=button]").all()
    print(f"\n--- {len(btns)} buttons/links ---")
    for b in btns[:40]:
        try:
            txt = (b.text_content() or "").strip()[:80]
            aid = b.get_attribute("data-automation-id") or ""
            if txt or aid:
                print(f"  [{aid}] {txt!r}")
        except Exception:
            pass
    # Dump headings
    print("\n--- headings ---")
    for h in page.locator("h1, h2, h3").all()[:20]:
        try:
            print(" ", (h.text_content() or "").strip()[:120])
        except Exception:
            pass
    # Dump body text snippet
    body = page.locator("body").text_content() or ""
    print("\n--- body[:1000] ---")
    print(body[:1000])
    ctx.close()
