import sys
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = b.contexts[0] if b.contexts else None
    if ctx:
        all_ck = ctx.cookies()
        for c in all_ck:
            n = c['name']
            v = c['value']
            if 'icims' in c.get('domain','') and 'login' in n.lower():
                print('NAME:', n)
                print('VALUE:', v[:200])
                print()
