from playwright.sync_api import sync_playwright
import json, time, os, sys
sys.path.insert(0, '.')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')

# Load plan and get answers
plan = json.load(open('output/inline-plan-hex-5743880004.json'))
ANSWERS = {
    'question_17751712004': 'Yes',
    'question_17751713004': 'Yes',
}

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto('https://hex.tech/careers/sales-engineer-commercial-midmarket/?gh_jid=5743880004', wait_until='networkidle')
    time.sleep(3)
    
    # Get the iframe frame
    iframe_frame = None
    for frame in page.frames:
        if 'greenhouse.io' in frame.url:
            iframe_frame = frame
            break
    
    if not iframe_frame:
        print('ERROR: no iframe frame found')
        ctx.close()
        sys.exit(1)
    
    print('iframe URL:', iframe_frame.url[:80])
    
    # Check what's in the iframe
    result = iframe_frame.evaluate("""() => {
        const hasForm = !!document.getElementById('application-form');
        const inputs = [...document.querySelectorAll('input[id]')].slice(0,5).map(i => i.id);
        const hasSubmit = !!document.querySelector('button[type=submit]');
        return {hasForm, inputs, hasSubmit, url: location.href.slice(0,60)};
    }""")
    print('iframe contents:', json.dumps(result, indent=2))
    ctx.close()
