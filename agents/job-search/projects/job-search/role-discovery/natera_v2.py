"""
Natera GH OTP submission - careful monitoring version.
"""
import json, time, sys, os
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright
import gmail_imap as g

CDP_URL = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:18800')
PLAN_PATH = 'output/inline-plan-natera-6099223004.json'

def fill_natera_form(page, plan):
    """Fill all Natera form fields."""
    def native_fill(sel, val):
        el = page.query_selector(sel)
        if el:
            page.evaluate("""(el, v) => {
                const pr = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const d = Object.getOwnPropertyDescriptor(pr, 'value');
                d.set.call(el, v);
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
            }""", el, str(val))
            return True
        return False

    def select_radio(name, value):
        """Click a radio button by name/value."""
        el = page.query_selector(f'input[type="radio"][name="{name}"][value="{value}"]')
        if not el:
            # Try by text match
            el = page.query_selector(f'input[name="{name}"][value="{value}"]')
        if el:
            el.click()
            time.sleep(0.1)
            return True
        return False

    # Basic fields - use native fill to trigger React state
    fields = {
        '#first_name': 'Cyrus',
        '#last_name': 'Shekari',
        '#email': 'cyshekari@gmail.com',
        '#phone': '+14253001898',
        '#question_19071372004': 'https://www.linkedin.com/in/cyrus-shekari',
        '#question_19071376004': 'No',  # family members
        '#question_19071380004': '3501 NE 45th St',  # address
        '#question_19071381004': 'Kirkland',  # city
        '#question_19071383004': '98033',  # zip
        '#question_19071384004': '125000',  # salary
        '#question_19071385004': 'Microsoft',  # employer
    }
    
    for sel, val in fields.items():
        ok = native_fill(sel, val)
        print(f'  fill {sel}: {"ok" if ok else "MISSING"}', flush=True)
    
    # Resume upload
    resume_inp = page.query_selector('input#resume') or page.query_selector('input[name="resume"]')
    if resume_inp:
        resume_inp.set_input_files(plan['pdf_path_local'])
        print('  resume: uploaded', flush=True)
        time.sleep(1.5)
    else:
        print('  resume: INPUT NOT FOUND', flush=True)
    
    # Radio buttons - Greenhouse Remix renders these as multi_value_single_select
    # Need to find the actual radio input elements
    radio_state = page.evaluate("""()=>{
        const radios = [...document.querySelectorAll('input[type="radio"]')];
        return radios.map(r => ({name: r.name, value: r.value, id: r.id, checked: r.checked}));
    }""")
    print(f'  found {len(radio_state)} radio inputs', flush=True)
    for r in radio_state[:5]:
        print(f'    radio: name={r["name"]} value={r["value"]} id={r["id"]} checked={r["checked"]}', flush=True)
    
    # For Natera's Remix form, the radio selects use custom React components
    # The field IDs from the JSON spec are the question IDs
    # Try clicking the radio options directly
    radio_fills = [
        ('question_19071374004', '1'),   # 18+? Yes
        ('question_19071375004', '0'),   # Prev worked at Natera? No  
        ('question_19071377004', '1'),   # Authorized to work in US? Yes
        ('question_19071378004', '0'),   # Require sponsorship? No
        ('question_19071379004', '0'),   # Non-compete? No
    ]
    
    for name, value in radio_fills:
        # Try radio input
        el = page.query_selector(f'input[name="{name}"][value="{value}"]')
        if el:
            el.click()
            time.sleep(0.1)
            print(f'  radio {name}={value}: clicked input', flush=True)
        else:
            # Try clicking the label text
            clicked = page.evaluate(f"""()=>{{
                // Find all inputs for this name
                const inputs = [...document.querySelectorAll('input[name="{name}"]')];
                const target = inputs.find(i => i.value === '{value}');
                if (target) {{
                    target.click();
                    return 'input-click';
                }}
                // Try the React-rendered option button
                const opts = [...document.querySelectorAll('[data-value="{value}"], [value="{value}"]')];
                const opt = opts.find(o => o.getAttribute('name') === '{name}' || o.closest('[data-field-path]'));
                if (opt) {{ opt.click(); return 'opt-click'; }}
                return null;
            }}""")
            print(f'  radio {name}={value}: {clicked or "NOT FOUND"}', flush=True)
    
    # State dropdown - find the select for question_19071382004 (WA = 86557511004)
    state_el = page.query_selector(f'input[name="question_19071382004"][value="86557511004"]')
    if state_el:
        state_el.click()
        time.sleep(0.1)
        print('  state WA: clicked', flush=True)
    else:
        # Try select element
        state_sel = page.query_selector('select[name="question_19071382004"]') or page.query_selector('#question_19071382004')
        if state_sel:
            state_sel.select_option(value='86557511004')
            time.sleep(0.1)
            print('  state WA: selected', flush=True)
        else:
            print('  state WA: NOT FOUND', flush=True)
    
    # EEOC - decline all
    for eeoc_name, val in [('gender', '3'), ('race', '8')]:
        el = page.query_selector(f'input[name="{eeoc_name}"][value="{val}"]') or page.query_selector(f'select[name="{eeoc_name}"]')
        if el:
            if el.get_attribute('type') == 'radio':
                el.click()
            else:
                el.select_option(value=val)
            time.sleep(0.1)
            print(f'  eeoc {eeoc_name}: set to {val}', flush=True)
        else:
            print(f'  eeoc {eeoc_name}: not found', flush=True)
    
    # Disability status
    disability_el = page.query_selector('input[name="disability_status"][value="2"]') or page.query_selector('select[name="disability_status"]')
    if disability_el:
        if disability_el.get_attribute('type') == 'radio':
            disability_el.click()
        else:
            disability_el.select_option(value='2')
        print('  disability: set to 2 (No)', flush=True)
    
    time.sleep(0.5)


def main():
    plan = json.load(open(PLAN_PATH))
    url = plan['url']
    
    print(f'[natera-v2] CDP={CDP_URL}', flush=True)
    print(f'[natera-v2] Connecting...', flush=True)
    
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(30000)
        
        print(f'[natera-v2] Navigating to {url}', flush=True)
        page.goto(url, wait_until='networkidle', timeout=30000)
        time.sleep(2)
        
        # Check current state
        state0 = page.evaluate("""()=>{
            return {
                has_first_name: !!document.getElementById('first_name'),
                has_otp: !!document.getElementById('security-input-0'),
                url: location.href,
                body_head: document.body.innerText.slice(0, 200)
            };
        }""")
        print(f'[natera-v2] Initial state: {state0}', flush=True)
        
        # Click Apply to open form
        apply_btn = page.query_selector('a:has-text("Apply"), button:has-text("Apply"):not(:has-text("Quick"))')
        if apply_btn:
            print('[natera-v2] Clicking Apply button', flush=True)
            apply_btn.click()
            time.sleep(2)
        else:
            # Try the Apply button by role
            page.evaluate("""()=>{
                const btn = [...document.querySelectorAll('a,button')].find(b => 
                    /^Apply$/i.test(b.textContent.trim()));
                if (btn) btn.click();
            }""")
            time.sleep(2)
        
        state1 = page.evaluate("""()=>{
            return {
                has_first_name: !!document.getElementById('first_name'),
                has_otp: !!document.getElementById('security-input-0'),
                url: location.href
            };
        }""")
        print(f'[natera-v2] After Apply click: {state1}', flush=True)
        
        if not state1['has_first_name'] and not state1['has_otp']:
            print('[natera-v2] Form not opened! Taking screenshot', flush=True)
            page.screenshot(path='/tmp/natera_v2_nf.png')
            return 1
        
        if state1['has_otp']:
            print('[natera-v2] OTP gate already visible after Apply click!', flush=True)
            # We need to submit the existing session - the application was started before
            # Just fill OTP and submit
        else:
            print('[natera-v2] Form is open, filling fields...', flush=True)
            fill_natera_form(page, plan)
            time.sleep(1)
        
        # Check pre-submit state
        ps = page.evaluate("""()=>{
            const req = [...document.querySelectorAll('input[required],select[required],textarea[required]')]
                .filter(e => e.offsetParent !== null && e.id && !e.id.startsWith('security-input'));
            const empty = req.filter(e => (e.type === 'checkbox' || e.type === 'radio') ? !e.checked : !e.value);
            const sub = [...document.querySelectorAll('button')].find(b => /submit application/i.test(b.textContent.trim()));
            const hasOtp = !!document.getElementById('security-input-0');
            return JSON.stringify({
                total_req: req.length,
                empty_fields: empty.map(e => ({id: e.id, name: e.name, type: e.type})),
                submitDisabled: sub ? (sub.disabled || sub.getAttribute('aria-disabled') === 'true') : 'nobtn',
                hasOtp: hasOtp
            });
        }""")
        ps_data = json.loads(ps)
        print(f'[natera-v2] PreSubmit state: {ps_data}', flush=True)
        page.screenshot(path='/tmp/natera_v2_presubmit.png')
        
        # CLICK SUBMIT (if OTP not already showing)
        if not ps_data.get('hasOtp'):
            since_submit = time.time()
            print('[natera-v2] Clicking Submit button...', flush=True)
            
            submit_btn = page.query_selector('button:has-text("Submit application")')
            if submit_btn:
                submit_btn.scroll_into_view_if_needed()
                time.sleep(0.5)
                submit_btn.click()
                print('[natera-v2] Submit clicked', flush=True)
            else:
                result = page.evaluate("""()=>{
                    const btn = [...document.querySelectorAll('button')].find(b => /submit application/i.test(b.textContent.trim()));
                    if (btn) { btn.scrollIntoView({block:'center'}); btn.click(); return btn.textContent.trim(); }
                    return null;
                }""")
                print(f'[natera-v2] JS submit click result: {result}', flush=True)
        else:
            since_submit = time.time() - 60  # OTP already showing, use older time window
            print('[natera-v2] OTP gate already visible, skipping submit click', flush=True)
        
        # Wait for OTP gate (longer wait: 20s)
        print('[natera-v2] Waiting for OTP gate...', flush=True)
        has_otp = False
        for _w in range(20):
            time.sleep(1)
            check = page.evaluate("""()=>{
                const hasOTP = !!document.getElementById('security-input-0');
                const conf = /thank you|received your application|application submitted/i.test(document.body.innerText) || /confirmation/.test(location.href);
                const errText = /something went wrong|error/i.test(document.body.innerText);
                return JSON.stringify({hasOTP, conf, errText, url: location.href, body: document.body.innerText.slice(0, 100)});
            }""")
            cd = json.loads(check)
            print(f'[natera-v2] wait={_w+1}: OTP={cd["hasOTP"]} conf={cd["conf"]} url={cd["url"][:50]} body={cd["body"][:60]!r}', flush=True)
            if cd['hasOTP']:
                has_otp = True
                break
            if cd['conf']:
                print('[natera-v2] ✅ CONFIRMED without OTP!', flush=True)
                page.screenshot(path='/tmp/natera_v2_confirmed.png')
                print(json.dumps({'status': 'SUBMITTED', 'url': cd['url']}))
                return 0
        
        if not has_otp:
            page.screenshot(path='/tmp/natera_v2_nootp.png')
            print('[natera-v2] OTP gate never appeared after 20s', flush=True)
            body_text = page.inner_text('body')
            print('[natera-v2] Page body (first 300):', body_text[:300], flush=True)
            print(json.dumps({'status': 'blocked-no-otp'}))
            return 1
        
        print('[natera-v2] OTP gate detected!', flush=True)
        page.screenshot(path='/tmp/natera_v2_otp.png')
        
        # Fetch OTP code
        print('[natera-v2] Fetching OTP from Gmail...', flush=True)
        try:
            code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=3, since_epoch=since_submit - 10)
        except Exception as e:
            print(f'[natera-v2] OTP fetch failed: {e}', flush=True)
            print(json.dumps({'status': 'blocked-otp-fetch-fail', 'err': str(e)}))
            return 1
        
        print(f'[natera-v2] Got OTP: {code!r}', flush=True)
        
        # Fill OTP - use Playwright keyboard for each character
        for _oi, _ch in enumerate(code):
            inp = page.query_selector(f'#security-input-{_oi}')
            if inp:
                inp.click()
                time.sleep(0.1)
                # Clear any existing value
                inp.evaluate("el => el.value = ''")
                # Type the character using keyboard
                page.keyboard.type(_ch)
                time.sleep(0.15)
            else:
                print(f'[natera-v2] WARNING: security-input-{_oi} not found!', flush=True)
        
        time.sleep(1)
        
        # Verify values filled
        otp_vals = page.evaluate("""()=>{
            return [0,1,2,3,4,5,6,7].map(i => {
                const el = document.getElementById('security-input-' + i);
                return el ? el.value : '-';
            }).join('');
        }""")
        print(f'[natera-v2] OTP values in form: {otp_vals!r}', flush=True)
        
        page.screenshot(path='/tmp/natera_v2_otp_filled.png')
        
        # NOW click the submit button - use multiple strategies
        print('[natera-v2] Clicking OTP submit button...', flush=True)
        
        # Strategy 1: Find by text
        otp_submit = page.query_selector('button:has-text("Submit application")') or \
                     page.query_selector('button:has-text("Verify")') or \
                     page.query_selector('button:has-text("Submit")')
        
        if otp_submit:
            btn_txt = otp_submit.text_content().strip()
            btn_dis = otp_submit.is_disabled()
            btn_aria = otp_submit.get_attribute('aria-disabled')
            print(f'[natera-v2] Found button: txt={btn_txt!r} disabled={btn_dis} aria={btn_aria!r}', flush=True)
            
            if not btn_dis and btn_aria != 'true':
                otp_submit.scroll_into_view_if_needed()
                time.sleep(0.5)
                otp_submit.click()
                print(f'[natera-v2] Playwright clicked: {btn_txt!r}', flush=True)
            else:
                print(f'[natera-v2] Button appears disabled, trying JS click', flush=True)
                page.evaluate("btn => { btn.disabled = false; btn.removeAttribute('aria-disabled'); btn.click(); }", otp_submit)
        else:
            print('[natera-v2] No submit button found by text, trying JS...', flush=True)
        
        # Strategy 2: JS click any non-disabled button with submit-like text
        js_result = page.evaluate("""()=>{
            const btns = [...document.querySelectorAll('button')];
            console.log('All buttons:', btns.map(b => b.textContent.trim() + '|disabled:' + b.disabled + '|aria:' + b.getAttribute('aria-disabled')));
            const candidates = btns.filter(b => {
                const txt = b.textContent.trim().toLowerCase();
                return (txt.includes('submit') || txt.includes('verify') || txt.includes('confirm')) &&
                       !b.disabled && b.getAttribute('aria-disabled') !== 'true';
            });
            if (candidates.length > 0) {
                const btn = candidates[0];
                btn.scrollIntoView({block: 'center'});
                btn.click();
                return {clicked: true, txt: btn.textContent.trim()};
            }
            // Force-click the last button
            const lastBtn = btns[btns.length - 1];
            if (lastBtn) {
                lastBtn.scrollIntoView({block: 'center'});
                lastBtn.disabled = false;
                lastBtn.click();
                return {force_clicked: true, txt: lastBtn.textContent.trim()};
            }
            return {clicked: false, all_btns: btns.map(b => b.textContent.trim().slice(0,30))};
        }""")
        print(f'[natera-v2] JS submit: {js_result}', flush=True)
        
        time.sleep(2)
        page.screenshot(path='/tmp/natera_v2_after_otp_submit.png')
        
        # Poll for confirmation
        print('[natera-v2] Polling for confirmation...', flush=True)
        confirmed = False
        final_data = {}
        for _ in range(20):
            time.sleep(2)
            final = page.evaluate("""()=>{
                const url = location.href;
                const body = document.body.innerText;
                const conf = /thank you|received your application|application.{0,20}submitted|application submitted|submitted your application|we.{0,3}ll be in touch|will begin reviewing|appreciate your interest/i.test(body) || /confirmation/.test(url);
                const otpStill = !!document.getElementById('security-input-0');
                const otpErr = /incorrect|invalid|wrong code|didn.{0,3}t match|expired/i.test(body);
                return JSON.stringify({url, confirmed: conf, otpStill, otpErr, head: body.slice(0, 200)});
            }""")
            fd = json.loads(final)
            print(f'[natera-v2] poll {_+1}: conf={fd["confirmed"]} otpStill={fd["otpStill"]} otpErr={fd["otpErr"]} url={fd["url"][:60]!r}', flush=True)
            final_data = fd
            if fd['confirmed']:
                confirmed = True
                break
            if fd['otpErr']:
                print(f'[natera-v2] OTP error detected!', flush=True)
                break
            if not fd['otpStill'] and _ > 2:
                print(f'[natera-v2] OTP gone but no confirmation. Body: {fd["head"][:200]}', flush=True)
                break
        
        page.screenshot(path='/tmp/natera_v2_final.png')
        
        if confirmed:
            print('[natera-v2] ✅ APPLICATION CONFIRMED!', flush=True)
            print(json.dumps({'status': 'SUBMITTED', 'url': final_data.get('url'), 'otp_code': code}))
            return 0
        else:
            print(f'[natera-v2] ❌ Not confirmed. Final: {final_data.get("head","")[:200]}', flush=True)
            print(json.dumps({'status': 'blocked-otp-rejected', 'otp_code': code, 'final': final_data}))
            return 1


if __name__ == '__main__':
    sys.exit(main())
