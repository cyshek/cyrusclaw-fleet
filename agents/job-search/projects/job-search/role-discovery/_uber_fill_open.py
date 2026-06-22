#!/usr/bin/env python3
"""Fill the OPEN Uber apply form (text fields + resume upload + screening radios + links).
Operates on the already-signed-in form page via CDP. Month dropdowns handled separately.
Usage: _uber_fill_open.py <job_id> <resume_pdf>
"""
import sys, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

_PI = json.loads((Path(__file__).resolve().parents[1] / "personal-info.json").read_text())

CDP="http://127.0.0.1:18800"
job_id=sys.argv[1]
resume=sys.argv[2]

pw=sync_playwright().start()
br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if f"/careers/apply/form/{job_id}" in p.url:
            page=p; break
    if page: break
if not page:
    print("NO FORM PAGE for", job_id); sys.exit(2)
print("page:", page.url)

def fill(name, val):
    loc=page.locator(f'input[name="{name}"], textarea[name="{name}"]').first
    if loc.count():
        loc.fill(val); print("filled", name, "=", val[:30]); return True
    print("MISS field", name); return False

# Basic info
fill("firstName", _PI["identity"]["first_name"])
fill("lastName", _PI["identity"]["last_name"])
# phone: digits only, no country code
fill("mobileNumber", _PI["contact"]["phone"].replace("-", ""))

# Experience 0 (Microsoft TPM, current)
fill("experiences.0.companyName","Microsoft")
fill("experiences.0.title","Technical Program Manager")
fill("experiences.0.startDate.year","2024")
fill("experiences.0.description","Technical Program Manager on Azure resilience/automation platform.")
# mark Current checkbox so end date not required
try:
    # find Current checkbox within experience section (first 'Current' checkbox)
    cbs=page.get_by_role("checkbox", name="Current")
    if cbs.count():
        if not cbs.nth(0).is_checked():
            cbs.nth(0).check(); print("checked Experience Current")
except Exception as e:
    print("exp current err", str(e)[:80])

# Education 0 (University of Houston, BS CS, 2021-2024)
fill("educations.0.schoolName","University of Houston")
fill("educations.0.degree","Bachelor of Science")
fill("educations.0.fieldOfStudy","Computer Science")
fill("educations.0.startDate.year","2021")
fill("educations.0.endDate.year","2024")

# Links
fill("linkedin", _PI.get("contact", {}).get("linkedin", "https://linkedin.com/in/cyshekari"))
fill("github", _PI.get("contact", {}).get("github", "https://github.com/cyshek"))

# Resume upload -> the file input with accept=.doc,.docx,.pdf,.rtf (2nd file input)
import os
uploaded=False
fis=page.locator('input[type=file]')
for i in range(fis.count()):
    acc=fis.nth(i).get_attribute("accept") or ""
    if "pdf" in acc.lower():
        fis.nth(i).set_input_files(os.path.abspath(resume), timeout=20000)
        uploaded=True; print("uploaded resume to file input", i, "accept=", acc)
        break
if not uploaded:
    print("WARN: no pdf file input found")
time.sleep(3)
# verify resume filename shows
body=page.inner_text("body")
fn=os.path.basename(resume)
print("resume_filename_in_body:", (fn in body) or (fn.replace('_',' ') in body))
for line in body.splitlines():
    if '.pdf' in line.lower():
        print("  pdf-line:", line.strip()[:90])

print("TEXT_FILL_DONE")
