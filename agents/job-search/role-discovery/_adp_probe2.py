#!/usr/bin/env python3
"""Probe currency react-select + the new add_info_select_box."""
import time, json
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

# 1) currency react-select: open and read options
print("=== CURRENCY ===")
try:
    cur = page.locator("#question_currency_type_2")
    cur.scroll_into_view_if_needed(timeout=2000)
    cur.click(timeout=2500)
    time.sleep(1.0)
    opts = page.evaluate(r"""
    () => [...document.querySelectorAll('[class*=MDFSelectBox__option],[id*=react-select][id*=option],[role=option]')]
          .filter(x=>x.offsetWidth>0).map(x=>({txt:x.innerText.trim().slice(0,30), cls:(x.className||'').slice(0,30), id:(x.id||'').slice(0,40)})).slice(0,12)
    """)
    print("currency options:", json.dumps(opts)[:600])
except Exception as exc:
    print("currency exc:", str(exc)[:120])
page.keyboard.press("Escape"); time.sleep(0.4)

# 2) add_info_select_box: label + options
print("=== ADD_INFO_SELECT_BOX ===")
ctx_info = page.evaluate(r"""
() => {
  const el=document.getElementById('add_info_select_box');
  if(!el) return {found:false};
  // find its question label
  let q=''; let n=el;
  for(let i=0;i<8&&n;i++){ let s=n.previousElementSibling; while(s){const t=(s.innerText||'').trim(); if(t&&t.length<140){q=t;break;} s=s.previousElementSibling;} if(q)break; n=n.parentElement;}
  return {found:true, tag:el.tagName, attrs:[...el.attributes].map(a=>a.name+'='+a.value.slice(0,30)), label:q.slice(0,100)};
}
""")
print("add_info struct:", json.dumps(ctx_info)[:500])
try:
    el = page.locator("#add_info_select_box")
    el.scroll_into_view_if_needed(timeout=2000)
    el.click(timeout=3000)
    time.sleep(1.0)
    opts2 = page.evaluate("() => [...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim().slice(0,40))")
    print("add_info options:", opts2)
except Exception as exc:
    print("add_info exc:", str(exc)[:120])
page.keyboard.press("Escape")
print("[done]")
