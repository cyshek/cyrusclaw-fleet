import os, glob
from playwright.sync_api import sync_playwright

CDP = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:19223')
URL = 'https://jobs.ashbyhq.com/benchling/61b20c5a-5c3d-4388-a19d-13a89886e73f/application'

cands = glob.glob('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/benchling-*/Cyrus_Shekari_Resume_ashby-benchling_*.pdf')
RESUME = cands[0] if cands else None
print('resume:', RESUME)

JS = """()=>{
  const out=[];
  const fes=[...document.querySelectorAll('fieldset, div[class*=_fieldEntry_], div[class*=_field_]')];
  for(const fe of fes){
    const lab=((fe.querySelector('label,legend')||{}).innerText||'');
    const radios=[...fe.querySelectorAll('input[type=radio]')];
    const yesno=fe.querySelector('div[class*=_yesno_]');
    if((radios.length||yesno)&&lab){
      out.push({label:lab.slice(0,90).replace(/\\s+/g,' '), radios:radios.length, yesno:!!yesno});
    }
  }
  return out;
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(3500)
    print('=== BEFORE upload ===')
    for r in pg.evaluate(JS):
        print(' ', r)
    if RESUME:
        inp = pg.query_selector('#_systemfield_resume') or pg.query_selector('input[type=file]')
        if inp:
            inp.set_input_files(RESUME)
            print('uploaded; parsing...')
            pg.wait_for_timeout(9000)
    print('=== AFTER upload ===')
    for r in pg.evaluate(JS):
        print(' ', r)
    pg.close()
