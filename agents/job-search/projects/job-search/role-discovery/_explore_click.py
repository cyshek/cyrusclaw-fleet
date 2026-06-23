"""Watch what happens after clicking applyButton_top."""
import os, time
os.environ['JOBSEARCH_CDP'] = 'http://127.0.0.1:18800'
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log
from pathlib import Path

debug_dir = Path('../.sf-debug')
pw, browser, ctx, page = _get_page()
try:
    ctx.clear_cookies()
    url = sf_job_save_url('career8.successfactors.com', 'aosmith', '27523')
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)

    email = 'cyshekari+aosmith2280@gmail.com'
    pwd = 'Cyrus2026!Apply'
    page.evaluate("""([e, p]) => {
        const setVal = (el, v) => {
            const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            if (d && d.set) d.set.call(el, v);
            el.dispatchEvent(new Event('input', {bubbles:true}));
        };
        const ef = document.querySelector('input[name=username],input[type=email],input[name=Email]');
        const pf = document.querySelector('input[type=password]');
        if (ef) setVal(ef, e);
        if (pf) setVal(pf, p);
    }""", [email, pwd])
    page.wait_for_timeout(300)
    page.evaluate("""() => {
        for (const btn of document.querySelectorAll('button,input[type=submit]')) {
            if (/^sign in$/i.test((btn.innerText||btn.value||'').trim())) { btn.click(); return; }
        }
        const f = document.querySelector('form'); if (f) f.submit();
    }""")
    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except: pass
    page.wait_for_timeout(5000)

    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    _log(f'Pre-click URL: {page.url[:100]}')
    on_listing = 'apply save job' in body
    _log(f'on_listing: {on_listing}')

    if on_listing:
        # Click applyButton_top
        page.evaluate("() => document.getElementById('applyButton_top').click()")
        _log('Clicked applyButton_top')

        # Poll every 1s for 30s
        for i in range(30):
            time.sleep(1)
            body = page.evaluate('() => document.body.innerText.toLowerCase()')
            url_now = page.url
            on_form = 'getting started' in body
            _log(f't+{i+1}s: url={url_now[-60:]} on_form={on_form} body[50]={body[:50]!r}')
            if on_form:
                _log('SUCCESS: form appeared!')
                break
        else:
            _screenshot(page, 'click_result', debug_dir)
            # Check for any dialogs or popups
            dialogs = page.evaluate("""() => {
                const d = document.querySelectorAll('[role=dialog],.ui-dialog,.modal');
                return [...d].map(e => e.innerText.trim().substring(0, 100));
            }""")
            _log(f'Dialogs: {dialogs}')
            # Check for any new content
            body_full = page.evaluate('() => document.body.innerText')
            _log(f'Full body (500): {body_full[:500]!r}')

finally:
    page.close()
    pw.stop()
    _log('Done')
