"""
Debug the OTP submission by intercepting network requests.
Opens the existing stale Natera page (with OTP already filled),
clears the OTP, requests fresh code, fills it, then submits with network capture.
"""
import json, time, sys, os, re
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright
import imaplib, email as email_mod

CDP_URL = 'http://127.0.0.1:18800'
APP_PW_PATH = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.gmail-app-password'


def get_latest_otp_code(since_time):
    """Fetch latest OTP code from Gmail since given epoch time."""
    app_pw = open(APP_PW_PATH).read().strip()
    deadline = since_time + 120
    while time.time() < deadline:
        try:
            M = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            M.login('cyshekari@gmail.com', app_pw)
            M.select('"[Gmail]/All Mail"')
            typ, data = M.search(None, 'FROM no-reply@us.greenhouse-mail.io SINCE 25-Jun-2026')
            ids = data[0].split() if typ == 'OK' and data[0] else []
            for mid in list(reversed(ids))[:10]:
                typ2, mdata = M.fetch(mid, '(RFC822)')
                if typ2 != 'OK':
                    continue
                msg = email_mod.message_from_bytes(mdata[0][1])
                if 'natera' not in msg.get('Subject', '').lower():
                    continue
                # Check email timestamp
                import email.utils
                date_tuple = email.utils.parsedate(msg.get('Date', ''))
                if date_tuple:
                    import calendar
                    msg_epoch = calendar.timegm(date_tuple)
                    if msg_epoch < since_time - 10:
                        continue
                body = ''
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct in ('text/plain', 'text/html'):
                        try:
                            body += part.get_payload(decode=True).decode('utf-8', errors='replace')
                        except:
                            pass
                codes = re.findall(r'\b([A-Za-z0-9]{8})\b', body)
                real_codes = [c for c in codes if c not in ('overflow', 'security', 'resubmit', 'password', 'contains')]
                if real_codes:
                    M.logout()
                    return real_codes[0]
            M.logout()
        except Exception as e:
            print(f'[gmail] Error: {e}')
        print('[gmail] No fresh code yet, waiting 5s...')
        time.sleep(5)
    return None


def main():
    net_log = []
    
    with sync_playwright() as pw:
        br = pw.chromium.connect_over_cdp(CDP_URL)
        ctx = br.contexts[0] if br.contexts else br.new_context()
        
        # Find an existing Natera page
        natera_pages = [p for p in ctx.pages if 'natera' in p.url]
        print(f'Found {len(natera_pages)} Natera pages')
        
        # Use a fresh page to avoid stale state
        page = ctx.new_page()
        
        def on_request(req):
            if 'greenhouse' in req.url and 'snowplow' not in req.url:
                pd = None
                try:
                    pd = req.post_data
                except:
                    pass
                net_log.append({
                    'type': 'req',
                    'method': req.method,
                    'url': req.url,
                    'body': (pd or '')[:500] if pd else None
                })
                if req.method in ('POST', 'PUT'):
                    print(f'[NET-REQ] {req.method} {req.url}', flush=True)
                    if pd and 'snowplow' not in req.url:
                        print(f'[NET-REQ-BODY] {(pd or "")[:300]}', flush=True)
        
        def on_response(resp):
            if 'greenhouse' in resp.url and 'snowplow' not in resp.url and resp.status != 200:
                print(f'[NET-RESP] {resp.status} {resp.url}', flush=True)
                try:
                    b = resp.body()
                    if b:
                        print(f'[NET-RESP-BODY] {b[:300]}', flush=True)
                except:
                    pass
        
        page.on('request', on_request)
        page.on('response', on_response)
        
        # Navigate fresh
        print('[nav] Loading Natera page...', flush=True)
        page.goto('https://job-boards.greenhouse.io/natera/jobs/6099223004', 
                  wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        
        # Check if OTP gate is showing (shouldn't be on fresh page)
        state = page.evaluate("""() => ({
            hasOTP: !!document.getElementById('security-input-0'),
            hasForm: !!document.getElementById('first_name'),
            url: location.href
        })""")
        print(f'[state] Initial: {state}', flush=True)
        
        # Click Apply
        page.evaluate("""() => {
            const b = [...document.querySelectorAll('button,a')].find(x => /^apply/i.test((x.textContent||'').trim()));
            if (b) { b.scrollIntoView(); b.click(); }
        }""")
        time.sleep(2)
        
        # Fill text fields
        text_fields = {
            'first_name': 'Cyrus',
            'last_name': 'Shekari',
            'preferred_name': 'Cyrus',
            'email': 'cyshekari@gmail.com',
            'phone': '3468040227',
            'question_19071372004': 'https://linkedin.com/in/cyshekari',
            'question_19071376004': 'Yes',
            'question_19071380004': '12420 NE 120th St #1437',
            'question_19071381004': 'Kirkland',
            'question_19071383004': '98034',
            'question_19071384004': 'Open to discuss',
            'question_19071385004': 'Microsoft',
        }
        page.evaluate("""(fields) => {
            const setN = (el, v) => {
                const pr = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const d = Object.getOwnPropertyDescriptor(pr, 'value');
                d.set.call(el, v);
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            };
            for (const [id, val] of Object.entries(fields)) {
                const el = document.getElementById(id);
                if (el && val) setN(el, String(val));
            }
        }""", text_fields)
        time.sleep(0.5)
        
        # Upload resume
        resume_inp = page.query_selector('input#resume')
        if resume_inp:
            print('[upload] Uploading resume...', flush=True)
            resume_inp.set_input_files('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/natera-6099223004/Cyrus_Shekari_Resume_natera_6099223004_v2.pdf')
            time.sleep(2)
            print('[upload] Done', flush=True)
        
        # Now submit the form (initial submit to get OTP)
        since_time = time.time()
        print('[submit1] Clicking initial Submit to trigger OTP...', flush=True)
        page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button')];
            const s = btns.find(b => /submit application/i.test(b.textContent.trim()));
            if (s) { s.scrollIntoView({block:'center'}); s.click(); }
        }""")
        
        # Wait for OTP gate
        print('[wait] Waiting for OTP gate...', flush=True)
        for i in range(30):
            time.sleep(2)
            otp_check = page.evaluate("() => !!document.getElementById('security-input-0')")
            print(f'[wait] {i+1}: hasOTP={otp_check}', flush=True)
            if otp_check:
                break
        else:
            print('[submit1] OTP gate never appeared!', flush=True)
            page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_nootp2.png')
            return 1
        
        print('[otp] OTP gate appeared, fetching code...', flush=True)
        code = get_latest_otp_code(since_time)
        if not code:
            print('[otp] No code found!', flush=True)
            return 1
        print(f'[otp] Got code: {code!r}', flush=True)
        
        # Fill OTP inputs
        for i, ch in enumerate(code):
            inp = page.query_selector(f'#security-input-{i}')
            if inp:
                inp.click()
                time.sleep(0.1)
                inp.fill(ch)
                time.sleep(0.1)
        time.sleep(0.5)
        
        # Verify OTP filled
        vals = page.evaluate("""() => [0,1,2,3,4,5,6,7].map(i => {
            const e = document.getElementById('security-input-'+i);
            return e ? e.value : '-';
        }).join('')""")
        print(f'[otp] OTP vals in form: {vals!r} (expected {code!r})', flush=True)
        
        # Screenshot before OTP submit
        page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_otp_before2.png')
        
        # Inject reCAPTCHA token
        try:
            from captcha_presubmit import solve_and_inject_recaptcha_v3
            cap = solve_and_inject_recaptcha_v3(
                page,
                fallback_sitekey='6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0',
                action='job_apply',
                page_url='https://job-boards.greenhouse.io/natera/jobs/6099223004'
            )
            print(f'[captcha] {cap}', flush=True)
        except Exception as e:
            print(f'[captcha] Failed: {e}', flush=True)
        
        # Submit OTP
        print('[submit2] Clicking OTP submit...', flush=True)
        since_submit2 = time.time()
        btn = page.query_selector('button:has-text("Submit application")')
        if btn:
            btn.scroll_into_view_if_needed()
            time.sleep(0.3)
            btn.click()
        else:
            page.evaluate("""() => {
                const s = [...document.querySelectorAll('button')].find(b => /submit/i.test(b.textContent.trim()));
                if (s) s.click();
            }""")
        
        # Wait and check result
        for i in range(20):
            time.sleep(2)
            result = page.evaluate("""() => ({
                url: location.href,
                hasOTP: !!document.getElementById('security-input-0'),
                confirmed: /thank you|received your application|application.*submitted/i.test(document.body.innerText) || /confirmation/.test(location.href),
                errorMsg: (document.body.innerText.match(/error.*?\n/i) || [''])[0].trim(),
                body200: document.body.innerText.slice(0, 300)
            })""")
            print(f'[poll] {i+1}: OTP={result["hasOTP"]} confirmed={result["confirmed"]} err={result["errorMsg"]!r}', flush=True)
            if result['confirmed']:
                print('✅ SUBMITTED SUCCESSFULLY!', flush=True)
                page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_confirmed2.png')
                return 0
            if result['errorMsg']:
                print(f'[error] {result["body200"][:300]}', flush=True)
                break
            if not result['hasOTP'] and i > 2:
                print(f'[poll] OTP gone, checking...', flush=True)
                print(f'[poll] Body: {result["body200"][:300]}', flush=True)
                break
        
        page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_debug_final.png')
        print(f'[done] Net log ({len(net_log)} entries):', flush=True)
        for entry in net_log:
            if entry['type'] == 'req' and entry['method'] in ('POST', 'PUT'):
                print(f'  POST {entry["url"][:100]}', flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
