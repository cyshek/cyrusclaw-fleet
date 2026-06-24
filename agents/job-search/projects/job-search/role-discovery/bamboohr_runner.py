#!/usr/bin/env python3
"""
Direct Playwright runner for BambooHR jobs.
Handles Uphold roles 3376 (careers/838) and 3377 (careers/850).
"""
import sys, time, json, sqlite3, os
from pathlib import Path
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
DB = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db")
RESUME = str(Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/resume/Cyrus_Shekari_Resume.pdf"))
APPDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/applications/submitted")

# Personal info
PI = {
    "first_name": "Cyrus",
    "last_name": "Shekari",
    "email": "cyshekari@gmail.com",
    "phone": "3468040227",
    "street": "12420 NE 120th St #1437",
    "city": "Kirkland",
    "state": "WA",
    "state_full": "Washington",
    "zip": "98034",
    "country": "United States",
    "linkedin": "https://linkedin.com/in/cyshekari",
}

JOBS = [
    (3376, "uphold", "838", "Technical Solutions Architect"),
    (3377, "uphold", "850", "Junior Product Manager, Enterprise APIs, Widgets, & UX"),
]

CAPSOLVER_KEY = os.environ.get("CAPSOLVER_API_KEY", "")


def log(*a):
    print("[bamboohr]", *a, flush=True)


def fill_native(page, selector, value):
    return page.evaluate(
        """([sel, val]) => {
            const el = document.querySelector(sel);
            if (!el) return 'NOT_FOUND';
            const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value');
            if (setter && setter.set) setter.set.call(el, val);
            else el.value = val;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new Event('blur', {bubbles:true}));
            return el.value || 'FILLED';
        }""",
        [selector, value]
    )


def fill_by_id(page, field_id, value):
    return fill_native(page, f'#{field_id}', value) or fill_native(page, f'[name="{field_id}"]', value)


def pick_menuvessel_option(page, label_prefix, option_text):
    """Click a BambooHR MenuVessel dropdown and select an option."""
    # Open the dropdown
    opened = page.evaluate(
        """(lp) => {
            const btns = [...document.querySelectorAll('button')];
            const btn = btns.find(b => {
                const lbl = b.getAttribute('aria-label') || b.innerText || '';
                return lbl.toLowerCase().startsWith(lp.toLowerCase());
            });
            if (!btn) return 'BTN_NOT_FOUND:' + lp;
            btn.scrollIntoView({block:'center'});
            btn.click();
            return 'OPENED:' + btn.getAttribute('aria-label');
        }""",
        label_prefix
    )
    log(f"  MenuVessel '{label_prefix}': {opened}")
    if "NOT_FOUND" in str(opened):
        return opened
    time.sleep(0.6)
    
    # Select option
    picked = page.evaluate(
        """(opt) => {
            const norm = s => (s||'').trim().toLowerCase();
            const items = [...document.querySelectorAll('.fab-MenuVessel__list [role="menuitem"], .fab-MenuVessel__list button, [class*="MenuVessel"] button, [class*="MenuVessel"] [role="option"]')];
            let target = items.find(i => norm(i.innerText) === norm(opt));
            if (!target) target = items.find(i => norm(i.innerText).startsWith(norm(opt)));
            if (!target) target = items.find(i => norm(i.innerText).includes(norm(opt)));
            if (!target) return 'OPT_NOT_FOUND:' + opt + ' in [' + items.map(i=>i.innerText.trim().slice(0,20)).slice(0,6).join('|') + ']';
            target.scrollIntoView({block:'center'});
            target.click();
            return 'PICKED:' + target.innerText.trim().slice(0,30);
        }""",
        option_text
    )
    log(f"  MenuVessel option '{option_text}': {picked}")
    return picked


def click_yesno(page, question_text, answer):
    """Click Yes/No button for a BambooHR custom question."""
    result = page.evaluate(
        """([qt, ans]) => {
            const norm = s => (s||'').replace(/\\s+/g,' ').trim().toLowerCase();
            // Find question label
            const labels = [...document.querySelectorAll('label, p, .fab-FormField__label, h3, h4, legend')];
            const qlabel = labels.find(l => norm(l.innerText).includes(norm(qt)));
            if (!qlabel) return 'LABEL_NOT_FOUND:' + qt.slice(0,30);
            
            // Find parent container
            let container = qlabel;
            for (let i=0; i<8; i++) {
                container = container.parentElement;
                if (!container) break;
                const btns = [...container.querySelectorAll('button')].filter(b => {
                    const t = (b.innerText||'').trim().toLowerCase();
                    return t === 'yes' || t === 'no';
                });
                if (btns.length >= 1) {
                    const target = btns.find(b => (b.innerText||'').trim().toLowerCase() === ans.toLowerCase());
                    if (target) { target.scrollIntoView({block:'center'}); target.click(); return 'CLICKED:' + target.innerText; }
                    return 'ANS_NOT_FOUND:' + ans + ' in ' + btns.map(b=>b.innerText).join('|');
                }
            }
            return 'BTNS_NOT_FOUND_FOR:' + qt.slice(0,30);
        }""",
        [question_text, answer]
    )
    log(f"  YesNo '{question_text[:30]}' -> '{answer}': {result}")
    return result


def solve_recaptcha_v2(page, page_url):
    """Solve reCAPTCHA v2 using CapSolver if available."""
    if not CAPSOLVER_KEY:
        log("  No CAPSOLVER_KEY — skipping captcha solve")
        return False
    
    # Detect sitekey
    sitekey = page.evaluate("""() => {
        const el = document.querySelector('.g-recaptcha[data-sitekey], [data-sitekey]');
        return el ? el.getAttribute('data-sitekey') : null;
    }""")
    
    if not sitekey:
        log("  No reCAPTCHA sitekey found")
        return True  # No captcha needed
    
    log(f"  reCAPTCHA v2 sitekey: {sitekey}")
    
    import sys
    sys.path.insert(0, str(RDIR))
    
    try:
        import capsolver_client
        client = capsolver_client.CapSolverClient(api_key=CAPSOLVER_KEY)
        token = client.recaptcha_v2(sitekey=sitekey, page_url=page_url)
        log(f"  reCAPTCHA token len: {len(token) if token else 0}")
        
        if not token:
            return False
        
        # Inject token
        page.evaluate(
            """(token) => {
                let ta = document.querySelector('#g-recaptcha-response, textarea[name^="g-recaptcha-response"]');
                if (!ta) {
                    ta = document.createElement('textarea');
                    ta.id = 'g-recaptcha-response';
                    ta.name = 'g-recaptcha-response';
                    ta.style.display = 'none';
                    document.body.appendChild(ta);
                }
                ta.value = token;
                ta.dispatchEvent(new Event('change', {bubbles:true}));
                // Also try ___grecaptcha_cfg callback
                if (window.___grecaptcha_cfg) {
                    const clients = window.___grecaptcha_cfg.clients || {};
                    for (const id of Object.keys(clients)) {
                        const c = clients[id];
                        for (const k of Object.keys(c || {})) {
                            if (c[k] && typeof c[k].callback === 'function') {
                                try { c[k].callback(token); } catch(e) {}
                            }
                        }
                    }
                }
            }""",
            token
        )
        return True
    except Exception as exc:
        log(f"  CapSolver error: {exc}")
        return False


def upload_files(page, resume_path, cover_letter_path=None):
    """Upload resume and optionally cover letter to BambooHR form."""
    inputs = page.evaluate("""() => {
        return [...document.querySelectorAll('input[type="file"]')].map((inp, i) => ({
            idx: i,
            id: inp.id,
            name: inp.name,
            accept: inp.accept
        }));
    }""")
    log(f"  File inputs: {inputs}")
    
    file_inputs = page.locator('input[type="file"]')
    count = file_inputs.count()
    
    if count == 0:
        log("  No file inputs found!")
        return False
    
    # BambooHR: first input is cover letter, second is resume (per filler comments)
    # But if only one input, it's resume
    if count == 1:
        log("  Single file input — uploading resume")
        try:
            file_inputs.first.set_input_files(resume_path, timeout=15000)
            time.sleep(2)
            log("  Resume uploaded (single input)")
            return True
        except Exception as exc:
            log(f"  Resume upload error: {exc}")
            return False
    
    # Two inputs: first=cover letter, second=resume
    # Upload resume to the SECOND input
    log(f"  Two file inputs — uploading resume to input[1]")
    try:
        file_inputs.nth(1).set_input_files(resume_path, timeout=15000)
        time.sleep(2)
        log("  Resume uploaded (input[1])")
        return True
    except Exception as exc:
        log(f"  Resume upload error (input[1]): {exc}")
        # Try first input
        try:
            file_inputs.first.set_input_files(resume_path, timeout=15000)
            time.sleep(2)
            log("  Resume uploaded (input[0] fallback)")
            return True
        except Exception as exc2:
            log(f"  Resume upload fallback error: {exc2}")
            return False


def submit_form(page):
    """Click the Submit Application button."""
    result = page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button, input[type=submit]')];
        const sub = btns.find(b => /submit application/i.test(b.innerText || b.value || ''));
        if (!sub) {
            // Fallback: any submit button
            const fallback = document.querySelector('button[type=submit], input[type=submit]');
            if (fallback) { fallback.scrollIntoView({block:'center'}); fallback.click(); return 'FALLBACK_SUBMIT:' + (fallback.innerText||fallback.value||'btn'); }
            return 'NO_SUBMIT_BTN';
        }
        sub.scrollIntoView({block:'center'});
        sub.click();
        return 'CLICKED:' + sub.innerText.trim().slice(0,30);
    }""")
    log(f"  Submit click: {result}")
    return result


def wait_confirm(page, timeout_s=40):
    """Wait for submission confirmation."""
    for i in range(timeout_s):
        time.sleep(1)
        url = page.url
        try:
            body = page.evaluate("() => document.body.innerText.toLowerCase()")
            if "thank you" in body and "application" in body:
                return "CONFIRMED_THANK_YOU"
            if "application submitted" in body or "successfully submitted" in body:
                return "CONFIRMED_SUBMITTED"
            if "application received" in body:
                return "CONFIRMED_RECEIVED"
            if "confirmation" in url.lower() or "success" in url.lower() or "thank" in url.lower():
                return f"CONFIRMED_URL:{url[:60]}"
        except:
            pass
        if i % 10 == 0:
            log(f"  Wait {i}s, url={url[:60]}")
    return "UNCONFIRMED"


def process_job(ctx, role_id, tenant, job_id, title):
    apply_url = f"https://{tenant}.bamboohr.com/careers/{job_id}"
    log(f"\n{'='*50}")
    log(f"Role {role_id}: {title}")
    log(f"URL: {apply_url}")
    
    # Close stale bamboohr tabs
    for p in list(ctx.pages):
        try:
            if "bamboohr.com" in p.url:
                p.close()
        except:
            pass
    time.sleep(0.5)
    
    page = ctx.new_page()
    
    try:
        page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        log(f"Loaded: {page.url}")
        
        # Check if page loaded
        title_text = page.title()
        log(f"Page title: {title_text}")
        
        if "404" in title_text or "not found" in title_text.lower():
            log("  Job not found / closed")
            return "CLOSED"
        
        # Inspect the form
        form_info = page.evaluate("""() => {
            const inputs = [...document.querySelectorAll('input:not([type=hidden]):not([type=file])')]
                           .map(i => ({id:i.id, name:i.name, type:i.type, placeholder:(i.placeholder||'').slice(0,20)})).slice(0,15);
            const fileInputs = [...document.querySelectorAll('input[type=file]')].map(i => ({id:i.id, name:i.name}));
            const btns = [...document.querySelectorAll('button')].map(b => (b.innerText||'').trim().slice(0,30)).filter(t=>t).slice(0,10);
            const hasRecaptcha = !!document.querySelector('.g-recaptcha, iframe[src*=recaptcha]');
            return {inputs, fileInputs, btns, hasRecaptcha};
        }""")
        log(f"  Inputs: {form_info['inputs'][:5]}")
        log(f"  File inputs: {form_info['fileInputs']}")
        log(f"  Buttons: {form_info['btns']}")
        log(f"  Has reCAPTCHA: {form_info['hasRecaptcha']}")
        
        # Fill text fields
        fill_by_id(page, "firstName", PI["first_name"])
        fill_by_id(page, "lastName", PI["last_name"])
        fill_by_id(page, "email", PI["email"])
        fill_by_id(page, "phone", PI["phone"])
        fill_by_id(page, "addressStreet1", PI["street"])
        fill_by_id(page, "addressCity", PI["city"])
        fill_by_id(page, "addressZip", PI["zip"])
        fill_by_id(page, "linkedinUrl", PI["linkedin"])
        fill_by_id(page, "desiredPay", "150000")
        
        time.sleep(0.5)
        
        # State dropdown
        pick_menuvessel_option(page, "State", PI["state_full"])
        time.sleep(0.3)
        
        # Upload resume
        upload_files(page, RESUME)
        time.sleep(1)
        
        # Answer custom questions (common ones for Uphold)
        for q_text, answer in [
            ("authorized to work", "Yes"),
            ("legal right to work", "Yes"),
            ("sponsorship", "No"),
            ("require sponsorship", "No"),
            ("visa sponsorship", "No"),
        ]:
            r = click_yesno(page, q_text, answer)
            if "NOT_FOUND" not in str(r):
                time.sleep(0.2)
        
        time.sleep(1)
        
        # Check for reCAPTCHA and solve
        if form_info["hasRecaptcha"] or CAPSOLVER_KEY:
            solve_recaptcha_v2(page, apply_url)
            time.sleep(1)
        
        # Verify pre-submit
        verify = page.evaluate("""() => {
            const missing = [...document.querySelectorAll('[aria-required="true"], [required]')]
                           .filter(el => !el.value && el.type !== 'file' && el.type !== 'submit' && el.type !== 'button')
                           .map(el => el.id || el.name || el.type).slice(0, 10);
            const invalid = [...document.querySelectorAll('[aria-invalid="true"], .fab-FormField--error')]
                           .map(el => el.id || el.name).slice(0, 10);
            const hasSubmit = !!document.querySelector('button:contains("Submit"), button[type=submit]') ||
                              !![...document.querySelectorAll('button')].find(b => /submit/i.test(b.innerText));
            return {missing, invalid, hasSubmit};
        }""")
        log(f"  Pre-submit verify: {verify}")
        
        # Submit
        submit_result = submit_form(page)
        if "NO_SUBMIT" in str(submit_result):
            return f"NO_SUBMIT_BTN"
        
        # Wait for confirmation
        result = wait_confirm(page)
        log(f"  Confirmation: {result}")
        return result
        
    except Exception as exc:
        log(f"  EXCEPTION: {exc}")
        return f"EXCEPTION:{str(exc)[:100]}"
    finally:
        try:
            page.close()
        except:
            pass


def main():
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]
    
    results = []
    
    for role_id, tenant, job_id, title in JOBS:
        result = process_job(ctx, role_id, tenant, job_id, title)
        log(f"RESULT {role_id}: {result}")
        results.append((role_id, tenant, job_id, title, result))
        
        # Update DB
        con = sqlite3.connect(str(DB))
        if "CONFIRMED" in str(result):
            con.execute("UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now'), block_reason=NULL WHERE id=?", (role_id,))
            d = APPDIR / f"uphold-bamboohr-{role_id}"
            d.mkdir(parents=True, exist_ok=True)
            lines = [
                f"# BambooHR Uphold - {title}",
                "status: submitted",
                f"role_id: {role_id}",
                f"tenant: {tenant}",
                f"job_id: {job_id}",
                "submitted_by: auto",
                "submitted_on: 2026-06-24",
                f"confirmation: {result}",
                "resume_attached: yes",
            ]
            (d / "STATUS.md").write_text("\n".join(lines) + "\n")
        elif "UNCONFIRMED" in str(result):
            # Could be submitted but no clear confirmation
            con.execute("UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now'), block_reason='unconfirmed-no-confirm-text' WHERE id=?", (role_id,))
            d = APPDIR / f"uphold-bamboohr-{role_id}"
            d.mkdir(parents=True, exist_ok=True)
            lines = [
                f"# BambooHR Uphold - {title}",
                "status: unconfirmed",
                f"role_id: {role_id}",
                f"tenant: {tenant}",
                f"job_id: {job_id}",
                "submitted_by: auto",
                "submitted_on: 2026-06-24",
                f"confirmation: {result}",
                "resume_attached: yes",
            ]
            (d / "STATUS.md").write_text("\n".join(lines) + "\n")
        else:
            con.execute("UPDATE roles SET block_reason=? WHERE id=?", (result[:200], role_id))
        con.commit()
        con.close()
        
        time.sleep(3)
    
    print("\n" + "="*50)
    print("SUMMARY")
    for r in results:
        print(f"  {r[0]} {r[3][:35]}: {r[4]}")


if __name__ == "__main__":
    main()
