from playwright.sync_api import sync_playwright
import json, time, os, sys
sys.path.insert(0, '.')
os.chdir('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto('https://hex.tech/careers/sales-engineer-commercial-midmarket/?gh_jid=5743880004', wait_until='networkidle')
    time.sleep(3)
    # Get the iframe src
    iframe_src = page.evaluate("() => {const f=document.querySelector('iframe'); return f ? f.src : null;}")
    print('iframe_src:', iframe_src)
    # Now navigate to the iframe URL but with Referer from hex.tech
    if iframe_src and 'greenhouse' in iframe_src:
        # Get the frame
        frames = page.frames
        for frame in frames:
            print('frame url:', frame.url[:100])
    ctx.close()
