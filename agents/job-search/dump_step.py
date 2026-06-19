#!/usr/bin/env python3
"""Drive forward to a target step then dump page state."""
import sys, json, time, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "role-discovery"))
from playwright.sync_api import sync_playwright
import workday_playwright as wp

ap = argparse.ArgumentParser()
ap.add_argument("--target-step", required=True, help="lowercase substring of step name to stop at")
ap.add_argument("--out", required=True)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".workday-browser-data" / "adobe"
DEBUG = ROOT / ".workday-debug" / args.out
DEBUG.mkdir(parents=True, exist_ok=True)
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

    for i in range(8):
        step = wp.detect_step(page)
        print(f"iter{i}: step='{step}'")
        if args.target_step.lower() in step.lower():
            print("REACHED TARGET")
            break
        kind = wp.classify_step(step)
        if kind == "info":
            wp.fill_my_information(page, info, args.out)
        elif kind == "exp":
            wp.fill_my_experience(page, info, args.out)
        elif kind == "questions":
            wp.fill_application_questions(page, info, args.out)
        elif kind == "voluntary":
            wp.fill_voluntary_disclosures(page, info, args.out)
        elif kind == "selfid":
            wp.fill_self_identify(page, info, args.out)
        else:
            wp.fill_generic_page(page, info, args.out, "unknown")
        wp.click_next(page, args.out, f"to-{args.target_step}")
        page.wait_for_timeout(7000)

    page.screenshot(path=str(DEBUG/"target.png"), full_page=True)
    (DEBUG/"target.html").write_text(page.content())

    # Dump structure
    info_dump = page.evaluate("""()=>{
      const out={inputs:[], textareas:[], dropdowns:[], radios:[], checkboxes:[], fieldsets:[], errors:[]};
      document.querySelectorAll('input').forEach(el=>{
        const id=el.id; let lab='';
        if(id){const l=document.querySelector(`label[for="${id}"]`);if(l)lab=l.textContent.trim().slice(0,120);}
        if(el.type==='radio')out.radios.push({id, name:el.name, value:el.value, checked:el.checked, required:el.required||el.getAttribute('aria-required')==='true', lab});
        else if(el.type==='checkbox')out.checkboxes.push({id, name:el.name, checked:el.checked, required:el.required||el.getAttribute('aria-required')==='true', lab});
        else if(el.type!=='hidden')out.inputs.push({id, type:el.type, role:el.getAttribute('role'), name:el.name, value:(el.value||'').slice(0,40), required:el.required||el.getAttribute('aria-required')==='true', auto:el.getAttribute('data-automation-id'), lab});
      });
      document.querySelectorAll('textarea').forEach(el=>{
        const id=el.id;let lab='';
        if(id){const l=document.querySelector(`label[for="${id}"]`);if(l)lab=l.textContent.trim().slice(0,120);}
        out.textareas.push({id, value:(el.value||'').slice(0,80), required:el.required||el.getAttribute('aria-required')==='true', lab});
      });
      document.querySelectorAll('button[aria-haspopup="listbox"]').forEach(b=>{
        if (b.id==='utilityMenuButton') return;
        const sel=b.querySelector('[data-automation-id="selectedItem"]');
        const fs=b.closest('fieldset, [data-automation-id^="formField-"]');
        let q='';
        if(fs){const lg=fs.querySelector('legend');q=lg?lg.textContent.trim():fs.textContent.trim().slice(0,200);}
        out.dropdowns.push({id:b.id, selected:(sel?sel.textContent:b.textContent).trim().slice(0,80), required:b.getAttribute('aria-required')==='true', q:q.slice(0,200)});
      });
      // Fieldsets with checkboxes (group questions)
      document.querySelectorAll('fieldset').forEach(fs=>{
        const cbs=fs.querySelectorAll('input[type=checkbox]');
        const rds=fs.querySelectorAll('input[type=radio]');
        if(cbs.length>=2 || rds.length>=2){
          const lg=fs.querySelector('legend');
          out.fieldsets.push({q:lg?lg.textContent.trim().slice(0,200):'', cbs:cbs.length, radios:rds.length});
        }
      });
      document.querySelectorAll('[role=alert],[data-automation-id*=error i],.Error').forEach(e=>{
        const t=(e.textContent||'').trim();
        if(t&&t.length<200) out.errors.push({auto:e.getAttribute('data-automation-id'), text:t});
      });
      return out;
    }""")
    (DEBUG/"fields.json").write_text(json.dumps(info_dump, indent=2, default=str))
    print("inputs:", len(info_dump['inputs']), "textareas:", len(info_dump['textareas']), "dropdowns:", len(info_dump['dropdowns']), "radios:", len(info_dump['radios']), "cbs:", len(info_dump['checkboxes']), "fieldsets:", len(info_dump['fieldsets']))
    print("ERRORS:")
    for e in info_dump['errors'][:10]: print(" ", e)
    print("DROPDOWNS:")
    for d in info_dump['dropdowns'][:15]: print(" ", d)
    print("REQUIRED INPUTS/TEXTAREAS without value:")
    for x in info_dump['inputs']+info_dump['textareas']:
        if x.get('required') and not x.get('value'):
            print(" ", {'id':x.get('id'),'lab':x.get('lab'),'type':x.get('type'),'role':x.get('role')})
    print("RADIOS required+unchecked groups:")
    rg = {}
    for r in info_dump['radios']:
        if not r['name']: continue
        rg.setdefault(r['name'], {'required':False,'checked':False,'lab':''})
        if r['required']: rg[r['name']]['required']=True
        if r['checked']: rg[r['name']]['checked']=True
        if r['lab']: rg[r['name']]['lab']=r['lab']
    for n, g in rg.items():
        if g['required'] and not g['checked']: print(" ", n, g)
    print("CHECKBOXES required+unchecked:")
    for c in info_dump['checkboxes']:
        if c['required'] and not c['checked']: print(" ", c)
    print("FIELDSETS (group questions):")
    for f in info_dump['fieldsets'][:15]: print(" ", f)
    ctx.close()
