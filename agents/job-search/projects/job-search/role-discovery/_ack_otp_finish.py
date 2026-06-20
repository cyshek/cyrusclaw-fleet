import sys,time,json
from playwright.sync_api import sync_playwright
import gmail_imap as g
CDP="http://127.0.0.1:18800"
jid=sys.argv[1]
pw=sync_playwright().start();br=pw.chromium.connect_over_cdp(CDP);ctx=br.contexts[0]
pg=[p for p in ctx.pages if jid in p.url][0]
has_otp=pg.evaluate("()=>!!document.getElementById('security-input-0')")
print("URL:",pg.url,"otp:",has_otp)
if has_otp:
    since=time.time()-180  # OTP was sent a couple min ago
    code=g.wait_for_verification_code(timeout_seconds=120,poll_seconds=5,since_epoch=since)
    print("CODE:",code)
    pg.evaluate("""(code)=>{const setN=(el,v)=>{const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};for(let i=0;i<8;i++){const el=document.getElementById('security-input-'+i);if(el){el.focus();setN(el,code[i]);el.dispatchEvent(new KeyboardEvent('keydown',{key:code[i],bubbles:true}));el.dispatchEvent(new KeyboardEvent('keyup',{key:code[i],bubbles:true}));}}}""",code)
    time.sleep(1.5)
    for _ in range(5):
        b=pg.query_selector('button:has-text("Submit application")') or pg.query_selector('button:has-text("Verify")') or pg.query_selector('button:has-text("Confirm")') or pg.query_selector('button[type=submit]')
        if b and not b.is_disabled() and (b.get_attribute('aria-disabled') or 'false')!='true':
            b.scroll_into_view_if_needed();time.sleep(0.3);b.click();print("clicked",(b.text_content() or '').strip());break
        time.sleep(1.5)
final=None
for _ in range(14):
    time.sleep(2)
    final=json.loads(pg.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application.{0,20}submitted|application submitted|submitted your application|we.{0,3}ll be in touch|will begin reviewing|appreciate your interest/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');return JSON.stringify({url,confirmed:conf,otpStill,head:body.slice(0,120)});}"""))
    if final['confirmed']:break
print(json.dumps(final,indent=1))
print("STATUS:", "SUBMITTED" if final['confirmed'] else "uncertain")
