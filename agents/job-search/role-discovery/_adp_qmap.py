#!/usr/bin/env python3
"""Map each Question to its input control precisely (handles MDF comboboxes)."""
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

data = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
  // Find all question blocks: each has a label/legend ending with * and a control
  const out=[];
  // ADP MDF: question wrappers often .mdf-question or contain a label + an input/combobox
  // Strategy: for each required control, walk up to find its question text.
  const controls=[...document.querySelectorAll('input,textarea,[role=combobox]')].filter(vis);
  controls.forEach(el=>{
    let q='';
    let n=el;
    for(let i=0;i<6 && n;i++){
      n=n.parentElement;
      if(!n) break;
      const lbl=n.querySelector('label,legend,.vdl-label,.question-text');
      if(lbl && lbl.innerText && lbl.innerText.trim().length>3){ q=lbl.innerText.trim(); break; }
    }
    out.push({
      id:el.id||el.name, tag:el.tagName, type:el.type||'', role:el.getAttribute('role')||'',
      req:el.getAttribute('aria-required')==='true'||el.required,
      ariaExpanded:el.getAttribute('aria-expanded'), ariaHaspopup:el.getAttribute('aria-haspopup'),
      question:q.slice(0,90), val:(el.value||'').slice(0,30)
    });
  });
  return out;
}
""")
print("CONTROLS->QUESTIONS:")
for c in data:
    print("  ", json.dumps(c))
print("[done]")
