import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Find question_0's own onChange handler (what fires when you type) by reading its react props
wire=page.evaluate(r"""
()=>{
  const el=document.getElementById('question_0');
  const pk=Object.keys(el).find(k=>k.startsWith('__reactProps'));
  if(!pk) return 'no-props';
  const p=el[pk];
  const out={keys:Object.keys(p)};
  ['onChange','onBlur','onInput'].forEach(h=>{ if(p[h]) out[h]=p[h].toString().slice(0,300); });
  return out;
}
""")
print("question_0 props:", json.dumps(wire, indent=1)[:1200])
