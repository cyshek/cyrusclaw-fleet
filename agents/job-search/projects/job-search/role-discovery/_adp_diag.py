import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:100])
d=page.evaluate(r"""
() => {
  const inv=[...document.querySelectorAll('[aria-invalid=true]')].filter(e=>e.offsetWidth>0).map(e=>({id:e.id||e.name,tag:e.tagName,val:(e.value||'').slice(0,18)}));
  const reqsdf=[...document.querySelectorAll('sdf-select-simple[required],sdf-select-simple[required-state=required]')].filter(e=>e.offsetWidth>0).map(e=>{
    let sel=''; if(e.shadowRoot){const s=e.shadowRoot.querySelector('#selected-label,.selected-label,[part=selected-value]');sel=s?s.innerText.trim():'';}
    return {id:e.id,sel,val:e.getAttribute('value')};
  });
  const ds=document.getElementById('desiredSalaryId');
  const errBlocks=[...document.querySelectorAll('.vdl-validation-error,[role=alert]')].filter(e=>e.offsetWidth>0&&e.innerText.trim().length>2&&!/Afghan/i.test(e.innerText)).map(e=>({txt:e.innerText.trim().slice(0,55), near:(e.closest('.qMainDiv,.additional-question,div')||{}).id||''}));
  return {invalidInputs:inv, requiredSdf:reqsdf, desiredSalary:ds?ds.value:null, errBlocks};
}
""")
print(json.dumps(d, indent=2)[:1800])
