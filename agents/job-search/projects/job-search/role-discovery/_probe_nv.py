import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent; sys.path.insert(0,str(HERE))
import _workday_runner as R
URL="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Technical-Program-Manager---VLSI_JR2015102"
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
    # advance to My Experience
    for i in range(6):
        pg.wait_for_timeout(1500); body=pg.locator("body").text_content() or ""; cur=R.current_step_name(pg,body)
        print("step",i,cur,flush=True)
        if "My Experience" in cur: break
        if "My Information" in cur: R.fill_my_information(pg,"LinkedIn")
        else: break
        R.click_next(pg)
    pg.wait_for_timeout(2000)
    # dump work-exp field ids + jobTitle test
    info=pg.evaluate(r"""()=>{
      const we=[...document.querySelectorAll('input')].filter(x=>/workExperience-\d+--jobTitle/.test(x.id||'')).map(x=>x.id);
      const ed=[...document.querySelectorAll('input')].filter(x=>/education-\d+--schoolName/.test(x.id||'')).map(x=>x.id);
      // full id of first jobTitle, and what getElementById returns
      const first=we[0]||null;
      let gbid = first? !!document.getElementById(first):null;
      // any 'Add' button labels
      const adds=[...document.querySelectorAll('button,[role=button],[data-automation-id=Add]')].map(b=>((b.getAttribute('data-automation-id')||'')+'/'+(b.textContent||'').trim().slice(0,20))).filter(s=>/add/i.test(s));
      return {weCount:we.length,we_ids:we.slice(0,3),ed_ids:ed.slice(0,2),first_jobTitle_id:first,getElementById_ok:gbid,adds:[...new Set(adds)].slice(0,8)};
    }""")
    print(json.dumps(info,indent=1))
    # try _set_native on first jobTitle
    fid=info.get("first_jobTitle_id")
    if fid:
        ok=R._set_native(pg,fid,"Technical Program Manager")
        pg.wait_for_timeout(800)
        val=pg.evaluate("(id)=>{const e=document.getElementById(id);return e?e.value:'(null)';}",fid)
        print("SET_NATIVE returned",ok,"-> value now:",repr(val))
    ctx.close()
