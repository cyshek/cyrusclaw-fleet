#!/usr/bin/env python3
"""Dedicated Natera GH OTP submission script.
Handles the OTP gate robustly with longer waits and keyboard-based entry.
"""
import json, os, sys, time, re
sys.path.insert(0, os.path.dirname(__file__))

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CDP_URL = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:18800')
PLAN_PATH = 'output/inline-plan-natera-6099223004.json'

def main():
    plan = json.load(open(PLAN_PATH))
    url = plan['url']  # https://job-boards.greenhouse.io/natera/jobs/6099223004
    pdf_path = plan['pdf_path_local']
    
    print(f'[natera] Plan loaded, url={url}', flush=True)
    print(f'[natera] PDF: {pdf_path}', flush=True)
    
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(30000)
        
        print(f'[natera] Navigating to {url}', flush=True)
        page.goto(url, wait_until='networkidle', timeout=30000)
        time.sleep(2)
        
        # Click the initial Apply button to open the form
        apply_btn = page.query_selector('a:has-text("Apply"), button:has-text("Apply")')
        if apply_btn:
            print('[natera] Clicking Apply button to open form', flush=True)
            apply_btn.click()
            time.sleep(2)
        
        # Check if form is visible
        first_name = page.query_selector('#first_name')
        if not first_name:
            print('[natera] Form not found after Apply click — trying direct form URL', flush=True)
            # Try the embed URL
            embed_url = 'https://boards.greenhouse.io/embed/job_app?for=natera&token=6099223004'
            page.goto(embed_url, wait_until='networkidle', timeout=30000)
            time.sleep(2)
            first_name = page.query_selector('#first_name')
        
        if not first_name:
            print('[natera] ERROR: Cannot find form. Page text:', page.inner_text('body')[:300], flush=True)
            return 1
        
        print('[natera] Form found — filling fields', flush=True)
        
        # Fill basic fields
        def fill_field(sel, val):
            el = page.query_selector(sel)
            if el:
                el.click(); time.sleep(0.1)
                el.fill(val)
                time.sleep(0.1)
                return True
            return False
        
        fill_field('#first_name', 'Cyrus')
        fill_field('#last_name', 'Shekari')
        fill_field('#email', 'cyshekari@gmail.com')
        fill_field('#phone', '+14253001898')
        
        # LinkedIn
        linkedin_inp = page.query_selector('#question_19071372004')
        if linkedin_inp:
            linkedin_inp.fill('https://www.linkedin.com/in/cyrus-shekari')
        
        # Upload resume
        resume_inp = page.query_selector('input#resume') or page.query_selector('input[name="resume"]')
        if resume_inp:
            resume_inp.set_input_files(pdf_path)
            print('[natera] Resume uploaded', flush=True)
            time.sleep(1)
        else:
            print('[natera] WARNING: resume input not found', flush=True)
        
        # Fill custom questions from plan
        text_fields = plan.get('text_fields', {})
        if isinstance(text_fields, dict):
            for fid, val in text_fields.items():
                el = page.query_selector(f'#{fid}') or page.query_selector(f'[name="{fid}"]')
                if el and val:
                    el.fill(str(val))
                    time.sleep(0.1)
        
        # Fill dropdowns from plan
        for dd in plan.get('dropdowns', []):
            fid = dd.get('id') or dd.get('field_id')
            val = dd.get('value') or dd.get('label')
            if not fid or not val:
                continue
            # Try select element
            sel_el = page.query_selector(f'select[id="{fid}"], select[name="{fid}"]')
            if sel_el:
                try:
                    sel_el.select_option(label=str(val))
                    time.sleep(0.1)
                except:
                    pass
            else:
                # React select — find by aria
                pass
        
        # Handle specific Natera questions from plan
        # Are you 18 or older? -> Yes (value=1)
        q_18 = page.query_selector('input[name="question_19071374004"][value="1"]')
        if q_18:
            q_18.click(); time.sleep(0.1)
        
        # Have you previously worked at Natera? -> No (value=0)
        q_prev = page.query_selector('input[name="question_19071375004"][value="0"]')
        if q_prev:
            q_prev.click(); time.sleep(0.1)
        
        # Family members at Natera? (textarea) -> No
        q_family = page.query_selector('#question_19071376004')
        if q_family:
            q_family.fill('No')
            time.sleep(0.1)
        
        # Legally authorized in US? -> Yes
        q_auth = page.query_selector('input[name="question_19071377004"][value="1"]')
        if q_auth:
            q_auth.click(); time.sleep(0.1)
        
        # Require sponsorship? -> No
        q_spon = page.query_selector('input[name="question_19071378004"][value="0"]')
        if q_spon:
            q_spon.click(); time.sleep(0.1)
        
        # Non-compete? -> No
        q_nc = page.query_selector('input[name="question_19071379004"][value="0"]')
        if q_nc:
            q_nc.click(); time.sleep(0.1)
        
        # Street address
        q_addr = page.query_selector('#question_19071380004')
        if q_addr:
            q_addr.fill('3501 NE 45th St')
            time.sleep(0.1)
        
        # City
        q_city = page.query_selector('#question_19071381004')
        if q_city:
            q_city.fill('Kirkland')
            time.sleep(0.1)
        
        # State -> WA (value=86557511004)
        q_state = page.query_selector('input[name="question_19071382004"][value="86557511004"]')
        if q_state:
            q_state.click(); time.sleep(0.1)
        
        # ZIP
        q_zip = page.query_selector('#question_19071383004')
        if q_zip:
            q_zip.fill('98033')
            time.sleep(0.1)
        
        # Salary expectations
        q_sal = page.query_selector('#question_19071384004')
        if q_sal:
            q_sal.fill('170000')
            time.sleep(0.1)
        
        # Most recent employer
        q_emp = page.query_selector('#question_19071385004')
        if q_emp:
            q_emp.fill('Microsoft')
            time.sleep(0.1)
        
        # EEO - gender -> Decline (value=3)
        q_gender = page.query_selector('select[name="gender"]')
        if q_gender:
            try:
                q_gender.select_option(value='3')
            except:
                pass
        
        # EEO - race -> Decline (value=8)
        q_race = page.query_selector('select[name="race"]')
        if q_race:
            try:
                q_race.select_option(value='8')
            except:
                pass
        
        time.sleep(1)
        
        # Check pre-submit state
        ps = page.evaluate("""()=>{
            const req=[...document.querySelectorAll('input[required],select[required],textarea[required]')].filter(e=>e.offsetParent!==null);
            const empty=req.filter(e=>(e.type==='checkbox'||e.type==='radio')?!e.checked:!e.value).map(e=>e.id||e.name);
            const sub=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));
            return JSON.stringify({emptyRequired:empty,submitDisabled:sub?(sub.disabled||sub.getAttribute('aria-disabled')==='true'):'nobtn'});
        }""")
        ps_data = json.loads(ps)
        print(f'[natera] PreSubmit: {ps_data}', flush=True)
        
        if ps_data.get('emptyRequired'):
            print(f'[natera] WARNING: empty required fields: {ps_data["emptyRequired"]}', flush=True)
        
        # Take screenshot before submit
        page.screenshot(path='/tmp/natera_presubmit.png')
        print('[natera] Screenshot saved to /tmp/natera_presubmit.png', flush=True)
        
        # Click submit button
        since_submit = time.time()
        submit_btn = page.query_selector('button:has-text("Submit application")') or page.query_selector('button[type=submit]')
        if submit_btn:
            print('[natera] Clicking submit button', flush=True)
            submit_btn.scroll_into_view_if_needed()
            time.sleep(0.5)
            submit_btn.click()
        else:
            print('[natera] Submit button not found by selector, using JS click', flush=True)
            page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));if(s){s.scrollIntoView({block:'center'});s.click();}}""")
        
        print('[natera] Waiting up to 15s for OTP gate...', flush=True)
        
        # Wait up to 15 seconds for OTP gate to appear
        has_otp = False
        for _wait in range(15):
            time.sleep(1)
            state = page.evaluate("""()=>{
                const hasOTP = !!document.getElementById('security-input-0') || 
                               /verification code was sent|enter the 8-character|security code/i.test(document.body.innerText);
                const confirmed = /thank you|received your application|application submitted/i.test(document.body.innerText) || /confirmation/.test(location.href);
                return JSON.stringify({hasOTP, confirmed, url: location.href, bodySnip: document.body.innerText.slice(0,200)});
            }""")
            state_data = json.loads(state)
            print(f'[natera] wait={_wait+1}s hasOTP={state_data["hasOTP"]} confirmed={state_data["confirmed"]} url={state_data["url"][:60]}', flush=True)
            if state_data['hasOTP']:
                has_otp = True
                break
            if state_data['confirmed']:
                print('[natera] CONFIRMED without OTP!', flush=True)
                print(json.dumps({'status': 'SUBMITTED', 'confirmed': True, 'url': state_data['url']}))
                return 0
        
        if not has_otp:
            print(f'[natera] OTP gate never appeared. Final url: {state_data["url"]}', flush=True)
            print(f'[natera] Body: {state_data["bodySnip"]}', flush=True)
            page.screenshot(path='/tmp/natera_nootp.png')
            print(json.dumps({'status': 'blocked-no-otp', 'url': state_data['url']}))
            return 1
        
        print('[natera] OTP gate detected! Fetching code from Gmail...', flush=True)
        
        # Fetch OTP from Gmail
        import gmail_imap as g
        try:
            code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=3, since_epoch=since_submit - 5)
        except Exception as e:
            print(f'[natera] Failed to fetch OTP: {e}', flush=True)
            print(json.dumps({'status': 'blocked-otp-fetch-fail', 'err': str(e)}))
            return 1
        
        print(f'[natera] Got OTP code: {code!r}', flush=True)
        
        # Screenshot of OTP form
        page.screenshot(path='/tmp/natera_otp.png')
        
        # Fill OTP using keyboard.type on each input (more natural than fill)
        for _oi, _ch in enumerate(code):
            inp = page.query_selector(f'#security-input-{_oi}')
            if inp:
                inp.click()
                time.sleep(0.15)
                # Clear first, then type
                inp.fill('')
                time.sleep(0.05)
                inp.type(_ch, delay=50)
                time.sleep(0.15)
            else:
                print(f'[natera] WARNING: input {_oi} not found', flush=True)
        
        time.sleep(1.5)
        
        # Debug state after OTP fill
        otp_state = page.evaluate("""()=>{
            const vals = [0,1,2,3,4,5,6,7].map(i => {
                const el = document.getElementById('security-input-' + i);
                return el ? el.value : '-';
            }).join('');
            const btns = [...document.querySelectorAll('button')].map(b => ({
                txt: b.textContent.trim().slice(0,40),
                disabled: b.disabled,
                aria: b.getAttribute('aria-disabled'),
                type: b.type
            }));
            return JSON.stringify({vals, btns});
        }""")
        otp_data = json.loads(otp_state)
        print(f'[natera] OTP vals: {otp_data["vals"]}', flush=True)
        print(f'[natera] Buttons:', flush=True)
        for btn in otp_data['btns']:
            if btn['txt'] or btn['type'] == 'submit':
                print(f'  {btn}', flush=True)
        
        # Click the OTP submit button
        otp_submitted = False
        for _try in range(6):
            # Find submit button (look for any enabled submit-like button)
            submit_result = page.evaluate("""()=>{
                // Try various selectors
                const btns = [...document.querySelectorAll('button')];
                const candidates = btns.filter(b => {
                    const txt = b.textContent.trim().toLowerCase();
                    return (txt.includes('submit') || txt.includes('verify') || txt.includes('confirm') || b.type === 'submit') &&
                           !b.disabled && b.getAttribute('aria-disabled') !== 'true';
                });
                if (candidates.length === 0) return JSON.stringify({found: false, allBtns: btns.map(b => b.textContent.trim().slice(0,30))});
                const btn = candidates[0];
                btn.scrollIntoView({block: 'center'});
                btn.click();
                return JSON.stringify({found: true, txt: btn.textContent.trim(), clicked: true});
            }""")
            sr = json.loads(submit_result)
            print(f'[natera] otp-submit try={_try}: {sr}', flush=True)
            if sr.get('clicked'):
                otp_submitted = True
                break
            time.sleep(1.5)
        
        if not otp_submitted:
            # Last resort: try pressing Enter
            print('[natera] Trying Enter key as last resort', flush=True)
            last_inp = page.query_selector('#security-input-7')
            if last_inp:
                last_inp.press('Enter')
            otp_submitted = True
        
        # Wait for confirmation
        print('[natera] Waiting for confirmation...', flush=True)
        confirmed = False
        final_url = ''
        for _ in range(20):
            time.sleep(2)
            final = page.evaluate("""()=>{
                const url = location.href;
                const body = document.body.innerText;
                const conf = /thank you|received your application|application.{0,20}submitted|application submitted|submitted your application|we.{0,3}ll be in touch|will begin reviewing|appreciate your interest/i.test(body) || /confirmation/.test(url);
                const otpStill = !!document.getElementById('security-input-0');
                const otpErr = /incorrect|invalid|wrong code|didn.{0,3}t match|expired/i.test(body);
                return JSON.stringify({url, confirmed: conf, otpStill, otpErr, head: body.slice(0, 300)});
            }""")
            fd = json.loads(final)
            print(f'[natera] poll: confirmed={fd["confirmed"]} otpStill={fd["otpStill"]} otpErr={fd["otpErr"]} url={fd["url"][:60]}', flush=True)
            if fd['confirmed']:
                confirmed = True
                final_url = fd['url']
                print(f'[natera] ✅ CONFIRMED! Head: {fd["head"][:200]}', flush=True)
                break
            if fd['otpErr']:
                print(f'[natera] ❌ OTP error: {fd["head"][:200]}', flush=True)
                break
            if not fd['otpStill'] and _ > 2:
                # OTP gone but no confirmation
                print(f'[natera] OTP gone, no confirmation. Head: {fd["head"][:200]}', flush=True)
                break
        
        page.screenshot(path='/tmp/natera_final.png')
        
        if confirmed:
            result = {'status': 'SUBMITTED', 'url': final_url, 'otp_code': code}
            print(json.dumps(result, indent=1))
            return 0
        else:
            result = {'status': 'blocked-otp-rejected', 'otp_code': code, 'final': fd}
            print(json.dumps(result, indent=1))
            return 1

if __name__ == '__main__':
    sys.exit(main())
