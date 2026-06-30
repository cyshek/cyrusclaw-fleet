from playwright.sync_api import sync_playwright
from captcha_presubmit import solve_and_inject_recaptcha_v3
import json, os, time, sys

sys.path.insert(0, '.')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')

# Load the plan
import json as _json
plan = _json.load(open('output/inline-plan-canonical-7490812.json'))

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    
    posts_to_boards = []
    def on_response(r):
        if 'boards.greenhouse.io' in r.url and r.request.method == 'POST':
            posts_to_boards.append({'url': r.url, 'status': r.status})
        elif 'canonical/jobs' in r.url:
            posts_to_boards.append({'url': r.url, 'status': r.status, 'method': r.request.method})
    page.on('response', on_response)
    
    page.goto('https://job-boards.greenhouse.io/canonical/jobs/7490812', wait_until='networkidle')
    time.sleep(2)
    
    # Fill just the required fields by ID using the runner JS technique
    page.evaluate("""(data) => {
        function setNative(el, val) {
            const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');
            if (d && d.set) d.set.call(el, val);
            else el.value = val;
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        }
        setNative(document.getElementById('first_name'), data.first_name);
        setNative(document.getElementById('last_name'), data.last_name);
        setNative(document.getElementById('email'), data.email);
    }""", {'first_name': 'Cyrus', 'last_name': 'Shekari', 'email': 'cyshekari@gmail.com'})
    time.sleep(0.5)
    
    # Solve reCAPTCHA
    cap = solve_and_inject_recaptcha_v3(page, fallback_sitekey='6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0', action='job_apply', page_url='https://job-boards.greenhouse.io/canonical/jobs/7490812')
    print('captcha:', cap.get('enabled'), cap.get('injected'), cap.get('token_len'))
    time.sleep(1)
    
    # Click submit
    btn = page.query_selector('button[type=submit]')
    if btn:
        btn.scroll_into_view_if_needed()
        btn.click()
        print('clicked submit')
    time.sleep(5)
    
    print('posts to boards/canonical:', posts_to_boards)
    print('final url:', page.url)
    
    ctx.close()
