import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])
d=page.evaluate(r"""
()=>{
  const vis=el=>{const r=el.getBoundingClientRect();const s=getComputedStyle(el);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
  const out={selects:[],sdfSelects:[],checks:[],radios:[],labels:[]};
  document.querySelectorAll('select').forEach(s=>{if(!vis(s))return;out.selects.push({id:s.id,name:s.name,aria:(s.getAttribute('aria-label')||'').slice(0,40),opts:[...s.options].map(o=>o.text.slice(0,40)).slice(0,12)});});
  document.querySelectorAll('sdf-select-simple').forEach(s=>{if(!vis(s))return;out.sdfSelects.push({id:s.id,aria:(s.getAttribute('aria-label')||s.getAttribute('label')||'').slice(0,40),req:s.getAttribute('required')});});
  document.querySelectorAll('input[type=checkbox]').forEach(c=>{if(!vis(c))return;const l=(c.closest('label')||{}).innerText||c.getAttribute('aria-label')||'';out.checks.push({id:c.id,name:c.name,label:(l||'').trim().slice(0,55),checked:c.checked});});
  document.querySelectorAll('input[type=radio]').forEach(r=>{if(!vis(r))return;const l=(r.closest('label')||{}).innerText||'';out.radios.push({name:r.name,id:r.id,label:(l||'').trim().slice(0,40),checked:r.checked});});
  document.querySelectorAll('label.qLabel,legend,h3,h4,.question-label-container').forEach(l=>{if(!vis(l))return;const t=(l.innerText||'').trim();if(t&&t.length<80)out.labels.push(t);});
  return out;
}
""")
print(json.dumps(d, indent=2)[:2600])
