"""Test Start Over dialog handling."""
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

    # Show ALL buttons in current DOM
    all_btns = page.evaluate("""() => {
        const r = [];
        for (const btn of document.querySelectorAll('button,[role=button]')) {
            const t = (btn.innerText||btn.textContent||'').trim();
            const rect = btn.getBoundingClientRect();
            if (t) r.push({text: t, visible: rect.height>0, display: getComputedStyle(btn).display, id: btn.id||'', cls: (btn.className||'').substring(0,40)});
        }
        return r.filter(b => b.visible).slice(0, 30);
    }""")
    _log(f"All visible buttons after apply click:")
    for b in all_btns:
        _log(f"  {b}")

    _screenshot(page, "startover_dialog", debug_dir)

    # Look specifically at the dialog
    dialog_info = page.evaluate("""() => {
        const dialogs = document.querySelectorAll('[role=dialog],[class*=dialog],[class*=modal],[id*=dialog]');
        return [...dialogs].map(el => ({
            id: el.id||'',
            class: (el.className||'').substring(0,80),
            visible: el.getBoundingClientRect().height > 0,
            text: (el.innerText||'').trim().substring(0,200),
            buttons: [...el.querySelectorAll('button')].map(b => (b.innerText||b.textContent||'').trim()).filter(Boolean)
        })).filter(d => d.visible);
    }""")
    _log(f"Dialog info: {dialog_info}")

    # Click Start Over carefully
    result = page.evaluate("""() => {
        // Find dialogs
        const dialogs = document.querySelectorAll('[role=dialog],[class*=dialog],[class*=modal],[id*=dialog],[class*=ui-dialog]');
        for (const dlg of dialogs) {
            const rect = dlg.getBoundingClientRect();
            if (rect.height === 0) continue;
            for (const btn of dlg.querySelectorAll('button')) {
                const t = (btn.innerText||btn.textContent||'').trim().toLowerCase();
                if (t === 'start over') {
                    btn.click();
                    return 'clicked start over in dialog id=' + dlg.id + ' class=' + dlg.className.substring(0,40);
                }
            }
        }
        // Direct button search
        for (const btn of document.querySelectorAll('button')) {
            const t = (btn.innerText||btn.textContent||'').trim().toLowerCase();
            const rect = btn.getBoundingClientRect();
            if (t === 'start over' && rect.height > 0) {
                btn.click();
                return 'clicked start over (direct) id=' + btn.id;
            }
        }
        return 'not found';
    }""")
    _log(f"Start Over click: {result}")
    page.wait_for_timeout(3000)
    _screenshot(page, "startover_after_click", debug_dir)

    # Check if there's a confirmation
    body2 = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"After Start Over body[:200]: {repr(body2[:200])}")

    all_btns2 = page.evaluate("""() => {
        return [...document.querySelectorAll('button')].filter(b => {
            const r = b.getBoundingClientRect();
            return r.height > 0 && (b.innerText||'').trim();
        }).map(b => (b.innerText||'').trim());
    }""")
    _log(f"Buttons after Start Over: {all_btns2}")

    page.wait_for_timeout(8000)
    _screenshot(page, "startover_final", debug_dir)
    body3 = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"Final body lines: {[l.strip() for l in body3.splitlines() if l.strip()][:15]}")

finally:
    page.close()
    pw.stop()
    _log("Done")
