#!/usr/bin/env python3
"""Extract full constraint metadata for question_0 and question_2 (outerHTML + nearby script hints)."""
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

data = page.evaluate(r"""
() => {
  const out={};
  ['question_0','question_2'].forEach(id=>{
    const e=document.getElementById(id);
    if(!e){out[id]='NOT FOUND';return;}
    const block=e.closest('.qMainDiv')||e.parentElement;
    out[id]={
      outer:e.outerHTML.slice(0,400),
      blockText:(block?block.innerText:'').replace(/\s+/g,' ').slice(0,200),
      // react fiber props sometimes hold validation
      maxlen:e.maxLength, pattern:e.pattern, min:e.min, max:e.max,
      dataAttrs:[...e.attributes].filter(a=>a.name.startsWith('data')).map(a=>a.name+'='+a.value.slice(0,40))
    };
  });
  return out;
}
""")
import json
print(json.dumps(data, indent=2)[:2000])

# Also: maybe question_0 is NOT actually required when 'Sager Employee' isn't chosen for Q1.
# Check if Q0 becomes optional. But it has aria-required=true. Try a realistic short value.
print("\n--- try Q2 small integer 100 and Q0 single word ---")
page.locator("#question_2").fill("100", timeout=2000); page.keyboard.press("Tab"); 
import time; time.sleep(0.6)
print("Q2=100:", page.evaluate("()=>({v:document.getElementById('question_2').value,inv:document.getElementById('question_2').getAttribute('aria-invalid')})"))
page.locator("#question_0").fill("NA", timeout=2000); page.keyboard.press("Tab"); time.sleep(0.6)
print("Q0=NA:", page.evaluate("()=>({v:document.getElementById('question_0').value,inv:document.getElementById('question_0').getAttribute('aria-invalid')})"))
print("[done]")
