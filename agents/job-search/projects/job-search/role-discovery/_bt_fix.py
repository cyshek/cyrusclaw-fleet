import time,json
from playwright.sync_api import sync_playwright
import gmail_imap as g
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start();br=pw.chromium.connect_over_cdp(CDP);ctx=br.contexts[0]
pg=[p for p in ctx.pages if '7899566' in p.url][0]
specs=[
  {"id":"question_66541725","label":"I have the right to work in the country of employment on a permanent basis"},
  {"id":"question_66541727","label":"Acknowledge/Confirm"},
]
# pick each: open its OWN control, then click option in the menu that belongs to it (scope to nearest .select__menu)
res=pg.evaluate("""async (specs)=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const out=[];for(const{id,label}of specs){const inp=document.getElementById(id);if(!inp){out.push({id,err:'noinput'});continue;}const ctrl=inp.closest('.select__control');ctrl.scrollIntoView({block:'center'});await sleep(150);const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(400);
  // find the menu associated with this control: search siblings/descendants of ctrl's parent
  let menu=null;let n=ctrl.parentElement;for(let k=0;k<4&&n;k++){menu=n.querySelector('.select__menu');if(menu)break;n=n.parentElement;}
  if(!menu)menu=document.querySelector('.select__menu');
  let opts=menu?[...menu.querySelectorAll('.select__option,[role=option]')]:[];
  const wl=label.toLowerCase();let t=opts.find(o=>o.textContent.trim().toLowerCase()===wl)||opts.find(o=>o.textContent.toLowerCase().includes(wl.slice(0,30)));
  if(!t){out.push({id,err:'noopt',avail:opts.slice(-5).map(o=>o.textContent.trim())});fire(document.body,'mousedown',0,0);await sleep(150);continue;}
  const tr=t.getBoundingClientRect();fire(t,'mousedown',tr.left+5,tr.top+5);fire(t,'mouseup',tr.left+5,tr.top+5);fire(t,'click',tr.left+5,tr.top+5);await sleep(250);const sv=ctrl.querySelector('.select__single-value');out.push({id,want:label,got:sv?sv.textContent:null});}
  return out;}""",specs)
print("PICK:",json.dumps(res))
time.sleep(0.5)
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
    final=json.loads(pg.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application.{0,20}submitted|we.{0,3}ll be in touch|appreciate your interest/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');return JSON.stringify({url,confirmed:conf,otpStill,head:body.slice(0,90)});}"""))
    if final['confirmed']:break
    if not final['otpStill'] and not has_otp:break
print(json.dumps(final,indent=1));print("STATUS:","SUBMITTED" if final['confirmed'] else "uncertain")
