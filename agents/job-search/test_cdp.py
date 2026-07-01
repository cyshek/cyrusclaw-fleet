#!/usr/bin/env python3
"""Quick test to find which CDP endpoint works."""
from playwright.sync_api import sync_playwright

for cdp in ['http://127.0.0.1:18800', 'http://[::1]:18900']:
    try:
        with sync_playwright() as p:\n+            b = p.chromium.connect_over_cdp(cdp, timeout=5000)\n+            nctx = len(b.contexts)\n+            npg = len(b.contexts[0].pages) if b.contexts else 0
            print(f'{cdp}: OK - {nctx} ctx, {npg} pages')
            b.close()
    except Exception as e:\n+        print(f'{cdp}: FAIL - {str(e)[:80]}')
