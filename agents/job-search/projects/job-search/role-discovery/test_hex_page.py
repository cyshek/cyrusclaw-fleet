from playwright.sync_api import sync_playwright
import json, time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto('https://hex.tech/careers/sales-engineer-commercial-midmarket/?gh_jid=5743880004', wait_until='networkidle')
    time.sleep(2)
    result = page.evaluate("""() => {
        const iframes = [...document.querySelectorAll('iframe')].map(f => f.src.slice(0,100));
        const form = document.querySelector('form');
        const hasGH = document.body.innerHTML.includes('greenhouse');
        const firstInputs = [...document.querySelectorAll('input')].slice(0,5).map(i => ({id: i.id, name: i.name, type: i.type}));
        return {url: location.href, iframes, hasForm: !!form, hasGH, inputs: firstInputs};
    }""")
    print(json.dumps(result, indent=2))
    ctx.close()
