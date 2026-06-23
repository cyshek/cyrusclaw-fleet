"""Find and fill shadow DOM fields in wizard Step 2."""
import os
import re
os.environ["JOBSEARCH_CDP"] = "http://127.0.0.1:18800"
from _successfactors_runner import _get_page, sf_job_save_url, _screenshot, _log
from pathlib import Path

debug_dir = Path("../.sf-debug")

JS_CLICK_UI5 = """(text) => {
    for (const tagName of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
        for (const el of document.querySelectorAll(tagName)) {
            const t = (el.textContent||el.innerText||'').trim();
            if (t === text) { el.click(); return 'clicked:' + tagName; }
        }
    }
    return null;
}"""


def wait_content(page, max_secs=20):
    for _ in range(max_secs * 2):
        body = page.evaluate("() => document.body.innerText.toLowerCase()")
        if len(re.sub(r"[\s\xa0]+", "", body)) > 100:
            return body
        page.wait_for_timeout(500)
    return page.evaluate("() => document.body.innerText.toLowerCase()")


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
    _screenshot(page, "shadow_s2_before", debug_dir)
    shadow_fields = page.evaluate("""() => {
        function getAllInputs(root) {
            const results = [];
            const els = root.querySelectorAll('*');
            for (const el of els) {
                if (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') {
                    const rect = el.getBoundingClientRect();
                    results.push({
                        tag: el.tagName,
                        name: el.name || '',
                        id: (el.id || '').substring(0, 50),
                        type: el.type || '',
                        value: (el.value || '').substring(0, 40),
                        visible: rect.height > 0,
                        placeholder: (el.placeholder || '').substring(0, 30)
                    });
                }
                if (el.shadowRoot) {
                    const sub = getAllInputs(el.shadowRoot);
                    results.push(...sub);
                }
            }
            return results;
        }
        return getAllInputs(document);
    }""")
    _log(f"Shadow DOM inputs total: {len(shadow_fields)}")
    visible = [f for f in shadow_fields if f["visible"]]
    _log(f"Visible ({len(visible)}):")
    for f in visible:
        _log(f"  {f}")
    try:
        all_inputs = page.locator("input:visible")
        cnt = all_inputs.count()
        _log(f"Playwright visible inputs: {cnt}")
        for i in range(min(cnt, 15)):
            inp = all_inputs.nth(i)
            try:
                _log(f"  [{i}] name={inp.get_attribute('name')} id={inp.get_attribute('id')} val={inp.input_value()!r}")
            except Exception as ex:
                _log(f"  [{i}] error: {ex}")
    except Exception as ex:
        _log(f"Playwright error: {ex}")
    for lbl_txt in ["Address Line1", "First Name", "Last Name", "Phone", "Mobile Phone"]:
        try:
            loc = page.get_by_label(lbl_txt)
            cnt2 = loc.count()
            if cnt2 > 0:
                val = loc.first.input_value()
                _log(f"label '{lbl_txt}': count={cnt2} val={val!r}")
        except Exception as ex:
            _log(f"label '{lbl_txt}' error: {ex}")
    _screenshot(page, "shadow_s2", debug_dir)
finally:
    page.close()
    pw.stop()
    _log("Done")
