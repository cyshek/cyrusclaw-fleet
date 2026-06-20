#!/usr/bin/env python3
"""Find the 'How did you hear' and 'VISA sponsorship' dropdown triggers (MDF, non-input)."""
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
  // Find the two question labels, then look at their following siblings for any clickable dropdown
  const want=['heard about','VISA sponsorship'];
  const res=[];
  document.querySelectorAll('*').forEach(el=>{
    if(!vis(el))return;
    const own=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();
    for(const w of want){
      if(own.includes(w) && own.length<120){
        // search the surrounding block + next siblings for combobox/select/dropdown trigger
        const scope = el.closest('div,fieldset,section') || el.parentElement;
        const cands=[];
        if(scope){
          scope.querySelectorAll('[role=combobox],[role=listbox],[role=button],select,.MDFSelectBox,[class*=SelectBox],[class*=dropdown],button,input').forEach(c=>{
            if(!vis(c))return;
            cands.push({tag:c.tagName, role:c.getAttribute('role'), cls:(c.className||'').slice(0,40), id:c.id||c.name, txt:(c.innerText||c.value||'').trim().slice(0,30), haspopup:c.getAttribute('aria-haspopup')});
          });
        }
        res.push({q:own.slice(0,60), candidates:cands.slice(0,8)});
      }
    }
  });
  return res;
}
""")
print(json.dumps(data, indent=2)[:2500])
print("[done]")
