"""Investigate City fill and state/province combobox behavior."""
import os
import re
os.environ["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log
from pathlib import Path

debug_dir = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.sf-debug")

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
            for (const btn of document.querySelectorAll('[role=dialog] button,.ui-dialog button')) {
                if ((btn.innerText||'').trim().toLowerCase() === 'continue') { btn.click(); return; }
            }
        }""")
        page.wait_for_timeout(8000)

    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"On form: {'profile information' in body}")

    # Fill all fields
    for label, value in [
        ("Address Line1", "12420 NE 120th St #1437"),
        ("City", "Kirkland"),
        ("Postal Code", "98034"),
        ("Mobile Phone", "3468040227"),
    ]:
        loc = page.get_by_label(label, exact=True)
        if loc.count() > 0:
            loc.first.click()
            page.wait_for_timeout(100)
            loc.first.click(click_count=3)
            page.keyboard.type(value)
            page.wait_for_timeout(200)
            val_check = loc.first.input_value()
            _log(f"  {label}: {val_check!r}")

    # State/Province - try as combobox
    try:
        state_loc = page.get_by_label("State/Province", exact=True)
        if state_loc.count() > 0:
            state_loc.first.click()
            page.wait_for_timeout(300)
            # Clear current value
            state_loc.first.click(click_count=3)
            page.keyboard.type("Washington")
            page.wait_for_timeout(1500)
            # Check for dropdown
            dropdown_items = page.evaluate("""() => {
                const items = document.querySelectorAll('[role=option],[class*=suggestion],[class*=dropdown-item],[class*=popover] li');
                return [...items].map(el => (el.innerText||el.textContent||'').trim()).filter(Boolean).slice(0, 10);
            }""")
            _log(f"State dropdown after 'Washington': {dropdown_items}")
            if dropdown_items:
                # Click the first matching item or press Enter
                page.keyboard.press("Enter")
                page.wait_for_timeout(500)
            state_val = state_loc.first.input_value()
            _log(f"State after fill: {state_val!r}")
    except Exception as ex:
        _log(f"State fill err: {ex}")

    # Phone
    phone_loc = page.get_by_label("Phone", exact=True)
    if phone_loc.count() > 0:
        phone_loc.first.click()
        page.wait_for_timeout(100)
        phone_loc.first.click(click_count=3)
        page.keyboard.type("3468040227")
        page.wait_for_timeout(200)
        _log(f"Phone: {phone_loc.first.input_value()!r}")

    page.wait_for_timeout(1000)
    _screenshot(page, "city_explore_filled", debug_dir)

    # Check all values now
    for label in ["Address Line1", "City", "Postal Code", "Mobile Phone", "State/Province", "Phone"]:
        loc = page.get_by_label(label, exact=True)
        cnt = loc.count()
        if cnt > 0:
            val = loc.first.input_value()
            _log(f"  CHECK {label}: {val!r}")

    # Click Next
    page.evaluate("""(text) => {
        for (const tagName of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
            for (const el of document.querySelectorAll(tagName)) {
                if ((el.textContent||el.innerText||'').trim() === text) {
                    el.scrollIntoView({block:'center'}); el.click(); return 'clicked';
                }
            }
        }
        return null;
    }""", "Next")
    page.wait_for_timeout(4000)
    _screenshot(page, "city_after_next", debug_dir)
    step = page.evaluate("() => { const a = document.getElementById('wizard-step-announcer'); return a ? a.textContent : ''; }")
    body_after = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"After Next: step={step!r}")
    _log(f"After Next: body[:300]={body_after[:300]!r}")

    # Check validation errors
    val_errors = page.evaluate("""() => {
        const sel = '[class*=error],[aria-invalid=true],[value-state=Error],[class*=hasError]';
        const els = document.querySelectorAll(sel);
        return [...els].map(el => ({
            tag: el.tagName,
            class: (el.className||'').substring(0,60),
            text: (el.innerText||el.textContent||'').trim().substring(0,50)
        }));
    }""")
    _log(f"Val errors: {val_errors}")

finally:
    page.close()
    pw.stop()
    _log("Done")
