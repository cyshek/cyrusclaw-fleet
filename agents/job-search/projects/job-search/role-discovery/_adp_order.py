#!/usr/bin/env python3
"""Correct order: country FIRST then Places address. Verify both stick."""
import time, json
import json as _json; from pathlib import Path as _Path; _PI = _json.loads((_Path('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/../personal-info.json').read_text()))
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

def pick_country():
    c = page.locator("#PersonalAddress_country")
    c.click(timeout=4000); time.sleep(0.5)
    c.type("United States", delay=40, timeout=5000); time.sleep(1.4)
    for sel in ("[role=option]:has-text('United States')",):
        o = page.locator(sel).filter(visible=True).first
        if o.count() > 0:
            o.click(timeout=2500); print("country picked"); break
    time.sleep(1.2)

def fill_places():
    line1 = page.locator("#PersonalAddress_address_line1")
    line1.click(timeout=4000); line1.fill("", timeout=2000)
    line1.type(f"{_PI['address']['street']}, {_PI['address']['city']}, {_PI['address']['state']} {_PI['address']['zip']}", delay=55, timeout=8000)
    time.sleep(2.5)
    items = page.evaluate("() => [...document.querySelectorAll('.pac-container .pac-item')].length")
    print("pac items:", items)
    if items:
        line1.press("ArrowDown"); time.sleep(0.4); line1.press("Enter")
        time.sleep(2.2)

# ORDER: country then places
pick_country()
fill_places()

# How is country stored? check display text near the combobox
ci = page.evaluate(r"""
() => {
  const c=document.getElementById('PersonalAddress_country');
  const wrap=c?c.closest('.MDFSelectBox, [class*=SelectBox], .vdl-select'):null;
  const g = id => { const e=document.getElementById(id); return e?e.value:null; };
  return {countryInputVal:c?c.value:null, countryWrapText:wrap?wrap.innerText.replace(/\s+/g,' ').slice(0,60):null,
          line1:g('PersonalAddress_address_line1'),city:g('PersonalAddress_city'),postal:g('PersonalAddress_postalCode'),county:g('PersonalAddress_county')};
}
""")
print("AFTER (country-then-places):", json.dumps(ci))

# Re-check required empties
req = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0; };
  const out=[];
  document.querySelectorAll('input,select,textarea').forEach(el=>{
    if(!vis(el)) return;
    const req=el.required||el.getAttribute('aria-required')==='true';
    if(req && !(el.value||'').trim()) out.push(el.id||el.name||el.getAttribute('aria-label'));
  });
  return out;
}
""")
print("REQUIRED-EMPTY now:", req)
print("[done]")
