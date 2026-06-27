#!/usr/bin/env python3
"""Resume the saved MedZed application and answer the questions."""
import sys
sys.path.insert(0, 'role-discovery')
from _adp_wfn_runner import connect, dump, log, click_text, _wait_for_step, PERSONAL

pw, br = connect()
ctx = br.contexts[0]
page = None
for p in ctx.pages:
    try:
        if 'workforcenow' in p.url or 'adp.com' in p.url:
            page = p
            break
    except Exception:
        pass

if page is None:
    page = ctx.new_page()

print('[adp] URL:', page.url)

# Navigate to the postLogin URL directly (saved app context)
base_url = ("https://workforcenow.adp.com/mascsr/applicant/mdf/recruitment/postLogin.html"
            "?cid=b5c3b72a-0075-4173-a14d-5e44badc4c59&jobId=9202246249828_1&")
if 'postLogin' not in page.url:
    print('[adp] Navigating to postLogin URL...')
    page.goto(base_url, timeout=20000)
    page.wait_for_timeout(3000)

print('[adp] URL now:', page.url)
print('[adp] Headings:', [h.inner_text() for h in page.locator('h1,h2,h3,h4').all()])

# Find the "Application Saved for Later" button (may have different text)
btns_all = [b.inner_text().strip() for b in page.locator('button').all()]
print('[adp] All buttons:', btns_all[:20])

# Click button containing 'Saved for Later' or 'Application'
saved_btn = None
for txt in ['Application Saved for Later', 'Saved for Later', 'Complete Your Application', 'Continue Application']:
    try:
        b = page.locator(f'button:has-text("{txt}")').first
        if b.count() > 0:
            saved_btn = b
            print(f'[adp] Found button: {txt}')
            break
    except Exception:
        pass

if saved_btn:
    saved_btn.click(timeout=8000)
    page.wait_for_timeout(4000)
    print('[adp] Clicked, URL:', page.url)
    print('[adp] Headings:', [h.inner_text() for h in page.locator('h1,h2,h3,h4').all()])
    print('[adp] Buttons:', [b.inner_text().strip()[:60] for b in page.locator('button').all()[:15]])

# Navigate through wizard to questions
# Look for Next/Questions step
body = page.inner_text('body')[:3000]
print('[adp] Body:', body[:600])

# If on resume step, advance
if 'Resume' in body and 'Questions' in body:
    headings = [h.inner_text() for h in page.locator('h1,h2,h3,h4').all()]
    if any('Resume' in h or 'Attachment' in h for h in headings):
        print('[adp] On Resume step, clicking Next...')
        click_text(page, 'Next')
        page.wait_for_timeout(3000)

# Navigate to questions
headings = [h.inner_text() for h in page.locator('h1,h2,h3,h4').all()]
print('[adp] After nav headings:', headings)
body2 = page.inner_text('body')[:3000]
print('[adp] Body2:', body2[:600])

# Scan all select/input fields
all_inputs = page.evaluate("""
    () => {
        const res = [];
        document.querySelectorAll('input, select, [role=combobox]').forEach(el => {
            if (el.offsetParent !== null || el.type === 'hidden') {
                res.push({
                    tag: el.tagName,
                    id: el.id || '',
                    type: el.type || '',
                    aria_label: el.getAttribute('aria-label') || '',
                    required: !!(el.required || el.getAttribute('aria-required') === 'true'),
                    value: el.value ? el.value.slice(0, 40) : ''
                });
            }
        });
        return res;
    }
""")
for inp in all_inputs[:30]:
    print(f'  field: {inp}')

dump(page, 'questions-probe')
print('[adp] Done')
