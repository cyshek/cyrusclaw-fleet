import sys,time,json
from playwright.sync_api import sync_playwright
import gmail_imap as g
CDP="http://127.0.0.1:18800"
jid="7673317"
pw=sync_playwright().start();br=pw.chromium.connect_over_cdp(CDP);ctx=br.contexts[0]
pg=[p for p in ctx.pages if jid in p.url][0]
# commit Yes to question_64733992 (US onsite Jersey City)
res=pg.evaluate("""async ({id,label})=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const inp=document.getElementById(id);if(!inp)return'noinput';const ctrl=inp.closest('.select__control');if(!ctrl)return'noctrl';ctrl.scrollIntoView({block:'center'});await sleep(120);const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(350);let opts=[...document.querySelectorAll('.select__option,[role=option]')];const wl=label.toLowerCase();let t=opts.find(o=>o.textContent.trim().toLowerCase()===wl)||opts.find(o=>o.textContent.toLowerCase().includes(wl));if(!t){fire(document.body,'mousedown',0,0);return'noopt:'+opts.map(o=>o.textContent.trim()).join('|');}const tr=t.getBoundingClientRect();fire(t,'mousedown',tr.left+5,tr.top+5);fire(t,'mouseup',tr.left+5,tr.top+5);fire(t,'click',tr.left+5,tr.top+5);await sleep(220);const sv=ctrl.querySelector('.select__single-value');return'picked:'+(sv?sv.textContent:'?');}""",{"id":"question_64733992","label":"Yes"})
print("ONSITE:",res)
time.sleep(0.5)
# also ensure consent checkboxes ticked (fixed CONSENT logic inline)
pg.evaluate("""()=>{for(const inp of document.querySelectorAll('input[type=checkbox]')){if(inp.offsetParent===null)continue;const req=inp.required||inp.getAttribute('aria-required')==='true';if(req&&!inp.checked){inp.scrollIntoView({block:'center'});inp.click();}}}""")
time.sleep(0.3)
btn=pg.query_selector('button:has-text("Submit application")') or pg.query_selector('button[type=submit]')
if btn: btn.scroll_into_view_if_needed();time.sleep(0.3);btn.click()
time.sleep(4)
has_otp=pg.evaluate("()=>!!document.getElementById('security-input-0')")
print("otp:",has_otp)
if has_otp:
    since=time.time()-30
    code=g.wait_for_verification_code(timeout_seconds=120,poll_seconds=5,since_epoch=since)
    print("CODE",code)
    pg.evaluate("""(code)=>{const setN=(el,v)=>{const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};for(let i=0;i<8;i++){const el=document.getElementById('security-input-'+i);if(el){el.focus();setN(el,code[i]);el.dispatchEvent(new KeyboardEvent('keydown',{key:code[i],bubbles:true}));el.dispatchEvent(new KeyboardEvent('keyup',{key:code[i],bubbles:true}));}}}""",code)
    time.sleep(1.5)
    for _ in range(5):
        b=pg.query_selector('button:has-text("Submit application")') or pg.query_selector('button:has-text("Verify")') or pg.query_selector('button[type=submit]')
        if b and not b.is_disabled() and (b.get_attribute('aria-disabled') or 'false')!='true':
            b.scroll_into_view_if_needed();time.sleep(0.3);b.click();break
        time.sleep(1.5)
final=None
for _ in range(14):
    time.sleep(2)
    final=json.loads(pg.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application.{0,20}submitted|application submitted|we.{0,3}ll be in touch|appreciate your interest/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');return JSON.stringify({url,confirmed:conf,otpStill,head:body.slice(0,100)});}"""))
    if final['confirmed']:break
    if not final['otpStill'] and not has_otp:break
print(json.dumps(final,indent=1));print("STATUS:","SUBMITTED" if final['confirmed'] else "uncertain")
