#!/usr/bin/env python3
"""Find the EXACT highlighted/invalid field on Personal Info after a failed Next."""
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

info = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0; };
  const bad=[];
  // aria-invalid
  document.querySelectorAll('[aria-invalid=true]').forEach(el=>{
    bad.push({by:'aria-invalid', id:el.id||el.name, aria:(el.getAttribute('aria-label')||'').slice(0,40), val:(el.value||'').slice(0,30)});
  });
  // error class on field wrappers
  document.querySelectorAll('.vdl-textbox--error,.has-error,.is-invalid,.error input,[class*=error] input,.vdl-validation-state--error').forEach(el=>{
    const inp = el.matches('input,select,textarea')?el:el.querySelector('input,select,textarea');
    bad.push({by:'errclass', cls:el.className.slice(0,50), id:(inp?inp.id||inp.name:''), val:inp?(inp.value||'').slice(0,30):''});
  });
  // any visible validation message text near a field
  const msgs=[];
  document.querySelectorAll('.vdl-validation-message,.validation-message,[class*=validation]').forEach(m=>{
    if(!vis(m))return; const t=(m.innerText||'').trim(); if(t) msgs.push(t.slice(0,80));
  });
  // red-bordered inputs (computed style)
  const reds=[];
  document.querySelectorAll('input,select,textarea').forEach(el=>{
    if(!vis(el))return;
    const s=getComputedStyle(el);
    const bc=s.borderColor||'';
    if(/rgb\(2[0-5][0-9],\s*[0-5]?[0-9],/.test(bc) || /rgb\(2[0-4][0-9]/.test(bc) && parseInt(bc.split(',')[1])<80){
      reds.push({id:el.id||el.name, border:bc, val:(el.value||'').slice(0,25), req:el.getAttribute('aria-required')});
    }
  });
  return {ariaInvalidAndErrClass:bad, validationMsgs:msgs, redBorders:reds};
}
""")
print(json.dumps(info, indent=2)[:2500])
print("[done]")
