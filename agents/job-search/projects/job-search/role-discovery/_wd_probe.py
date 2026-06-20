#!/usr/bin/env python3
"""Probe a Workday apply flow: goto apply URL, click Apply Manually, dump sign-in/create-account modal."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DBG = HERE.parent / ".workday-debug"
DBG.mkdir(exist_ok=True)

URL = sys.argv[1]
TENANT = sys.argv[2] if len(sys.argv) > 2 else "probe"

def dump(page, tag):
    print(f"\n===== {tag} =====")
    print("URL:", page.url)
    try: print("TITLE:", page.title())
    except Exception: pass
    page.screenshot(path=str(DBG / f"probe-{TENANT}-{tag}.png"), full_page=True)
    print("--- buttons/links ---")
    for b in page.locator("button, a[role=button], [role=button], a").all()[:50]:
        try:
            txt = (b.text_content() or "").strip()[:60]
            aid = b.get_attribute("data-automation-id") or ""
            if txt or aid:
                print(f"  [{aid}] {txt!r}")
        except Exception: pass
    print("--- inputs ---")
    for i in page.locator("input").all()[:30]:
        try:
            print(f"  id={i.get_attribute('id')!r} type={i.get_attribute('type')!r} aid={i.get_attribute('data-automation-id')!r}")
        except Exception: pass
    print("--- body[:1200] ---")
    print((page.locator("body").text_content() or "")[:1200])

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / TENANT),
        headless=True,
        viewport={"width": 1400, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    dump(page, "01-jd")
    # Find apply button
    for sel in ["[data-automation-id=applyManually]", "[data-automation-id=adventureButton]", "a[data-automation-id=applyButton]", "button:has-text('Apply')", "a:has-text('Apply')"]:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                print(f"\n>>> clicking {sel}")
                loc.click()
                page.wait_for_timeout(4000)
                break
        except Exception as e:
            print("  click fail", sel, e)
    dump(page, "02-after-apply")
    # If there's an Apply Manually option now
    try:
        am = page.locator("[data-automation-id=applyManually]").first
        if am.count() and am.is_visible():
            print("\n>>> clicking applyManually")
            am.click()
            page.wait_for_timeout(4000)
            dump(page, "03-after-manual")
    except Exception as e:
        print("manual fail", e)
    ctx.close()
