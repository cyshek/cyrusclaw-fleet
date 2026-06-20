import os, json
from playwright.sync_api import sync_playwright

CDP = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:19223')
URL = 'https://jobs.ashbyhq.com/benchling/61b20c5a-5c3d-4388-a19d-13a89886e73f/application'

JS = r"""()=>{
  function bySub(sub){
    const els=[...document.querySelectorAll('input')].filter(e=>(e.id||'').includes(sub));
    return els.map(e=>{
      const lab=document.querySelector('label[for="'+(e.id||'').replace(/"/g,'')+'"]');
      return {id:e.id, type:e.type, checked:e.checked, name:e.name, text:(lab?lab.innerText:'').slice(0,45).replace(/\s+/g,' ')};
    });
  }
  return {
    workauth: bySub('question_38004773'),
    hybrid: bySub('question_58774653')
  };
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(4500)
    print(json.dumps(pg.evaluate(JS), indent=1))
    pg.close()
