#!/usr/bin/env python3
"""Test moniker selection on Adobe Page 1 - try multiple strategies to pick 'LinkedIn'."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / "adobe-monikertest"),
        headless=True, viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    page.click("[data-automation-id=applyManually]")
    page.wait_for_timeout(4000)

    DBG = HERE.parent / ".workday-debug" / "moniker-test"
    DBG.mkdir(parents=True, exist_ok=True)

    # Strategy 1: click source field, dump what becomes visible
    page.click("#source--source")
    page.wait_for_timeout(800)
    page.screenshot(path=str(DBG / "01-source-opened.png"), full_page=True)
    # Look for promptOptions
    opts = page.evaluate("""
        () => Array.from(document.querySelectorAll('[data-automation-id="promptOption"]')).map(o => ({
            id: o.id, label: o.getAttribute('data-automation-label'), text: o.textContent.trim()
        }))
    """)
    print(f"\n--- {len(opts)} promptOptions visible ---")
    for o in opts[:15]:
        print(f"  {o}")

    # Strategy 2: try clicking 'Social Media' to expand
    page.wait_for_timeout(500)
    sm = page.locator('[data-automation-id="promptOption"][data-automation-label="Social Media"]').first
    if sm.count():
        sm.click(force=True)
        page.wait_for_timeout(800)
        page.screenshot(path=str(DBG / "02-social-media-clicked.png"), full_page=True)
        opts2 = page.evaluate("""
            () => Array.from(document.querySelectorAll('[data-automation-id="promptOption"]')).map(o => ({
                id: o.id, label: o.getAttribute('data-automation-label'), text: o.textContent.trim()
            }))
        """)
        print(f"\n--- {len(opts2)} promptOptions after Social Media click ---")
        for o in opts2[:15]:
            print(f"  {o}")
        # Try LinkedIn
        li = page.locator('[data-automation-id="promptOption"][data-automation-label="LinkedIn"]').first
        if li.count():
            li.click(force=True)
            page.wait_for_timeout(800)
            page.screenshot(path=str(DBG / "03-linkedin-picked.png"), full_page=True)
            print("\nLinkedIn clicked")
        else:
            print("\nLinkedIn option not found")
    else:
        print("\nSocial Media option not found")

    # Check selected
    sel = page.evaluate("""
        () => Array.from(document.querySelectorAll('[data-automation-id="selectedItem"]')).map(s => s.textContent.trim())
    """)
    print(f"\nSelected items: {sel}")
    ctx.close()
