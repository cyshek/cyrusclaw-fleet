import sys
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = b.contexts[0] if b.contexts else None
    if ctx:
        all_ck = ctx.cookies()
        amd_ck = [c for c in all_ck if 'icims' in c.get('domain', '')]
        print('Total AMD iCIMS:', len(amd_ck))
        for c in sorted(amd_ck, key=lambda x: x['name']):
            n = c['name']; v = str(c['value'])
            print('  ' + n[:50] + ' = ' + v[:80])
