import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent; sys.path.insert(0,str(HERE))
import _workday_runner as R
URL="https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Group-Product-Manager--Manager-Product-Management_R165611-1"
RESUME=str(ROOT/"resume"/"Cyrus_Shekari_Resume.pdf")
with sync_playwright() as p:
    ctx=p.chromium.launch_persistent_context(user_data_dir=str(ROOT/".workday-browser-data"/"adobe"),headless=True,viewport={"width":1400,"height":900},user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",accept_downloads=True)
    pg=ctx.new_page(); pg.set_default_timeout(20000)
    pg.goto(URL,wait_until="domcontentloaded",timeout=60000); pg.wait_for_timeout(4000)
    for _ in range(6):
        if pg.locator("[data-automation-id=pageFooterNextButton]").count(): break
        for s in ["[data-automation-id=continueButton]","[data-automation-id=applyManually]","[data-automation-id=adventureButton]"]:
            if pg.locator(s).count(): pg.locator(s).first.click(force=True); pg.wait_for_timeout(3500); break
        else: pg.wait_for_timeout(1500)
    for i in range(8):
        pg.wait_for_timeout(1500); body=pg.locator("body").text_content() or ""; cur=R.current_step_name(pg,body)
        if "Application Question" in cur: break
        if "My Information" in cur: R.fill_my_information(pg,"LinkedIn")
        elif "My Experience" in cur: R.handle_experience(pg,RESUME)
        else: break
        R.click_next(pg)
    pg.wait_for_timeout(1500)
    # Dump the FULL questions form structure - all form controls in order with surrounding text
    d=pg.evaluate(r"""()=>{
      const out=[];
      // find the questionnaire container
      const fields=document.querySelectorAll('[data-automation-id=formField], [data-automation-id*=questionItem], fieldset, [role=group]');
      for(const f of fields){
        const label=(f.querySelector('label,legend')||{}).innerText||'';
        const ctrls=[];
        for(const c of f.querySelectorAll('input,select,button,textarea')){
          ctrls.push((c.tagName)+'['+(c.type||'')+']'+' aid='+(c.getAttribute('data-automation-id')||'')+' role='+(c.getAttribute('role')||'')+' haspopup='+(c.getAttribute('aria-haspopup')||'')+' name='+(c.name||'').slice(-30));
        }
        const txt=(f.innerText||'').trim().slice(0,90);
        if(/worked at adobe|capacity/i.test(txt)) out.push({MATCH:true,txt,ctrls});
      }
      // Also: find any control near 'worked at Adobe' text
      const all=[...document.querySelectorAll('*')].filter(e=>/worked at adobe in the following capacity/i.test(e.textContent||'')&&e.children.length<8);
      const near=all.slice(0,2).map(e=>({tag:e.tagName,html:e.outerHTML.slice(0,800)}));
      return {fields:out,near};
    }""")
    print(json.dumps(d,indent=1)[:4500])
    ctx.close()
