#!/usr/bin/env python3
"""Definitive Personal Info: country, places (MOUSE-click pac-item), both phones, Next. One flow."""
import time, json
import json as _json; from pathlib import Path as _Path; _PI = _json.loads((_Path('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/../personal-info.json').read_text()))
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

# 1) country
c = page.locator("#PersonalAddress_country")
c.click(timeout=4000); time.sleep(0.5)
c.type("United States", delay=40, timeout=5000); time.sleep(1.4)
o = page.locator("[role=option]:has-text('United States')").filter(visible=True).first
if o.count() > 0:
    o.click(timeout=2500); print("country picked")
time.sleep(1.0)

# 2) address line1 via Places, MOUSE-click the first pac-item to fire place_changed
line1 = page.locator("#PersonalAddress_address_line1")
line1.click(timeout=4000); line1.fill("", timeout=2000)
line1.type(f"{_PI['address']['street']}, {_PI['address']['city']}, {_PI['address']['state']} {_PI['address']['zip']}", delay=60, timeout=8000)
time.sleep(2.6)
pac = page.locator(".pac-container .pac-item").first
if pac.count() > 0:
    box = pac.bounding_box()
    print("pac-item box:", box)
    pac.hover()
    time.sleep(0.3)
    pac.click(timeout=3000)
    print("mouse-clicked first pac-item")
time.sleep(2.2)
vals = page.evaluate("() => ({l1:document.getElementById('PersonalAddress_address_line1').value, city:document.getElementById('PersonalAddress_city').value, zip:document.getElementById('PersonalAddress_postalCode').value, county:document.getElementById('PersonalAddress_county').value})")
print("addr:", vals)

# 3) fill BOTH phone inputs with the full number
fullnum = "+1 346 804 0227"
for pid in ("personalInfomationMobileNumberError", "personalInfomationMobileNumberErrorMessage"):
    try:
        el = page.locator("#%s" % pid)
        if el.count() > 0 and el.first.is_visible():
            el.first.click(timeout=2000)
            el.first.fill(fullnum, timeout=2500)
            print("filled phone", pid)
    except Exception as exc:
        print("phone fill exc", pid, str(exc)[:80])
time.sleep(0.6)
# blur to commit
page.keyboard.press("Tab")
time.sleep(0.8)

# Re-check borders/invalid BEFORE clicking Next
pre = page.evaluate(r"""
() => {
  const reds=[];
  document.querySelectorAll('input').forEach(el=>{
    const s=getComputedStyle(el); const bc=s.borderColor||'';
    if(bc.includes('222, 70, 53')) reds.push({id:el.id||el.name, val:(el.value||'').slice(0,28)});
  });
  return reds;
}
""")
print("red-bordered before Next:", pre)

# 4) Next
loc = page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000)
print("clicked Next")
time.sleep(5)

res = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0; };
  const errs=[];
  document.querySelectorAll('.error,.vdl-validation-message,[role=alert]').forEach(e=>{if(!vis(e))return;const t=(e.innerText||'').trim();if(t&&!/be advised|currently signed|Afghanistan/i.test(t))errs.push(t.slice(0,90));});
  const fileInput=document.querySelector("input[type=file]");
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<80).slice(0,6);
  const stillPI = /Correct the information/i.test(document.body.innerText);
  return {errs, hasFileInput:!!fileInput, fileId:fileInput?fileInput.id:null, headings:h, stillPersonalInfo:stillPI, bodySample:document.body.innerText.replace(/\s+/g,' ').slice(0,500)};
}
""")
print("RESULT:", json.dumps(res, indent=1)[:1400])
print("[done]")
