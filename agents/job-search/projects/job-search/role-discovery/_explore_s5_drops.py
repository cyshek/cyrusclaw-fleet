"""Explore Step 5 dropdown options."""
import os, re
os.environ["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log
from pathlib import Path

debug_dir = Path("../.sf-debug")

pw, browser, ctx, page = _get_page()
try:
    ctx.clear_cookies()
    url = sf_job_save_url("career8.successfactors.com", "aosmith", "27523")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    page.evaluate("""([e, p]) => {
        const setVal = (el, v) => {
            const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            if (d && d.set) d.set.call(el, v); else el.value = v;
            el.dispatchEvent(new Event('input', {bubbles:true}));
        };
        const ef = document.querySelector('input[name=username],input[type=email],input[name=Email]');
        const pf = document.querySelector('input[type=password]');
        if (ef) setVal(ef, e); if (pf) setVal(pf, p);
    }""", ["cyshekari+aosmith2280@gmail.com", "Cyrus2026!Apply"])
    page.wait_for_timeout(300)
    page.evaluate("""() => {
        for (const b of document.querySelectorAll('button,input[type=submit]')) {
            if (/^sign in$/i.test((b.innerText||b.value||'').trim())) { b.click(); return; }
        }
        document.querySelector('form').submit();
    }""")
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(5000)

    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    if "apply save job" in body:
        page.evaluate("() => document.getElementById('applyButton_top').click()")
        page.wait_for_timeout(4000)
        page.evaluate("""() => {
            for (const btn of document.querySelectorAll('button')) {
                if ((btn.innerText||'').trim().toLowerCase() === 'start over') { btn.click(); return; }
            }
        }""")
        page.wait_for_timeout(8000)

    # Skip to step 5 if we're on step 2
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    if "profile information" in body:
        _log("On step 2, filling and advancing to step 5")
        for label, value in [
            ("Address Line1", "12420 NE 120th St #1437"),
            ("City", "Kirkland"),
            ("Postal Code", "98034"),
            ("Mobile Phone", "3468040227"),
            ("State/Province", "Washington"),
            ("Phone", "3468040227"),
        ]:
            loc = page.get_by_label(label, exact=True)
            if loc.count() > 0:
                loc.first.click(); page.wait_for_timeout(50)
                loc.first.click(click_count=3)
                page.keyboard.type(value)
                page.wait_for_timeout(100)
        page.wait_for_timeout(1000)
        for _ in range(3):  # S2, S3, S4
            page.evaluate("""() => {
                for (const el of document.querySelectorAll('UI5-BUTTON-XWEB-DYNAMIC-CONTENT')) {
                    if ((el.textContent||'').trim() === 'Next') {
                        const op = parseFloat(getComputedStyle(el).opacity);
                        if (op >= 0.5) { el.scrollIntoView(); el.click(); return 'clicked'; }
                    }
                }
                return null;
            }""")
            page.wait_for_timeout(5000)

    body5 = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"Current step: {[l for l in body5.splitlines() if l.strip()][:5]}")
    _screenshot(page, "s5_drop_start", debug_dir)

    # Click on "How did you learn about this position?" to see dropdown options
    how_loc = page.get_by_label("How did you learn about this position?")
    if how_loc.count() > 0:
        how_loc.first.click()
        page.wait_for_timeout(1000)
        # Get all option/list items that appeared
        options = page.evaluate("""() => {
            const r = [];
            for (const sel of ['[role=option],[class*=option],[class*=suggestion],[class*=listitem]',
                                'li[class*=item]', '[data-ui5-suggestion-item]']) {
                for (const el of document.querySelectorAll(sel)) {
                    const rect = el.getBoundingClientRect();
                    const txt = (el.innerText||el.textContent||'').trim();
                    if (rect.height > 0 && txt) r.push(txt.substring(0,50));
                }
            }
            return [...new Set(r)];
        }""")
        _log(f"How learned dropdown options: {options}")
        _screenshot(page, "s5_how_dropdown", debug_dir)
        # Pick "Internet" or "Job Board" or first option
        chosen = None
        for pref in ["Internet", "Job Board", "Online", "Company Website", "LinkedIn", "Indeed"]:
            if pref in options or pref.lower() in [o.lower() for o in options]:
                chosen = pref
                break
        if not chosen and options:
            chosen = options[0]
        _log(f"Choosing: {chosen!r}")
        if chosen:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            how_loc.first.click()
            page.wait_for_timeout(300)
            how_loc.first.click(click_count=3)
            page.keyboard.type(chosen)
            page.wait_for_timeout(1000)
            # Try to select from dropdown
            for sel in ['[role=option]', '[data-ui5-suggestion-item]', 'li']:
                for el in page.query_selector_all(sel):
                    txt = el.inner_text().strip()
                    if chosen.lower() in txt.lower():
                        el.click()
                        _log(f"Clicked option: {txt!r}")
                        break
            page.wait_for_timeout(500)
            val_after = how_loc.first.input_value()
            _log(f"How learned after: {val_after!r}")

    # Click "Have you ever been an employee" dropdown
    emp_loc = page.get_by_label("Have you ever been an employee of A. O. Smith or its affiliates?")
    if emp_loc.count() > 0:
        emp_loc.first.click()
        page.wait_for_timeout(1000)
        emp_options = page.evaluate("""() => {
            const r = [];
            for (const el of document.querySelectorAll('[role=option],[data-ui5-suggestion-item],li')) {
                const rect = el.getBoundingClientRect();
                const txt = (el.innerText||el.textContent||'').trim();
                if (rect.height > 0 && txt) r.push(txt.substring(0,50));
            }
            return [...new Set(r)];
        }""")
        _log(f"Employee dropdown options: {emp_options}")
        _screenshot(page, "s5_emp_dropdown", debug_dir)

    _screenshot(page, "s5_drop_end", debug_dir)

finally:
    page.close()
    pw.stop()
    _log("Done")
