#!/usr/bin/env python3
"""List every interactive control in DOM order with the nearest preceding question text."""
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
  // Collect ALL nodes in document order; track last seen question-ish text; when we hit a control, pair them.
  const walker=document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let lastQ='';
  const pairs=[];
  let node=walker.currentNode;
  while(node){
    if(vis(node)){
      const own=[...node.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();
      if(own.length>8 && own.length<140 && (own.endsWith('*')||own.endsWith('?')||/sponsorship|heard about|Compensation|referred|desired salary|anything else/i.test(own))){
        lastQ=own;
      }
      const tag=node.tagName;
      const isCtrl = (tag==='INPUT'&&node.type!=='hidden') || tag==='SELECT' || tag==='TEXTAREA' || node.getAttribute('role')==='combobox';
      if(isCtrl){
        pairs.push({q:lastQ.slice(0,90), id:node.id||node.name, tag, type:node.type||'', role:node.getAttribute('role')||'', req:node.getAttribute('aria-required')==='true'||node.required, haspopup:node.getAttribute('aria-haspopup')});
      }
    }
    node=walker.nextNode();
  }
  return pairs;
}
""")
print("CONTROL <- preceding question:")
for p_ in data:
    print("  ", json.dumps(p_))
print("[done]")
