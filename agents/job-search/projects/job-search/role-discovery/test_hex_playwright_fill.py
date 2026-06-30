from playwright.sync_api import sync_playwright
import json, time, os, sys
sys.path.insert(0, '.')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    
    posts = []
    def on_resp(r):
        if r.request.method == 'POST' and 'greenhouse' in r.url:
            posts.append({'url': r.url[:100], 'status': r.status})
    page.on('response', on_resp)
    
    EMBED_URL = 'https://job-boards.greenhouse.io/embed/job_app?for=hextechnologies&validityToken=n7iAFKlkaoGOVdHrT6tFgtXSheIk8NOB-hpnZe92CoLOYldDIDgj6-LqvO0KN65-XolxFo2Zifss-x1L0SwI5DSjilJDvt1RTbXv2xnmeF8FZj-WHw8XEOKt2Cncgj2q5sAyEJjIz95a3g4Q9Jge-ti3GIB6tGcJZ4GsMoAyrThLRS6-YFeaW58aolgDAdPZInitJejXs3V880pMx54pJ3iDniOGN4ZLxg2j-kY8XF2eX6HnIBsrMXzqTGLEQFzWCw5lDEmyNgZvEJX-8k8Mt4KvqbaKGQgfTafw8J3BmygJYComRfm7GEFJ1omn8DDdhOBX7ZyBWEe13DTYQJ5EGA%3D%3D&token=5743880004'
    page.goto(EMBED_URL, wait_until='networkidle')
    time.sleep(2)
    
    # Use Playwright fill() for text inputs
    page.fill('#first_name', 'Cyrus')
    page.fill('#last_name', 'Shekari')
    page.fill('#email', 'cyshekari@gmail.com')
    time.sleep(0.5)
    
    # Check state
    state = page.evaluate("""() => {
        const fn = document.getElementById('first_name');
        const ln = document.getElementById('last_name');
        return {fn: fn.value, ln: ln.value};
    }""")
    print('state:', json.dumps(state))
    
    # Click submit
    btn = page.query_selector('button[type=submit]')
    if btn:
        btn.scroll_into_view_if_needed()
        btn.click()
        time.sleep(5)
    
    print('posts:', json.dumps(posts))
    print('url:', page.url[:100])
    ctx.close()
