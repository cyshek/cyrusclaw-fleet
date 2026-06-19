#!/usr/bin/env python3
"""Remove junk parser experience blocks on Uber form, keeping only experiences.0 (Microsoft).
Then report remaining experience count + any aria-invalid required fields.
Usage: _uber_rmexp.py <job_id>
"""
import sys, time
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"; job=sys.argv[1]
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if f'/careers/apply/form/{job}' in p.url: page=p; break
    if page: break
if not page: print("NO PAGE"); sys.exit(2)
print("page:", page.url)

# Click every "Remove experience" button (each click removes one block; list shrinks).
# Loop because the DOM re-renders after each removal.
removed=0
for _ in range(8):
    n=page.evaluate("""()=>{
      const btns=[...document.querySelectorAll('button')].filter(b=>/remove experience/i.test(b.innerText));
      if(!btns.length) return 0;
      btns[btns.length-1].scrollIntoView({block:'center'}); btns[btns.length-1].click();
      return btns.length;
    }""")
    if not n: break
    removed+=1
    time.sleep(0.8)
print("remove clicks:", removed)
time.sleep(1)

info=page.evaluate("""()=>{
  const exps=[...document.querySelectorAll('input[name^="experiences."][name$=".companyName"]')].map(e=>({n:e.name, co:e.value}));
  const rm=[...document.querySelectorAll('button')].filter(b=>/remove experience/i.test(b.innerText)).length;
  const inv=[...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name||e.id||e.getAttribute('aria-label')||e.tagName);
  return JSON.stringify({exps, removeBtns:rm, invalid:inv});
}""")
print("AFTER:", info)
