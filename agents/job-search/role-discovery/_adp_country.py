#!/usr/bin/env python3
"""Fill country combobox + re-check Personal Info required state."""
import time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]
page = None
for p in ctx.pages:
    if "workforcenow.adp.com" in p.url:
        page = p
        break
print("attached:", page.url[:110])

# Country is an MDFSelectBox combobox. Click to open, type, pick option.
country = page.locator("#PersonalAddress_country")
try:
    country.click(timeout=4000)
    time.sleep(0.6)
    country.type("United States", delay=40, timeout=5000)
    time.sleep(1.5)
    # MDF listbox options
    opts = page.evaluate("() => [...document.querySelectorAll('[role=option],li[role=option],.MDFSelectBox__option,.dropdown-item,li.ui-menu-item')].slice(0,8).map(o=>o.innerText.slice(0,40))")
    print("country opts:", opts)
    # click the United States option
    picked = False
    for sel in ("[role=option]:has-text('United States')", "li:has-text('United States')",
                ".MDFSelectBox__option:has-text('United States')"):
        try:
            o = page.locator(sel).filter(visible=True).first
            if o.count() > 0:
                o.click(timeout=2500)
                picked = True
                print("picked country via", sel)
                break
        except Exception:
            continue
    if not picked:
        country.press("ArrowDown"); time.sleep(0.3); country.press("Enter")
        print("picked country via keyboard")
    time.sleep(1.5)
except Exception as exc:
    print("country exc:", str(exc)[:140])

# Now enumerate ALL required empty fields + any state field + Next button
state = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };
  const reqEmpty=[];
  document.querySelectorAll('input,select,textarea').forEach(el=>{
    if(!vis(el)) return;
    const req = el.required || el.getAttribute('aria-required')==='true';
    const v=(el.value||'').trim();
    if(req && !v) reqEmpty.push({id:el.id||el.name||'', aria:(el.getAttribute('aria-label')||'').slice(0,40), type:el.type||el.tagName});
  });
  const g = id => { const e=document.getElementById(id); return e?e.value:null; };
  const stateField = [...document.querySelectorAll('input,select')].filter(x=>/state|province/i.test((x.getAttribute('aria-label')||'')+x.name+x.id)).map(x=>({id:x.id||x.name, val:x.value, tag:x.tagName}));
  return {reqEmpty, addr:{line1:g('PersonalAddress_address_line1'),city:g('PersonalAddress_city'),postal:g('PersonalAddress_postalCode'),country:g('PersonalAddress_country'),county:g('PersonalAddress_county')}, stateField};
}
""")
import json
print("STATE:", json.dumps(state, indent=2)[:1500])
print("[country+check done]")
