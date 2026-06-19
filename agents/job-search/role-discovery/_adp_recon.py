#!/usr/bin/env python3
"""Recon: connect to CDP, open ADP WFN job URL, dump page state to understand the wizard."""
import os, sys, time
from playwright.sync_api import sync_playwright

CDP_CANDIDATES = [
    os.environ.get("JOBSEARCH_CDP"),
    "http://127.0.0.1:18800",
    "http://[::1]:18800",
    "http://127.0.0.1:18900",
    "http://[::1]:18900",
]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=8720f224-b740-4129-895f-4c2f0dce1359&ccId=19000101_000001&type=MP&lang=en_US&jobId=543016"


def connect():
    pw = sync_playwright().start()
    last = None
    for cdp in CDP_CANDIDATES:
        if not cdp:
            continue
        try:
            br = pw.chromium.connect_over_cdp(cdp)
            if br.contexts:
                print("[connect] OK via %s; contexts=%d" % (cdp, len(br.contexts)))
                return pw, br, cdp
        except Exception as e:
            last = e
    raise RuntimeError("no CDP endpoint worked; last=%s" % last)


pw, br, cdp = connect()
ctx = br.contexts[0]
print("[ctx] existing pages=%d" % len(ctx.pages))
for i, p in enumerate(ctx.pages):
    try:
        print("  page[%d] url=%s" % (i, p.url[:120]))
    except Exception:
        pass

page = ctx.new_page()
print("[nav] navigating to job URL ...")
try:
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
except Exception as e:
    print("[nav] goto exception (continuing): %s" % e)
time.sleep(8)
print("[nav] final url=%s" % page.url[:160])
try:
    print("[nav] title=%s" % page.title()[:120])
except Exception:
    pass

js = r"""
() => {
  const out = {buttons:[], inputs:[], headings:[], bodyTextSample:''};
  document.querySelectorAll('button, a[role=button], [role=button], input[type=submit]').forEach(b=>{
    const t=(b.innerText||b.value||b.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ');
    if(t) out.buttons.push(t.slice(0,60));
  });
  document.querySelectorAll('input, select, textarea').forEach(el=>{
    out.inputs.push({tag:el.tagName.toLowerCase(), type:el.type||'', name:el.name||'', id:el.id||'', ph:el.placeholder||'', aria:(el.getAttribute('aria-label')||'').slice(0,40)});
  });
  document.querySelectorAll('h1,h2,h3,[role=heading]').forEach(h=>{const t=(h.innerText||'').trim(); if(t) out.headings.push(t.slice(0,80));});
  out.bodyTextSample=(document.body.innerText||'').replace(/\s+/g,' ').slice(0,800);
  return out;
}
"""
try:
    data = page.evaluate(js)
    print("\n=== HEADINGS ===")
    for h in data["headings"][:20]:
        print("  -", h)
    print("\n=== BUTTONS ===")
    for b in data["buttons"][:40]:
        print("  -", b)
    print("\n=== INPUTS ===")
    for inp in data["inputs"][:40]:
        print("  ", inp)
    print("\n=== BODY SAMPLE ===")
    print(data["bodyTextSample"])
except Exception as e:
    print("[dump] evaluate failed: %s" % e)

try:
    page.screenshot(path="role-discovery/_adp_recon.png", full_page=False)
    print("\n[shot] saved role-discovery/_adp_recon.png")
except Exception as e:
    print("[shot] failed: %s" % e)

print("\n[done]")
