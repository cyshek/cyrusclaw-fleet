import sys, time, json
from playwright.sync_api import sync_playwright
import gmail_imap as g
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
  for p in ctx.pages:
    if 'intercom/jobs/7926025' in p.url and 'recaptcha' not in p.url: page=p
# check the data-transfer acknowledge checkbox via real click
cb=page.query_selector("#question_66870568\\[\\]_716838218")
if cb:
    if not cb.is_checked():
        cb.click()
    print("ack checked:", cb.is_checked())
time.sleep(0.5)
since=time.time()-3
# click submit
c=page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));if(s){s.scrollIntoView({block:'center'});s.click();return true;}return false;}""")
print("submit clicked:", c)
time.sleep(4)
# OTP?
has=page.evaluate("""()=>!!document.getElementById('security-input-0')""")
print("otp:", has)
if has:
    try:
        code=g.wait_for_verification_code(timeout_seconds=120, poll_seconds=5, since_epoch=since)
    except Exception as e:
        print("otp-fetch-fail", e); code=None
    print("code:", code)
    if code and len(code)>=8:
        fb=page.query_selector('#security-input-0'); fb.click(); time.sleep(0.2)
        for ch in code[:8]:
            page.keyboard.press(ch); time.sleep(0.18)
        time.sleep(1)
        for _ in range(6):
            cc=page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit|verify|confirm/i.test(b.textContent.trim())&&!b.disabled&&b.getAttribute('aria-disabled')!=='true');if(s){s.click();return s.textContent.trim();}return null;}""")
            if cc: print("verify:",cc); break
            time.sleep(1.5)
final=None
for _ in range(14):
    time.sleep(2)
    final=json.loads(page.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application submitted|appreciate your interest|will be reviewed|we will be in touch/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');const err=[...document.querySelectorAll('.error,[aria-invalid=true]')].map(e=>e.textContent.trim()).filter(Boolean).slice(0,3);return JSON.stringify({url,confirmed:conf,otpStill,err,head:body.slice(0,150)});}"""))
    if final['confirmed']: break
    if not final['otpStill'] and not has: 
        if 'confirmation' in final['url'] or final['confirmed']: break
print("FINAL:", json.dumps(final))
