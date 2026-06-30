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
    iframe_src = page.evaluate("() => {const f=document.querySelector('iframe[src*=greenhouse]'); return f ? f.src : null;}")
    print(iframe_src)
    ctx.close()
