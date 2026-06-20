#!/usr/bin/env python3
"""Find which field shows 'Enter a valid value' / aria-invalid now."""
import json
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
  const invalid=[];
  document.querySelectorAll('[aria-invalid=true]').forEach(el=>{
    if(!vis(el))return;
    // nearest validation message
    let msg=''; const wrap=el.closest('.qMainDiv,.vdl-form-group,div');
    if(wrap){const m=wrap.querySelector('.vdl-validation-error,[role=alert]'); msg=m?m.innerText.trim():'';}
    invalid.push({id:el.id||el.name, tag:el.tagName, val:(el.value||'').slice(0,30), msg:msg.slice(0,60)});
  });
  // also list all error labels with text + their associated 'for'
  const labels=[];
  document.querySelectorAll('.vdl-validation-error,[role=alert]').forEach(l=>{
    if(!vis(l))return; const t=(l.innerText||'').trim();
    if(t&&t.length>1&&!/Afghan/i.test(t)) labels.push({for:l.getAttribute('for')||'', txt:t.slice(0,60)});
  });
  // current values of the question fields
  const g=id=>{const e=document.getElementById(id);return e?e.value:null;};
  return {invalid, labels, vals:{q0:g('question_0'),q2:g('question_2'),desired:g('desiredSalaryId')}};
}
""")
print(json.dumps(info, indent=2)[:1800])
print("[done]")
