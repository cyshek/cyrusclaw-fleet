#!/usr/bin/env python3
"""Fill BOTH desired-salary fields consistently: salary=150000 THEN add_info currency=USD. Then Next."""
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

# 1) fill desired salary FIRST (may enable the currency select)
ds = page.locator("#desiredSalaryId")
ds.first.click(timeout=2500)
ds.first.press("Control+a"); ds.first.press("Delete")
page.keyboard.type("150000", delay=60)
page.keyboard.press("Tab"); time.sleep(0.8)
print("desiredSalary ->", page.evaluate("()=>document.getElementById('desiredSalaryId').value"))

# 2) open add_info_select_box currency; check disabled/options
ai_state = page.evaluate(r"""
() => {
  const el=document.getElementById('add_info_select_box');
  return {disabled:el.hasAttribute('disabled'), ariaDisabled:el.getAttribute('aria-disabled'),
          shadowTrigger: el.shadowRoot ? (()=>{const t=el.shadowRoot.querySelector('.trigger-button,[role=button]'); return t?{ad:t.getAttribute('aria-disabled'),txt:t.innerText.slice(0,20)}:null;})() : null};
}
""")
print("add_info before open:", json.dumps(ai_state))

ai = page.locator("#add_info_select_box")
ai.scroll_into_view_if_needed(timeout=2000)
ai.click(timeout=3000)
time.sleep(1.2)
opts = page.evaluate("() => [...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
print("add_info options after fill:", opts[:8])

picked=False
if opts:
    target=None
    for o in opts:
        if 'united states dollar' in o.lower() or o.strip()=='USD' or 'USD' in o:
            target=o; break
    if not target: target=opts[0]
    page.locator("[role=option]").filter(has_text=target).first.click(timeout=3000)
    print("add_info -> %r" % target); picked=True
    time.sleep(0.8)
page.keyboard.press("Escape")
time.sleep(0.6)

# Click Next
loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next")
time.sleep(5)
after = page.evaluate(r"""
() => {
  const body=document.body.innerText;
  const stuck=/Please answer the following questions/i.test(body)&&/Correct the information/i.test(body);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,6);
  return {stuck, headings:h, errs, sample:body.replace(/\s+/g,' ').slice(0,500)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1300])
print("[done]")
