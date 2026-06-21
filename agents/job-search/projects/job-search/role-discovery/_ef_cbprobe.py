import os, base64
from playwright.sync_api import sync_playwright
CDP_URL = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")
URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315472265"
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    page = browser.contexts[0].new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    try:
        page.evaluate("()=>{const s=document.getElementById('onetrust-consent-sdk'); if(s) s.remove();}")
    except Exception:
        pass
    # Inspect the genderIdentity group DOM: the 'I choose not to disclose' option structure
    info = page.evaluate("""() => {
        const gid = 'Self_ID_Questions_US_genderIdentity';
        const g = document.getElementById(gid);
        if (!g) return {err:'no group'};
        const out = {tag: g.tagName, role: g.getAttribute('role'), html_snippet: g.outerHTML.substring(0,600)};
        // find the 'I choose not to disclose' option
        const cbs = Array.from(g.querySelectorAll('input[type=checkbox]'));
        out.checkboxes = cbs.map(cb => ({id: cb.id, value: cb.value, checked: cb.checked, hidden: cb.offsetParent===null, hasLabel: !!document.querySelector('label[for="'+cb.id+'"]')}));
        return out;
    }""")
    import json
    print(json.dumps(info, indent=2)[:2500])
    page.close()
