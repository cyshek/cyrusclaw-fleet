"""Navigate full wizard filling required fields."""
import os
import re
os.environ["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log
from pathlib import Path

debug_dir = Path("../.sf-debug")


def wait_content(page, max_secs=25):
    for _ in range(max_secs * 2):
        body = page.evaluate("() => document.body.innerText.toLowerCase()")
        if len(re.sub(r"[\s\xa0]+", "", body)) > 100:
            return body
        page.wait_for_timeout(500)
    return page.evaluate("() => document.body.innerText.toLowerCase()")


def click_ui5(page, text):
    return page.evaluate("""(text) => {
        for (const tagName of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
            for (const el of document.querySelectorAll(tagName)) {
                const t = (el.textContent||el.innerText||'').trim();
                if (t === text) { el.scrollIntoView({block:'center'}); el.click(); return 'clicked:' + t; }
            }
        }
        return null;
    }""", text)


def fill_by_label(page, label_text, value):
    """Fill a field identified by its label."""
    try:
        loc = page.get_by_label(label_text, exact=True)
        cnt = loc.count()
        if cnt > 0:
            loc.first.fill(value)
            return f"filled {label_text}={value!r}"
        return f"NOT FOUND: {label_text}"
    except Exception as e:


def fill_by_index(page, idx, value):
    """Fill nth visible input by index."""
    try:
        loc = page.locator("input:visible").nth(idx)
        loc.fill(value)
        return f"filled idx={idx} val={value!r}"
    except Exception as e:\n        return f"ERROR idx={idx}: {e}"


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

    # Click Apply + Continue
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
    _log(f"URL: {page.url[-60:]}")

    # Step 2: Profile Information - fill required fields
    _log("=== Step 2: Profile Information ===")
    _screenshot(page, "fw_s2", debug_dir)

    # Fill fields by label
    for label, value in [
        ("Address Line1", "12420 NE 120th St #1437"),
        ("City", "Kirkland"),
        ("Postal Code", "98034"),
        ("Phone", "3468040227"),
        ("Mobile Phone", "3468040227"),
    ]:
        r = fill_by_label(page, label, value)
        _log(f"  {r}")

    # State/Province - needs special handling (select or text)
    state_result = page.evaluate("""() => {
        // Find State/Province field
        const labels = document.querySelectorAll('label, [data-sap-ui]');
        for (const lbl of labels) {
            if (/state\\/province/i.test(lbl.innerText||'')) {
                const forId = lbl.htmlFor || lbl.getAttribute('for');
                if (forId) {
                    const el = document.getElementById(forId);
                    if (el) { el.value = 'WA'; el.dispatchEvent(new Event('input', {bubbles:true})); return 'filled state ' + forId; }
                }
            }
        }
        return null;
    }""")
    _log(f"  state: {state_result}")
    
    # Try by label
    r_state = fill_by_label(page, "State/Province", "WA")
    _log(f"  state by label: {r_state}")

    page.wait_for_timeout(1000)
    _screenshot(page, "fw_s2_filled", debug_dir)

    # Click Next - step 2 -> 3
    r = click_ui5(page, "Next")
    _log(f"S2 Next: {r}")
    body3 = wait_content(page, 25)
    _screenshot(page, "fw_s3", debug_dir)
    _log(f"S3 body: {body3[:300]!r}")

    # Step 3: Previous Employment
    _log("=== Step 3 ===")
    ui5_3 = page.evaluate("""() => {
        const r = [];
        for (const t of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
            for (const el of document.querySelectorAll(t)) {
                const txt = (el.textContent||el.innerText||'').trim();
                if (['Next','Previous','Close','Submit Application','Submit'].includes(txt)) r.push(txt);
            }
        }
        return [...new Set(r)];
    }""")
    _log(f"S3 nav buttons: {ui5_3}")
    r3 = click_ui5(page, "Next")
    _log(f"S3 Next: {r3}")
    body4 = wait_content(page, 25)
    _screenshot(page, "fw_s4", debug_dir)
    _log(f"S4 body: {body4[:300]!r}")

    # Step 4: Formal Education
    _log("=== Step 4 ===")
    r4 = click_ui5(page, "Next")
    _log(f"S4 Next: {r4}")
    body5 = wait_content(page, 25)
    _screenshot(page, "fw_s5", debug_dir)
    _log(f"S5 body: {body5[:300]!r}")

    # Step 5: Job-Specific Information
    _log("=== Step 5 ===")
    ui5_5 = page.evaluate("""() => {
        const r = [];
        for (const t of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
            for (const el of document.querySelectorAll(t)) {
                const txt = (el.textContent||el.innerText||'').trim();
                if (['Next','Previous','Close','Submit Application','Submit'].includes(txt)) r.push(txt);
            }
        }
        return [...new Set(r)];
    }""")
    _log(f"S5 nav buttons: {ui5_5}")
    r5 = click_ui5(page, "Next")
    if not r5:
        r5 = click_ui5(page, "Submit Application")
    _log(f"S5 Next/Submit: {r5}")
    body6 = wait_content(page, 25)
    _screenshot(page, "fw_s6", debug_dir)
    _log(f"S6 body: {body6[:400]!r}")

    # Step 6: Additional Information
    _log("=== Step 6 ===")
    ui5_6 = page.evaluate("""() => {
        const r = [];
        for (const t of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
            for (const el of document.querySelectorAll(t)) {
                const txt = (el.textContent||el.innerText||'').trim();
                if (['Next','Previous','Close','Submit Application','Submit','Yes, Proceed'].includes(txt)) r.push(txt);
            }
        }
        return [...new Set(r)];
    }""")
    _log(f"S6 nav buttons: {ui5_6}")
    has_fbqa = page.evaluate("() => !!document.querySelector('#fbqa_apply')")
    _log(f"S6 has #fbqa_apply: {has_fbqa}")
    r6 = click_ui5(page, "Submit Application")
    if not r6:
        r6 = click_ui5(page, "Next")
    _log(f"S6 Submit/Next: {r6}")

    body_final = wait_content(page, 25)
    _screenshot(page, "fw_final", debug_dir)
    _log(f"Final body: {body_final[:400]!r}")
    _log(f"Final URL: {page.url}")

finally:
    page.close()
    pw.stop()
    _log("Done")
