import sys, time, json
from playwright.sync_api import sync_playwright
import gmail_imap as g

CDP = "http://127.0.0.1:18800"
URL_SUB = sys.argv[1]  # url substring to find the page

def find_page(br, sub):
    for ctx in br.contexts:
        for p in ctx.pages:
            if sub in p.url:
                return p
    return None

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
page = find_page(br, URL_SUB)
if not page:
    print(json.dumps({"err": "page-not-found"})); sys.exit(1)

state = page.evaluate("""()=>{const has=!!document.getElementById('security-input-0');return JSON.stringify({has,url:location.href,body:document.body.innerText.slice(0,300)});}""")
print("STATE:", state)
st = json.loads(state)
if not st['has']:
    print(json.dumps({"err": "no-otp-boxes", "body": st['body']})); sys.exit(1)

# Click "Send New Code" to get a fresh code
since = time.time() - 5
clicked = page.evaluate("""()=>{const b=[...document.querySelectorAll('button,a')].find(x=>/send new code|resend/i.test(x.textContent||''));if(b){b.click();return b.textContent.trim();}return null;}""")
print("send-new-code:", clicked)
time.sleep(2)

# fetch fresh code
try:
    code = g.wait_for_verification_code(timeout_seconds=150, poll_seconds=5, since_epoch=since)
except Exception as e:
    print(json.dumps({"err": "otp-fetch-fail", "detail": str(e)})); sys.exit(1)
print("CODE:", code)
if not code or len(code) < 8:
    print(json.dumps({"err": "bad-code", "code": code})); sys.exit(1)

# Type digits with real keyboard. Focus first box, then type sequentially (auto-advance).
page.evaluate("""()=>{for(let i=0;i<8;i++){const e=document.getElementById('security-input-'+i);if(e)e.value='';}const f=document.getElementById('security-input-0');if(f)f.focus();}""")
time.sleep(0.3)
first = page.query_selector('#security-input-0')
first.click()
for ch in code[:8]:
    page.keyboard.press(ch)
    time.sleep(0.15)
time.sleep(1.0)

vals = page.evaluate("""()=>{const v=[];for(let i=0;i<8;i++){const e=document.getElementById('security-input-'+i);v.push(e?e.value:'X');}return v.join('');}""")
print("BOXVALS:", vals)

# click submit/verify/confirm
for _ in range(5):
    clicked = page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit|verify|confirm/i.test(b.textContent.trim())&&!b.disabled&&!b.getAttribute('aria-disabled'));if(s){s.scrollIntoView({block:'center'});s.click();return s.textContent.trim();}return null;}""")
    if clicked:
        print("submit-btn:", clicked); break
    time.sleep(1.5)

final = None
for _ in range(12):
    time.sleep(2)
    final = json.loads(page.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application.{0,20}submitted|application submitted|submitted your application|we.{0,3}ll be in touch|will begin reviewing|appreciate your interest/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');const otpErr=/incorrect|invalid|wrong code|didn.{0,3}t match|expired/i.test(body);return JSON.stringify({url,confirmed:conf,otpStill,otpErr,head:body.slice(0,250)});}"""))
    if final['confirmed'] or final.get('otpErr'):
        break
    if not final['otpStill']:
        break
print("FINAL:", json.dumps(final, indent=1))
