#!/usr/bin/env python3
"""Screenshot the Questions step + dump ALL role=combobox + MDFSelectBox elements anywhere."""
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

page.screenshot(path="role-discovery/_adp_questions.png", full_page=True)
print("shot saved")

# Dump EVERY combobox / MDFSelectBox / select anywhere with its DOM-order index + a snippet of preceding text
data = page.evaluate(r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
  const all=[...document.querySelectorAll('[role=combobox],.MDFSelectBox,[class*=SelectBox],select')].filter(vis);
  return all.map(el=>{
    // nearest preceding label text (previous siblings / ancestors)
    let q=''; let n=el;
    for(let i=0;i<8 && n;i++){
      let s=n.previousElementSibling;
      while(s){ const t=(s.innerText||'').trim(); if(t&&t.length<120){ q=t; break; } s=s.previousElementSibling; }
      if(q) break; n=n.parentElement;
    }
    return {tag:el.tagName, role:el.getAttribute('role'), cls:(el.className||'').slice(0,45), id:el.id||el.name,
            txt:(el.innerText||el.value||'').trim().slice(0,40).replace(/\n/g,'|'), precedingText:q.slice(0,70).replace(/\n/g,'|')};
  });
}
""")
print("ALL DROPDOWNS/COMBOBOXES:")
for d in data:
    print("  ", json.dumps(d))
print("[done]")
