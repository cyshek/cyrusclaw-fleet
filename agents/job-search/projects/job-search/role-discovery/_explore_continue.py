"""Click Continue on Saved Applications dialog, then navigate wizard."""
import os, re
os.environ['JOBSEARCH_CDP'] = 'http://127.0.0.1:18800'
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log
from pathlib import Path

debug_dir = Path('../.sf-debug')

JS_CLICK_UI5 = """(text) => {
    for (const tagName of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
        for (const el of document.querySelectorAll(tagName)) {
            const t = (el.textContent||el.innerText||'').trim();
            if (t === text) { el.click(); return 'clicked:' + tagName + ':' + t; }
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

def wait_content(page, max_secs=30):
    for _ in range(max_secs * 2):
        body = page.evaluate('() => document.body.innerText.toLowerCase()')
        stripped = re.sub(r'[\s\xa0]+', '', body)
        if len(stripped) > 100:
            return body
        page.wait_for_timeout(500)
    return page.evaluate('() => document.body.innerText.toLowerCase()')

def click_continue_dialog(page):
    """Click 'Continue' on Saved Applications dialog if present."""
    return page.evaluate("""() => {
        for (const btn of document.querySelectorAll('[role=dialog] button, [role=dialog] a, .ui-dialog button')) {
            const t = (btn.innerText||btn.textContent||btn.value||'').trim().toLowerCase();
            if (t === 'continue' || t === 'yes' || t === 'proceed') {
                btn.click();
                return 'clicked Continue: ' + btn.outerHTML.substring(0,100);
            }
        }
        return null;
    }""")

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
    on_listing = 'apply save job' in body
    _log(f'on_listing={on_listing}')

    if on_listing:
        page.evaluate("() => document.getElementById('applyButton_top').click()")
        _log('Clicked applyButton_top')
        page.wait_for_timeout(4000)

        # Check for dialog
        dialogs = page.evaluate("""() => {
            return [...document.querySelectorAll('[role=dialog],.ui-dialog')]
                .filter(d => {
                    const r = d.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                })
                .map(d => d.innerText.trim().substring(0,200));
        }""")
        _log(f'Dialogs found: {dialogs}')
        _screenshot(page, 'cont_01_after_apply_click', debug_dir)

        # Click Continue
        r = click_continue_dialog(page)
        _log(f'Continue click: {r}')
        page.wait_for_timeout(8000)
        _screenshot(page, 'cont_02_after_continue', debug_dir)

        body = page.evaluate('() => document.body.innerText.toLowerCase()')
        _log(f'After continue URL: {page.url[:120]}')
        _log(f'After continue body: {body[:400]!r}')
        on_form = 'getting started' in body or 'profile information' in body
        _log(f'on_form: {on_form}')

        if on_form:
            _log('SUCCESS: on apply form after Continue click')
            ui5 = page.evaluate(JS_ALL_UI5)
            _log(f'UI5 buttons: {ui5}')

            # Click Next through steps
            for step in range(1, 6):
                has_fbqa = page.evaluate("() => !!document.querySelector('#fbqa_apply')")
                if has_fbqa:
                    _log(f'Step {step}: has #fbqa_apply - DONE')
                    break
                _screenshot(page, f'cont_s{step}', debug_dir)
                body = page.evaluate('() => document.body.innerText.toLowerCase()')
                ui5 = page.evaluate(JS_ALL_UI5)
                fields = page.evaluate("() => [...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(e=>e.getBoundingClientRect().height>0).map(e=>({n:e.name||'',t:e.type||e.tagName}))")
                _log(f'Step {step}: body={body[:200]!r}')
                _log(f'Step {step}: UI5={ui5}')
                _log(f'Step {step}: fields={fields}')
                r = page.evaluate(JS_CLICK_UI5, 'Next')
                _log(f'Step {step}: Next={r}')
                if not r:
                    break
                body = wait_content(page, 30)
                _log(f'After Next body[100]: {body[:100]!r}')

finally:
    page.close()
    pw.stop()
    _log('Done')
