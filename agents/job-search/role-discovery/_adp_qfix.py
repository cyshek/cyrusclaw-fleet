#!/usr/bin/env python3
"""Clear optional desired-salary (both fields), confirm Q2 currency committed, Next."""
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

# Clear desired salary text
try:
    ds = page.locator("#desiredSalaryId")
    if ds.count() > 0:
        ds.first.fill("", timeout=2500)
        page.keyboard.press("Tab")
        print("cleared desiredSalaryId")
except Exception as exc:
    print("clear ds exc", str(exc)[:80])
time.sleep(0.6)

# Check Q2 currency committed: read the react-select's displayed value text
cur_state = page.evaluate(r"""
() => {
  const inp=document.getElementById('question_currency_type_2');
  if(!inp) return {found:false};
  // react-select shows selected value in a sibling .MDFSelectBox__single-value
  const wrap=inp.closest('.MDFSelectBox__control, [class*=MDFSelectBox], .currencySelectDiv') || inp.parentElement;
  let disp='';
  if(wrap){ const sv=wrap.querySelector('.MDFSelectBox__single-value,[class*=single-value]'); disp=sv?sv.innerText.trim():''; }
  return {found:true, displayed:disp, inputVal:inp.value};
}
""")
print("Q2 currency state:", cur_state)

# If not committed, set it
if not cur_state.get("displayed"):
    cur = page.locator("#question_currency_type_2")
    cur.scroll_into_view_if_needed(timeout=2000); cur.click(timeout=2500); time.sleep(0.8)
    opt = page.locator(".MDFSelectBox__option").filter(has_text="United States Dollar").first
    if opt.count() > 0:
        opt.click(timeout=3000); print("re-committed USD"); time.sleep(0.6)
    page.keyboard.press("Escape")

# also clear add_info currency if it somehow has a value (keep both desired-salary empty)
time.sleep(0.5)

# Click Next
loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next")
time.sleep(5)

after = page.evaluate(r"""
() => {
  const stillQ=/Please answer the following questions/i.test(document.body.innerText) && /Correct the information/i.test(document.body.innerText);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,8);
  return {stuckOnQuestions:stillQ, headings:h, errs, bodySample:document.body.innerText.replace(/\s+/g,' ').slice(0,500)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1300])
print("[done]")
