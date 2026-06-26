"""
Capture Natera form submit network request for analysis.
"""
import json, time, sys, os
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright

CDP_URL = os.environ.get('JOBSEARCH_CDP', 'http://127.0.0.1:18800')

requests_captured = []

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(30000)
    
    # Capture network requests
    def on_request(request):
        if 'greenhouse' in request.url and request.method == 'POST':
            print(f'[req] POST {request.url}', flush=True)
            try:
                post_data = request.post_data
                print(f'[req] post_data length: {len(post_data) if post_data else 0}', flush=True)
                if post_data and len(post_data) < 2000:
                    print(f'[req] post_data: {post_data[:500]}', flush=True)
            except Exception as e:
                print(f'[req] err: {e}', flush=True)
    
    def on_response(response):
        if 'greenhouse' in response.url and 'jobs' in response.url:
            print(f'[resp] {response.status} {response.url}', flush=True)
    
    page.on('request', on_request)
    page.on('response', on_response)
    
    # Navigate
    page.goto('https://job-boards.greenhouse.io/natera/jobs/6099223004', wait_until='domcontentloaded', timeout=30000)
    time.sleep(2)
    
    # Click Apply
    apply_btn = page.query_selector('a:has-text("Apply"), button:has-text("Apply")')
    if apply_btn:
        print('[nav] Clicking Apply', flush=True)
        apply_btn.click()
        time.sleep(2)
    
    # Fill basic fields
    def native_fill(sel, val):
        el = page.query_selector(sel)
        if el:
            page.evaluate("""(args) => {
                const [el, v] = args;
                const pr = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const d = Object.getOwnPropertyDescriptor(pr, 'value');
                d.set.call(el, v);
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
            }""", [el, str(val)])
            return True
        return False
    
    native_fill('#first_name', 'Cyrus')
    native_fill('#last_name', 'Shekari')
    native_fill('#email', 'cyshekari@gmail.com')
    native_fill('#phone', '+14253001898')
    native_fill('#question_19071372004', 'https://www.linkedin.com/in/cyrus-shekari')
    native_fill('#question_19071380004', '3501 NE 45th St')
    native_fill('#question_19071381004', 'Kirkland')
    native_fill('#question_19071383004', '98033')
    native_fill('#question_19071384004', '125000')
    native_fill('#question_19071385004', 'Microsoft')
    native_fill('#question_19071376004', 'No')
    
    # Resume
    plan = json.load(open('output/inline-plan-natera-6099223004.json'))
    resume_inp = page.query_selector('input#resume') or page.query_selector('input[name="resume"]')
    if resume_inp:
        resume_inp.set_input_files(plan['pdf_path_local'])
        time.sleep(1)
    
    # Click required radio/select fields
    # Use JS to find all inputs of type radio and click appropriately
    radio_result = page.evaluate("""()=>{
        const results = [];
        // Find all radio inputs
        const radios = [...document.querySelectorAll('input[type="radio"], input[type="checkbox"]')];
        for (const r of radios) {
            results.push({name: r.name, value: r.value, id: r.id, checked: r.checked, visible: r.offsetParent !== null});
        }
        return results;
    }""")
    print(f'[form] Found {len(radio_result)} radio/checkbox inputs:', flush=True)
    for r in radio_result:
        if r['visible']:
            print(f'  name={r["name"]!r} value={r["value"]!r} id={r["id"]!r} checked={r["checked"]}', flush=True)
    
    time.sleep(2)
    
    # Click submit to capture the network request
    print('[form] Clicking submit to capture network request', flush=True)
    submit_btn = page.query_selector('button:has-text("Submit application")')
    if submit_btn:
        submit_btn.scroll_into_view_if_needed()
        time.sleep(0.5)
        submit_btn.click()
    time.sleep(5)
    
    print('[form] Done capturing', flush=True)
    page.close()
