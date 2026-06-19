import sys, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
URL="https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Group-Product-Manager--Manager-Product-Management_R165611-1"
with sync_playwright() as p:
    ctx=p.chromium.launch_persistent_context(user_data_dir=str(ROOT/".workday-browser-data"/"adobe"),headless=True,viewport={"width":1400,"height":900},user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36")
    pg=ctx.new_page(); pg.set_default_timeout(20000)
    pg.goto(URL,wait_until="domcontentloaded",timeout=60000); pg.wait_for_timeout(4000)
    # resume in-progress
    for _ in range(6):
        if pg.locator("[data-automation-id=pageFooterNextButton]").count(): break
        for s in ["[data-automation-id=continueButton]","[data-automation-id=applyManually]","[data-automation-id=adventureButton]"]:
            if pg.locator(s).count():
                pg.locator(s).first.click(force=True); pg.wait_for_timeout(3500); break
        else: pg.wait_for_timeout(1500)
    # try to advance to questions step: click next a couple times if on info/experience
    pg.wait_for_timeout(2000)
    heads=[ (h.text_content() or '').strip() for h in pg.locator('h1,h2,h3').all() ]
    print("HEADS:", json.dumps(heads[:12]))
    # dump ALL required/invalid widgets + buttons + errors
    dump = pg.evaluate(r"""()=>{
      const o={requiredEmpty:[],invalid:[],errors:[],listboxes:[],radios:[],checkboxes:[],nextBtn:null};
      for(const el of document.querySelectorAll('input,select,textarea,button')){
        const aid=el.getAttribute('data-automation-id')||'';
        const id=el.id||'';
        const req=el.getAttribute('aria-required')==='true'||el.required;
        const inv=el.getAttribute('aria-invalid')==='true';
        const val=(el.value||el.getAttribute('aria-label')||el.innerText||'').trim().slice(0,40);
        if(inv) o.invalid.push((id||aid)+' :: '+val);
        if(req && el.tagName==='INPUT' && !(el.value||'').trim()) o.requiredEmpty.push((id||aid));
        if(el.getAttribute('aria-haspopup')==='listbox') o.listboxes.push((id||aid).slice(-30)+' = '+val);
      }
      for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert],[data-automation-id=errorMessage]')){const t=(e.textContent||'').trim(); if(t&&t.length<200)o.errors.push(t);}
      // radios
      const rseen={};
      for(const r of document.querySelectorAll('input[type=radio]')){const n=r.name||''; if(!rseen[n]){rseen[n]={name:n,checked:null,opts:[]};} const l=document.querySelector('label[for=\''+r.id+'\']'); rseen[n].opts.push((l?l.textContent.trim():r.value)+(r.checked?'[X]':'')); if(r.checked)rseen[n].checked=(l?l.textContent.trim():r.value);}
      o.radios=Object.values(rseen).map(x=>x.name.slice(-20)+': checked='+x.checked+' opts='+x.opts.join('|'));
      for(const c of document.querySelectorAll('input[type=checkbox]')){const l=document.querySelector('label[for=\''+c.id+'\']'); o.checkboxes.push((l?l.textContent.trim().slice(0,30):c.id)+'='+c.checked);}
      const nb=document.querySelector('[data-automation-id=pageFooterNextButton]');
      if(nb) o.nextBtn={text:nb.innerText.trim(),disabled:nb.disabled,aria:nb.getAttribute('aria-disabled')};
      return o;
    }""")
    print(json.dumps(dump,indent=1)[:3500])
    pg.screenshot(path=str(HERE/".probe-adobe-q.png"),full_page=True)
    ctx.close()
