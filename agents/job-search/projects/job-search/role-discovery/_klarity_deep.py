#!/usr/bin/env python3
"""Klarity submit DEEP — fill, verify all fields still set right before submit,
inject token, click submit, then poll DOM + network for 25s. Reports any
client-side validation error text that appears, button state, and confirmation.
"""
import os, sys, json, time, pathlib
os.environ.setdefault("JOBSEARCH_CDP", "http://127.0.0.1:19223")
from playwright.sync_api import sync_playwright

_PI = json.loads((pathlib.Path(__file__).resolve().parent.parent / "personal-info.json").read_text())

URL = "https://jobs.ashbyhq.com/klarity-ai/4843b6cd-405e-412f-8261-d1a2d6acd850/application"
CDP = os.environ["JOBSEARCH_CDP"]
PROJ = pathlib.Path(__file__).resolve().parent.parent
RESUME = str(PROJ / "applications/submitted/klarity-4843b6cd-405e-412f-8261-d1a2d6acd850/Cyrus_Shekari_Resume_ashby-klarity-ai_4843b6cd_v2.pdf")
SF_UUID="b4ff3fea-a627-4945-b958-9df48cbc63fd"; SPON_UUID="5658b589-ea7a-4582-b9c7-92a4c5809fbd"
TEXT_FIELDS={"_systemfield_name": _PI["identity"]["first_name"] + " " + _PI["identity"]["last_name"], "_systemfield_email": _PI["contact"]["email"], "988ea71d-2e8f-424b-a2d5-b21752d94c8a": _PI["contact"].get("linkedin", "https://linkedin.com/in/cyshekari")}
RADIO_TARGETS=[(SPON_UUID,"I am a US Citizen / Green Card Holder"),(SF_UUID,"I am open to relocating to San Francisco")]
SITEKEY="6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y"

def commit_radio(page,uuid,target):
    rid=page.evaluate(r"""(a)=>{const c=document.querySelector(`[data-field-path="${a.uuid}"]`);if(!c)return null;const t=a.target.trim().toLowerCase();const L=[...c.querySelectorAll('label')].filter(l=>(l.getAttribute('for')||'').includes('labeled-radio'));let m=L.find(l=>(l.innerText||'').trim().toLowerCase()===t)||L.find(l=>(l.innerText||'').trim().toLowerCase().includes(t));return m?m.getAttribute('for'):null;}""",{"uuid":uuid,"target":target})
    if not rid: return False
    try: page.click(f'input[id="{rid}"]',force=True,timeout=8000); return True
    except Exception:
        try: page.click(f'label[for="{rid}"]',force=True,timeout=8000); return True
        except Exception: return False

def fill_text(page,fid,val):
    try:
        loc=page.locator(f'[data-field-path="{fid}"] input, [data-field-path="{fid}"] textarea, input[id="{fid}"]').first
        loc.click(timeout=3000); loc.fill(""); loc.type(val,delay=20); return True
    except Exception: return False

def verify_all(page):
    out={}
    for uuid,_ in RADIO_TARGETS:
        st=page.evaluate(r"""(uuid)=>{const c=document.querySelector(`[data-field-path="${uuid}"]`);if(!c)return null;const radios=[...c.querySelectorAll('input[type=radio]')];const probe=radios[0]||c;const fk=Object.keys(probe).find(k=>k.startsWith('__reactFiber$'));let value=null,saved=null;if(fk){let f=probe[fk],d=0;while(f&&d<30){const mp=f.memoizedProps;if(mp){if('value'in mp&&'fieldEntryId'in mp&&value===null)value=mp.value;if('savedValue'in mp&&saved===null)saved=mp.savedValue;}f=f.return;d++;}}return{value,saved,checkedIdx:radios.findIndex(r=>r.checked)};}""",uuid)
        out[uuid[:12]]=st
    return out

def main():
    pw=sync_playwright().start()
    browser=pw.chromium.connect_over_cdp(CDP)
    ctx=browser.contexts[0] if browser.contexts else browser.new_context()
    page=ctx.new_page()
    ops=[]
    page.on('response', lambda r: ops.append((r.url.split('op=')[-1][:36] if 'op=' in r.url else '?', r.status, (r.text() if 'graphql' in r.url.lower() and r.request.method=='POST' else ''))) if ('graphql' in r.url.lower() and r.request.method=='POST') else None)
    print("[deep] nav", flush=True)
    page.goto(URL,wait_until='domcontentloaded',timeout=60000)
    for _ in range(40):
        if page.query_selector('[data-field-path]'): break
        time.sleep(0.5)
    time.sleep(2)
    for fid,val in TEXT_FIELDS.items(): fill_text(page,fid,val)
    try:
        fi=page.locator('#_systemfield_resume')
        if fi.count()==0: fi=page.locator('input[type=file]')
        fi.first.set_input_files(RESUME,timeout=15000); time.sleep(3)
        print("[deep] resume up", flush=True)
    except Exception as e: print(f"[deep] up fail {e}", flush=True)
    for uuid,t in RADIO_TARGETS: commit_radio(page,uuid,t)
    time.sleep(1)

    print("[deep] field state BEFORE token:", json.dumps(verify_all(page), default=str), flush=True)

    # token
    tok=page.evaluate("""([sk])=>new Promise(res=>{try{window.grecaptcha.ready(()=>{window.grecaptcha.execute(sk,{action:'submit'}).then(t=>res(t||null)).catch(()=>res(null));});setTimeout(()=>res(null),12000);}catch(e){res(null);}})""",[SITEKEY])
    inj=page.evaluate("""(t)=>{const s=new Set();document.querySelectorAll('textarea[id^=g-recaptcha-response],textarea[name^=g-recaptcha-response]').forEach(e=>{if(e.id)s.add(e.id);});if(!s.size)s.add('g-recaptcha-response-100000');let n=0;for(const id of s){let el=document.getElementById(id);if(!el){el=document.createElement('textarea');el.id=id;el.name=id;el.style.display='none';document.body.appendChild(el);}el.value=t;n++;}return [...s];}""",tok) if tok else []
    print(f"[deep] token len={len(tok) if tok else 0} injected_slots={inj}", flush=True)
    print("[deep] field state AFTER token:", json.dumps(verify_all(page), default=str), flush=True)

    # locate submit button and inspect its react props / onclick
    bprops=page.evaluate(r"""()=>{
      const btns=[...document.querySelectorAll('button')];
      const b=btns.find(x=>/submit application/i.test(x.innerText||''));
      if(!b) return {found:false};
      const fk=Object.keys(b).find(k=>k.startsWith('__reactProps$'));
      const props=fk?b[fk]:{};
      return {found:true, disabled:b.disabled, type:b.type, text:b.innerText, propKeys:Object.keys(props), hasOnClick:typeof props.onClick==='function', formAction:b.getAttribute('form')};
    }""")
    print(f"[deep] submit button props: {json.dumps(bprops)}", flush=True)

    if '--submit' in sys.argv:
        # click via real Playwright trusted gesture
        try:
            b=page.locator('button:has-text("Submit Application")').first
            b.scroll_into_view_if_needed(timeout=2000)
            b.click(timeout=8000)
            print("[deep] submit clicked (playwright)", flush=True)
        except Exception as e:
            print(f"[deep] click fail {e}", flush=True)
        # poll for 25s
        for s in range(13):
            time.sleep(2)
            dom=page.evaluate(r"""()=>{
              const body=document.body.innerText||'';
              return {
                submitted: /application submitted|thank you for applying|we.ve received your application|successfully submitted/i.test(body),
                errs: [...document.querySelectorAll('[class*="error"],[class*="Error"],[role=alert]')].map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,6),
                url: location.href,
                btnText: (()=>{const b=[...document.querySelectorAll('button')].find(x=>/submit/i.test(x.innerText||''));return b?(b.innerText||'').trim()+(b.disabled?' [disabled]':''):null;})()
              };
            }""")
            submit_ops=[o for o in ops if 'Submit' in o[0]]
            print(f"[deep] t={s*2+2}s submitted={dom['submitted']} url={dom['url'][-40:]} btn={dom['btnText']!r} errs={dom['errs']} submit_ops={len(submit_ops)}", flush=True)
            if dom['submitted'] or submit_ops:
                break
        # final op dump
        print("\n[deep] GRAPHQL OPS:", flush=True)
        success=False
        for op,status,body in ops:
            tag=''
            if 'Submit' in op: tag='<<SUBMIT'
            if body and 'FormSubmitSuccess' in body: tag+=' SUCCESS'; success=True
            if body and ('"errorMessages":["' in body or '"formErrors":["' in body): tag+=' HAS-ERR'
            print(f"   {op} {status} {tag}", flush=True)
        for op,status,body in ops:
            if 'Submit' in op and body:
                print(f"\n[deep] SUBMIT BODY:\n{body[:1800]}", flush=True)
        print(f"\n[deep] RESULT SUCCESS={success}", flush=True)
        print(f"RESULT_{'SUCCESS' if success else 'FAIL'}", flush=True)
    page.close()

if __name__=='__main__': main()
