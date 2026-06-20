#!/usr/bin/env python3
"""Inspect Experience page after fill, identify what's still required and missing."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from workday_playwright import (
    fill_my_information, fill_my_experience, click_next, load_personal_info, screenshot, detect_step, check_errors
)

URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"
info = load_personal_info()

DBG = HERE.parent / ".workday-debug" / "exp-inspect"
DBG.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / "adobe-exp"),
        headless=True, viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    page.click("[data-automation-id=applyManually]")
    page.wait_for_timeout(4000)
    print("STEP:", detect_step(page))
    fill_my_information(page, info, "exp-inspect")
    click_next(page, "exp-inspect", "p1")
    page.wait_for_timeout(6000)
    print("STEP after Next:", detect_step(page))
    print("ERRORS:", check_errors(page))
    page.screenshot(path=str(DBG / "after-p1-next.png"), full_page=True)
    # Now we should be on Experience
    fill_my_experience(page, info, "exp-inspect")
    page.wait_for_timeout(2000)
    print("STEP after exp fill:", detect_step(page))
    # Dump all inputs with state
    fields = page.evaluate("""
        () => {
          const out = [];
          document.querySelectorAll('input, textarea, select, button[aria-haspopup="listbox"]').forEach(el => {
            const req = el.required || el.getAttribute('aria-required') === 'true';
            const id = el.id || '';
            const name = el.name || '';
            const t = el.tagName + (el.type ? '['+el.type+']' : '');
            let val = '';
            if (el.tagName === 'BUTTON') {
              const sel = el.querySelector('[data-automation-id="selectedItem"]');
              val = sel ? sel.textContent.trim() : el.textContent.trim().slice(0,40);
            } else if (el.type === 'checkbox' || el.type === 'radio') {
              val = el.checked ? '[CHECKED]' : '';
            } else {
              val = el.value || '';
            }
            let label = '';
            if (id) {
              const lab = document.querySelector(`label[for="${id}"]`);
              if (lab) label = lab.textContent.trim().slice(0,80);
            }
            out.push({tag: t, id, name, req, val: val.slice(0,40), label});
          });
          return out;
        }
    """)
    print(f"\n--- {len(fields)} form elements ---")
    for f in fields:
        mark = '*' if f['req'] else ' '
        print(f"  {mark} {f['tag']:18s} id={f['id'][:50]:50s} val={f['val']:40s} | {f['label']}")
    # Click Next
    click_next(page, "exp-inspect", "p2")
    page.wait_for_timeout(6000)
    print("\nSTEP after exp Next:", detect_step(page))
    print("ERRORS:", check_errors(page))
    page.screenshot(path=str(DBG / "after-p2-next.png"), full_page=True)
    ctx.close()
