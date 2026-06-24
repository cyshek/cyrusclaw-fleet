import sys
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
import json

CDP = 'http://127.0.0.1:18800'
URL = 'https://jobs.lever.co/veeva/6bcc8228-5b43-43e5-b96b-d62679b8c64a/apply'

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.new_context()
    page = ctx.new_page()
    
    page.goto(URL, wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(3000)
    
    # Check what input IDs exist for hcaptcha
    inputs = page.evaluate("""() => {
        const inputs = [...document.querySelectorAll('input, textarea')];
        return inputs.map(i => ({name: i.name, id: i.id, type: i.type, value: (i.value||'').slice(0,30)})).slice(0, 30);
    }""")
    print("INPUTS:", json.dumps(inputs, indent=2))
    
    # Check hcaptcha state
    hcap = page.evaluate("""() => {
        const h = window.hcaptcha;
        if (!h) return {found: false};
        try {
            const r = h.getResponse();
            return {found: true, response: r, responseLen: (r||'').length};
        } catch(e) { return {found: true, err: String(e)}; }
    }""")
    print("HCAPTCHA STATE:", json.dumps(hcap))
    
    # Check if there's a hidden submit button
    btns = page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button, input[type=submit]')];
        return btns.map(b => ({tag: b.tagName, id: b.id, type: b.type, text: (b.textContent||b.value||'').slice(0,30), hidden: b.hidden || window.getComputedStyle(b).display === 'none'}));
    }""")
    print("BUTTONS:", json.dumps(btns, indent=2))
    
    ctx.close()
