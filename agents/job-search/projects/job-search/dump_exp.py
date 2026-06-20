#!/usr/bin/env python3
"""Re-fill Info via existing driver functions, click Next, then dump Experience page state."""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "role-discovery"))
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".workday-browser-data" / "adobe"
DEBUG = ROOT / ".workday-debug" / "exp-dump"
DEBUG.mkdir(parents=True, exist_ok=True)
URL = "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"

import workday_playwright as wp

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
    wp.fill_my_information(page, info, "exp-dump")
    page.wait_for_timeout(1500)
    # Click Next
    page.locator('[data-automation-id="pageFooterNextButton"]').click()
    page.wait_for_timeout(7000)
    step = page.evaluate("""()=>{const c=document.querySelector('[data-automation-id="progressBarActiveStep"]');return c?c.textContent.trim():'';}""")
    print("step after info next:", step)
    page.screenshot(path=str(DEBUG/"after-info-next.png"), full_page=True)
    (DEBUG/"after-info-next.html").write_text(page.content())

    if 'experience' not in step.lower():
        print("did NOT advance to experience")
        # Check info-page errors
        errs = page.evaluate("""()=>{const out=[];document.querySelectorAll('[role=alert],[data-automation-id*=error i],.Error').forEach(e=>{const t=(e.textContent||'').trim();if(t&&t.length<300)out.push(t);});return out;}""")
        for e in errs[:15]: print(" e:", e)
        ctx.close(); sys.exit(0)

    # We're on Experience. Run filler then dump
    wp.fill_my_experience(page, info, "exp-dump")
    page.wait_for_timeout(2000)

    # Now click Next
    page.locator('[data-automation-id="pageFooterNextButton"]').click()
    page.wait_for_timeout(8000)
    step2 = page.evaluate("""()=>{const c=document.querySelector('[data-automation-id="progressBarActiveStep"]');return c?c.textContent.trim():'';}""")
    print("step after exp next:", step2)
    page.screenshot(path=str(DEBUG/"after-exp-next.png"), full_page=True)
    (DEBUG/"after-exp-next.html").write_text(page.content())

    # Errors and blanks
    state = page.evaluate("""()=>{
      const out={errors:[], requiredBlanks:[], dateFields:[], allInputs:[]};
      document.querySelectorAll('[role=alert],[data-automation-id*=error i],.Error,[id*=error i]').forEach(e=>{
        const t=(e.textContent||'').trim();
        if(t&&t.length<200) out.errors.push({auto:e.getAttribute('data-automation-id'),text:t});
      });
      // All input-likes
      document.querySelectorAll('input, textarea, button[role=spinbutton]').forEach(el=>{
        const id=el.id;
        let lab='';
        if (id){ const l=document.querySelector(`label[for="${id}"]`); if(l) lab=l.textContent.trim().slice(0,80); }
        const isReq = el.required||el.getAttribute('aria-required')==='true';
        const val = el.value || el.textContent.trim();
        out.allInputs.push({id:id, type:el.type||el.getAttribute('role'), name:el.name, required:isReq, value:val.slice(0,40), lab:lab});
        if (id && (id.toLowerCase().includes('date') || id.toLowerCase().includes('month') || id.toLowerCase().includes('year') || id.toLowerCase().includes('from') || id.toLowerCase().includes('to'))){
          out.dateFields.push({id:id, role:el.getAttribute('role'), type:el.type, lab:lab, val:val.slice(0,30)});
        }
      });
      // Required blanks
      document.querySelectorAll('input[aria-invalid="true"], textarea[aria-invalid="true"], button[aria-invalid="true"]').forEach(el=>{
        let lab='';
        if (el.id){ const l=document.querySelector(`label[for="${el.id}"]`); if(l) lab=l.textContent.trim().slice(0,100); }
        out.requiredBlanks.push({id:el.id, tag:el.tagName, lab:lab});
      });
      return out;
    }""")
    (DEBUG/"state.json").write_text(json.dumps(state, indent=2, default=str))
    print("\nerrors:", len(state['errors']))
    for e in state['errors'][:15]: print(" err:", e)
    print("\ninvalid fields:", len(state['requiredBlanks']))
    for b in state['requiredBlanks'][:15]: print(" inv:", b)
    print("\ndate-ish fields:", len(state['dateFields']))
    for d in state['dateFields'][:25]: print(" date:", d)
    ctx.close()
