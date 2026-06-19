import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent; sys.path.insert(0,str(HERE))
import _workday_runner as R
URL="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Technical-Program-Manager--Dataset-Operations_JR2018252"
RESUME=str(ROOT/"resume"/"Cyrus_Shekari_Resume.pdf")
with sync_playwright() as p:
    ctx=p.chromium.launch_persistent_context(user_data_dir=str(ROOT/".workday-browser-data"/"nvidia"),headless=True,viewport={"width":1400,"height":900},user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",accept_downloads=True)
    pg=ctx.new_page(); pg.set_default_timeout(20000)
    pg.goto(URL,wait_until="domcontentloaded",timeout=60000); pg.wait_for_timeout(4000)
    for _ in range(6):
        if pg.locator("[data-automation-id=pageFooterNextButton]").count(): break
        for s in ["[data-automation-id=continueButton]","[data-automation-id=applyManually]","[data-automation-id=adventureButton]"]:
            if pg.locator(s).count(): pg.locator(s).first.click(force=True); pg.wait_for_timeout(3500); break
        else: pg.wait_for_timeout(1500)
    R.ensure_signed_in(pg,"nvidia",base_url=URL)
    for i in range(6):
        pg.wait_for_timeout(1500); body=pg.locator("body").text_content() or ""; cur=R.current_step_name(pg,body)
        if "My Experience" in cur: break
        if "My Information" in cur: R.fill_my_information(pg,"LinkedIn")
        else: break
        R.click_next(pg)
    R.handle_experience(pg,RESUME)
    pg.wait_for_timeout(1500)
    # dump ALL invalid/error + date fields + next button + any aria-invalid
    d=pg.evaluate(r"""()=>{
      const o={invalid:[],errors:[],dates:[],req_empty:[],next:null};
      for(const el of document.querySelectorAll('input,button,[role=spinbutton]')){
        if(el.getAttribute('aria-invalid')==='true') o.invalid.push((el.id||el.getAttribute('data-automation-id')||'?')+'='+(el.value||''));
        if(/dateSection/.test(el.id||'')) o.dates.push((el.id||'').match(/workExperience-\d+--(start|end)Date-dateSection(Month|Day|Year)/)?(el.id.split('--').slice(-2).join('--')+'='+(el.value||'')):null);
        const req=el.getAttribute('aria-required')==='true'; if(req&&el.tagName==='INPUT'&&!(el.value||'').trim()) o.req_empty.push(el.id||el.getAttribute('data-automation-id'));
      }
      o.dates=o.dates.filter(Boolean).slice(0,20);
      for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert],[data-automation-id=errorMessage]')){const t=(e.textContent||'').trim();if(t&&t.length<200)o.errors.push(t);}
      const nb=document.querySelector('[data-automation-id=pageFooterNextButton]');
      if(nb)o.next={text:nb.innerText.trim(),disabled:nb.disabled,aria:nb.getAttribute('aria-disabled')};
      return o;
    }""")
    print("BEFORE NEXT:",json.dumps(d,indent=1)[:2500])
    # click next, watch
    before=R.current_step_name(pg, pg.locator('body').text_content() or '')
    R.click_next(pg); pg.wait_for_timeout(4000)
    after=R.current_step_name(pg, pg.locator('body').text_content() or '')
    print("step before->after:",before,"->",after)
    err2=pg.evaluate("()=>{const o=[];for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert]')){const t=(e.textContent||'').trim();if(t&&t.length<200)o.push(t);}return o.slice(0,8);}")
    print("errors after next:",json.dumps(err2))
    ctx.close()
