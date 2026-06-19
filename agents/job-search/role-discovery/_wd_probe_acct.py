#!/usr/bin/env python3
"""Probe Workday create-account modal after clicking 'Sign in with email'."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DBG = HERE.parent / ".workday-debug"
DBG.mkdir(exist_ok=True)
URL = sys.argv[1]
TENANT = sys.argv[2]

def dump(page, tag):
    print(f"\n===== {tag} =====")
    print("URL:", page.url)
    page.screenshot(path=str(DBG / f"acct-{TENANT}-{tag}.png"), full_page=True)
    print("--- buttons/links ---")
    for b in page.locator("button, a[role=button], [role=button], a").all()[:40]:
        try:
            txt = (b.text_content() or "").strip()[:60]
            aid = b.get_attribute("data-automation-id") or ""
            if txt or aid: print(f"  [{aid}] {txt!r}")
        except Exception: pass
    print("--- inputs ---")
    for i in page.locator("input").all()[:30]:
        try:
            print(f"  id={i.get_attribute('id')!r} type={i.get_attribute('type')!r} aid={i.get_attribute('data-automation-id')!r} name={i.get_attribute('name')!r}")
        except Exception: pass
    print("--- body[:800] ---")
    print((page.locator("body").text_content() or "")[:800])

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / TENANT),
        headless=True, viewport={"width": 1400, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    # click sign in with email
    try:
        page.locator("[data-automation-id=SignInWithEmailButton]").first.click()
        page.wait_for_timeout(3500)
    except Exception as e: print("email btn fail", e)
    dump(page, "01-email-signin")
    # Look for Create Account link
    for sel in ["[data-automation-id=createAccountLink]", "button:has-text('Create Account')", "a:has-text('Create Account')", "text=Create Account"]:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                print(f"\n>>> clicking {sel}")
                loc.click(); page.wait_for_timeout(3500); break
        except Exception as e: print("  fail", sel, e)
    dump(page, "02-create-account")
    ctx.close()
