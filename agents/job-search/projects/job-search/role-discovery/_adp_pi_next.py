#!/usr/bin/env python3
"""ONE continuous flow: fill PersonalInfo address (country->places), Next, report advance/errors."""
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

# If we got bounced back to Personal Info, fill it fresh in ONE flow.
def fill_personal():
    # country first
    c = page.locator("#PersonalAddress_country")
    c.click(timeout=4000); time.sleep(0.5)
    c.type("United States", delay=40, timeout=5000); time.sleep(1.4)
    o = page.locator("[role=option]:has-text('United States')").filter(visible=True).first
    if o.count() > 0:
        o.click(timeout=2500); print("country picked")
    time.sleep(1.0)
    # places address
    line1 = page.locator("#PersonalAddress_address_line1")
    line1.click(timeout=4000); line1.fill("", timeout=2000)
    line1.type("12420 NE 120th St, Kirkland, WA 98034", delay=55, timeout=8000)
    time.sleep(2.5)
    n = page.evaluate("() => [...document.querySelectorAll('.pac-container .pac-item')].length")
    print("pac items:", n)
    if n:
        line1.press("ArrowDown"); time.sleep(0.4); line1.press("Enter"); time.sleep(2.2)
    vals = page.evaluate("() => ({l1:document.getElementById('PersonalAddress_address_line1').value, city:document.getElementById('PersonalAddress_city').value, zip:document.getElementById('PersonalAddress_postalCode').value})")
    print("addr after fill:", vals)

fill_personal()
time.sleep(1)

# Click Next
loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000)
loc.click(timeout=6000)
print("clicked Next")
time.sleep(5)

# Did we advance? check active step + errors
res = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0; };
  const errs=[];
  document.querySelectorAll('.error,.vdl-validation-message,[role=alert],.invalid-feedback,.has-error').forEach(e=>{if(!vis(e))return;const t=(e.innerText||'').trim();if(t&&!/be advised|currently signed/i.test(t))errs.push(t.slice(0,90));});
  // active step (often has aria-current or active class in a stepper)
  const steps=[...document.querySelectorAll('[aria-current],.active-step,.is-active,.current')].map(s=>(s.innerText||'').trim().slice(0,40)).filter(Boolean);
  const fileInput = document.querySelector("input[type=file]");
  const h = [...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<80);
  return {errs, steps, hasFileInput:!!fileInput, fileId: fileInput?fileInput.id:null, headings:h.slice(0,10), bodyHas:{resume:/resume/i.test(document.body.innerText), upload:/upload|drag|drop/i.test(document.body.innerText)}};
}
""")
print("RESULT:", json.dumps(res, indent=1)[:1200])
print("[done]")
