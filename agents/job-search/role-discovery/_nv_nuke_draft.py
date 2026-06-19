import sys, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent; sys.path.insert(0,str(HERE))
import _workday_runner as R
URL="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Technical-Program-Manager---VLSI_JR2015102"
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
    # advance to My Experience
    for i in range(6):
        pg.wait_for_timeout(1500); body=pg.locator("body").text_content() or ""; cur=R.current_step_name(pg,body)
        print("step",i,cur,flush=True)
        if "My Experience" in cur: break
        if "My Information" in cur: R.fill_my_information(pg,"LinkedIn")
        else: break
        R.click_next(pg)
    pg.wait_for_timeout(2000)
    n0=pg.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')).length")
    print("empty/total work-exp blocks before nuke:",n0,flush=True)
    # NUKE: delete EVERY work-exp block (empty AND filled) repeatedly until none remain.
    deleted=0
    for _ in range(2000):
        r=pg.evaluate("""()=>{const inp=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')); if(!inp)return 0; let sec=inp; for(let i=0;i<14&&sec;i++){sec=sec.parentElement; if(sec){const del=sec.querySelector('[data-automation-id=panel-set-delete-button],[data-automation-id*=delete-button],button[aria-label^=Delete],button[title^=Delete]'); if(del){del.click();return 1;}}} return -1;}""")
        if r==0: break
        if r==-1:
            print("no delete button found; remaining present"); break
        deleted+=1
        pg.wait_for_timeout(350)
        if deleted%20==0:
            rem=pg.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')).length")
            print(f"  deleted={deleted} remaining={rem}",flush=True)
    rem=pg.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')).length")
    print("DELETED total:",deleted,"remaining work-exp blocks:",rem)
    # Save the draft by clicking Save & Continue OR Save for Later if present, else just Next stays.
    # Click 'Save and Continue'/Next to persist the cleaned state.
    R.click_next(pg); pg.wait_for_timeout(3000)
    body=pg.locator('body').text_content() or ''
    print("after save step:", R.current_step_name(pg,body))
    errs=pg.evaluate("()=>{const o=[];for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert]')){const t=(e.textContent||'').trim();if(t&&t.length<160)o.push(t);}return o.slice(0,5);}")
    print("errors:",json.dumps(errs))
    ctx.close()
