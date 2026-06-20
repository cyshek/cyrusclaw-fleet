import sys, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(HERE))
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
            if pg.locator(s).count():
                pg.locator(s).first.click(force=True); pg.wait_for_timeout(3500); break
        else: pg.wait_for_timeout(1500)
    for i in range(8):
        pg.wait_for_timeout(1500); body=pg.locator("body").text_content() or ""; cur=R.current_step_name(pg,body)
        print(f"--- step {i}: {cur} ---",flush=True)
        if "Application Question" in cur: break
        if "My Information" in cur: R.fill_my_information(pg,"LinkedIn")
        elif "My Experience" in cur: R.handle_experience(pg,RESUME)
        else: print("unexpected"); break
        R.click_next(pg)
    # answer questions
    R.handle_questions(pg)
    pg.wait_for_timeout(1500)
    vals=pg.evaluate(r"""()=>Array.from(document.querySelectorAll('button[aria-haspopup=listbox]')).map(b=>(b.id||'').slice(-12)+'='+((b.getAttribute('aria-label')||b.innerText||'').trim()))""")
    print("AFTER ANSWER:",json.dumps(vals))
    # click next, see what happens
    ok=R.click_next(pg); pg.wait_for_timeout(3000)
    body2=pg.locator("body").text_content() or ""; cur2=R.current_step_name(pg,body2)
    print("click_next returned",ok,"-> now step:",cur2)
    errs=pg.evaluate(r"""()=>{const o=[];for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert],[data-automation-id=errorMessage]')){const t=(e.textContent||'').trim();if(t&&t.length<200)o.push(t);}return o;}""")
    print("ERRORS:",json.dumps(errs))
    vals2=pg.evaluate(r"""()=>Array.from(document.querySelectorAll('button[aria-haspopup=listbox]')).map(b=>(b.id||'').slice(-12)+'='+((b.getAttribute('aria-label')||b.innerText||'').trim()))""")
    print("AFTER NEXT vals:",json.dumps(vals2))
    pg.screenshot(path=str(HERE/".probe-adobe-q3.png"),full_page=True)
    ctx.close()
