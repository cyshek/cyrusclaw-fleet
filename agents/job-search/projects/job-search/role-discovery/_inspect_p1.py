#!/usr/bin/env python3
"""Inspect page 1 final state after fill."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"
sys.path.insert(0, str(HERE))
from workday_playwright import fill_page1_my_information, load_personal_info

info = load_personal_info()

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(HERE.parent / ".workday-browser-data" / "adobe-inspect"),
        headless=True, viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    page.click("[data-automation-id=applyManually]")
    page.wait_for_timeout(4000)
    fill_page1_my_information(page, info, "inspect")
    page.wait_for_timeout(2000)
    # Dump field state
    state = page.evaluate("""
        () => {
          const out = {};
          ['name--legalName--firstName','name--legalName--lastName','address--addressLine1','address--city','address--postalCode','emailAddress--emailAddress','phoneNumber--phoneNumber'].forEach(id => {
            const el = document.getElementById(id);
            out[id] = el ? el.value : 'NOT FOUND';
          });
          // State dropdown current text
          const stBtn = document.getElementById('address--countryRegion');
          out['state'] = stBtn ? stBtn.textContent.trim().slice(0,60) : 'no-btn';
          // Country
          const cBtn = document.getElementById('country--country');
          out['country'] = cBtn ? cBtn.textContent.trim().slice(0,60) : 'no-btn';
          // Source button text
          const srcContainer = document.getElementById('source--source');
          out['source'] = srcContainer ? srcContainer.parentElement.parentElement.textContent.trim().slice(0,100) : 'no-src';
          // Radio
          out['prev_employed_yes'] = document.querySelector('input[name=candidateIsPreviousWorker][value=true]')?.checked;
          out['prev_employed_no'] = document.querySelector('input[name=candidateIsPreviousWorker][value=false]')?.checked;
          // Selected source count badge
          const badges = document.querySelectorAll('[data-automation-id="selectedItem"]');
          out['selectedItems'] = Array.from(badges).map(b => b.textContent.trim()).filter(s => s).slice(0,10);
          return out;
        }
    """)
    import json
    print(json.dumps(state, indent=2))
    ctx.close()
