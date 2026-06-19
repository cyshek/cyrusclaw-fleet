#!/usr/bin/env python3
"""Probe a Workday dropdown to list its options."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "role-discovery"))
from playwright.sync_api import sync_playwright
import workday_playwright as wp

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".workday-browser-data" / "adobe"
URL = "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"

import shutil
if DATA.exists(): shutil.rmtree(DATA)
DATA.mkdir(parents=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(DATA), headless=True,
        viewport={"width":1400,"height":900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)
    if page.locator('[data-automation-id="applyManually"]').count():
        page.click('[data-automation-id="applyManually"]')
        page.wait_for_timeout(4000)
    info = wp.load_personal_info()

    # Drive to voluntary
    for i in range(6):
        step = wp.detect_step(page)
        print(f"iter{i}: {step}")
        if 'voluntary' in step.lower(): break
        kind = wp.classify_step(step)
        if kind == "info": wp.fill_my_information(page, info, "probe")
        elif kind == "exp": wp.fill_my_experience(page, info, "probe")
        elif kind == "questions": wp.fill_application_questions(page, info, "probe")
        wp.click_next(page, "probe", f"to-vol")
        page.wait_for_timeout(7000)

    # Probe each dropdown
    for did in ['personalInfoUS--veteranStatus','personalInfoUS--gender','personalInfoUS--ethnicity']:
        btn = page.locator(f"#{did}").first
        btn.scroll_into_view_if_needed()
        btn.click()
        page.wait_for_timeout(700)
        opts = page.evaluate("""()=>{
          return Array.from(document.querySelectorAll('[role=option]')).map(o=>o.textContent.trim()).filter(t=>t);
        }""")
        print(f"\n{did} options ({len(opts)}):")
        for o in opts: print('  -', o)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    ctx.close()
