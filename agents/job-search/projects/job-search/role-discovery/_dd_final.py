from playwright.sync_api import sync_playwright
import time, json
import gmail_imap as g
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp('http://127.0.0.1:18800')
page=None
for ctx in br.contexts:
  for p in ctx.pages:
    if 'datadog' in p.url and 'recaptcha' not in p.url: page=p

def pick(label):
    jo=r"""()=>{const inp=document.getElementById('question_64361675[]');const ctrl=inp.closest('.select__control');const r=ctrl.getBoundingClientRect();['mousedown','mouseup','click'].forEach(t=>ctrl.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,clientX:r.left+5,clientY:r.top+5})));return 'o';}"""
    page.evaluate(jo); time.sleep(0.5)
    jp=r"""(lbl)=>{const m=document.querySelector('.select__menu');if(!m)return 'nomenu';const o=[...m.querySelectorAll('.select__option,[role=option]')].find(x=>x.textContent.trim()===lbl);if(!o)return 'noopt';const r=o.getBoundingClientRect();['mousedown','mouseup','click'].forEach(t=>o.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,clientX:r.left+5,clientY:r.top+5})));return 'picked';}"""
    return page.evaluate(jp, label)

print("NYC:", pick("New York City"))
time.sleep(0.4)
print("Remote:", pick("Remote"))
time.sleep(0.4)
# verify value set
val=page.evaluate(r"""()=>{const inp=document.getElementById('question_64361675[]');const ctrl=inp.closest('.select__control');return [...ctrl.querySelectorAll('.select__multi-value__label')].map(x=>x.textContent.trim());}""")
print("values:", val)

# submit
since=time.time()-3
c=page.evaluate(r"""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));if(s){s.scrollIntoView({block:'center'});s.click();return true;}return false;}""")
print("submit:",c)
time.sleep(5)
has=page.evaluate(r"""()=>!!document.getElementById('security-input-0')""")
print("otp:",has)
if has:
    try: code=g.wait_for_verification_code(timeout_seconds=120,poll_seconds=5,since_epoch=since)
    except Exception as e: print("fetchfail",e); code=None
    print("code:",code)
    if code and len(code)>=8:
        fb=page.query_selector('#security-input-0'); fb.click(); time.sleep(.2)
        for ch in code[:8]: page.keyboard.press(ch); time.sleep(.18)
        time.sleep(1)
        for _ in range(6):
            cc=page.evaluate(r"""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit|verify|confirm/i.test(b.textContent.trim())&&!b.disabled&&b.getAttribute('aria-disabled')!=='true');if(s){s.click();return s.textContent.trim();}return null;}""")
            if cc: print("verify:",cc); break
            time.sleep(1.5)
final=None
for _ in range(14):
    time.sleep(2)
    final=json.loads(page.evaluate(r"""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|application has been|received your application|appreciate your interest|we will be|submitted/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');const errs=[...document.querySelectorAll('.error,[aria-invalid=true]')].map(e=>e.textContent.trim()).filter(Boolean).slice(0,3);return JSON.stringify({url,confirmed:conf,otpStill,errs,head:body.slice(0,140)});}"""))
    if final['confirmed']: break
    if not final['otpStill'] and not has and 'confirmation' in final['url']: break
print("FINAL:",json.dumps(final))
