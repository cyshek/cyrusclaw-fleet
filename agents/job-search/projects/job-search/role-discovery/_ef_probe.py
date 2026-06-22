import os, sys, base64
from playwright.sync_api import sync_playwright
import json as _json
from pathlib import Path as _Path
_PI = _json.loads((_Path(__file__).resolve().parents[1] / "personal-info.json").read_text())

CDP_URL = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")
PID = sys.argv[1] if len(sys.argv) > 1 else "790315472265"
URL = "https://explore.jobs.netflix.net/careers/apply?pid=" + PID
RESUME = os.path.abspath("../resume/Cyrus_Shekari_Resume.pdf")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    try:
        page.evaluate("()=>{const s=document.getElementById('onetrust-consent-sdk'); if(s) s.remove();}")
    except Exception:
        pass
    csrf = page.evaluate("document.querySelector('meta[name=_csrf]')?.content || ''")
    with open(RESUME, 'rb') as f:
        pdf_b64 = base64.b64encode(f.read()).decode()
    enc = page.evaluate("""async (args) => {
        const [csrf, b64] = args;
        const bin = atob(b64); const bytes = new Uint8Array(bin.length);
        for (let i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
        const blob = new Blob([bytes], {type:'application/pdf'});
        const fd = new FormData(); fd.append('resume', blob, 'Cyrus_Shekari_Resume.pdf');
        const r = await fetch('/api/application/v2/resume_upload?domain=netflix.com&user_mode=logged_out_candidate', {method:'POST', headers:{'X-CSRF-Token':csrf}, body:fd, credentials:'include'});
        const d = await r.json(); return (((d.data||{}).profile)||{}).encId || null;
    }""", [csrf, pdf_b64])
    print("UPLOAD encId:", enc)
    page.wait_for_timeout(1500)
    for sel, val in [("#Contact_Information_email", _PI["contact"]["email"]), ("#Contact_Information_firstname", "Cyrus"), ("#Contact_Information_lastname", "Shekari"), ("#Contact_Information_phone", _PI["contact"]["phone"]), ("#Contact_Information_city", "Kirkland")]:
        try:
            page.fill(sel, val)
        except Exception as e:
            print("fill fail", sel, e)
    page.wait_for_timeout(1000)
    state = page.evaluate("""() => {
        const out = {required_inputs: [], error_divs_nonempty: [], comboboxes: [], submit_disabled: null, checkbox_groups: []};
        document.querySelectorAll('input,select,textarea').forEach(el => { const req = el.required || el.getAttribute('aria-required')==='true'; if (req) out.required_inputs.push({id: el.id, name: el.name, type: el.type, val: (el.value||'').substring(0,40), invalid: el.getAttribute('aria-invalid')}); });
        document.querySelectorAll('[id$="_error"]').forEach(el => { const t = (el.textContent||'').trim(); if (t) out.error_divs_nonempty.push({id: el.id, text: t.substring(0,120)}); });
        document.querySelectorAll('[role="combobox"]').forEach(c => { out.comboboxes.push({lb: c.getAttribute('aria-labelledby'), v: c.value, invalid: c.getAttribute('aria-invalid')}); });
        ['Self_ID_Questions_US_genderIdentity','Self_ID_Questions_US_raceEthnicity','Self_ID_Questions_US_sexualOrientation'].forEach(gid => { const g = document.getElementById(gid); if (g) { const checked = g.querySelectorAll('input[type=checkbox]:checked, input[type=radio]:checked').length; const total = g.querySelectorAll('input[type=checkbox], input[type=radio]').length; out.checkbox_groups.push({gid, checked, total}); } });
        const btn = Array.from(document.querySelectorAll('button')).find(b => /submit application/i.test(b.textContent||'')); out.submit_disabled = btn ? (btn.disabled) : 'no-button';
        return out;
    }""")
    print("REQUIRED INPUTS:")
    for r in state['required_inputs']: print("  ", r)
    print("NON-EMPTY ERROR DIVS:")
    for e in state['error_divs_nonempty']: print("  ", e)
    print("COMBOBOXES:")
    for c in state['comboboxes']: print("  ", c)
    print("CHECKBOX SELF-ID GROUPS:")
    for g in state['checkbox_groups']: print("  ", g)
    print("SUBMIT DISABLED:", state['submit_disabled'])
    page.close()
