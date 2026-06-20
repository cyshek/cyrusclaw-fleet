import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])
info=page.evaluate(r"""
() => {
  const el=document.getElementById('add_info_select_box');
  if(!el) return {found:false};
  // enumerate own + prototype properties/methods
  const props=[]; let o=el;
  for(let d=0; d<3 && o; d++){ Object.getOwnPropertyNames(o).forEach(n=>{ if(!props.includes(n)) props.push(n); }); o=Object.getPrototypeOf(o); }
  const interesting=props.filter(n=>/option|item|value|select|data|list|choice|open|expand/i.test(n)).slice(0,40);
  // try reading some
  const reads={};
  ['value','options','items','data','selectedValue','choices'].forEach(k=>{ try{ const v=el[k]; reads[k]= (typeof v==='function')?'<fn>':JSON.stringify(v)?.slice(0,150);}catch(e){reads[k]='err';} });
  // also compare to a WORKING one (question_3) to see how options are sourced
  const q3=document.getElementById('question_3');
  const q3reads={};
  ['value','options','items','data'].forEach(k=>{ try{ const v=q3[k]; q3reads[k]=(typeof v==='function')?'<fn>':JSON.stringify(v)?.slice(0,120);}catch(e){q3reads[k]='err';} });
  // child light-dom of both (sdf-select-option children?)
  const aiKids=[...el.querySelectorAll('*')].map(c=>c.tagName).slice(0,10);
  const q3Kids=[...q3.querySelectorAll('*')].map(c=>c.tagName).slice(0,10);
  return {interestingProps:interesting, reads, q3reads, aiKids, q3Kids};
}
""")
print(json.dumps(info, indent=2)[:2200])
