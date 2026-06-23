"""Understand UI5 dropdown components on Step 5."""
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
    _log(f"Landed on: {body[:100]!r}")
    if "apply save job" in body:
        page.evaluate("() => document.getElementById('applyButton_top').click()")
        page.wait_for_timeout(4000)
        page.evaluate("""() => {
            for (const btn of document.querySelectorAll('button')) {
                if ((btn.innerText||'').trim().toLowerCase() === 'start over') { btn.click(); return; }
            }
        }""")
        page.wait_for_timeout(8000)
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"After dialog: {body[:80]!r}")
    # advance to step 5 if needed
    if "profile information" in body:
        for label, value in [
            ("Address Line1", "12420 NE 120th St #1437"), ("City", "Kirkland"),
            ("Postal Code", "98034"), ("Mobile Phone", "3468040227"),
            ("State/Province", "Washington"), ("Phone", "3468040227"),
        ]:
            loc = page.get_by_label(label, exact=True)
            if loc.count() > 0:
                loc.first.click(); page.wait_for_timeout(50)
                loc.first.click(click_count=3); page.keyboard.type(value)
                page.wait_for_timeout(100)
        page.wait_for_timeout(1000)
        for _ in range(3):
            page.evaluate("""() => {
                for (const el of document.querySelectorAll('UI5-BUTTON-XWEB-DYNAMIC-CONTENT')) {
                    if ((el.textContent||'').trim() === 'Next') {
                        const op = parseFloat(getComputedStyle(el).opacity);
                        if (op >= 0.5) { el.scrollIntoView(); el.click(); return; }
                    }
                }
            }""")
            page.wait_for_timeout(5000)

    body5 = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"Step: {[l.strip() for l in body5.splitlines() if l.strip()][3:6]}")
    _screenshot(page, "s5u_start", debug_dir)

    # Find UI5 custom elements on Step 5 (combobox/select)
    ui5_selects = page.evaluate("""() => {
        const tags = ['UI5-SELECT-XWEB-DYNAMIC-CONTENT', 'UI5-COMBOBOX-XWEB-DYNAMIC-CONTENT',
                      'UI5-SELECT', 'UI5-COMBOBOX', 'ui5-select', 'ui5-combobox',
                      '[ui5-select]', '[ui5-combobox]'];
        const r = [];
        for (const tag of tags) {
            for (const el of document.querySelectorAll(tag)) {
                const rect = el.getBoundingClientRect();
                r.push({tag: el.tagName, id: el.id||'', label: el.getAttribute('accessible-name')||'',
                        value: el.value||'', visible: rect.height > 0,
                        innerHTML_50: el.innerHTML.substring(0,50)});
            }
        }
        return r;
    }""")
    _log(f"UI5 select/combobox: {ui5_selects}")

    # Try finding all elements with accessible names matching the labels
    label_elements = page.evaluate("""() => {
        const r = [];
        for (const el of document.querySelectorAll('[accessible-name],[aria-label],[aria-labelledby]')) {
            const lbl = el.getAttribute('accessible-name') || el.getAttribute('aria-label') || '';
            if (lbl && el.getBoundingClientRect().height > 0) {
                r.push({tag: el.tagName, label: lbl.substring(0,80), id: el.id||''});
            }
        }
        return r;
    }""")
    _log(f"Accessible-name elements: {label_elements[:20]}")

    # Try the Playwright combobox approach
    _log("Trying get_by_role combobox:")
    combos = page.get_by_role("combobox").all()
    _log(f"combobox count: {len(combos)}")
    for i, cb in enumerate(combos[:10]):
        try:
            val = cb.input_value()
            aria_label = cb.get_attribute("aria-label") or ""
            _log(f"  [{i}] val={val!r} aria-label={aria_label!r}")
        except Exception as e:\n            _log(f"  [{i}] err: {e}")

    # Try to open the first dropdown using page.locator
    _log("Trying listbox approach:")
    try:
        # Click the "How did you learn" label input
        how_loc = page.get_by_label("How did you learn about this position?")
        if how_loc.count() > 0:
            # Get the parent element (UI5 component)
            parent_tag = how_loc.first.evaluate("el => el.parentElement && el.parentElement.parentElement ? el.parentElement.parentElement.tagName : 'N/A'")
            _log(f"Parent tag: {parent_tag}")
            # Try clicking the parent component
            how_loc.first.evaluate("""el => {
                let p = el.parentElement;
                while (p && !p.tagName.startsWith('UI5')) p = p.parentElement;
                if (p) { p.click(); }
            }""")
            page.wait_for_timeout(1000)
            _screenshot(page, "s5u_dropdown_open", debug_dir)

            # Check what appeared
            new_items = page.evaluate("""() => {
                const r = [];
                for (const el of document.querySelectorAll('[role=option],[role=listitem],[role=listbox] *')) {
                    const rect = el.getBoundingClientRect();
                    const txt = (el.innerText||el.textContent||'').trim();
                    if (rect.height > 0 && txt && txt.length < 100) r.push(txt);
                }
                return [...new Set(r)];
            }""")
            _log(f"Items after parent click: {new_items[:20]}")
    except Exception as e:\n        _log(f"Error: {e}")

    _screenshot(page, "s5u_end", debug_dir)

finally:
    page.close()
    pw.stop()
    _log("Done")
