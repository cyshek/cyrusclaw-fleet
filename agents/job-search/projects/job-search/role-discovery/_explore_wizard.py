"""Explore wizard steps by clicking Next through all steps."""
import os
import re
os.environ['JOBSEARCH_CDP'] = 'http://127.0.0.1:18800'
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log
from pathlib import Path

debug_dir = Path('../.sf-debug')
debug_dir.mkdir(exist_ok=True)

JS_CLICK_UI5 = """(text) => {
    for (const tagName of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
        for (const el of document.querySelectorAll(tagName)) {
            const t = (el.textContent || el.innerText || '').trim();
            if (t === text) { el.click(); return 'clicked:' + tagName; }
        }
    }
    return null;
}"""

JS_ALL_UI5 = """() => {
    const r = [];
    for (const t of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
        for (const el of document.querySelectorAll(t)) {
            const txt = (el.textContent||el.innerText||'').trim();
            if (txt) r.push({tag: t.substring(0,15), text: txt});
        }
    }
    return r;
}"""

JS_FIELDS = """() => {
    return [...document.querySelectorAll('input:not([type=hidden]), select, textarea')]
        .filter(e => e.getBoundingClientRect().height > 0)
        .map(e => ({n: e.name||'', id: (e.id||'').substring(0,40), t: e.type||e.tagName}));
}"""


def wait_content(page, max_secs=30):
    for _ in range(max_secs * 2):
        body = page.evaluate('() => document.body.innerText.toLowerCase()')
        stripped = re.sub(r'[\s\xa0]+', '', body)
        if len(stripped) > 100:
            return body
        page.wait_for_timeout(500)
    return page.evaluate('() => document.body.innerText.toLowerCase()')


pw, browser, ctx, page = _get_page()
try:
    ctx.clear_cookies()
    _log('Cleared all cookies')

    url = sf_job_save_url('career8.successfactors.com', 'aosmith', '27523')
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    _screenshot(page, 'wz_01_signin', debug_dir)

    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    _log(f'Landing: {body[:100]!r}')

    # Fill credentials using native setter
    email = 'cyshekari+aosmith2280@gmail.com'
    pwd = 'Cyrus2026!Apply'
    page.evaluate("""([e, p]) => {
        const ef = document.querySelector('input[name=username],input[type=email],input[name=Email]');
        const pf = document.querySelector('input[type=password]');
        const setVal = (el, v) => {
            const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            if (d && d.set) d.set.call(el, v);
            else el.value = v;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
        };
        if (ef) setVal(ef, e);
        if (pf) setVal(pf, p);
        return {email: !!ef, pwd: !!pf};
    }""", [email, pwd])
    page.wait_for_timeout(500)

    page.evaluate("""() => {
        for (const btn of document.querySelectorAll('button,input[type=submit]')) {
            const t = (btn.innerText||btn.value||'').trim();
            if (/^sign in$/i.test(t)) { btn.click(); return; }
        }
        const form = document.querySelector('form[name=careerform],form');
        if (form) form.submit();
    }""")
    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(5000)
    _screenshot(page, 'wz_02_post_signin', debug_dir)

    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    _log(f'Post-signin URL: {page.url}')
    _log(f'Post-signin body: {body[:200]!r}')

    on_form = 'getting started' in body
    on_listing = 'apply save job' in body or 'return to list' in body
    _log(f'on_form={on_form} on_listing={on_listing}')

    if on_listing and not on_form:
        _log('On listing, clicking Apply...')
        r = page.evaluate("""() => {
            const b = document.getElementById('applyButton_top');
            if (b) { b.click(); return 'applyButton_top'; }
            for (const a of document.querySelectorAll('a')) {
                if ((a.innerText||'').trim().toLowerCase() === 'apply') {
                    a.click(); return 'a:apply href=' + a.href.substring(0,60);
                }
            }
            return null;
        }""")
        _log(f'Apply click: {r}')
        page.wait_for_timeout(6000)
        _screenshot(page, 'wz_03_after_apply', debug_dir)
        body = page.evaluate('() => document.body.innerText.toLowerCase()')
        _log(f'After apply URL: {page.url[:120]}')
        _log(f'After apply body: {body[:300]!r}')
        on_form = 'getting started' in body
        _log(f'on_form after apply click: {on_form}')

    if not on_form:
        _log('FAILED: not on apply form after all attempts')
    else:
        _log('SUCCESS: on apply form')
        # Enumerate wizard steps
        for step in range(1, 6):
            _screenshot(page, f'wz_s{step}', debug_dir)
            body = page.evaluate('() => document.body.innerText.toLowerCase()')
            ui5 = page.evaluate(JS_ALL_UI5)
            fields = page.evaluate(JS_FIELDS)
            has_fbqa = page.evaluate("() => !!document.querySelector('#fbqa_apply')")
            _log(f'=== STEP {step} ===')
            _log(f'  URL: {page.url[-80:]}')
            _log(f'  body: {body[:500]!r}')
            _log(f'  UI5: {ui5}')
            _log(f'  fields: {fields}')
            _log(f'  has_fbqa_apply: {has_fbqa}')
            if has_fbqa:
                _log('  >>> Submit button found! Stopping.')
                break
            r = page.evaluate(JS_CLICK_UI5, 'Next')
            _log(f'  Next click: {r}')
            if not r:
                _log('  No Next button.')
                r2 = page.evaluate(JS_CLICK_UI5, 'Submit Application')
                r3 = page.evaluate(JS_CLICK_UI5, 'Apply')
                _log(f'  Submit={r2}, Apply={r3}')
                break
            body2 = wait_content(page, 30)
            _log(f'  After Next body[100]: {body2[:100]!r}')

finally:
    page.close()
    pw.stop()
    _log('Done')
