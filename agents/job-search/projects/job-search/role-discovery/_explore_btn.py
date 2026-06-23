"""Inspect the Apply button on the listing page."""
import os
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

    # Fill and submit sign-in
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

    _log(f'URL after signin: {page.url}')
    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    _log(f'Body: {body[:200]!r}')

    # Inspect apply button
    btn_info = page.evaluate("""() => {
        const b = document.getElementById('applyButton_top');
        if (!b) return 'NOT FOUND';
        return {
            tag: b.tagName,
            href: b.href || b.getAttribute('href') || '',
            onclick: (b.onclick || '').toString().substring(0, 200),
            text: (b.innerText||b.textContent||'').trim(),
            outerHTML: b.outerHTML.substring(0, 400)
        };
    }""")
    _log(f'applyButton_top: {btn_info}')

    # Get all links with 'apply' in href
    apply_links = page.evaluate("""() => {
        return [...document.querySelectorAll('a[href*=apply], a[href*=Apply]')]
            .map(a => ({text: (a.innerText||'').trim(), href: a.href.substring(0, 150)}))
            .slice(0, 10);
    }""")
    _log(f'Apply links: {apply_links}')

    # Navigate to what Apply link points to
    apply_href = page.evaluate("""() => {
        for (const a of document.querySelectorAll('a')) {
            if ((a.innerText||'').trim().toLowerCase() === 'apply') return a.href;
        }
        return null;
    }""")
    _log(f'Apply href: {apply_href}')

finally:
    page.close()
    pw.stop()
    _log('Done')
