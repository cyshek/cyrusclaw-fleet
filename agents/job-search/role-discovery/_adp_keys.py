#!/usr/bin/env python3
"""Does aria-invalid clear on real keystroke input? Type into Q0/Q2 char-by-char + fire events."""
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

# Q0: clear, click, type via keyboard
q0 = page.locator("#question_0")
q0.click(timeout=2500)
q0.press("Control+a"); q0.press("Delete")
page.keyboard.type("Referral none", delay=70)
time.sleep(0.4)
q0.press("Tab")
time.sleep(0.8)
print("Q0 after keystroke:", page.evaluate("()=>({v:document.getElementById('question_0').value,inv:document.getElementById('question_0').getAttribute('aria-invalid')})"))

# Q2: clear, type digits
q2 = page.locator("#question_2")
q2.click(timeout=2500)
q2.press("Control+a"); q2.press("Delete")
page.keyboard.type("150000", delay=70)
time.sleep(0.4)
q2.press("Tab")
time.sleep(0.8)
print("Q2 after keystroke:", page.evaluate("()=>({v:document.getElementById('question_2').value,inv:document.getElementById('question_2').getAttribute('aria-invalid')})"))

# Now check ALL aria-invalid and the specific validation messages with their position
allinv = page.evaluate(r"""
() => {
  const out=[];
  document.querySelectorAll('[aria-invalid=true]').forEach(e=>{
    if(e.offsetWidth===0)return;
    const block=e.closest('.qMainDiv');
    const lbl=block?(block.querySelector('label.qLabel')||{}).innerText:'';
    const err=block?(block.querySelector('.vdl-validation-error')||{}).innerText:'';
    out.push({id:e.id, label:(lbl||'').slice(0,60), errText:(err||'').slice(0,50), val:(e.value||'').slice(0,20)});
  });
  return out;
}
""")
print("ALL INVALID + labels:", json.dumps(allinv, indent=1)[:1000])
print("[done]")
