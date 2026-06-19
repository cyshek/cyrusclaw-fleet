#!/usr/bin/env python3
"""Fully clear the optional desired-salary block (text + add_info_select_box currency), then Next."""
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

# Inspect add_info_select_box value + shadow selected label + any clear button
st = page.evaluate(r"""
() => {
  const el=document.getElementById('add_info_select_box');
  if(!el) return {found:false};
  let sel='';
  if(el.shadowRoot){
    const s=el.shadowRoot.querySelector('#selected-label,.selected-label,[part=selected-value]');
    sel=s?s.innerText.trim():'';
    // clear button in shadow?
    const clr=el.shadowRoot.querySelector('[part=clear-button],.clear-button,[aria-label*=lear]');
    return {found:true, value:el.getAttribute('value'), selectedLabel:sel, hasClear:!!clr, attrs:[...el.attributes].map(a=>a.name+'='+a.value.slice(0,25))};
  }
  return {found:true, value:el.getAttribute('value'), shadow:false};
}
""")
print("add_info_select_box state:", json.dumps(st)[:500])

# Clear desiredSalaryId text
ds = page.locator("#desiredSalaryId")
if ds.count() > 0:
    ds.first.click(timeout=2000)
    ds.first.press("Control+a"); ds.first.press("Delete")
    page.keyboard.press("Tab"); time.sleep(0.5)
    print("desiredSalaryId cleared ->", page.evaluate("()=>document.getElementById('desiredSalaryId').value"))

# Clear add_info_select_box: set its value attribute empty + try to reset via property/web component API
cleared = page.evaluate(r"""
() => {
  const el=document.getElementById('add_info_select_box');
  if(!el) return 'no-el';
  try{
    // sdf web component: setting value='' or calling reset
    el.value='';
    el.setAttribute('value','');
    if(typeof el.reset==='function') el.reset();
    // dispatch change so React/SDF picks it up
    el.dispatchEvent(new CustomEvent('sdfChange',{bubbles:true,detail:{value:''}}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
    return 'cleared value='+el.getAttribute('value');
  }catch(e){return 'err '+e.message;}
}
""")
print("add_info clear attempt:", cleared)
time.sleep(0.8)

# Now click Next
loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next")
time.sleep(5)

after = page.evaluate(r"""
() => {
  const body=document.body.innerText;
  const stuck=/Please answer the following questions/i.test(body)&&/Correct the information/i.test(body);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,6);
  return {stuck, headings:h, errs, sample:body.replace(/\s+/g,' ').slice(0,450)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1200])
print("[done]")
