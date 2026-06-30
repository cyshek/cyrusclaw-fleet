from playwright.sync_api import sync_playwright
import json, time, os, sys
sys.path.insert(0, '.')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto('https://job-boards.greenhouse.io/canonical/jobs/7490812', wait_until='networkidle')
    time.sleep(1)
    result = page.evaluate("""() => {
        const form = document.getElementById('application-form');
        if (!form) return {err: 'no form'};
        const allInputs = [...form.querySelectorAll('input,textarea,select')].map(i => ({
            id: i.id || i.name,
            type: i.type,
            required: i.required,
            val: i.value ? i.value.slice(0,20) : '',
            ariaReq: i.getAttribute('aria-required')
        })).filter(i => i.required || i.ariaReq === 'true');
        return {action: form.action, method: form.method, enctype: form.enctype, requiredInputs: allInputs.slice(0,10)};
    }""")
    print(json.dumps(result, indent=2))
    ctx.close()
