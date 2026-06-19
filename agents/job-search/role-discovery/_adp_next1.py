#!/usr/bin/env python3
"""Click Next on Personal Info, dump the Resume step."""
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

# Click Next
clicked = False
for sel in ("button:has-text('Next')", "button:has-text('Continue')", "[role=button]:has-text('Next')"):
    loc = page.locator(sel).filter(visible=True).first
    if loc.count() > 0:
        loc.scroll_into_view_if_needed(timeout=2000)
        loc.click(timeout=6000)
        clicked = True
        print("clicked Next via", sel)
        break
print("clicked:", clicked)
time.sleep(5)

d = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
  const out={buttons:[],inputs:[],headings:[],fileInputs:[],errors:[],body:''};
  document.querySelectorAll('button,a[role=button],[role=button]').forEach(b=>{if(!vis(b))return;const t=(b.innerText||b.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ');if(t)out.buttons.push(t.slice(0,60));});
  document.querySelectorAll('input').forEach(el=>{out.inputs.push({type:el.type,id:el.id,name:el.name,aria:(el.getAttribute('aria-label')||'').slice(0,40),vis:vis(el),accept:el.accept||''});if(el.type==='file')out.fileInputs.push({id:el.id,name:el.name,accept:el.accept,vis:vis(el)});});
  document.querySelectorAll('h1,h2,h3,h4,legend,.step-title').forEach(h=>{if(!vis(h))return;const t=(h.innerText||'').trim();if(t&&t.length<90)out.headings.push(t);});
  document.querySelectorAll('.error,.vdl-validation-message,[role=alert],.invalid-feedback').forEach(e=>{if(!vis(e))return;const t=(e.innerText||'').trim();if(t)out.errors.push(t.slice(0,80));});
  out.body=(document.body.innerText||'').replace(/\s+/g,' ').slice(0,1500);
  return out;
}
""")
print("\nHEADINGS:", " | ".join(d["headings"][:12]))
print("BUTTONS:", " | ".join(d["buttons"][:20]))
print("ERRORS:", d["errors"])
print("FILE INPUTS:", json.dumps(d["fileInputs"]))
print("ALL INPUTS:")
for inp in d["inputs"][:25]:
    print("  ", inp)
print("BODY:", d["body"][:1200])
print("[done]")
