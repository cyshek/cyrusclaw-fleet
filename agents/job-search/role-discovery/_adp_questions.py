#!/usr/bin/env python3
"""Click Next from Resume, map the Questions step fully (every input/select/radio/textarea)."""
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

loc = page.locator("button:has-text('Next')").filter(visible=True).first
if loc.count() > 0:
    loc.scroll_into_view_if_needed(timeout=2000)
    loc.click(timeout=6000)
    print("clicked Next from Resume")
time.sleep(5)

d = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
  const out={headings:[],questions:[],radios:[],selects:[],checks:[],textareas:[],texts:[],buttons:[],body:''};
  document.querySelectorAll('h1,h2,h3,h4,legend,.question-label,.vdl-label,label').forEach(h=>{
    if(!vis(h))return; const t=(h.innerText||'').trim(); if(t&&t.length<160) out.headings.push(t.slice(0,140));});
  // radio groups
  const seen={};
  document.querySelectorAll('input[type=radio]').forEach(r=>{
    if(!vis(r))return; const nm=r.name||r.getAttribute('name')||'?';
    if(!seen[nm]){seen[nm]=[]; }
    const lbl=(r.closest('label')||{}).innerText || (document.querySelector('label[for="'+r.id+'"]')||{}).innerText || r.value || '';
    seen[nm].push((lbl||'').trim().slice(0,30));
  });
  out.radios=Object.entries(seen).map(([nm,opts])=>({name:nm,opts}));
  document.querySelectorAll('select').forEach(s=>{if(!vis(s))return; out.selects.push({id:s.id,name:s.name,aria:(s.getAttribute('aria-label')||'').slice(0,50),opts:[...s.options].slice(0,10).map(o=>o.text.slice(0,30))});});
  document.querySelectorAll('input[type=checkbox]').forEach(c=>{if(!vis(c))return; const l=(c.closest('label')||{}).innerText||c.getAttribute('aria-label')||''; out.checks.push({id:c.id,name:c.name,label:(l||'').trim().slice(0,60),checked:c.checked});});
  document.querySelectorAll('textarea').forEach(t=>{if(!vis(t))return; out.textareas.push({id:t.id,name:t.name,aria:(t.getAttribute('aria-label')||'').slice(0,50),req:t.getAttribute('aria-required')});});
  document.querySelectorAll('input[type=text],input[type=number],input:not([type])').forEach(t=>{if(!vis(t))return; out.texts.push({id:t.id,name:t.name,aria:(t.getAttribute('aria-label')||'').slice(0,50),ph:t.placeholder,req:t.getAttribute('aria-required'),role:t.getAttribute('role')});});
  document.querySelectorAll('button,[role=button]').forEach(b=>{if(!vis(b))return;const t=(b.innerText||'').trim();if(t)out.buttons.push(t.slice(0,40));});
  out.body=(document.body.innerText||'').replace(/\s+/g,' ').slice(0,2500);
  return out;
}
""")
print("\nHEADINGS/LABELS:")
for h in d["headings"][:40]:
    print("  -", h)
print("\nRADIO GROUPS:", json.dumps(d["radios"], indent=1)[:1500])
print("\nSELECTS:", json.dumps(d["selects"], indent=1)[:1000])
print("\nCHECKBOXES:", json.dumps(d["checks"], indent=1)[:800])
print("\nTEXTAREAS:", json.dumps(d["textareas"])[:500])
print("\nTEXT INPUTS:", json.dumps(d["texts"])[:800])
print("\nBUTTONS:", d["buttons"][:15])
print("\nBODY:", d["body"][:2200])
print("[done]")
