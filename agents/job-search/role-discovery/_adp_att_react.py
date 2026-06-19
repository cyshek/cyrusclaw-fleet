import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[-40:])

d=page.evaluate(r"""
()=>{
  const out={};
  const c=document.querySelector('input[name="self_att_agree_chk"]');
  // input react props
  if(c){const pk=Object.keys(c).find(k=>k.startsWith('__reactProps')); if(pk){const p=c[pk]; out.inputOnChange=p.onChange?p.onChange.toString().slice(0,200):null; out.inputChecked=p.checked;}}
  // walk up to find submit-guard state (selfAttest agree flag)
  if(c){const fk=Object.keys(c).find(k=>k.startsWith('__reactFiber')); let f=c[fk];
    for(let i=0;i<16&&f;i++){const m=f.memoizedProps;
      if(m){const keys=Object.keys(m).filter(k=>/attest|agree|sign|checked|valid/i.test(k)); if(keys.length){out.guardLevel=i; out.guardProps={}; keys.forEach(k=>{try{out.guardProps[k]=(typeof m[k]==='function')?'<fn:'+m[k].toString().slice(0,90)+'>':JSON.stringify(m[k]);}catch(e){}}); break;}}
      f=f.return;}}
  // submit button onClick
  const b=[...document.querySelectorAll('button')].find(x=>/^Submit$/i.test(x.innerText.trim())&&x.offsetWidth>0);
  if(b){const pk=Object.keys(b).find(k=>k.startsWith('__reactProps')); if(pk){const p=b[pk]; out.submitOnClick=p.onClick?p.onClick.toString().slice(0,260):null;}}
  return out;
}
""")
print(json.dumps(d, indent=1)[:2200])
