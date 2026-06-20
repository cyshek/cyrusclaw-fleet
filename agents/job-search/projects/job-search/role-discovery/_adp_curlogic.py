import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Dump ALL props in the bag that has currencyValidation, to understand currencyType source
mp=page.evaluate(r"""
()=>{
  const el=document.getElementById('question_0')||document.body;
  const k=Object.keys(el).find(x=>x.startsWith('__reactFiber'));
  if(!k) return null; let f=el[k];
  for(let i=0;i<16&&f;i++){
    const m=f.memoizedProps;
    if(m&&('currencyValidation'in m)){
      const o={};
      Object.keys(m).forEach(key=>{ try{ const v=m[key]; o[key]= (typeof v==='function')?'<fn>':(JSON.stringify(v)||'').slice(0,90);}catch(e){o[key]='?';} });
      return o;
    }
    f=f.return;
  }
  return null;
}
""")
print(json.dumps(mp, indent=2)[:3000] if mp else "no props bag")
