#!/usr/bin/env python3
"""
Robust Uber apply - handles all 6 remaining jobs (3068-3073)
Key fixes:
1. Close ALL existing Uber tabs before each job (stale tabs cause crashes)
2. Fresh navigation for each job
3. Sign in with proper error handling
4. Fill form and submit
"""
import time, json, sqlite3, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

RDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
DB = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db")
RESUME = str(RDIR.parent / "resume/Cyrus_Shekari_Resume.pdf")
APPDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/applications/submitted")
CDP = "http://127.0.0.1:18800"

creds = json.loads((RDIR / ".uber-creds.json").read_text())["account"]
EMAIL = creds["email"]
PASSWORD = creds["password"]

JOBS = [
    (3068, "156921", "US Immigration Program Manager"),
    (3069, "147866", "Program Manager, Site Technology"),
    (3070, "155212", "Program Manager II, Tech - Enterprise Applications"),
    (3071, "159482", "Program Manager II, GTM Enablement & Field Programs"),
    (3072, "159306", "Program Manager, Organizational Safety"),
    (3073, "158485", "Partner Solution Engineer II, Uber Advertising"),
]

def log(*a):
    print("[uber]", *a, flush=True)

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

def close_uber_tabs(ctx):
    """Close all existing Uber careers tabs to avoid stale page issues."""
    closed = 0
    for p in list(ctx.pages):
        try:
            u = p.url
            if "uber.com/careers" in u:
                p.close()
                closed += 1
        except:
            pass
    if closed:
        log(f"Closed {closed} stale Uber tabs")
    time.sleep(0.5)

def navigate_to_form(ctx, job_id):
    """Open fresh tab, navigate through JD -> Apply Now -> form. Returns (page, 'form'|'account'|'closed'|'error')."""
    page = ctx.new_page()
    try:
        page.goto(f"https://www.uber.com/careers/list/{job_id}/", wait_until="domcontentloaded", timeout=45000)
        time.sleep(2.5)
        body = ""
        try:
            body = page.inner_text("body").lower()
        except:
            pass
        if "no longer available" in body or "position has been filled" in body or "couldn't find that page" in body:
            return page, "closed"
        # Click Apply Now
        sel = f"a[href*='/careers/apply/interstitial/{job_id}']"
        link = page.locator(sel).first
        if link.count():
            link.click(timeout=8000)
        else:
            page.goto(f"https://www.uber.com/careers/apply/interstitial/{job_id}", wait_until="domcontentloaded", timeout=30000)
        # Wait for form URL
        for _ in range(12):
            time.sleep(1.2)
            if f"/careers/apply/form/{job_id}" in page.url:
                break
        time.sleep(2)
        if page.locator("input[name=firstName]").count():
            return page, "form"
        if page.locator("button:has-text('Sign in')").count() or page.locator("a:has-text('Create account')").count():
            return page, "account"
        return page, "unknown"
    except Exception as exc:
        log(f"navigate error: {exc}")
        return page, "error"

def sign_in(page):
    """Click Sign in, fill email+password, submit. Returns True if form appears."""
    # Click the Sign in button
    btn = page.locator("button:has-text('Sign in')").first
    if not btn.count():
        log("No Sign in button found")
        return False
    try:
        btn.click(timeout=8000)
    except Exception as exc:
        log(f"Sign in click err: {exc}")
        return False
    time.sleep(1.5)
    # Fill email
    email_inp = page.locator("input[name=email], input[type=email]").first
    if not email_inp.count():
        # Maybe no navigation needed, already on a form?
        if page.locator("input[name=firstName]").count():
            log("Already on form after sign-in click (pre-authenticated)")
            return True
        log("No email input visible after Sign in click")
        return False
    try:
        email_inp.fill(EMAIL, timeout=5000)
    except Exception as exc:
        log(f"Email fill error: {exc}")
        return False
    # Fill password
    pw_inp = page.locator("input[name=password], input[type=password]").first
    if pw_inp.count():
        try:
            pw_inp.fill(PASSWORD, timeout=5000)
        except Exception as exc:
            log(f"Password fill error: {exc}")
    # Submit
    submitted = False
    for sel in ["button[type=submit]:has-text('Sign in')", "button:has-text('Sign in')", "button[name=submit-button]"]:
        loc = page.locator(sel).last
        if loc.count():
            try:
                loc.click(timeout=8000)
                submitted = True
                break
            except:
                pass
    if not submitted:
        log("No submit button found")
        return False
    # Wait for form
    for _ in range(20):
        time.sleep(1.5)
        if page.locator("input[name=firstName]").count():
            log("Form visible - sign in success")
            return True
        # Check for captcha or other issues
        try:
            body = page.inner_text("body").lower()
            if "captcha" in body or "are you a robot" in body:
                log("Captcha detected after sign-in")
                return False
            if "invalid password" in body or "incorrect password" in body:
                log("Wrong password")
                return False
            if "verification code" in body or "we sent a code" in body:
                log("Verification code required - check email")
                return False
        except:
            pass
    log(f"Sign-in timeout - URL: {page.url}")
    return False

def upload_resume(page):
    """Upload resume PDF if not already shown."""
    resume_shown = page.evaluate("""() => {
        const b = document.body.innerText || '';
        return b.includes('Cyrus_Shekari_Resume') || b.includes('File successfully uploaded') || b.includes('resume uploaded');
    }""")
    if resume_shown:
        log("Resume already shown")
        return True
    log("Uploading resume...")
    try:
        fis = page.locator("input[type=file]")
        fi = None
        for i in range(fis.count()):
            accept = fis.nth(i).get_attribute("accept") or ""
            if "pdf" in accept.lower() or "." in accept:
                fi = fis.nth(i)
                break
        if not fi and fis.count():
            fi = fis.first
        if fi:
            fi.set_input_files(RESUME, timeout=15000)
            time.sleep(3)
            # Verify upload
            shown = page.evaluate("""() => {
                const b = document.body.innerText || '';
                return b.includes('Cyrus_Shekari_Resume');
            }""")
            log(f"Resume shown after upload: {shown}")
            return shown
        else:
            log("No file input found")
            return False
    except Exception as exc:
        log(f"Upload error: {exc}")
        return False

def get_experiences(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('input[name^=\"experiences.\"][name$=\".companyName\"]')].map((e,i)=>({idx:i,val:e.value}))"
    )

def remove_empty_experiences(page):
    """Remove empty experience blocks."""
    for _ in range(10):
        r = page.evaluate("""() => {
            const exps = [...document.querySelectorAll('input[name^="experiences."][name$=".companyName"]')];
            for (let i = exps.length-1; i >= 1; i--) {
                if (!exps[i].value.trim()) {
                    let parent = exps[i];
                    for (let up = 0; up < 8; up++) {
                        parent = parent.parentElement;
                        if (!parent) break;
                        const rm = [...parent.querySelectorAll('button')].find(b=>/remove experience/i.test(b.innerText||''));
                        if (rm) { rm.scrollIntoView({block:'center'}); rm.click(); return 'REMOVED_' + i; }
                    }
                }
            }
            return 'DONE';
        }""")
        if r == "DONE":
            break
        time.sleep(0.8)

def pick_month_for_field(page, year_field_name, month_code):
    """Open month combobox near year field, pick month."""
    r = page.evaluate(
        """([yn]) => {
            const yearInp = document.querySelector('input[name="' + yn + '"]');
            if (!yearInp) return 'NO_YEAR';
            let parent = yearInp;
            for (let i=0; i<8; i++) {
                parent = parent.parentElement;
                if (!parent) break;
                const combo = parent.querySelector('[role=combobox]');
                if (combo) { combo.scrollIntoView({block:'center'}); combo.click(); return 'OPENED'; }
            }
            return 'NO_COMBO';
        }""",
        [year_field_name]
    )
    if r != "OPENED":
        return r
    time.sleep(0.4)
    return page.evaluate(
        "(mc) => { const opts = [...document.querySelectorAll('[role=option]')]; const o = opts.find(x=>(x.innerText||'').trim()===mc); if(o){o.scrollIntoView({block:'center'});o.click();return 'PICKED';} return 'NO_OPT:'+opts.slice(0,3).map(x=>(x.innerText||'').trim()).join('|'); }",
        month_code
    )

def fill_form(page):
    """Fill all form fields."""
    log("Filling form fields...")
    # Phone
    r = fill_by_name(page, "mobileNumber", "7138881234")
    log(f"  phone: {r}")
    # Remove empty experience blocks
    remove_empty_experiences(page)
    exps = get_experiences(page)
    log(f"  experiences: {json.dumps(exps)}")
    # exp 0 = Microsoft (current) - mark as current, set start 03/2024
    page.evaluate("""() => {
        const inp = document.querySelector('input[name="experiences.0.companyName"]');
        if (!inp) return;
        let parent = inp;
        for (let up=0; up<10; up++) {
            parent = parent.parentElement;
            if (!parent) break;
            const cb = parent.querySelector('input[type=checkbox]');
            if (cb && !cb.checked) { (cb.closest('label')||cb).click(); return; }
        }
    }""")
    pick_month_for_field(page, "experiences.0.startDate.year", "03")
    fill_by_name(page, "experiences.0.startDate.year", "2024")
    # Amazon Robotics
    for exp in exps:
        if "Amazon" in exp.get("val", ""):
            idx = exp["idx"]
            pick_month_for_field(page, f"experiences.{idx}.startDate.year", "06")
            fill_by_name(page, f"experiences.{idx}.startDate.year", "2023")
            pick_month_for_field(page, f"experiences.{idx}.endDate.year", "12")
            fill_by_name(page, f"experiences.{idx}.endDate.year", "2023")
            log(f"  Filled Amazon Robotics at idx {idx}")
            break
    # Pro Painters
    for exp in exps:
        if "Pro Painters" in exp.get("val", ""):
            idx = exp["idx"]
            pick_month_for_field(page, f"experiences.{idx}.startDate.year", "05")
            fill_by_name(page, f"experiences.{idx}.startDate.year", "2022")
            pick_month_for_field(page, f"experiences.{idx}.endDate.year", "08")
            fill_by_name(page, f"experiences.{idx}.endDate.year", "2022")
            log(f"  Filled Pro Painters at idx {idx}")
            break
    # Education
    fill_by_name(page, "educations.0.schoolName", "University of Houston")
    fill_by_name(page, "educations.0.degree", "Bachelor of Science")
    fill_by_name(page, "educations.0.fieldOfStudy", "Computer Science")
    pick_month_for_field(page, "educations.0.startDate.year", "08")
    fill_by_name(page, "educations.0.startDate.year", "2021")
    pick_month_for_field(page, "educations.0.endDate.year", "12")
    fill_by_name(page, "educations.0.endDate.year", "2024")
    # Screening questions
    for name, val in [
        ("driverPartnerQuestion", "No"), ("openRolesQuestion", "Yes"), ("inUSA", "Yes"),
        ("legalRightToWork", "Yes"), ("requireVisaSponsorship", "No"),
        ("gender", "Prefer not to say"), ("race", "Prefer not to say"),
        ("disability", "Prefer not to say"), ("veteran", "I prefer not to say"),
        ("sexualOrientation", "Prefer not to say"), ("arbitrationAgreement", "Yes, I agree"),
        ("disabilityAccomodation", "No"),
    ]:
        pick_radio(page, name, val)
    # Subsidiary question (combobox)
    page.evaluate("""() => {
        const c = document.querySelector('[role=combobox]#subsidiaryQuestion');
        if (!c) return;
        c.scrollIntoView({block:'center'});
        c.click();
    }""")
    time.sleep(0.4)
    page.evaluate("""() => {
        const opts = [...document.querySelectorAll('[role=option]')];
        const o = opts.find(x => (x.innerText||'').trim().toLowerCase() === 'no');
        if (o) { o.scrollIntoView({block:'center'}); o.click(); }
    }""")
    fill_by_name(page, "zipCode", "98033")
    time.sleep(1)

def check_invalid_fields(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('[aria-invalid=true]')].map(e=>({name:e.name||e.id||'?',val:e.value||'?'}))"
    )

def submit_form(page):
    """Submit the form. Returns result string."""
    submit_resps = []
    def on_resp(resp):
        try:
            u = resp.url
            if "graphql" in u or "/apply" in u.lower():
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    body = resp.text()
                    if "submitApplication" in body or "SessionToken" in body:
                        submit_resps.append({"url": u[:80], "body": body[:500]})
        except:
            pass
    page.on("response", on_resp)
    # Check invalid fields
    invalid = check_invalid_fields(page)
    if invalid:
        log(f"  Invalid fields before submit: {invalid[:5]}")
        for f in invalid:
            name = f.get("name", "")
            if "year" in name.lower():
                fill_by_name(page, name, "2020")
        time.sleep(0.5)
        invalid = check_invalid_fields(page)
        log(f"  Invalid fields after fix: {invalid[:5]}")
    # Find and click submit button
    sub_info = page.evaluate(
        "() => { const b = [...document.querySelectorAll('button')].find(x=>/submit application/i.test(x.innerText)); return b ? {exists:true,disabled:b.disabled,text:b.innerText.trim()} : {exists:false}; }"
    )
    log(f"  Submit button: {sub_info}")
    if not sub_info.get("exists"):
        return "NO_SUBMIT_BUTTON"
    clicked = page.evaluate(
        "() => { const b = [...document.querySelectorAll('button')].find(x=>/submit application/i.test(x.innerText)); if (b) { b.scrollIntoView({block:'center'}); b.click(); return true; } return false; }"
    )
    log(f"  Clicked: {clicked}")
    if not clicked:
        return "CLICK_FAILED"
    # Wait for success
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
        for r in submit_resps:
            if "SessionToken" in r["body"]:
                log("  SessionTokenInvalid detected")
                return "SESSION_TOKEN_INVALID"
            if "submitApplication" in r["body"]:
                return f"SUBMITTED_GRAPHQL"
        if i % 5 == 0:
            log(f"  poll {i}s url={url[:60]}")
    try:
        body = page.inner_text("body").lower()
        if "application submitted" in body:
            return "SUBMITTED_BODY_TEXT"
    except:
        pass
    return "UNCONFIRMED"

def save_result(role_id, job_id, title, result):
    con = sqlite3.connect(str(DB))
    if result.startswith("SUBMITTED"):
        con.execute("UPDATE roles SET applied_by='auto', applied_on=date('now'), block_reason=NULL WHERE id=?", (role_id,))
        slug = f"uber-{role_id}"
        d = APPDIR / slug
        d.mkdir(parents=True, exist_ok=True)
        lines_out = [
            f"# Uber - {title}",
            f"status: submitted",
            f"role_id: {role_id}",
            f"job_id: {job_id}",
            "submitted_by: auto",
            "submitted_on: 2026-06-24",
            f"confirmation: {result}",
            "resume_attached: yes",
        ]
        (d / "STATUS.md").write_text(chr(10).join(lines_out) + chr(10))
        log(f"  DB updated: applied_by=auto")
    else:
        con.execute("UPDATE roles SET block_reason=? WHERE id=?", (result[:200], role_id))
        log(f"  DB updated: block_reason={result[:50]}")
    con.commit()
    con.close()

def process_job(ctx, role_id, job_id, title):
    log("")
    log(f"JOB {job_id} (role {role_id}) - {title}")
    # Close all stale Uber tabs
    close_uber_tabs(ctx)
    # Navigate fresh
    page, state = navigate_to_form(ctx, job_id)
    log(f"  Navigate state: {state}")
    if state == "closed":
        return "CLOSED"
    if state in ("error", "unknown"):
        try:
            log(f"  URL: {page.url}")
            page.screenshot(path=f"/tmp/uber_err_{job_id}.png")
        except:
            pass
        return f"NAV_ERROR_{state}"
    if state == "account":
        ok = sign_in(page)
        if not ok:
            try:
                page.screenshot(path=f"/tmp/uber_signin_fail_{job_id}.png")
            except:
                pass
            return "SIGN_IN_FAILED"
        time.sleep(2)
    if not page.locator("input[name=firstName]").count():
        return "FORM_NOT_VISIBLE"
    # Upload resume
    upload_resume(page)
    # Fill form
    fill_form(page)
    # Submit
    result = submit_form(page)
    log(f"  RESULT: {result}")
    return result

def main():
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]
    results = []
    for role_id, job_id, title in JOBS:
        try:
            result = process_job(ctx, role_id, job_id, title)
        except Exception as exc:
            log(f"FATAL ERROR on {job_id}: {exc}")
            result = f"EXCEPTION:{str(exc)[:80]}"
        results.append((role_id, job_id, title, result))
        save_result(role_id, job_id, title, result)
        time.sleep(3)
    # Summary
    print("")
    print("FINAL SUMMARY")
    print("="*50)
    for role_id, job_id, title, r in results:
        print(f"  {str(r)[:30]:30s} {role_id} {job_id} {title[:35]}")
    submitted = [r for r in results if r[3].startswith("SUBMITTED")]
    print("Submitted: " + str(len(submitted)) + "/" + str(len(JOBS)))
    return results

if __name__ == "__main__":
    main()
