#!/usr/bin/env python3
"""Probe the two phone inputs + fix address border by re-picking place via mouse click."""
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

phones = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
  return [...document.querySelectorAll('input[type=tel],input[name=phone]')].map(el=>({
    id:el.id, name:el.name, val:el.value, vis:vis(el),
    aria:(el.getAttribute('aria-label')||''), req:el.getAttribute('aria-required'),
    rect:el.getBoundingClientRect().width
  }));
}
""")
print("PHONES:", json.dumps(phones, indent=1))
print("[done]")
