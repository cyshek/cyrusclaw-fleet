import os, json
from playwright.sync_api import sync_playwright

CDP = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:19223')
URL = 'https://jobs.ashbyhq.com/starbridge/3b0bd418-6de0-4cc1-a8fe-7a409238532c/application'

JS = r"""()=>{
  const out=[];
  const fes=[...document.querySelectorAll('div[class*=_fieldEntry_], fieldset')];
  for(const fe of fes){
    const lab=((fe.querySelector('label,legend')||{}).innerText||'').slice(0,120).replace(/\s+/g,' ');
    const ta=fe.querySelector('textarea');
    const ti=fe.querySelector('input[type=text]');
    if(ta||(ti && lab && /acv|portfolio|average|account/i.test(lab))){
      const el=ta||ti;
      out.push({lab, tag:el.tagName, id:el.id, name:el.name, val:(el.value||'').slice(0,30)});
    }
  }
  return out;
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(4000)
    print(json.dumps(pg.evaluate(JS), indent=1))
    pg.close()
