import sys, time, json
from playwright.sync_api import sync_playwright
import gmail_imap as g

CDP = "http://127.0.0.1:18800"
SUB = sys.argv[1]
SINCE = float(sys.argv[2]) if len(sys.argv) > 2 else (time.time() - 600)
LOG = open("/tmp/otpx.log", "a")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if SUB in p.url: page=p
if not page: log("ERR page-not-found", SUB); sys.exit(1)

has=page.evaluate("""()=>!!document.getElementById('security-input-0')""")
log("has-otp-boxes:", has)
if not has: log("ERR no-otp"); sys.exit(1)

try:
    code=g.wait_for_verification_code(timeout_seconds=60, poll_seconds=5, since_epoch=SINCE)
except Exception as e:
    log("ERR fetch", str(e)); sys.exit(1)
log("CODE:", code)
if not code or len(code)<8: log("ERR badcode", code); sys.exit(1)

page.evaluate("""()=>{for(let i=0;i<8;i++){const e=document.getElementById('security-input-'+i);if(e)e.value='';}}""")
fb=page.query_selector('#security-input-0')
fb.click(); time.sleep(0.25)
for ch in code[:8]:
    page.keyboard.press(ch); time.sleep(0.18)
time.sleep(1.0)
vals=page.evaluate("""()=>{let v='';for(let i=0;i<8;i++){const e=document.getElementById('security-input-'+i);v+=e?e.value:'_';}return v;}""")
log("BOXVALS:", vals)

for _ in range(6):
    c=page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit|verify|confirm/i.test(b.textContent.trim())&&!b.disabled&&b.getAttribute('aria-disabled')!=='true');if(s){s.scrollIntoView({block:'center'});s.click();return s.textContent.trim();}return null;}""")
    if c: log("clicked:", c); break
    time.sleep(1.5)
else:
    log("WARN no-enabled-submit-btn")

final=None
for _ in range(15):
    time.sleep(2)
    final=json.loads(page.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application submitted|submitted your application|appreciate your interest|will begin reviewing/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');const otpErr=/incorrect|invalid|wrong code|expired|didn.t match/i.test(body);return JSON.stringify({url,confirmed:conf,otpStill,otpErr,head:body.slice(0,150)});}"""))
    if final['confirmed'] or final.get('otpErr'): break
    if not final['otpStill']: break
log("FINAL:", json.dumps(final))
