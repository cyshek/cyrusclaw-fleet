#!/usr/bin/env python3
"""Inspect current state of the My Experience page after re-loading the persistent context."""
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".workday-browser-data" / "adobe"
DEBUG = ROOT / ".workday-debug" / "exp-inspect2"
DEBUG.mkdir(parents=True, exist_ok=True)
URL = "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced/job/San-Jose/Engineering-Product-Manager_R163295/apply"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(DATA), headless=True,
        viewport={"width":1400,"height":900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(5000)
    # Click apply manually if visible
    if page.locator('[data-automation-id="applyManually"]').count():
        page.click('[data-automation-id="applyManually"]')
        page.wait_for_timeout(4000)
    print("url:", page.url)
    step = page.evaluate("""()=>{
      const c=document.querySelector('[data-automation-id="progressBarActiveStep"]');
      return c?c.textContent.trim():'';
    }""")
    print("step:", step)

    # If My Info, click Next to get past to My Experience
    if 'information' in step.lower():
        # Try click Next
        page.locator('[data-automation-id="pageFooterNextButton"]').click()
        page.wait_for_timeout(5000)
        step = page.evaluate("""()=>{
          const c=document.querySelector('[data-automation-id="progressBarActiveStep"]');
          return c?c.textContent.trim():'';
        }""")
        print("step after next:", step)

    page.screenshot(path=str(DEBUG/"current.png"), full_page=True)
    (DEBUG/"current.html").write_text(page.content())

    # Dump form structure
    fields = page.evaluate("""()=>{
      const out = {inputs:[], textareas:[], selects:[], buttons:[], dropdowns:[], radios:[], checkboxes:[], errors:[]};
      document.querySelectorAll('input').forEach(el=>{
        if (el.type==='radio') out.radios.push({id:el.id, name:el.name, value:el.value, checked:el.checked, required:el.required||el.getAttribute('aria-required')==='true'});
        else if (el.type==='checkbox') out.checkboxes.push({id:el.id, name:el.name, checked:el.checked, required:el.required||el.getAttribute('aria-required')==='true'});
        else if (el.type==='file') out.inputs.push({id:el.id, type:'file', auto:el.getAttribute('data-automation-id')});
        else if (el.type!=='hidden') out.inputs.push({id:el.id, type:el.type, name:el.name, value:el.value, required:el.required||el.getAttribute('aria-required')==='true', auto:el.getAttribute('data-automation-id')});
      });
      document.querySelectorAll('textarea').forEach(el=>{
        out.textareas.push({id:el.id, value:(el.value||'').slice(0,80), required:el.required||el.getAttribute('aria-required')==='true'});
      });
      document.querySelectorAll('button[aria-haspopup="listbox"]').forEach(b=>{
        const sel = b.querySelector('[data-automation-id="selectedItem"]');
        out.dropdowns.push({id:b.id, name:b.getAttribute('name'), selected:(sel?sel.textContent:b.textContent||'').trim().slice(0,80), required:b.getAttribute('aria-required')==='true'});
      });
      document.querySelectorAll('button[type=button], button:not([type])').forEach(b=>{
        const t=(b.textContent||'').trim().slice(0,60);
        if (t && t.length>1 && !t.toLowerCase().includes('cookie')) out.buttons.push({auto:b.getAttribute('data-automation-id'), text:t});
      });
      document.querySelectorAll('[data-automation-id*="error" i], .Error, [role=alert]').forEach(e=>{
        const t=(e.textContent||'').trim();
        if (t && t.length<300) out.errors.push({auto:e.getAttribute('data-automation-id'), role:e.getAttribute('role'), text:t});
      });
      // Field labels for blank required
      out.requiredBlanks=[];
      document.querySelectorAll('input[aria-required="true"], input[required], textarea[required], textarea[aria-required="true"], button[aria-required="true"]').forEach(el=>{
        let v = el.value;
        if (el.tagName==='BUTTON'){ const s=el.querySelector('[data-automation-id="selectedItem"]'); v = s?s.textContent.trim():''; }
        if (!v || /select one/i.test(v)){
          let lab='';
          if (el.id){ const l=document.querySelector(`label[for="${el.id}"]`); if (l) lab=l.textContent.trim().slice(0,100); }
          out.requiredBlanks.push({id:el.id, tag:el.tagName, lab:lab});
        }
      });
      return out;
    }""")
    (DEBUG/"fields.json").write_text(json.dumps(fields, indent=2, default=str))
    print("inputs:", len(fields['inputs']), "textareas:", len(fields['textareas']), "dropdowns:", len(fields['dropdowns']), "radios:", len(fields['radios']), "checkboxes:", len(fields['checkboxes']))
    print("errors:", len(fields['errors']))
    for e in fields['errors'][:10]:
        print(" err:", e)
    print("required blanks:", len(fields['requiredBlanks']))
    for b in fields['requiredBlanks'][:20]:
        print(" blank:", b)
    print("buttons:")
    for b in fields['buttons'][:20]:
        print(" btn:", b)
    ctx.close()
