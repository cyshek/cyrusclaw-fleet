#!/usr/bin/env python3
"""Test Google Places autocomplete fill on ADP Personal Information address."""
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

line1 = page.locator("#PersonalAddress_address_line1")
line1.click(timeout=4000)
line1.fill("", timeout=2000)
# type slowly to trigger Places
query = "12420 NE 120th St, Kirkland, WA 98034"
line1.type(query, delay=60, timeout=8000)
print("typed query")
time.sleep(3)
# collect pac items
items = page.evaluate("() => [...document.querySelectorAll('.pac-container .pac-item')].slice(0,6).map(i=>i.innerText.replace(/\\s+/g,' ').slice(0,80))")
print("PAC items:", items)

if items:
    # Press ArrowDown then Enter to select first suggestion (more reliable than clicking pac-item)
    line1.press("ArrowDown")
    time.sleep(0.4)
    line1.press("Enter")
    print("selected first suggestion via keyboard")
    time.sleep(2.5)

# read resulting field values
vals = page.evaluate(r"""
() => {
  const g = id => { const e=document.getElementById(id); return e?e.value:null; };
  return {line1:g('PersonalAddress_address_line1'), city:g('PersonalAddress_city'),
          postal:g('PersonalAddress_postalCode'), country:g('PersonalAddress_country'),
          county:g('PersonalAddress_county'), line2:g('PersonalAddress_address_line2'),
          stateSel: (()=>{ const s=[...document.querySelectorAll('select')].find(x=>/state|province|region/i.test(x.getAttribute('aria-label')||x.name||x.id||'')); return s?s.value:null;})()};
}
""")
print("RESULT VALUES:", vals)
print("[places test done]")
