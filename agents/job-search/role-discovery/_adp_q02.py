#!/usr/bin/env python3
"""Inspect question_0 + question_2 validation attrs; try 'None' for Q0 and re-test Q2 formats."""
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

attrs = page.evaluate(r"""
() => {
  const dump=id=>{const e=document.getElementById(id); if(!e)return null; const o={}; for(const a of e.attributes)o[a.name]=a.value.slice(0,50); return o;};
  return {q0:dump('question_0'), q2:dump('question_2')};
}
""")
print("Q0 attrs:", json.dumps(attrs["q0"]))
print("Q2 attrs:", json.dumps(attrs["q2"]))

# Try Q0 = 'None'
q0 = page.locator("#question_0")
q0.fill("", timeout=2000); q0.fill("None", timeout=2000)
page.keyboard.press("Tab"); time.sleep(0.6)
inv0 = page.evaluate("() => document.getElementById('question_0').getAttribute('aria-invalid')")
print("Q0='None' aria-invalid:", inv0)

# If still invalid try a plain word
if inv0 == "true":
    q0.fill("", timeout=2000); q0.fill("Not applicable", timeout=2000)
    page.keyboard.press("Tab"); time.sleep(0.6)
    print("Q0='Not applicable' aria-invalid:", page.evaluate("() => document.getElementById('question_0').getAttribute('aria-invalid')"))

# Try Q2 variations: plain integer
q2 = page.locator("#question_2")
for v in ["150000", "150,000", "150000.00", "120000"]:
    q2.fill("", timeout=2000); q2.fill(v, timeout=2000)
    page.keyboard.press("Tab"); time.sleep(0.7)
    state = page.evaluate("() => ({val:document.getElementById('question_2').value, inv:document.getElementById('question_2').getAttribute('aria-invalid')})")
    print("Q2=%r -> %s" % (v, state))
print("[done]")
