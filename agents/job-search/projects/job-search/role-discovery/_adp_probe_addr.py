#!/usr/bin/env python3
"""Probe the ADP Personal Information address widget behavior."""
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
print("attached:", page.url[:120])

# Inspect the address line1 field: is it a Google places autocomplete? look at attrs + siblings
info = page.evaluate(r"""
() => {
  const el = document.getElementById('PersonalAddress_address_line1');
  if(!el) return {found:false};
  const attrs={};
  for(const a of el.attributes) attrs[a.name]=a.value.slice(0,60);
  // any pac-container (google places) on page?
  const pac = document.querySelector('.pac-container, [class*=autocomplete], [role=listbox]');
  // country field current
  const country = document.getElementById('PersonalAddress_country');
  return {found:true, attrs, hasPac: !!pac, pacClass: pac?pac.className:'',
          countryVal: country?country.value:null, countryAttrs: country?[...country.attributes].map(a=>a.name+'='+a.value.slice(0,30)):[]};
}
""")
print("line1 field:", info)

# Try filling country first (it may be a typeahead too)
try:
    c = page.locator("#PersonalAddress_country")
    if c.count() > 0:
        c.click(timeout=3000)
        c.fill("United States", timeout=3000)
        time.sleep(2)
        # dropdown?
        opts = page.evaluate("() => [...document.querySelectorAll('[role=option],li.ui-menu-item,.pac-item,.dropdown-item')].slice(0,8).map(o=>o.innerText.slice(0,40))")
        print("country dropdown opts:", opts)
except Exception as e:
    print("country fill exc:", str(e)[:120])

print("[probe done]")
