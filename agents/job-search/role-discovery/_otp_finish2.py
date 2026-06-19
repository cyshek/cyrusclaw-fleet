import sys, time, json
from playwright.sync_api import sync_playwright
import gmail_imap as g

CDP = "http://127.0.0.1:18800"
SUB = sys.argv[1]
LOG = open("/tmp/otp_run.log", "w")
def log(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
page = None
for ctx in br.contexts:
    for p in ctx.pages:
        if SUB in p.url:
            page = p
if not page:
    log("ERR page-not-found"); sys.exit(1)

# clear boxes
page.evaluate("""()=>{for(let i=0;i<8;i++){const e=document.getElementById('security-input-'+i);if(e)e.value='';}}""")

# trigger fresh code: click Submit application
since = time.time() - 3
btn = page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/^submit application/i.test(b.textContent.trim()));if(s){s.scrollIntoView({block:'center'});s.click();return true;}return false;}""")
log("clicked submit:", btn)
time.sleep(3)

# fetch fresh code (newer than 'since')
try:
    code = g.wait_for_verification_code(timeout_seconds=150, poll_seconds=6, since_epoch=since)
except Exception as e:
    log("ERR otp-fetch", str(e)); sys.exit(1)
log("CODE:", code)
if not code or len(code) < 8:
    log("ERR bad-code", code); sys.exit(1)

# ensure OTP boxes present
has = page.evaluate("""()=>!!document.getElementById('security-input-0')""")
log("has boxes:", has)
if not has:
    time.sleep(2)

# type with keyboard
page.evaluate("""()=>{for(let i=0;i<8;i++){const e=document.getElementById('security-input-'+i);if(e)e.value='';}}""")
fb = page.query_selector('#security-input-0')
if fb:
    fb.click(); time.sleep(0.2)
    for ch in code[:8]:
        page.keyboard.press(ch); time.sleep(0.18)
time.sleep(1.0)
vals = page.evaluate("""()=>{let v='';for(let i=0;i<8;i++){const e=document.getElementById('security-input-'+i);v+=e?e.value:'_';}return v;}""")
log("BOXVALS:", vals)

# submit/verify
for _ in range(5):
    c = page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit|verify|confirm/i.test(b.textContent.trim())&&!b.disabled&&b.getAttribute('aria-disabled')!=='true');if(s){s.scrollIntoView({block:'center'});s.click();return s.textContent.trim();}return null;}""")
    if c: log("submit-btn:", c); break
    time.sleep(1.5)

final=None
for _ in range(14):
    time.sleep(2)
    final = json.loads(page.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application submitted|submitted your application|appreciate your interest|will begin reviewing/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');const otpErr=/incorrect|invalid|wrong code|expired|didn.t match/i.test(body);return JSON.stringify({url,confirmed:conf,otpStill,otpErr,head:body.slice(0,200)});}"""))
    if final['confirmed'] or final.get('otpErr'): break
    if not final['otpStill']: break
log("FINAL:", json.dumps(final))
