"""Inspect profile fields on Step 2 of wizard."""
import os, re
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

    # Sign in
    page.evaluate("""([e, p]) => {
        const setVal = (el, v) => {
            const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            if (d && d.set) d.set.call(el, v); else el.value = v;
            el.dispatchEvent(new Event('input', {bubbles:true}));
        };
        const ef = document.querySelector('input[name=username],input[type=email],input[name=Email]');
        const pf = document.querySelector('input[type=password]');
        if (ef) setVal(ef, e); if (pf) setVal(pf, p);
    }""", ['cyshekari+aosmith2280@gmail.com', 'Cyrus2026!Apply'])
    page.wait_for_timeout(300)
    page.evaluate("() => { for (const b of document.querySelectorAll('button,input[type=submit]')) { if (/^sign in$/i.test((b.innerText||b.value||'').trim())) { b.click(); return; } } document.querySelector('form').submit(); }")
    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except: pass
    page.wait_for_timeout(5000)

    # Click Apply and Continue
    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    if 'apply save job' in body:
        page.evaluate("() => document.getElementById('applyButton_top').click()")
        page.wait_for_timeout(4000)
        # Click Continue on Saved Applications dialog
        page.evaluate("""() => {
            for (const btn of document.querySelectorAll('[role=dialog] button,.ui-dialog button')) {
                const t = (btn.innerText||btn.textContent||'').trim().toLowerCase();
                if (t === 'continue') { btn.click(); return 'clicked'; }
            }
        }""")
        page.wait_for_timeout(8000)

    body = page.evaluate('() => document.body.innerText.toLowerCase()')
    _log(f'URL: {page.url[-60:]}')
    _log(f'Body: {body[:200]!r}')
    _screenshot(page, 'fld_s2', debug_dir)

    # Inspect the profile information step fields in detail
    field_info = page.evaluate("""() => {
        const r = [];
        // Try all visible inputs including those in shadow roots
        const inputs = document.querySelectorAll('input, select, textarea');
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            r.push({
                tag: el.tagName,
                name: el.name || '',
                id: (el.id || '').substring(0, 60),
                type: el.type || '',
                value: (el.value || '').substring(0, 40),
                visible: rect.height > 0,
                placeholder: el.placeholder || ''
            });
        }
        return r;
    }""")
    _log(f'All inputs ({len(field_info)}):')
    for f in field_info:
        if f['visible'] or f['name']:
            _log(f'  {f}')

    # Also check all SF-specific form components
    sf_inputs = page.evaluate("""() => {
        const r = [];
        // Check UI5 input components and their shadow DOM
        for (const el of document.querySelectorAll('[class*=sapMInput],[class*=sapUiForm],[id*=formContainer]')) {
            const txt = (el.innerText||'').trim();
            if (txt) r.push({class: (el.className||'').substring(0,60), text: txt.substring(0,80), id: el.id||''});
        }
        return r.slice(0, 20);
    }""")
    _log(f'SF inputs ({len(sf_inputs)}):')
    for s in sf_inputs:
        _log(f'  {s}')

    # Check actual form structure
    form_structure = page.evaluate("""() => {
        // Find the wizard/form container
        const containers = document.querySelectorAll('[class*=wizard],[class*=apply-form],[class*=applicationWizard],[id*=wizard]');
        const result = [];
        for (const c of containers) {
            result.push({
                id: c.id || '',
                class: (c.className || '').substring(0, 80),
                innerHTML_50: c.innerHTML.substring(0, 50),
                children: c.children.length
            });
        }
        return result;
    }""")
    _log(f'Form containers: {form_structure}')

    # Get all labels to understand what fields are expected
    labels = page.evaluate("""() => {
        return [...document.querySelectorAll('label, [class*=label]')]
            .filter(l => {
                const r = l.getBoundingClientRect();
                return r.height > 0 && (l.innerText||'').trim().length > 2;
            })
            .map(l => ({text: (l.innerText||'').trim().substring(0,50), forAttr: l.htmlFor||''}))
            .slice(0, 30);
    }""")
    _log(f'Visible labels:')
    for lbl in labels:
        _log(f'  {lbl}')

    # Scroll page to reveal all form fields
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
    _screenshot(page, 'fld_s2_bottom', debug_dir)

    # Try filling the address field by label text
    fill_result = page.evaluate("""() => {
        // Find inputs near 'Address' label
        const labels = [...document.querySelectorAll('label,span')].filter(l =>
            /address line 1/i.test(l.innerText||'')
        );
        for (const lbl of labels) {
            // Try sibling or nearby inputs
            const parent = lbl.closest('tr,.sf-field-row,.formRow,.formItem,.control-group');
            if (parent) {
                const inp = parent.querySelector('input:not([type=hidden])');
                if (inp) {
                    inp.value = '12420 NE 120th St';
                    inp.dispatchEvent(new Event('input', {bubbles:true}));
                    inp.dispatchEvent(new Event('change', {bubbles:true}));
                    return 'filled address via label: ' + inp.id + ' name=' + inp.name;
                }
            }
        }
        return null;
    }""")
    _log(f'Address fill: {fill_result}')

finally:
    page.close()
    pw.stop()
    _log('Done')
