#!/usr/bin/env python3
"""Generic CDP resume uploader for the OpenClaw browser (port 18800).
Usage: _cdp_upload.py <url_substr> <selector> <pdf_path>
Finds the page whose URL contains url_substr, sets pdf on selector (default #resume).
"""
import sys, time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"

def main():
    url_substr = sys.argv[1]
    selector = sys.argv[2] if len(sys.argv) > 2 else "#resume"
    pdf = sys.argv[3]
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    page = None
    for ctx in br.contexts:
        for p in ctx.pages:
            if url_substr in p.url:
                page = p; break
        if page: break
    if not page:
        print("NO PAGE MATCHING", url_substr); 
        for ctx in br.contexts:
            for p in ctx.pages: print(" open:", p.url)
        return 2
    print("page:", page.url)
    fi = page.query_selector(selector)
    if not fi:
        print("NO SELECTOR", selector); return 3
    fi.set_input_files(pdf, timeout=15000)
    time.sleep(2)
    body = page.inner_text("body")
    import os
    fname = os.path.basename(pdf)
    ok = fname in body or fname.replace('_',' ') in body
    print("UPLOAD_DONE filename_in_body=", ok)
    # print any line mentioning pdf
    for line in body.splitlines():
        if '.pdf' in line.lower() or 'resume' in line.lower():
            print("  >>", line.strip()[:90])
    return 0

if __name__ == "__main__":
    sys.exit(main())
