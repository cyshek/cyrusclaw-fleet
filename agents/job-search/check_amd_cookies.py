#!/usr/bin/env python3
"""Check if AMD iCIMS session cookies exist in the CDP browser."""
import sys
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:\n+    b = p.chromium.connect_over_cdp('http://127.0.0.1:18800', timeout=5000)
    ctx = b.contexts[0] if b.contexts else None
    if ctx:\n+        cookies = ctx.cookies('https://careers-amd.icims.com')
        print(f'AMD iCIMS cookies: {len(cookies)}')
        for c in cookies[:10]:
            print(f'  {c["name"][:40]}: {str(c["value"])[:50]}...')
    else:
        print('No browser context')
