import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Truly clear desiredSalaryId: triple-click select-all + delete + fire input/change
ds=page.locator("#desiredSalaryId")
ds.scroll_into_view_if_needed(timeout=2000)
ds.click(timeout=2500)
ds.press("Control+a"); ds.press("Delete")
page.evaluate(r"""() => { const e=document.getElementById('desiredSalaryId'); if(e){ e.value=''; e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); e.dispatchEvent(new Event('blur',{bubbles:true})); } }""")
page.keyboard.press("Tab"); time.sleep(0.8)
print("desiredSalary after clear:", page.evaluate("()=>document.getElementById('desiredSalaryId').value"))

# Click Next
loc=page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next"); time.sleep(5)
after=page.evaluate(r"""
() => {
  const body=document.body.innerText;
  const stuck=/Please answer the following questions/i.test(body)&&/Correct the information/i.test(body);
  const onSelfId=/Self-?ID|Self-Identification|veteran|disability|gender|race|ethnicity/i.test(body)&&!/Please answer the following questions/i.test(body);
  const onReview=/Review Your Application/i.test(body)&&!/Please answer the following questions/i.test(body);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,6);
  return {stuck, onSelfId, onReview, headings:h, errs, sample:body.replace(/\s+/g,' ').slice(0,450)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1300])
