import os, glob
from playwright.sync_api import sync_playwright

CDP = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:19223')
URL = 'https://jobs.ashbyhq.com/benchling/61b20c5a-5c3d-4388-a19d-13a89886e73f/application'
cands = glob.glob('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/benchling-*/Cyrus_Shekari_Resume_ashby-benchling_*.pdf')
RESUME = cands[0] if cands else None
print('resume:', RESUME)

JS = r"""()=>{
  const out=[];
  const fes=[...document.querySelectorAll('div[class*=_fieldEntry_], fieldset')];
  for(const fe of fes){
    const lab=((fe.querySelector('label,legend')||{}).innerText||'').slice(0,80).replace(/\s+/g,' ');
    if(!lab) continue;
    const radios=fe.querySelectorAll('input[type=radio]').length;
    const yesno=!!fe.querySelector('div[class*=_yesno_]');
    const sel=fe.querySelectorAll('select').length;
    const combo=!!fe.querySelector('[role=combobox], input[role=combobox], [class*=_select_], [class*=Select]');
    const inp=[...fe.querySelectorAll('input')].map(i=>i.id||i.name).filter(Boolean).slice(0,3);
    out.push({lab, radios, yesno, sel, combo, inp});
  }
  return out;
}"""

def dump(pg, tag):
    print('=== ' + tag + ' ===')
    for r in pg.evaluate(JS):
        print(' ', r)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(4000)
    dump(pg, 'BEFORE upload')
    if RESUME:
        inp = pg.query_selector('#_systemfield_resume') or pg.query_selector('input[type=file]')
        if inp:
            inp.set_input_files(RESUME)
            print('uploaded; parsing...')
            pg.wait_for_timeout(10000)
    dump(pg, 'AFTER upload')
    pg.close()
