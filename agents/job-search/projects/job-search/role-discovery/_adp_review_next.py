import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# From Review, click Next/Continue to reach Self-Attest & Submit
btns=page.evaluate("()=>[...document.querySelectorAll('button')].filter(b=>b.offsetWidth>0).map(b=>b.innerText.trim()).filter(Boolean).slice(0,12)")
print("buttons on review:", json.dumps(btns))
nxt=page.locator("button:has-text('Next')").filter(visible=True).first
if nxt.count()==0:
    nxt=page.locator("button:has-text('Continue')").filter(visible=True).first
nxt.scroll_into_view_if_needed(timeout=2000); nxt.click(timeout=6000); print("clicked Next/Continue"); time.sleep(6)

d=page.evaluate(r"""
()=>{
  const body=document.body.innerText;
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,5);
  const btns=[...document.querySelectorAll('button')].filter(b=>b.offsetWidth>0).map(b=>b.innerText.trim()).filter(Boolean).slice(0,12);
  // attestation checkboxes
  const checks=[...document.querySelectorAll('input[type=checkbox]')].filter(c=>{const r=c.getBoundingClientRect();return true;}).map(c=>({name:c.name,id:c.id,checked:c.checked,req:c.getAttribute('aria-required')}));
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,4);
  return {headings:h,buttons:btns,checks,errs,sample:body.replace(/\s+/g,' ').slice(0,600)};
}
""")
print("SELF-ATTEST PAGE:", json.dumps(d, indent=1)[:1600])
