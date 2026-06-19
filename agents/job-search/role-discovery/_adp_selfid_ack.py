import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

def check_box(name):
    c=page.locator('input[name="%s"]'%name)
    if c.count()==0:
        print("  %s not found"%name); return
    if not c.first.is_checked():
        # click via label (checkbox may be visually hidden); try element then label
        try:
            c.first.check(timeout=3000)
        except Exception:
            # click the wrapping label
            lbl=page.locator('label:has(input[name="%s"])'%name).first
            if lbl.count()>0: lbl.click(timeout=3000)
            else: c.first.click(timeout=3000, force=True)
    print("  %s checked=%s"%(name, page.locator('input[name="%s"]'%name).first.is_checked()))

# Required acknowledgment
check_box("disabilityStatusCheck")
# Decline race/ethnicity (doctrine: decline where allowed)
check_box("enthinicityAndRaceId")
time.sleep(0.6)

loc=page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next"); time.sleep(6)
after=page.evaluate(r"""
()=>{
  const body=document.body.innerText;
  const stillSelfId=/Gender\s*--Select One--/i.test(body);
  const onReview=/Review Your Application/i.test(body)&&!/Gender\s*--Select One--/i.test(body);
  const onSubmit=/Self-Attest/i.test(body)&&/(Submit Application|I certify|attest)/i.test(body);
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,5);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,5);
  return {stillSelfId,onReview,onSubmit,headings:h,errs,sample:body.replace(/\s+/g,' ').slice(0,550)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1300])
