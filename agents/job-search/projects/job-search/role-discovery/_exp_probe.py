#!/usr/bin/env python3
"""Probe: open Experience page, check date input behavior + degree options + skills moniker + radio meaning."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from workday_playwright import (
    fill_my_information, click_next, load_personal_info, detect_step
)

URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"
info = load_personal_info()

DBG = HERE.parent / ".workday-debug" / "exp-probe"
DBG.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / "adobe-exp-probe"),
        headless=True, viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    page.click("[data-automation-id=applyManually]")
    page.wait_for_timeout(4000)
    fill_my_information(page, info, "exp-probe")
    click_next(page, "exp-probe", "p1")
    page.wait_for_timeout(6000)
    print("STEP:", detect_step(page))

    # Try to type into the month input
    print("\n--- Date input test ---")
    mo = page.locator('input[id$="-dateSectionMonth-input"]').first
    if mo.count():
        try:
            mo.click()
            mo.type("03")
            page.wait_for_timeout(300)
            print("  month val:", mo.input_value())
        except Exception as e:
            print(f"  month click/type failed: {e}")
    yr = page.locator('input[id$="-dateSectionYear-input"]').first
    if yr.count():
        try:
            yr.click()
            yr.type("2024")
            page.wait_for_timeout(300)
            print("  year val:", yr.input_value())
        except Exception as e:
            print(f"  year fill failed: {e}")

    # Open degree dropdown and list options
    print("\n--- Degree options ---")
    deg = page.locator('#education-5--degree, button[id$="--degree"]').first
    if deg.count():
        deg.click()
        page.wait_for_timeout(700)
        opts = page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).map(o => o.textContent.trim()).filter(s=>s)")
        for o in opts[:30]: print(" ", o)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

    # Inspect the radios - find what fieldset they belong to
    print("\n--- Radio fieldsets ---")
    radios = page.evaluate("""
        () => {
          const out = [];
          const seen = new Set();
          document.querySelectorAll('input[type=radio]').forEach(r => {
            const name = r.name || r.id;
            if (seen.has(name)) return;
            seen.add(name);
            let p = r.closest('fieldset, [role=group], [role=radiogroup]');
            let q = '';
            if (p) {
              const legend = p.querySelector('legend, label, h3, h4');
              if (legend) q = legend.textContent.trim().slice(0,120);
            } else {
              // Walk up
              let n = r.parentElement;
              for (let i=0; i<6 && n; i++) {
                const lab = n.querySelector('label');
                if (lab && !lab.contains(r)) { q = lab.textContent.trim().slice(0,120); break; }
                n = n.parentElement;
              }
            }
            const sib = Array.from(document.querySelectorAll(`input[name="${r.name}"]`)).map(s => s.value);
            out.push({id: r.id, name: r.name, q, values: sib});
          });
          return out;
        }
    """)
    for r in radios:
        print(f"  {r['id']} name={r['name']} vals={r['values']} q={r['q']!r}")

    # Skills - check if it's required
    sk = page.locator('#skills--skills').first
    if sk.count():
        req = sk.get_attribute('aria-required')
        print(f"\n  skills required: {req}")

    page.screenshot(path=str(DBG / "exp-state.png"), full_page=True)
    ctx.close()
