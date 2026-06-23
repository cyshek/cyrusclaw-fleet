"""
Explore the CXE wizard DOM to understand:
1. How many Next buttons are in the DOM at once
2. Which one is the "active" one
3. How to detect current step accurately
"""
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
            for (const btn of document.querySelectorAll('[role=dialog] button,.ui-dialog button')) {
                if ((btn.innerText||'').trim().toLowerCase() === 'continue') { btn.click(); return; }
            }
        }""")
        page.wait_for_timeout(8000)

    # Wait for wizard to load
    for _ in range(60):
        b = page.evaluate("() => document.body.innerText.toLowerCase()")
        if len(re.sub(r"[\s\xa0]+", "", b)) > 100:
            break
        page.wait_for_timeout(500)

    _screenshot(page, "dom_01_initial", debug_dir)

    # Count ALL UI5 buttons in DOM
    all_ui5 = page.evaluate("""() => {
        const r = [];
        for (const t of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
            for (const el of document.querySelectorAll(t)) {
                const txt = (el.textContent||el.innerText||'').trim();
                const rect = el.getBoundingClientRect();
                r.push({
                    tag: t,
                    text: txt,
                    visible: rect.height > 0 && rect.width > 0,
                    inViewport: rect.top >= 0 && rect.top < window.innerHeight,
                    offsetTop: el.offsetTop,
                    display: getComputedStyle(el).display,
                    visibility: getComputedStyle(el).visibility,
                    opacity: getComputedStyle(el).opacity,
                });
            }
        }
        return r;
    }""")
    _log(f"All UI5 buttons: {len(all_ui5)}")
    for b in all_ui5:
        _log(f"  {b}")

    # Check wizard step structure
    step_info = page.evaluate("""() => {
        // Find wizard step containers
        const steps = document.querySelectorAll('ui5-wizard-step-xweb-dynamic-content, [class*=wizardStep], [class*=WizardStep]');
        return [...steps].map((el, i) => ({
            idx: i,
            id: el.id || '',
            tag: el.tagName,
            class: (el.className||'').substring(0,80),
            titleText: el.getAttribute('title-text') || '',
            selected: el.getAttribute('selected') || '',
            disabled: el.getAttribute('disabled') || '',
            display: getComputedStyle(el).display,
            visibility: getComputedStyle(el).visibility,
        }));
    }""")
    _log(f"Wizard step elements: {len(step_info)}")
    for s in step_info:
        _log(f"  {s}")

    # Check step panels/content areas
    panels = page.evaluate("""() => {
        const r = [];
        // Look for visible step content
        for (const el of document.querySelectorAll('[class*=panel],[class*=Panel],[class*=step-content],[id*=step]')) {
            const rect = el.getBoundingClientRect();
            const txt = (el.innerText||'').trim();
            if (txt.length > 20) {
                r.push({
                    id: el.id||'',
                    class: (el.className||'').substring(0,60),
                    visible: rect.height > 0,
                    text: txt.substring(0,80)
                });
            }
        }
        return r.slice(0,10);
    }""")
    _log(f"Panels: {panels}")

    # Current step text
    body_txt = page.evaluate("() => document.body.innerText")
    lines = [l.strip() for l in body_txt.splitlines() if l.strip()]
    _log(f"Body lines 0-20: {lines[:20]}")

    # Step announcer
    ann = page.evaluate("""() => {
        const a = document.getElementById('wizard-step-announcer');
        if (a) return {text: a.textContent, innerHTML: a.innerHTML.substring(0,200)};
        // Try aria-live
        for (const el of document.querySelectorAll('[aria-live],[role=status]')) {
            if (el.textContent.trim()) return {text: el.textContent, id: el.id};
        }
        return null;
    }""")
    _log(f"Announcer: {ann}")

finally:
    page.close()
    pw.stop()
    _log("Done")
