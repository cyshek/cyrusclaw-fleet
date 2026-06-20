#!/usr/bin/env python3
"""Fill mobileNumber + verify firstName/lastName/email present; report remaining invalid required fields."""
import sys, time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"; job=sys.argv[1]
PI=json.load(open("../personal-info.json"))
phone=PI.get("phone") or PI.get("mobile") or "346-804-0227"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if f'/careers/apply/form/{job}' in p.url: page=p; break
    if page: break
if not page: print("NO PAGE"); sys.exit(2)
print("page:", page.url, "phone:", phone)

def setval(name, val):
    loc=page.locator(f'input[name="{name}"]').first
    if not loc.count(): return f"MISS:{name}"
    cur=loc.input_value()
    if cur and cur.strip(): return f"already:{name}={cur[:20]}"
    loc.fill(val)
    return f"filled:{name}={loc.input_value()[:20]}"

# fill mobileNumber (try common name variants)
for nm in ["mobileNumber","phone","phoneNumber"]:
    r=setval(nm, phone)
    print(r)
    if not r.startswith("MISS"): break
# ensure name/email
for nm,val in [("firstName",PI.get("first_name","Cyrus")),("lastName",PI.get("last_name","Shekari")),("email",PI.get("email","cyshekari@gmail.com"))]:
    print(setval(nm,val))
time.sleep(0.6)
inv=page.evaluate("""()=>{const i=[...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name||e.id||e.getAttribute('aria-label')||e.tagName); const sub=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.innerText)); return JSON.stringify({invalid:i, submitFound: !!sub, submitDisabled: sub? (sub.disabled||sub.getAttribute('aria-disabled')==='true'):null});}""")
print("STATE:", inv)
