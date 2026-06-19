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
        print("step",i,cur,flush=True)
        if "My Experience" in cur: break
        if "My Information" in cur: R.fill_my_information(pg,"LinkedIn")
        else: break
        R.click_next(pg)
    pg.wait_for_timeout(2000)
    # BEFORE touching anything, dump every work-exp block's jobTitle/companyName values + delete-button presence + required state
    d=pg.evaluate(r"""()=>{
      const out=[];
      for(const inp of [...document.querySelectorAll('input')].filter(x=>/workExperience-\d+--jobTitle/.test(x.id||''))){
        const m=inp.id.match(/workExperience-(\d+)--/); const ix=m?m[1]:'?';
        const cn=document.getElementById(inp.id.replace('jobTitle','companyName'));
        let sec=inp,hasDel=false;for(let i=0;i<14&&sec;i++){sec=sec.parentElement;if(sec&&sec.querySelector('[data-automation-id=panel-set-delete-button],[data-automation-id*=delete-button],button[aria-label^=Delete]')){hasDel=true;break;}}
        out.push({ix,jt:(inp.value||'').slice(0,30),cn:cn?(cn.value||'').slice(0,30):'?',req:inp.getAttribute('aria-required'),hasDel});
      }
      // resume rows
      const resume=/successfully uploaded/i.test(document.body.innerText);
      return {blocks:out,resumeUploaded:resume};
    }""")
    print("FRESH My Experience state:",json.dumps(d,indent=1)[:1500])
    # upload resume then re-check + try Next ONCE
    R.handle_experience.__wrapped__ if hasattr(R.handle_experience,'__wrapped__') else None
    # just upload
    inp=pg.locator("[data-automation-id=file-upload-input-ref]").first
    if not inp.count(): inp=pg.locator("input[type=file]").first
    if inp.count() and not d["resumeUploaded"]:
        inp.set_input_files(RESUME); pg.wait_for_timeout(6000); print("uploaded resume")
    nb=pg.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')).length")
    print("blocks after upload:",nb)
    R.click_next(pg); pg.wait_for_timeout(3500)
    body=pg.locator('body').text_content() or ''
    print("after ONE next:",R.current_step_name(pg,body))
    nb2=pg.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')).length")
    errs=pg.evaluate("()=>{const o=[];for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert]')){const t=(e.textContent||'').trim();if(t&&t.length<160)o.push(t);}return o.slice(0,6);}")
    print("blocks after next:",nb2,"errors:",json.dumps(errs))
    ctx.close()
