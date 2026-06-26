"""
Try to intercept Natera OTP form submission network requests.
This fills the form, triggers OTP, fills OTP, and captures network traffic.
"""
import json, time, sys, os
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright
import gmail_imap as g

CDP_URL = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:19223')

requests_log = []

def main():
    plan = json.load(open('output/inline-plan-natera-6099223004.json'))
    
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(30000)
        
        def on_request(req):
            if req.method in ('POST', 'PUT') and 'greenhouse' in req.url:
                print(f'[NET-REQ] {req.method} {req.url}', flush=True)
                try:
                    pd = req.post_data
                    if pd and len(pd) < 3000 and 'snowplow' not in req.url:
                        print(f'[NET-REQ] body: {pd[:500]}', flush=True)
                except:
                    pass
        
        def on_response(resp):
            if 'greenhouse' in resp.url and 'snowplow' not in resp.url:
                print(f'[NET-RESP] {resp.status} {resp.url}', flush=True)
                if resp.status >= 400:
                    try:
                        body = resp.body()
                        print(f'[NET-RESP] err body: {body[:300]}', flush=True)
                    except:
                        pass
        
        page.on('request', on_request)
        page.on('response', on_response)
        
        # Navigate and fill form (using existing _gh_submit approach)
        url = plan['url']
        SEL_PICK = open('_gh_submit.py').read().split('SEL_PICK = ')[1].split('\n')[0].strip('"')
        
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(1.5)
        
        # Click Apply
        page.evaluate("""() => { const b=[...document.querySelectorAll('button,a')].find(x=>/^apply/i.test((x.textContent||'').trim())); if(b)b.click(); }""")
        time.sleep(1.2)
        
        # Fill text fields
        text_fields = plan.get('text_fields', {})
        page.evaluate("""(fields)=>{const setN=(el,v)=>{const pr=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const d=Object.getOwnPropertyDescriptor(pr,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};const o={};for(const[id,val]of Object.entries(fields)){const el=document.getElementById(id);if(!el)continue;if(val===''||val==null)continue;setN(el,String(val));o[id]=String(el.value).slice(0,30);}return o;}""", text_fields)
        
        # Upload resume
        resume_inp = page.query_selector('input#resume')
        if resume_inp:
            resume_inp.set_input_files(plan['pdf_path_local'])
            time.sleep(1)
        
        # SEL_PICK dropdowns (reuse the actual JS)
        ghsubmit_src = open('_gh_submit.py').read()
        sel_pick_match = ghsubmit_src.find('SEL_PICK = """')
        if sel_pick_match >= 0:
            sel_pick_end = ghsubmit_src.find('"""', sel_pick_match + 14) + 3
            SEL_PICK_JS = ghsubmit_src[sel_pick_match+14:sel_pick_end-3]
        else:
            SEL_PICK_JS = None
        
        if SEL_PICK_JS:
            specs = [{'id': d['id'], 'label': d['label']} for d in plan.get('dropdowns', [])]
            if specs:
                result = page.evaluate(SEL_PICK_JS, specs)
                print('[SEL_PICK]', json.dumps(result), flush=True)
        
        time.sleep(1)
        
        # Click submit (initial)
        since_submit = time.time()
        print('[form] Clicking initial Submit...', flush=True)
        submit_btn = page.query_selector('button:has-text("Submit application")')
        if submit_btn:
            submit_btn.scroll_into_view_if_needed()
            time.sleep(0.5)
            submit_btn.click()
        else:
            page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));if(s){s.scrollIntoView();s.click();}}""")
        
        # Wait for OTP
        has_otp = False
        for _w in range(15):
            time.sleep(1)
            check = page.evaluate("""()=>{
                return {
                    hasOTP: !!document.getElementById('security-input-0'),
                    url: location.href
                };
            }""")
            print(f'[wait] {_w+1}: OTP={check["hasOTP"]}', flush=True)
            if check['hasOTP']:
                has_otp = True
                break
        
        if not has_otp:
            print('[form] No OTP gate appeared!', flush=True)
            return 1
        
        print('[form] OTP gate appeared, fetching code...', flush=True)
        code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=3, since_epoch=since_submit - 5)
        print(f'[form] OTP code: {code!r}', flush=True)
        
        # Fill OTP using keyboard
        for _oi, _ch in enumerate(code):
            inp = page.query_selector(f'#security-input-{_oi}')
            if inp:
                inp.click()
                time.sleep(0.1)
                page.keyboard.press('Control+a')
                page.keyboard.type(_ch)
                time.sleep(0.2)
        
        time.sleep(1)
        
        # Verify
        vals = page.evaluate("""()=>{return [0,1,2,3,4,5,6,7].map(i=>{const e=document.getElementById('security-input-'+i);return e?e.value:'-';}).join('');}""")
        print(f'[form] OTP vals in form: {vals!r}', flush=True)
        
        # Take screenshot
        page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_otp_before_submit.png')
        
        # Click submit with monitoring
        print('[form] Clicking OTP submit...', flush=True)
        btn = page.query_selector('button:has-text("Submit application")')
        if btn:
            btn_txt = btn.text_content()
            btn_disabled = btn.is_disabled()
            btn_aria = btn.get_attribute('aria-disabled')
            print(f'[form] Button: txt={btn_txt!r} disabled={btn_disabled} aria={btn_aria!r}', flush=True)
            
            # Click and wait longer
            btn.scroll_into_view_if_needed()
            time.sleep(0.5)
            btn.click()
            time.sleep(0.5)
            
            # Check immediately after click
            after_click = page.evaluate("""()=>{
                return {
                    hasOTP: !!document.getElementById('security-input-0'),
                    url: location.href,
                    body100: document.body.innerText.slice(0, 100)
                };
            }""")
            print(f'[form] Immediately after click: {after_click}', flush=True)
            
            page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_otp_after_click.png')
        
        # Wait and poll
        for _ in range(15):
            time.sleep(2)
            state = page.evaluate("""()=>{
                return {
                    hasOTP: !!document.getElementById('security-input-0'),
                    url: location.href,
                    confirmed: /thank you|received your application/i.test(document.body.innerText),
                    error: /incorrect|invalid|wrong|expired/i.test(document.body.innerText),
                    body: document.body.innerText.slice(0, 200)
                };
            }""")
            print(f'[poll] {_+1}: OTP={state["hasOTP"]} conf={state["confirmed"]} err={state["error"]}', flush=True)
            if state['confirmed']:
                print('[form] ✅ SUBMITTED!', flush=True)
                page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_confirmed.png')
                return 0
            if state['error']:
                print(f'[form] OTP Error: {state["body"][:200]}', flush=True)
                break
            if not state['hasOTP'] and _ > 2:
                print(f'[form] OTP gone, no confirmation. Body: {state["body"][:200]}', flush=True)
                break
        
        page.screenshot(path='/home/azureuser/.openclaw/agents/job-search/workspace/natera_final_state.png')
        print('[form] Final state captured', flush=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
