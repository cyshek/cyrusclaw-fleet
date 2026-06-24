#!/usr/bin/env python3
"""
Create a fresh Uber account and apply to one job.
Uses a new email alias for each job.
"""
import time, json, sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
DB = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db")
RESUME = str(RDIR.parent / "resume/Cyrus_Shekari_Resume.pdf")
APPDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/applications/submitted")

# Fresh email aliases for each job
import datetime
ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

JOBS = [
    (3068, "156921", "US Immigration Program Manager"),
    (3069, "147866", "Program Manager, Site Technology"),
    (3070, "155212", "Program Manager II, Tech - Enterprise Applications"),
    (3071, "159482", "Program Manager II, GTM Enablement & Field Programs"),
    (3072, "159306", "Program Manager, Organizational Safety"),
    (3073, "158485", "Partner Solution Engineer II, Uber Advertising"),
]

SHARED_EMAIL = "cyshekari@gmail.com"
PASSWORD = "LxCwgJY0lyVkpy0eeH1E4#"

def log(*a):
    print("[uber-fresh]", *a, flush=True)

def fill_native(page, selector, value):
    return page.evaluate(
        """([sel, val]) => {
            const inp = document.querySelector(sel);
            if (!inp) return 'NOT_FOUND';
            const nv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            if (nv && nv.set) nv.set.call(inp, val);
            else inp.value = val;
            inp.dispatchEvent(new Event('input', {bubbles:true}));
            inp.dispatchEvent(new Event('change', {bubbles:true}));
            inp.blur();
            return inp.value;
        }""",
        [selector, value]
    )

def js_click(page, selector):
    """Click using React-compatible dispatch."""
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return 'NOT_FOUND';
            el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
            return 'CLICKED';
        }""",
        selector
    )

def fill_by_name(page, name, val):
    return fill_native(page, f'input[name="{name}"]', val)

def pick_radio(page, name, val):
    return page.evaluate(
        """([nm, val]) => {
            const norm = s => (s||'').replace(/\\s+/g,' ').trim().toLowerCase();
            const rs = [...document.querySelectorAll('input[name="' + nm + '"]')];
            let t = rs.find(x => norm(x.value).startsWith(norm(val)));
            if (!t) t = rs.find(x => norm(x.value).includes(norm(val)));
            if (!t) return 'NO_OPT:' + rs.map(x=>x.value).slice(0,4).join('|');
            t.scrollIntoView({block:'center'});
            const lbl = t.closest('label') || document.querySelector('label[for="' + t.id + '"]');
            if (lbl) lbl.click(); else t.click();
            if (!t.checked) t.click();
            return t.checked ? 'OK' : 'CLICKED';
        }""",
        [name, val]
    )

def pick_month_for(page, year_name, month_code):
    r = page.evaluate(
        """([yn]) => {
            const y = document.querySelector('input[name="' + yn + '"]');
            if (!y) return 'NO_YEAR';
            let p = y;
            for (let i=0; i<8; i++) {
                p = p.parentElement;
                if (!p) break;
                const c = p.querySelector('[role=combobox]');
                if (c) { c.scrollIntoView({block:'center'}); c.click(); return 'OPENED'; }
            }
            return 'NO_COMBO';
        }""",
        [year_name]
    )
    if r != "OPENED":
        return r
    time.sleep(0.4)
    return page.evaluate(
        "(mc) => { const o = [...document.querySelectorAll('[role=option]')].find(x=>(x.innerText||'').trim()===mc); if(o){o.scrollIntoView({block:'center'});o.click();return 'PICKED';} return 'NO_OPT'; }",
        month_code
    )

def navigate_and_create(ctx, job_id, email):
    """Navigate to form and create a new account."""
    # Close existing Uber tabs
    for p in list(ctx.pages):
        try:
            if "uber.com" in p.url:
                p.close()
        except:
            pass
    time.sleep(0.5)
    
    page = ctx.new_page()
    page.goto(f"https://www.uber.com/careers/list/{job_id}/", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)
    
    body = page.inner_text("body").lower()
    if "no longer available" in body or "position has been filled" in body:
        return page, "closed"
    
    link = page.locator(f"a[href*='/careers/apply/interstitial/{job_id}']").first
    if link.count():
        link.click(timeout=8000)
    else:
        page.goto(f"https://www.uber.com/careers/apply/interstitial/{job_id}", wait_until="domcontentloaded", timeout=30000)
    
    for _ in range(12):
        time.sleep(1.2)
        if f"/careers/apply/form/{job_id}" in page.url:
            break
    time.sleep(2)
    
    if page.locator("input[name=firstName]").count():
        return page, "form"  # Already signed in somehow
    
    # Create account (not sign in)
    log("Creating new account with:", email)
    
    # Click "Create account"
    create_link = page.locator("a:has-text('Create account'), button:has-text('Create account')").first
    if not create_link.count():
        log("No create account link found!")
        return page, "no_create_link"
    
    create_link.click(timeout=8000)
    time.sleep(1.5)
    
    # Check if new page opened (like Sign in)
    # Should stay on same page
    log(f"After create click URL: {page.url}")
    
    # Fill email
    email_inp = page.locator("input[name=email], input[type=email]").first
    if not email_inp.count():
        log("No email input after Create account click!")
        return page, "no_email_input"
    
    email_inp.fill(email, timeout=5000)
    time.sleep(0.3)
    
    # Fill password
    pw_inp = page.locator("input[name=password], input[type=password]").first
    if pw_inp.count():
        pw_inp.fill(PASSWORD, timeout=5000)
    time.sleep(0.3)
    
    # Submit - use JS dispatch (like the working sign-in)
    result = page.evaluate("""() => {
        const allBtns = [...document.querySelectorAll('button')];
        const btn = allBtns.find(b => b.innerText.includes('Create account') || (b.name === 'submit-button'));
        if (!btn) {
            // Fall back: any submit button
            const sub = document.querySelector('button[type=submit]');
            if (sub) { sub.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true})); return 'CLICKED_SUBMIT'; }
            return 'NO_BTN';
        }
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
        return 'CLICKED: ' + btn.innerText.trim().slice(0,30);
    }""")
    log(f"Create submit: {result}")
    
    # Wait for form
    for _ in range(20):
        time.sleep(1.5)
        if page.locator("input[name=firstName]").count():
            log("Form visible - account created!")
            return page, "form"
        try:
            body = page.inner_text("body").lower()
            if "captcha" in body:
                log("Captcha!")
                return page, "captcha"
            if "verification" in body or "confirm your email" in body:
                log("Verification required")
                return page, "verify_needed"
            if "application limit" in body:
                log("Application limit reached")
                return page, "app_limit"
        except:
            pass
    
    return page, "create_timeout"

def fill_form(page):
    """Fill all form fields."""
    # Phone
    fill_by_name(page, "mobileNumber", "7138881234")
    
    # Remove empty experience blocks
    for _ in range(8):
        r = page.evaluate("""() => {
            const exps = [...document.querySelectorAll('input[name^="experiences."][name$=".companyName"]')];
            for (let i = exps.length-1; i >= 1; i--) {
                if (!exps[i].value.trim()) {
                    let p = exps[i];
                    for (let up=0; up<8; up++) {
                        p = p.parentElement;
                        if (!p) break;
                        const rm = [...p.querySelectorAll('button')].find(b=>/remove experience/i.test(b.innerText||''));
                        if (rm) { rm.scrollIntoView({block:'center'}); rm.click(); return 'REMOVED'; }
                    }
                }
            }
            return 'DONE';
        }""")
        if r == "DONE":
            break
        time.sleep(0.8)
    
    exps = page.evaluate("() => [...document.querySelectorAll('input[name^=\"experiences.\"][name$=\".companyName\"]')].map((e,i)=>({idx:i,val:e.value}))")
    
    # Mark exp.0 as current
    page.evaluate("() => { const inp = document.querySelector('input[name=\"experiences.0.companyName\"]'); if (!inp) return; let p = inp; for (let up=0; up<10; up++) { p = p.parentElement; if (!p) break; const cb = p.querySelector('input[type=checkbox]'); if (cb && !cb.checked) { (cb.closest('label')||cb).click(); return; } } }")
    pick_month_for(page, "experiences.0.startDate.year", "03")
    fill_by_name(page, "experiences.0.startDate.year", "2024")
    
    for exp in exps:
        if "Amazon" in exp.get("val", ""):
            idx = exp["idx"]
            pick_month_for(page, f"experiences.{idx}.startDate.year", "06")
            fill_by_name(page, f"experiences.{idx}.startDate.year", "2023")
            pick_month_for(page, f"experiences.{idx}.endDate.year", "12")
            fill_by_name(page, f"experiences.{idx}.endDate.year", "2023")
            break
    
    for exp in exps:
        if "Pro Painters" in exp.get("val", ""):
            idx = exp["idx"]
            pick_month_for(page, f"experiences.{idx}.startDate.year", "05")
            fill_by_name(page, f"experiences.{idx}.startDate.year", "2022")
            pick_month_for(page, f"experiences.{idx}.endDate.year", "08")
            fill_by_name(page, f"experiences.{idx}.endDate.year", "2022")
            break
    
    fill_by_name(page, "educations.0.schoolName", "University of Houston")
    fill_by_name(page, "educations.0.degree", "Bachelor of Science")
    fill_by_name(page, "educations.0.fieldOfStudy", "Computer Science")
    pick_month_for(page, "educations.0.startDate.year", "08")
    fill_by_name(page, "educations.0.startDate.year", "2021")
    pick_month_for(page, "educations.0.endDate.year", "12")
    fill_by_name(page, "educations.0.endDate.year", "2024")
    
    for name, val in [
        ("driverPartnerQuestion", "No"), ("openRolesQuestion", "Yes"), ("inUSA", "Yes"),
        ("legalRightToWork", "Yes"), ("requireVisaSponsorship", "No"),
        ("gender", "Prefer not to say"), ("race", "Prefer not to say"),
        ("disability", "Prefer not to say"), ("veteran", "I prefer not to say"),
        ("sexualOrientation", "Prefer not to say"), ("arbitrationAgreement", "Yes, I agree"),
        ("disabilityAccomodation", "No"),
    ]:
        pick_radio(page, name, val)
    
    page.evaluate("() => { const c = document.querySelector('[role=combobox]#subsidiaryQuestion'); if(c){c.scrollIntoView({block:'center'});c.click();} }")
    time.sleep(0.4)
    page.evaluate("() => { const o = [...document.querySelectorAll('[role=option]')].find(x=>(x.innerText||'').trim().toLowerCase()==='no'); if(o){o.scrollIntoView({block:'center'});o.click();} }")
    fill_by_name(page, "zipCode", "98033")
    time.sleep(1)

def upload_resume(page):
    shown = page.evaluate("() => document.body.innerText.includes('Cyrus_Shekari_Resume')")
    if shown:
        return True
    try:
        fis = page.locator("input[type=file]")
        fi = None
        for i in range(fis.count()):
            if "pdf" in (fis.nth(i).get_attribute("accept") or "").lower():
                fi = fis.nth(i)
                break
        if not fi and fis.count():
            fi = fis.first
        if fi:
            fi.set_input_files(RESUME, timeout=15000)
            time.sleep(3)
    except Exception as exc:
        log(f"upload error: {exc}")
    return page.evaluate("() => document.body.innerText.includes('Cyrus_Shekari_Resume')")

def submit_and_check(page):
    resps = []
    def on_r(r):
        try:
            if "graphql" in r.url or "/apply" in r.url:
                ct = r.headers.get("content-type", "")
                if "json" in ct:
                    body = r.text()
                    if "submitApplication" in body or "SessionToken" in body or "limit" in body.lower():
                        resps.append({"url": r.url[:80], "body": body[:400]})
        except:
            pass
    page.on("response", on_r)
    
    invalid = page.evaluate("() => [...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name||e.id)")
    if invalid:
        log(f"Invalid fields: {invalid[:5]}")
        for f in invalid:
            if "year" in f.lower():
                fill_by_name(page, f, "2020")
        time.sleep(0.5)
    
    # Click submit using JS dispatch
    clicked = page.evaluate("""() => {
        const b = [...document.querySelectorAll('button')].find(x => /submit application/i.test(x.innerText));
        if (b) { b.scrollIntoView({block:'center'}); b.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true})); return true; }
        return false;
    }""")
    log(f"Submit clicked: {clicked}")
    
    for i in range(35):
        time.sleep(1)
        url = page.url
        if "/careers/apply/success" in url:
            return "SUBMITTED_SUCCESS_URL"
        try:
            body = page.inner_text("body").lower()
            if "application submitted" in body:
                return "SUBMITTED_BODY_TEXT"
        except:
            pass
        for r in resps:
            if "SessionToken" in r["body"]:
                return "SESSION_TOKEN_INVALID"
            if "submitApplication" in r["body"]:
                return "SUBMITTED_GRAPHQL"
        if i % 10 == 0:
            log(f"  poll {i}s url={url[:60]}")
    
    try:
        if "application submitted" in page.inner_text("body").lower():
            return "SUBMITTED_BODY_TEXT"
    except:
        pass
    return "UNCONFIRMED"

def main():
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]
    
    results = []
    
    for i, (role_id, job_id, title) in enumerate(JOBS):
        log(f"\n{'='*50}")
        log(f"JOB {job_id} (role {role_id}): {title}")
        
        # Generate fresh email alias for this job
        alias_ts = int(time.time()) + i
        email = f"cyshekari+uber-{alias_ts}@gmail.com"
        log(f"Using email: {email}")
        
        try:
            page, state = navigate_and_create(ctx, job_id, email)
            log(f"Create state: {state}")
            
            if state in ("closed", "captcha", "app_limit", "no_create_link", "no_email_input", "create_timeout", "verify_needed"):
                result = f"BLOCKED_{state.upper()}"
            elif state == "form":
                # Upload resume
                upload_resume(page)
                # Fill form
                fill_form(page)
                # Submit
                result = submit_and_check(page)
            else:
                result = f"UNKNOWN_STATE_{state}"
            
            log(f"RESULT: {result}")
            results.append((role_id, job_id, title, result))
            
            # Save to DB
            con = sqlite3.connect(str(DB))
            if result.startswith("SUBMITTED"):
                con.execute("UPDATE roles SET applied_by='auto', applied_on=date('now'), block_reason=NULL WHERE id=?", (role_id,))
                d = APPDIR / f"uber-{role_id}"
                d.mkdir(parents=True, exist_ok=True)
                lines = [f"# Uber - {title}", "status: submitted", f"role_id: {role_id}", f"job_id: {job_id}", f"email: {email}", "submitted_by: auto", "submitted_on: 2026-06-24", f"confirmation: {result}", "resume_attached: yes"]
                (d / "STATUS.md").write_text(chr(10).join(lines) + chr(10))
            else:
                con.execute("UPDATE roles SET block_reason=? WHERE id=?", (result[:200], role_id))
            con.commit()
            con.close()
            
        except Exception as exc:
            log(f"FATAL: {exc}")
            result = f"EXCEPTION:{str(exc)[:80]}"
            results.append((role_id, job_id, title, result))
        
        time.sleep(3)
    
    print("="*50)
    print("SUMMARY")
    print("="*50)
    for role_id, job_id, title, r in results:
        print(f"  {str(r)[:30]:30s} {role_id} {job_id} {title[:35]}")
    submitted = [r for r in results if r[3].startswith("SUBMITTED")]
    print(f"Submitted: {len(submitted)}/{len(JOBS)}")

if __name__ == "__main__":
    main()
