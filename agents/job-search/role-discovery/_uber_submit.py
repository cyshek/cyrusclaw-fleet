import sys, time, json
from playwright.sync_api import sync_playwright
CDP = "http://127.0.0.1:18800"
job = sys.argv[1]
pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
page = None
for ctx in br.contexts:
    for p in ctx.pages:
        if f'/careers/apply/form/{job}' in p.url:
            page = p
            break
    if page:
        break
if not page:
    print("NO PAGE")
    sys.exit(2)
print("page-before:", page.url)

# Capture graphql submitApplication responses
submit_resps = []


def on_resp(resp):
    try:
        u = resp.url
        if 'graphql' in u or 'apply' in u.lower():
            ct = resp.headers.get('content-type', '')
            if 'json' in ct:
                body = resp.text()
                if 'submitApplication' in body or 'applicationId' in body or 'SessionToken' in body:
                    submit_resps.append({'url': u[:80], 'status': resp.status, 'body': body[:600]})
    except Exception:
        pass


page.on('response', on_resp)

# Pre-submit: confirm no invalid + submit enabled
pre = page.evaluate("""()=>{const inv=[...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name||e.id); const sub=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.innerText)); return {invalid:inv, submitDisabled: sub?(sub.disabled):null};}""")
print("PRE_SUBMIT:", json.dumps(pre))
if pre['invalid']:
    print("ABORT: invalid fields remain:", pre['invalid'])
    sys.exit(5)

# Click Submit application
clicked = page.evaluate("""()=>{const b=[...document.querySelectorAll('button')].find(x=>/submit application/i.test(x.innerText)); if(b){b.scrollIntoView({block:'center'}); b.click(); return true;} return false;}""")
print("submit clicked:", clicked)

# Wait for route change to /apply/success OR graphql confirmation, up to ~25s
success_route = False
for i in range(25):
    time.sleep(1)
    u = page.url
    if '/careers/apply/success' in u or '/apply/success' in u:
        success_route = True
        break
    if submit_resps:
        # got a graphql submit response; keep a couple more polls for route
        pass

final_url = page.url
body_txt = ''
try:
    body_txt = page.inner_text('body')[:500]
except Exception:
    pass
app_submitted_text = 'application submitted' in body_txt.lower()
form_gone = page.evaluate("""()=>document.querySelector('input[name="firstName"]')===null""")

print("FINAL_URL:", final_url)
print("SUCCESS_ROUTE:", success_route)
print("APP_SUBMITTED_TEXT:", app_submitted_text)
print("FORM_GONE:", form_gone)
print("GRAPHQL_SUBMIT_RESPS:", json.dumps(submit_resps, indent=1)[:1400])
print("BODY_HEAD:", body_txt[:300])

# Verdict
if success_route or (app_submitted_text and form_gone):
    print("VERDICT: SUBMITTED")
elif submit_resps and any('SessionToken' in r['body'] for r in submit_resps):
    print("VERDICT: SESSION_TOKEN_INVALID")
else:
    print("VERDICT: UNCONFIRMED")
