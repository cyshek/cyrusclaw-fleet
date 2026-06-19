import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Dump the qMainDiv block that contains question_0 fully (HTML) to find any referral toggle
h=page.evaluate(r"""
()=>{
  const q0=document.getElementById('question_0');
  const block=q0?q0.closest('.qMainDiv'):null;
  if(!block) return 'no-block';
  // list all interactive controls + sdf + radios in this block
  const ctrls=[...block.querySelectorAll('input,select,textarea,sdf-radio-group,sdf-select-simple,[role=radio],[role=button],button')].map(c=>({tag:c.tagName,type:c.type||'',id:c.id||c.name,role:c.getAttribute('role'),txt:(c.innerText||c.value||'').trim().slice(0,25)}));
  return {ctrls, html:block.outerHTML.slice(0,900)};
}
""")
print(json.dumps(h, indent=1)[:1500] if isinstance(h,dict) else h)
