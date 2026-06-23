"""Explore Step 5 required fields and advance through wizard."""
import os, re
os.environ["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log, _type_into_label
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
        # Start Over
        page.evaluate("""() => {
            for (const btn of document.querySelectorAll('button')) {
                if ((btn.innerText||'').trim().toLowerCase() === 'start over') { btn.click(); return; }
            }
        }""")
        page.wait_for_timeout(10000)

    # Now on Step 2 - fill profile and click through to Step 5
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"After Start Over: {body[:100]!r}")
    if "profile information" in body:
        # Quick fill - click next
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
                loc.first.click()
                page.wait_for_timeout(50)
                loc.first.click(click_count=3)
                page.keyboard.type(value)
                page.wait_for_timeout(100)
        page.wait_for_timeout(1000)

        # Click Next on S2
        page.evaluate("""(text) => {
            for (const t of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT']) {
                for (const el of document.querySelectorAll(t)) {
                    if ((el.textContent||'').trim() === text) {
                        const op = parseFloat(getComputedStyle(el).opacity);
                        if (op >= 0.5) { el.scrollIntoView(); el.click(); return 'clicked'; }
                    }
                }
            }
            return null;
        }""", "Next")
        page.wait_for_timeout(5000)
        # Skip Steps 3, 4
        for _ in range(2):
            page.evaluate("""() => {
                for (const el of document.querySelectorAll('UI5-BUTTON-XWEB-DYNAMIC-CONTENT')) {
                    if ((el.textContent||'').trim() === 'Next') {
                        const op = parseFloat(getComputedStyle(el).opacity);
                        if (op >= 0.5) { el.scrollIntoView(); el.click(); return; }
                    }
                }
            }""")
            page.wait_for_timeout(4000)

    # Now should be on Step 5
    body5 = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"Step 5 body[:300]: {body5[:300]!r}")
    _screenshot(page, "s5_start", debug_dir)

    # Find all dropdowns/selects on this step
    select_info = page.evaluate("""() => {
        const r = [];
        // Find UI5 select/combobox components
        for (const el of document.querySelectorAll('select')) {
            const rect = el.getBoundingClientRect();
            if (rect.height > 0) {
                const opts = [...el.options].map(o => o.text.trim()).slice(0,10);
                r.push({tag:'select', id:el.id||'', name:el.name||'', visible:true, options:opts, value:el.value});
            }
        }
        return r;
    }""")
    _log(f"Selects visible: {select_info}")

    # Find all labels with asterisks (required)
    required_labels = page.evaluate("""() => {
        const r = [];
        for (const el of document.querySelectorAll('label, [class*=label]')) {
            const txt = (el.innerText||el.textContent||'').trim();
            if (txt.includes('*') || el.querySelector('[class*=required],[aria-required=true]')) {
                const rect = el.getBoundingClientRect();
                if (rect.height > 0) r.push(txt.substring(0,80));
            }
        }
        return r;
    }""")
    _log(f"Required labels: {required_labels}")

    # Find visible inputs/dropdowns
    visible_inputs = page.locator("input:visible, select:visible").all()
    _log(f"Visible inputs/selects: {len(visible_inputs)}")
    for i, inp in enumerate(visible_inputs[:20]):
        try:
            tag = inp.evaluate("el => el.tagName")
            name = inp.get_attribute("name") or ""
            id_ = inp.get_attribute("id") or ""
            val = inp.input_value() if tag == "INPUT" else ""
            _log(f"  [{i}] {tag} name={name} id={id_} val={val!r}")
        except Exception as e:
            _log(f"  [{i}] err: {e}")

    # Try Playwright get_by_label for known fields
    for lbl in ["How did you learn about this position?",
                "Have you ever been an employee of A. O. Smith or its affiliates?"]:
        try:
            loc = page.get_by_label(lbl)
            cnt = loc.count()
            _log(f"label '{lbl}': count={cnt}")
            if cnt > 0:
                tag = loc.first.evaluate("el => el.tagName")
                val = loc.first.input_value()
                _log(f"  tag={tag} val={val!r}")
        except Exception as e:
            _log(f"  label '{lbl}' err: {e}")

    # Scroll down to see all step 5 content
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
    _screenshot(page, "s5_bottom", debug_dir)
    body5b = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"S5 full body lines: {[l.strip() for l in body5b.splitlines() if l.strip()][:40]}")

finally:
    page.close()
    pw.stop()
    _log("Done")
