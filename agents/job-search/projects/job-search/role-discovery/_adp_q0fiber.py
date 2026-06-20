import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])
info=page.evaluate(r"""
() => {
  const el=document.getElementById('question_0');
  if(!el) return {found:false};
  // find react fiber key
  const fk=Object.keys(el).find(k=>k.startsWith('__reactFiber')||k.startsWith('__reactInternalInstance'));
  const pk=Object.keys(el).find(k=>k.startsWith('__reactProps'));
  let props=null, fiberProps=null;
  if(pk){ try{ const p=el[pk]; props=Object.keys(p); }catch(e){} }
  // walk fiber up to find memoizedProps with validation/question metadata
  let metas=[];
  if(fk){
    let f=el[fk];
    for(let i=0;i<12 && f;i++){
      const mp=f.memoizedProps;
      if(mp){
        const keys=Object.keys(mp).filter(k=>/valid|question|type|required|regex|pattern|format|min|max|length|answer|dataType/i.test(k));
        if(keys.length){ const o={}; keys.forEach(k=>{try{o[k]=JSON.stringify(mp[k])?.slice(0,80);}catch(e){o[k]='?';}}); metas.push({depth:i, keys:o}); }
      }
      f=f.return;
    }
  }
  return {found:true, propKeys:props, fiberMetas:metas.slice(0,8)};
}
""")
print(json.dumps(info, indent=2)[:2500])
