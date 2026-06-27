#!/usr/bin/env python3
"""Resume the saved MedZed application, answer questions, and submit."""
import sys
sys.path.insert(0, 'role-discovery')
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:18800"
ADP_TARGET_ID = "F5EB1EE38DF4D5952E7B26419D261846"

from _adp_wfn_runner import PERSONAL, log, click_text

def click_btn(page, text, timeout=8000):
    loc = page.locator(f'button:has-text("{text}")').first
    if loc.count() > 0:
        loc.click(timeout=timeout)
        page.wait_for_timeout(2000)
        return True
    return False

def get_state(page):
    headings = [h.inner_text().strip() for h in page.locator('h1,h2,h3,h4').all()]
    btns = [b.inner_text().strip()[:60] for b in page.locator('button').all()[:15]]
    body = page.inner_text('body')[:500]
    return headings, btns, body

pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP_URL)
ctx = br.contexts[0]

page = None
for p in ctx.pages:
    try:
        if 'workforcenow' in p.url:
            page = p
            break
    except Exception:
        pass

if page is None:
    print('[adp] ERROR: No ADP page found')
    sys.exit(1)

print('[adp] URL:', page.url)
page.bring_to_front()
page.wait_for_timeout(1500)

headings, btns, body = get_state(page)
print('[adp] Headings:', headings)
print('[adp] Buttons:', btns)

# Step 1: Click the saved application tile to resume it
print('[adp] Clicking saved app tile...')
tile = page.locator('#myAppsSavedForLaterItemLink_0').first
if tile.count() > 0:
    tile.click(timeout=8000)
    page.wait_for_timeout(4000)
    print('[adp] Clicked tile, URL:', page.url)
    headings, btns, body = get_state(page)
    print('[adp] Headings:', headings)
    print('[adp] Buttons:', btns)
    print('[adp] Body:', body[:400])
else:
    print('[adp] Tile not found, trying button...')
    for btn_text in ['Application Saved for Later', 'Complete Your Application', 'Continue']:
        if click_btn(page, btn_text):
            print(f'[adp] Clicked: {btn_text}')
            break
    headings, btns, body = get_state(page)
    print('[adp] Headings:', headings)
    print('[adp] Buttons:', btns)

# Step 2: Check if we need to click "Complete Your Application"
page.wait_for_timeout(1000)
body = page.inner_text('body')[:1000]
if 'Complete Your Application' in body:
    print('[adp] Found Complete Your Application, clicking...')
    click_btn(page, 'Complete Your Application')
    page.wait_for_timeout(3000)
    headings, btns, body = get_state(page)
    print('[adp] After CYA - Headings:', headings)
    print('[adp] After CYA - Buttons:', btns)

# Step 3: Navigate to Questions step (may be on Resume step first)
body = page.inner_text('body')[:3000]
headings = [h.inner_text().strip() for h in page.locator('h1,h2,h3,h4').all()]
print('[adp] State - headings:', headings)

if any('Resume' in h or 'Attachment' in h for h in headings) and 'Resume' in body:
    print('[adp] On Resume step, clicking Next...')
    click_btn(page, 'Next')
    page.wait_for_timeout(3000)
    headings, btns, body = get_state(page)
    print('[adp] After Resume Next - Headings:', headings)

# Step 4: We should be on Questions step now
body = page.inner_text('body')[:3000]
print('[adp] Body:', body[:800])

# Find all select dropdowns (ADP uses sdf-select pattern: <ul> with li[role=option])
# Also look for button-based radio answers (common in ADP)
print('[adp] Scanning for ADP question fields...')
fields_info = page.evaluate("""
    () => {
        const res = [];
        // ADP questions are typically in a form-group pattern
        document.querySelectorAll('[class*="question"], [class*="sdf-select"], [data-sdf-type]').forEach(el => {
            const txt = el.textContent.trim().slice(0, 150);
            res.push({
                tag: el.tagName,
                id: el.id || '',
                class: el.className.slice(0, 80),
                type: el.getAttribute('data-sdf-type') || el.getAttribute('type') || '',
                text: txt
            });
        });
        // Also get button elements that look like Yes/No answers
        document.querySelectorAll('[class*="answer"], [class*="option"], button[value]').forEach(el => {
            const txt = el.textContent.trim().slice(0, 60);
            if (txt) {
                res.push({
                    tag: el.tagName,
                    id: el.id || '',
                    class: el.className.slice(0, 80),
                    type: el.getAttribute('type') || '',
                    text: txt,
                    value: el.value || el.getAttribute('data-value') || ''
                });
            }
        });
        return res;
    }
""")
print('[adp] Fields found:', len(fields_info))
for f in fields_info[:20]:
    print(' ', f)

# Deep scan: get ALL inputs and selects
all_inputs = page.evaluate("""
    () => {
        const res = [];
        document.querySelectorAll('input, select, textarea, [role=combobox], [role=option], [role=listbox], [role=radio], [role=checkbox]').forEach(el => {
            if (el.offsetHeight > 0 || el.type === 'hidden') {
                res.push({
                    tag: el.tagName,
                    id: el.id || '',
                    name: el.name || '',
                    type: el.type || el.getAttribute('role') || '',
                    aria: el.getAttribute('aria-label') || '',
                    required: !!(el.required || el.getAttribute('aria-required') === 'true'),
                    value: el.value ? el.value.slice(0, 60) : '',
                    text: el.textContent ? el.textContent.trim().slice(0, 60) : ''
                });
            }
        });
        return res;
    }
""")
print('[adp] All inputs:')
for inp in all_inputs[:30]:
    print(' ', inp)

print('[adp] Probe complete')
