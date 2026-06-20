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
    # walk steps using runner helpers until we hit Application Questions
    for i in range(8):
        pg.wait_for_timeout(1500)
        body=pg.locator("body").text_content() or ""
        cur=R.current_step_name(pg,body)
        print(f"--- step {i}: {cur} ---", flush=True)
        if "Application Question" in cur:
            print("AT QUESTIONS"); break
        if "My Information" in cur:
            R.fill_my_information(pg, "LinkedIn")
        elif "My Experience" in cur:
            R.handle_experience(pg, RESUME)
        else:
            print("unexpected:", body[:150]); break
        R.click_next(pg)
    # Now dump the questions step in detail
    pg.wait_for_timeout(2000)
    dump=pg.evaluate(r"""()=>{
      const o={listboxes:[],errors:[],requiredEmpty:[],radios:[],invalid:[],qtexts:[]};
      for(const b of document.querySelectorAll('button[aria-haspopup=listbox]')){
        const v=(b.getAttribute('aria-label')||b.innerText||'').trim();
        // walk up for question text
        let n=b,qt='';for(let i=0;i<7&&n;i++){n=n.parentElement;if(n){const t=(n.innerText||'').trim();if(t.includes('?')){qt=t.split('\n')[0];break;}}}
        o.listboxes.push({id:(b.id||'').slice(-24),val:v.slice(-40),q:qt.slice(0,80)});
      }
      for(const el of document.querySelectorAll('input,textarea')){const req=el.getAttribute('aria-required')==='true'||el.required; if(req&&!(el.value||'').trim())o.requiredEmpty.push((el.id||el.getAttribute('data-automation-id')||'?')); if(el.getAttribute('aria-invalid')==='true')o.invalid.push(el.id||el.getAttribute('data-automation-id'));}
      const rseen={};for(const r of document.querySelectorAll('input[type=radio]')){const n=r.name||'';if(!rseen[n]){rseen[n]={opts:[],checked:null};}const l=document.querySelector('label[for=\''+r.id+'\']');rseen[n].opts.push((l?l.textContent.trim():r.value)+(r.checked?'[X]':''));if(r.checked)rseen[n].checked=true;}
      o.radios=Object.entries(rseen).map(([k,v])=>k.slice(-20)+' checked='+v.checked+' '+v.opts.join('|'));
      for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert]')){const t=(e.textContent||'').trim();if(t&&t.length<200)o.errors.push(t);}
      return o;
    }""")
    print(json.dumps(dump,indent=1)[:4000])
    pg.screenshot(path=str(HERE/".probe-adobe-q2.png"),full_page=True)
    ctx.close()
