#!/usr/bin/env python3
"""Dump question blocks in DOM order with the control immediately following each label."""
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

data = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
  // Walk the questions container; collect text nodes that look like a question (end with * or ?)
  // and the next interactive control after each.
  const all=[...document.querySelectorAll('*')].filter(vis);
  const blocks=[];
  // Find elements whose direct text ends with * (the question labels)
  document.querySelectorAll('label,legend,div,span,p').forEach(el=>{
    if(!vis(el)) return;
    const own=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();
    if(own.length>8 && (own.endsWith('*')||own.endsWith('?')||/sponsorship|heard about|Compensation|referred/i.test(own)) && own.length<140){
      // find next control within this block's parent
      const scope=el.closest('.mdf-question,.vdl-form-group,fieldset,.question,div')||el.parentElement;
      let ctrl=null;
      if(scope){
        ctrl=scope.querySelector('[role=combobox],select,textarea,input[type=text],input[type=radio],input[type=checkbox],input:not([type])');
      }
      blocks.push({q:own.slice(0,110), ctrlId: ctrl?(ctrl.id||ctrl.name):null, ctrlRole: ctrl?ctrl.getAttribute('role'):null, ctrlTag: ctrl?ctrl.tagName:null, ctrlType: ctrl?ctrl.type:null});
    }
  });
  // dedup by q
  const seen=new Set(); const uniq=[];
  for(const b of blocks){ if(!seen.has(b.q)){seen.add(b.q); uniq.push(b);} }
  return uniq;
}
""")
print("ORDERED QUESTION BLOCKS:")
for b in data:
    print("  ", json.dumps(b))
print("[done]")
