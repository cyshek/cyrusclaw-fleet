import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
d=page.evaluate(r"""
()=>{
  const body=document.body.innerText;
  const stuckQ=/following questions/i.test(body)&&/Correct the information/i.test(body);
  const onSelfId=/Voluntary Self-?ID/i.test(body)&&/(veteran|disability|gender|race|ethnicity|self-identif)/i.test(body)&&!/following questions/i.test(body);
  const onReview=/Review Your Application/i.test(body)&&!/following questions/i.test(body);
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,5);
  // which stepper item is active
  const active=[...document.querySelectorAll('[aria-current],.active,.is-active,.current-step,li.active')].map(e=>e.innerText.trim().slice(0,30)).filter(Boolean).slice(0,4);
  return {stuckQ,onSelfId,onReview,headings:h,errs,activeStep:active,sample:body.replace(/\s+/g,' ').slice(0,600)};
}
""")
print(json.dumps(d, indent=2)[:1700])
