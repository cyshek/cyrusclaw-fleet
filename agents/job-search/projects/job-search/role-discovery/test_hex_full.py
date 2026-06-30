from playwright.sync_api import sync_playwright
from captcha_presubmit import solve_and_inject_recaptcha_v3
import json, time, os, sys
sys.path.insert(0, '.')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    
    all_reqs = []
    def on_req(r):
        all_reqs.append({'url': r.url[:80], 'method': r.method})
    page.on('request', on_req)
    
    EMBED_URL = 'https://job-boards.greenhouse.io/embed/job_app?for=hextechnologies&validityToken=n7iAFKlkaoGOVdHrT6tFgtXSheIk8NOB-hpnZe92CoLOYldDIDgj6-LqvO0KN65-XolxFo2Zifss-x1L0SwI5DSjilJDvt1RTbXv2xnmeF8FZj-WHw8XEOKt2Cncgj2q5sAyEJjIz95a3g4Q9Jge-ti3GIB6tGcJZ4GsMoAyrThLRS6-YFeaW58aolgDAdPZInitJejXs3V880pMx54pJ3iDniOGN4ZLxg2j-kY8XF2eX6HnIBsrMXzqTGLEQFzWCw5lDEmyNgZvEJX-8k8Mt4KvqbaKGQgfTafw8J3BmygJYComRfm7GEFJ1omn8DDdhOBX7ZyBWEe13DTYQJ5EGA%3D%3D&token=5743880004'
    page.goto(EMBED_URL, wait_until='networkidle')
    time.sleep(2)
    
    # Fill all required fields with Playwright fill()
    page.fill('#first_name', 'Cyrus')
    page.fill('#last_name', 'Shekari')
    page.fill('#email', 'cyshekari@gmail.com')
    time.sleep(0.3)
    
    # Upload resume
    file_input = page.query_selector('input#resume')
    if file_input:
        file_input.set_input_files('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/hex-5743880004/Cyrus_Shekari_Resume_hextechnologies_5743880004_v2.pdf')
        time.sleep(3)
    
    # Solve recaptcha
    cap = solve_and_inject_recaptcha_v3(page, fallback_sitekey='6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0', action='job_apply', page_url=EMBED_URL)
    print('captcha:', cap.get('injected'))
    time.sleep(1)
    
    # Check state BEFORE submit
    state = page.evaluate("""() => {
        const req = [...document.querySelectorAll('[aria-required=\"true\"]')].map(e => ({id: e.id||e.name, val: (e.value||"").slice(0,20)}));
        const sub = document.querySelector('button[type=submit]');
        return {required: req.filter(e => !e.val), submitDisabled: sub ? sub.disabled : 'nobtn'};
    }""")
    print('state before submit:', json.dumps(state))
    
    # Click submit
    btn = page.query_selector('button[type=submit]')
    if btn:
        btn.scroll_into_view_if_needed()
        btn.click()
        time.sleep(8)
    
    print('posts after:', [r for r in all_reqs if r['method'] == 'POST'])
    print('final url:', page.url[:100])
    body = page.evaluate('() => document.body.innerText.slice(0,200)')
    print('body:', body)
    ctx.close()
