from playwright.sync_api import sync_playwright
from captcha_presubmit import solve_and_inject_recaptcha_v3
import json, os, time, sys

sys.path.insert(0, '.')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    reqs = []
    page.on('response', lambda r: reqs.append({'url': r.url, 'status': r.status}))
    page.goto('https://job-boards.greenhouse.io/canonical/jobs/7490812', wait_until='networkidle')
    time.sleep(1)
    # Check recaptcha
    rc_info = page.evaluate("""() => {
        const ta = document.getElementById('g-recaptcha-response-100000');
        const scripts = [...document.scripts].filter(s => /recaptcha/.test(s.src)).map(s => s.src.slice(0,80));
        const grecap = typeof window.grecaptcha !== 'undefined';
        return {ta_exists: !!ta, ta_val: ta ? ta.value.slice(0,20) : null, scripts, grecap};
    }""")
    print('recaptcha info:', json.dumps(rc_info))
    # Try to solve
    cap_result = solve_and_inject_recaptcha_v3(page, fallback_sitekey='6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0', action='job_apply', page_url='https://job-boards.greenhouse.io/canonical/jobs/7490812')
    print('captcha result:', json.dumps(cap_result))
    # Check recaptcha after
    ta_val = page.evaluate("() => {const ta=document.getElementById('g-recaptcha-response-100000'); return ta ? ta.value.slice(0,30) : null;}")
    print('token after inject:', ta_val)
    ctx.close()
