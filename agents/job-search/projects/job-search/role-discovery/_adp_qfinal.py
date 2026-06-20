#!/usr/bin/env python3
"""DEFINITIVE Questions handler: fill all, commit currency, click Next, report advance."""
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

def esc():
    try: page.keyboard.press("Escape")
    except Exception: pass
    time.sleep(0.3)

def select_sdf(qid, want):
    el = page.locator("#%s" % qid)
    el.scroll_into_view_if_needed(timeout=2000); el.click(timeout=3000); time.sleep(0.9)
    opts = page.evaluate("() => [...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
    target=None
    for w in want:
        for o in opts:
            if o.lower()==w.lower(): target=o; break
        if target: break
    if not target:
        for w in want:
            for o in opts:
                if w.lower() in o.lower(): target=o; break
            if target: break
    if target:
        page.locator("[role=option]").filter(has_text=target).first.click(timeout=3000)
        print("  %s -> %r" % (qid, target)); time.sleep(0.6); return True
    print("  %s NO MATCH; opts=%s" % (qid, opts)); esc(); return False

def select_reactselect(rsid, want):
    el = page.locator("#%s" % rsid)
    el.scroll_into_view_if_needed(timeout=2000); el.click(timeout=2500); time.sleep(0.8)
    opt = page.locator(".MDFSelectBox__option").filter(has_text=want).first
    if opt.count() > 0:
        opt.click(timeout=3000); print("  %s -> %r" % (rsid, want)); time.sleep(0.6); return True
    print("  %s NO react option for %r" % (rsid, want)); esc(); return False

# Q0
page.locator("#question_0").fill("N/A", timeout=3000); print("Q0=N/A")
# Q1
select_sdf("question_1", ["LinkedIn"]); esc()
# Q2 comp + currency
page.locator("#question_2").fill("150000", timeout=3000); print("Q2=150000")
select_reactselect("question_currency_type_2", "United States Dollar"); esc()
# Q3 VISA
select_sdf("question_3", ["No"]); esc()
# optional desired salary + its currency (add_info_select_box) to clear the required twin
try:
    ds = page.locator("#desiredSalaryId")
    if ds.count() > 0 and ds.first.is_visible():
        ds.first.fill("150000", timeout=2500); print("desiredSalary=150000")
except Exception as exc:
    print("desiredSalary exc", str(exc)[:80])
# add_info_select_box currency (sdf-select-simple)
ai = page.locator("#add_info_select_box")
if ai.count() > 0 and ai.first.is_visible():
    select_sdf("add_info_select_box", ["United States Dollar", "USD"]); esc()

time.sleep(1)
# verify required-empty
req = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0; };
  const out=[];
  document.querySelectorAll('[aria-required=true],[required],[required-state=required]').forEach(el=>{
    if(!vis(el))return;
    let v=(el.value||'').trim();
    if(el.tagName==='SDF-SELECT-SIMPLE'){ v=el.getAttribute('value')|| (el.shadowRoot?(el.shadowRoot.querySelector('#selected-label,.selected-label')||{}).innerText:'')||''; }
    if(!v) out.push({id:el.id||el.name, tag:el.tagName, ai:el.getAttribute('aria-invalid')});
  });
  return out;
}
""")
print("REQUIRED-EMPTY:", json.dumps(req))

# Click Next
loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next")
time.sleep(5)
after = page.evaluate(r"""
() => {
  const stillQ=/Please answer the following questions/i.test(document.body.innerText);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,8);
  return {stillQuestions:stillQ, headings:h, errs, bodySample:document.body.innerText.replace(/\s+/g,' ').slice(0,400)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1200])
print("[done]")
