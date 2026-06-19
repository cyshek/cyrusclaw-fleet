#!/usr/bin/env python3
"""Resume step: find file input, upload the tailored PDF, verify, Next. One flow."""
import time, json, os
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RESUME = os.path.abspath("applications/queued/Sager Electronics-2539/Cyrus_Shekari_Resume_Sager Electronics_2539_v2.pdf")
print("resume exists:", os.path.exists(RESUME), RESUME)

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]
page = None
for p in ctx.pages:
    if "workforcenow.adp.com" in p.url:
        page = p
        break
print("attached:", page.url[:110])

# Enumerate all file inputs (the resume one vs attachments one)
finputs = page.evaluate(r"""
() => [...document.querySelectorAll('input[type=file]')].map((el,i)=>({
  idx:i, id:el.id, name:el.name, accept:el.accept, aria:(el.getAttribute('aria-label')||''),
  near:(el.closest('[class*=upload],[class*=resume],[class*=attach],section,div')||{}).innerText? (el.closest('[class*=upload],[class*=resume],[class*=attach],section,div').innerText||'').replace(/\s+/g,' ').slice(0,60):''
}))
""")
print("FILE INPUTS:", json.dumps(finputs, indent=1)[:900])

# The resume input is the FIRST file input (Resume section comes before Attachments).
# Upload via Playwright set_input_files (works even if input is hidden behind a dropzone).
fi = page.locator("input[type=file]").first
fi.set_input_files(RESUME, timeout=8000)
print("set_input_files done")
time.sleep(4)

# Verify: a filename label should appear; 'Required' indicator should clear
after = page.evaluate(r"""
() => {
  const body=document.body.innerText;
  const hasFilename=/Cyrus_Shekari_Resume/i.test(body) || /\.pdf/i.test(body);
  const stillRequiredEmpty=/Resume\s*Required/i.test(body.replace(/\s+/g,' '));
  // any progress/uploaded indicator
  const uploaded=[...document.querySelectorAll('[class*=file],[class*=uploaded],.attachment-name,.file-name')].map(e=>e.innerText.trim()).filter(Boolean).slice(0,5);
  return {hasFilename, stillRequiredEmpty, uploaded, bodySample:body.replace(/\s+/g,' ').slice(0,400)};
}
""")
print("AFTER UPLOAD:", json.dumps(after, indent=1)[:900])
print("[done — NOT clicking Next yet]")
