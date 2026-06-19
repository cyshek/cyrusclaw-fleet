#!/usr/bin/env python3
"""Robust resume upload into Uber's react dropzone. Tries set_input_files on the pdf
file input, then verifies the filename appears. If not, tries the Browse-files filechooser.
Usage: _uber_upload.py <job_id> <resume_pdf>
"""
import sys, os, time
from playwright.sync_api import sync_playwright

CDP="http://127.0.0.1:18800"
job_id=sys.argv[1]; resume=os.path.abspath(sys.argv[2])
fn=os.path.basename(resume)
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if f"/careers/apply/form/{job_id}" in p.url: page=p; break
    if page: break
if not page: print("NO PAGE"); sys.exit(2)
print("page:", page.url)

def shows():
    b=page.inner_text("body")
    return (fn in b) or (fn.replace('_',' ') in b)

# Attempt 1: set_input_files on the pdf-accepting hidden input
fi=None
fis=page.locator('input[type=file]')
for i in range(fis.count()):
    if "pdf" in (fis.nth(i).get_attribute("accept") or "").lower():
        fi=fis.nth(i); break
if fi is None:
    print("no pdf input"); sys.exit(3)
try:
    fi.set_input_files(resume, timeout=15000)
    print("attempt1 set_input_files done")
except Exception as e:
    print("attempt1 err", str(e)[:80])
time.sleep(3)
print("after attempt1 shows:", shows())

if not shows():
    # Attempt 2: filechooser via Browse files button
    try:
        with page.expect_file_chooser(timeout=8000) as fc_info:
            page.get_by_role("button", name="Browse files").first.click()
        fc=fc_info.value
        fc.set_files(resume)
        print("attempt2 filechooser set")
    except Exception as e:
        print("attempt2 err", str(e)[:120])
    time.sleep(3)
    print("after attempt2 shows:", shows())

# Final report
b=page.inner_text("body")
for line in b.splitlines():
    s=line.strip()
    if '.pdf' in s.lower() or 'remove' in s.lower() or 'uploaded' in s.lower():
        print("  >>", s[:80])
print("UPLOAD_SHOWS_FILENAME:", shows())
