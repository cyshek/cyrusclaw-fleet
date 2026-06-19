import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])
src=page.evaluate(r"""
()=>{
  const el=document.getElementById('question_0')||document.body;
  const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
  for(let i=0;i<16&&f;i++){const m=f.memoizedProps;
    if(m&&('onDesiredSalaryType'in m)){
      const out={};
      ['onDesiredSalaryType','onDesiredSalaryValue','onCurrencyValueChange','onCurrencyChange','setRefferalIndicatorValue','onRefferedEmplChange'].forEach(fn=>{
        try{ out[fn]= m[fn] ? m[fn].toString().slice(0,260) : null; }catch(e){ out[fn]='err'; }
      });
      return out;
    }
    f=f.return;
  }
  return null;
}
""")
print(json.dumps(src, indent=2)[:2600] if src else "none")
