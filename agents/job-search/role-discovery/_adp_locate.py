#!/usr/bin/env python3
"""Locate the 'Enter a valid value.' message in the DOM and identify its owning field."""
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
  const hits=[];
  document.querySelectorAll('*').forEach(el=>{
    const own=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();
    if(/Enter a valid value/i.test(own)){
      // climb to find the question block + its control
      const block=el.closest('.qMainDiv')||el.parentElement.parentElement;
      let label='', ctrlId='', ctrlTag='';
      if(block){
        const lb=block.querySelector('label.qLabel,.qLabel,label'); label=lb?lb.innerText.trim():'';
        const c=block.querySelector('input,select,textarea,sdf-select-simple,[role=combobox]'); 
        if(c){ctrlId=c.id||c.name; ctrlTag=c.tagName;}
      }
      hits.push({msg:own.slice(0,40), forAttr:el.getAttribute('for')||'', label:label.slice(0,80), ctrlId, ctrlTag,
                 parentChain:(()=>{let p=el,arr=[];for(let i=0;i<5&&p;i++){arr.push(p.tagName+(p.id?'#'+p.id:'')+(p.className?'.'+String(p.className).split(' ')[0]:''));p=p.parentElement;}return arr.join(' < ');})()});
    }
  });
  return hits;
}
""")
print("'Enter a valid value' locations:")
print(json.dumps(data, indent=2)[:2000])
print("[done]")
