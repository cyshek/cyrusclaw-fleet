#!/usr/bin/env python3
"""Set Q0=None, Q2=150000, click Next; report whether we ADVANCE past Questions."""
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

page.locator("#question_0").fill("None", timeout=2500)
page.locator("#question_2").fill("150000", timeout=2500)
page.keyboard.press("Tab"); time.sleep(0.8)

loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next")
time.sleep(5)

after = page.evaluate(r"""
() => {
  const body=document.body.innerText;
  const stuck=/Please answer the following questions/i.test(body) && /Correct the information/i.test(body);
  const onSelfId=/Voluntary Self-?ID|Self-Identification|gender|veteran|disability/i.test(body) && !/Please answer the following questions/i.test(body);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,6);
  // which fields invalid now
  const inv=[...document.querySelectorAll('[aria-invalid=true]')].filter(e=>e.offsetWidth>0).map(e=>({id:e.id||e.name,val:(e.value||'').slice(0,20)}));
  return {stuckOnQuestions:stuck, looksLikeSelfId:onSelfId, headings:h, errs, invalidFields:inv, bodySample:body.replace(/\s+/g,' ').slice(0,450)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1400])
print("[done]")
