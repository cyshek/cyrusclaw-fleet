#!/usr/bin/env python3
"""Re-attach to the live (OTP-authenticated) ADP WFN page and map the wizard.
Clicks 'Complete Your Application' then dumps each step as we Continue through.
Usage: _adp_map.py [--click "Complete Your Application"] [--continue N]
"""
import os, sys, time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"

DUMP_JS = r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };
  const out = {buttons:[], inputs:[], headings:[], radios:[], selects:[], body:''};
  document.querySelectorAll('button, a[role=button], [role=button], input[type=submit], input[type=button]').forEach(b=>{
    if(!vis(b)) return;
    const t=(b.innerText||b.value||b.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ');
    if(t) out.buttons.push(t.slice(0,70));
  });
  document.querySelectorAll('input, textarea').forEach(el=>{
    if(!vis(el)) return;
    out.inputs.push({type:el.type||'', name:el.name||'', id:el.id||'',
      ph:el.placeholder||'', aria:(el.getAttribute('aria-label')||'').slice(0,55), req:el.required||el.getAttribute('aria-required')==='true', val:(el.value||'').slice(0,20)});
  });
  document.querySelectorAll('select').forEach(el=>{
    if(!vis(el)) return;
    out.selects.push({name:el.name||'', id:el.id||'', aria:(el.getAttribute('aria-label')||'').slice(0,55),
      opts:[...el.options].slice(0,8).map(o=>o.text.slice(0,30))});
  });
  document.querySelectorAll('h1,h2,h3,h4,[role=heading],legend,.step-title,.section-title').forEach(h=>{
    if(!vis(h)) return; const t=(h.innerText||'').trim(); if(t&&t.length<100) out.headings.push(t);});
  out.body=(document.body.innerText||'').replace(/\s+/g,' ').slice(0,2000);
  out.url=location.href;
  return out;
}
"""

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]
page = None
for p in ctx.pages:
    try:
        if "workforcenow.adp.com" in p.url:
            page = p
            break
    except Exception:
        pass
if not page:
    print("NO WFN PAGE FOUND; pages:", [p.url[:80] for p in ctx.pages])
    sys.exit(1)

print("attached:", page.url[:140])


def dump(label):
    try:
        d = page.evaluate(DUMP_JS)
    except Exception as exc:
        print("dump fail", str(exc)[:120])
        return {}
    print("\n==== %s ====" % label)
    print("url:", d.get("url", "")[:150])
    if d.get("headings"):
        print("HEADINGS:", " | ".join(d["headings"][:15]))
    if d.get("buttons"):
        print("BUTTONS:", " | ".join(d["buttons"][:25]))
    for inp in d.get("inputs", [])[:35]:
        print("  INPUT", inp)
    for s in d.get("selects", [])[:15]:
        print("  SELECT", s)
    print("BODY:", d.get("body", "")[:1500])
    return d


def click_text(*texts, timeout=8000):
    for t in texts:
        for sel in ("button:has-text(\"%s\")" % t, "a[role=button]:has-text(\"%s\")" % t,
                    "[role=button]:has-text(\"%s\")" % t):
            try:
                loc = page.locator(sel).filter(visible=True).first
                if loc.count() > 0:
                    loc.scroll_into_view_if_needed(timeout=2000)
                    loc.click(timeout=timeout)
                    print("clicked:", t)
                    return True
            except Exception:
                continue
    return False


dump("CURRENT")

if "--complete" in sys.argv:
    if click_text("Complete Your Application", "Complete your application", "Continue Application"):
        time.sleep(6)
        dump("AFTER-COMPLETE")

print("\n[map done]")
