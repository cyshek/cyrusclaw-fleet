#!/usr/bin/env python3
"""Try other source picks and see which don't trigger followup question."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"

def test_source(path):
    user_dir = HERE.parent / ".workday-browser-data" / f"src-test-{'-'.join(path).replace('/', '_')}"
    import shutil
    if user_dir.exists():
        shutil.rmtree(user_dir)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(user_data_dir=str(user_dir), headless=True, viewport={"width":1400,"height":900})
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        page.click("[data-automation-id=applyManually]")
        page.wait_for_timeout(4000)
        # Pick source via path
        page.click("#source--source")
        page.wait_for_timeout(700)
        for level in path:
            opt = page.locator(f'[data-automation-id="promptOption"][data-automation-label="{level}"]').first
            if opt.count() == 0:
                print(f"  PATH {path}: level {level!r} NOT FOUND")
                ctx.close(); return None
            opt.click(force=True)
            page.wait_for_timeout(700)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        # Check: are there extra required text fields below source now?
        fields = page.evaluate("""
            () => {
              const out = [];
              document.querySelectorAll('input[type=text]').forEach(el => {
                const id = el.id;
                if (!id) return;
                const lab = document.querySelector(`label[for="${id}"]`);
                out.push({id, label: lab ? lab.textContent.trim().slice(0,80) : ''});
              });
              return out;
            }
        """)
        # Look for referredBy or similar followups
        followup = [f for f in fields if 'source' in f['id'].lower() or 'refer' in f['id'].lower()]
        print(f"  PATH {path}: source-followup fields = {followup}")
        ctx.close()
        return followup

for path in [
    ["Job Board"],
    ["Job Board", "LinkedIn"],
    ["Job Board", "Indeed"],
    ["External Organizations / Events"],
    ["Adobe Source"],
    ["Through my University"],
]:
    print(f"\nTesting: {path}")
    test_source(path)
