#!/usr/bin/env python3
"""Dump simplified HTML of the questions area to see how each Q renders."""
import re
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

html = page.evaluate(r"""
() => {
  // find the container holding 'how you heard' and 'VISA sponsorship'
  let host=null;
  document.querySelectorAll('div,section,form').forEach(el=>{
    const t=el.innerText||'';
    if(t.includes('heard about Sager') && t.includes('VISA sponsorship') && t.length<4000 && (!host || el.innerText.length<host.innerText.length)) host=el;
  });
  if(!host) host=document.body;
  // strip scripts/styles, keep tags + a bit of structure
  let h=host.innerHTML;
  return h;
}
""")
# simplify: collapse whitespace, drop class noise but keep tag names, ids, types, roles, option text
h = html
h = re.sub(r'\s+', ' ', h)
# Keep only meaningful attrs
h = re.sub(r'class="[^"]{40,}"', 'class="..."', h)
# Print in chunks around key tags
print("LENGTH", len(h))
# Show around each question keyword
for kw in ["heard about Sager", "VISA sponsorship", "Total Compensation", "referred by a Sager"]:
    i = h.find(kw)
    if i >= 0:
        print("\n===== around %r =====" % kw)
        print(h[max(0, i-400):i+600])
print("[done]")
