from playwright.sync_api import sync_playwright
import time

with sync_playwright() as pw:
    br = pw.chromium.connect_over_cdp('http://127.0.0.1:18800')
    ctx = br.contexts[0] if br.contexts else br.new_context()
    natera_pages = [p for p in ctx.pages if 'natera' in p.url]
    print(f'Closing {len(natera_pages)} stale Natera pages...')
    for p in natera_pages:
        try:
            print(f'  Closing: {p.url[:60]}')
            p.close()
        except Exception as e:
            print(f'  Error: {e}')
    time.sleep(1)
    remaining = [p for p in ctx.pages if 'natera' in p.url]
    print(f'Remaining Natera pages: {len(remaining)}')
    print('All pages:', [p.url[:50] for p in ctx.pages])
