import os
os.environ['JOBSEARCH_CDP'] = 'http://127.0.0.1:18800'
from _successfactors_runner import _get_page, sf_job_save_url, sign_in, _screenshot, _log
from pathlib import Path

debug_dir = Path('../.sf-debug')
debug_dir.mkdir(exist_ok=True)

JS_CLICK_UI5 = """(text) => {
    for (const tagName of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
        for (const el of document.querySelectorAll(tagName)) {
            if ((el.textContent || '').trim() === text) {
                el.scrollIntoView({behavior:'instant',block:'center'});
                el.click();
                return 'clicked: ' + tagName;
            }
        }
    }
    return null;
}"""

def wait_content(page, max_secs=20):
    for _ in range(max_secs * 2):
        body = page.evaluate('() => document.body.innerText.toLowerCase()')
        stripped = body.replace('\n','').replace('\xa0','').replace('\t','').strip()
        if len(stripped) > 50:
            return body
        page.wait_for_timeout(500)
    return page.evaluate('() => document.body.innerText.toLowerCase()')

pw, browser, ctx, page = _get_page()
try:
    # Clear SF cookies to force fresh sign-in
    ctx.clear_cookies(domain='career8.successfactors.com')
    _log('Cleared SF cookies')
    
    url = sf_job_save_url('career8.successfactors.com', 'aosmith', '27523')
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    _screenshot(page, 'dd_01_landing', debug_dir)
    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    _log(f'Landing body: {body[:100]!r}')
    
    sign_in(page, 'cyshekari+aosmith2280@gmail.com', 'Cyrus2026!Apply', debug_dir)
    page.wait_for_timeout(5000)
    _screenshot(page, 'dd_02_post_signin', debug_dir)
    
    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    _log(f'Post-signin URL: {page.url[:150]}')
    _log(f'Post-signin body: {body[:200]!r}')
    on_form = 'getting started' in body
    _log(f'on_form: {on_form}')
    
    if on_form:
        _log('SUCCESS: on apply form after cookie clear + signin')
        r = page.evaluate(JS_CLICK_UI5, 'Next')
        _log(f'Next: {r}')
        body2 = wait_content(page, 20)
        _screenshot(page, 'dd_03_s2', debug_dir)
        _log(f'step2: {body2[:400]!r}')

finally:
    page.close()
    pw.stop()
    _log('Done')
