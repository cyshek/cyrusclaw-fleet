import os, glob, json
from playwright.sync_api import sync_playwright

CDP = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:19223')
URL = 'https://jobs.ashbyhq.com/benchling/61b20c5a-5c3d-4388-a19d-13a89886e73f/application'
cands = glob.glob('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/benchling-*/Cyrus_Shekari_Resume_ashby-benchling_*.pdf')
RESUME = cands[0] if cands else None

CHECK_STATE = r"""()=>{
  const boxes=[...document.querySelectorAll('input[type=checkbox]')].filter(e=>(e.id||'').includes('question_58774653'));
  return boxes.map(b=>{const l=document.querySelector('label[for="'+(b.id||'').replace(/"/g,'')+'"]'); return {id:b.id, checked:b.checked, name:b.name, val:b.value, text:(l?l.innerText:'').trim()};});
}"""

def show(pg, tag):
    print(tag, json.dumps(pg.evaluate(CHECK_STATE)))

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=45000)
    pg.wait_for_timeout(4000)
    if RESUME:
        inp = pg.query_selector('#_systemfield_resume') or pg.query_selector('input[type=file]')
        if inp:
            inp.set_input_files(RESUME)
            pg.wait_for_timeout(9000)
    show(pg, 'after-upload:')
    # method 1: Playwright trusted click on the YES label
    yes = pg.query_selector("label:has-text('Yes')")
    # narrow: find the label whose 'for' targets question_58774653[]-labeled-checkbox-0
    target = pg.query_selector("label[for*='question_58774653'][for$='checkbox-0']")
    print('target label found:', bool(target), 'text=', (target.inner_text() if target else None))
    if target:
        target.scroll_into_view_if_needed()
        target.click()
        pg.wait_for_timeout(800)
    show(pg, 'after-label-click:')
    # force a re-render by focusing/blurring another field, then re-check state
    pg.wait_for_timeout(2500)
    show(pg, 'after-2.5s-settle:')
    pg.close()
