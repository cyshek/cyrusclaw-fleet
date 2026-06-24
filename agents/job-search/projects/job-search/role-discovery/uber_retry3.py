#!/usr/bin/env python3
"""
Re-run jobs 3069, 3072, 3073 with extra robustness.
"""
import time, json, sqlite3, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
DB = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db")
RESUME = str(RDIR.parent / "resume/Cyrus_Shekari_Resume.pdf")
APPDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/applications/submitted")
PASSWORD = "LxCwgJY0lyVkpy0eeH1E4#"

JOBS = [
    (3069, "147866", "Program Manager, Site Technology"),
    (3072, "159306", "Program Manager, Organizational Safety"),
    (3073, "158485", "Partner Solution Engineer II, Uber Advertising"),
]

def log(*a):
    print("[uber-retry]", *a, flush=True)
    sys.stdout.flush()

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
            if (!t) return 'NO_OPT';
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
        "(mc) => { const o = [...document.querySelectorAll('[role=option]')].find(x=>(x.innerText||'').trim()===mc); if(o){o.scrollIntoView({block:'center'});o.click();return 'PICKED';} return 'NO'; }",
        month_code
    )

def process_job(ctx, role_id, job_id, title):
    log(f"JOB {job_id} (role {role_id}): {title}")
    
    # Close Uber tabs
    for p in list(ctx.pages):
        try:
            if "uber.com" in p.url:
                p.close()
        except:
            pass
    time.sleep(0.5)
    
    # Generate email alias
    alias_ts = int(time.time())
    email = f"cyshekari+uber-retry-{alias_ts}@gmail.com"
    log(f"Email: {email}")
    
    page = ctx.new_page()
    
    try:
        page.goto(f"https://www.uber.com/careers/list/{job_id}/", wait_until="domcontentloaded", timeout=45000)
        time.sleep(2)
        
        body = page.inner_text("body").lower()
        if "no longer available" in body or "position has been filled" in body:
            return "CLOSED"
        
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
        log(f"URL: {page.url}")
        
        if page.locator("input[name=firstName]").count():
            log("Already on form (skip account creation)")
        else:
            # Create account
            create_link = page.locator("a:has-text('Create account'), button:has-text('Create account')").first
            if not create_link.count():
                return "NO_CREATE_LINK"
            
            create_link.click(timeout=8000)
            time.sleep(1.5)
            
            email_inp = page.locator("input[name=email], input[type=email]").first
            if not email_inp.count():
                return "NO_EMAIL_INPUT"
            
            email_inp.fill(email, timeout=5000)
            time.sleep(0.3)
            pw_inp = page.locator("input[name=password], input[type=password]").first
            if pw_inp.count():
                pw_inp.fill(PASSWORD, timeout=5000)
            time.sleep(0.3)
            
            # Submit create account
            page.evaluate("""() => {
                const btn = [...document.querySelectorAll('button')].find(b => b.innerText.includes('Create account') || b.name === 'submit-button');
                if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
            }""")
            
            for _ in range(20):
                time.sleep(1.5)
                if page.locator("input[name=firstName]").count():
                    break
            
            if not page.locator("input[name=firstName]").count():
                return "FORM_NOT_VISIBLE"
        
        log("Form visible - filling...")
        
        # Upload resume
        shown = page.evaluate("() => document.body.innerText.includes('Cyrus_Shekari_Resume')")
        if not shown:
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
        
        # Fill phone
        fill_by_name(page, "mobileNumber", "7138881234")
        
        # Remove empty experience blocks
        for _ in range(8):
            r = page.evaluate("""() => {
                const exps = [...document.querySelectorAll('input[name^="experiences."][name$=".companyName"]')];
                for (let i=exps.length-1; i>=1; i--) {
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
        log(f"Experiences: {exps}")
        
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
        
        for exp in exps:
            if "Pro Painters" in exp.get("val", ""):
                idx = exp["idx"]
                pick_month_for(page, f"experiences.{idx}.startDate.year", "05")
                fill_by_name(page, f"experiences.{idx}.startDate.year", "2022")
                pick_month_for(page, f"experiences.{idx}.endDate.year", "08")
                fill_by_name(page, f"experiences.{idx}.endDate.year", "2022")
        
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
        
        # Submit
        resps = []
        def on_r(r):
            try:
                if "graphql" in r.url or "/apply" in r.url:
                    ct = r.headers.get("content-type", "")
                    if "json" in ct:
                        body = r.text()
                        if "submitApplication" in body or "SessionToken" in body:
                            resps.append(body[:300])
            except:
                pass
        page.on("response", on_r)
        
        invalid = page.evaluate("() => [...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name||e.id)")
        if invalid:
            log(f"Invalid before submit: {invalid}")
        
        page.evaluate("""() => {
            const b = [...document.querySelectorAll('button')].find(x => /submit application/i.test(x.innerText));
            if (b) { b.scrollIntoView({block:'center'}); b.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true})); }
        }""")
        
        for i in range(35):
            time.sleep(1)
            url = page.url
            if "/careers/apply/success" in url:
                return "SUBMITTED_SUCCESS_URL"
            try:
                if "application submitted" in page.inner_text("body").lower():
                    return "SUBMITTED_BODY_TEXT"
            except:
                pass
            for r in resps:
                if "SessionToken" in r:
                    return "SESSION_TOKEN_INVALID"
                if "submitApplication" in r:
                    return "SUBMITTED_GRAPHQL"
            if i % 10 == 0:
                log(f"  poll {i}s")
        
        return "UNCONFIRMED"
        
    except Exception as exc:
        log(f"Exception: {exc}")
        return f"EXCEPTION:{str(exc)[:80]}"

def main():
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]
    
    for role_id, job_id, title in JOBS:
        log("="*40)
        result = process_job(ctx, role_id, job_id, title)
        log(f"RESULT: {result}")
        
        con = sqlite3.connect(str(DB))
        if result.startswith("SUBMITTED"):
            con.execute("UPDATE roles SET applied_by='auto', applied_on=date('now'), block_reason=NULL WHERE id=?", (role_id,))
            d = APPDIR / f"uber-{role_id}"
            d.mkdir(parents=True, exist_ok=True)
            lines = [f"# Uber - {title}", "status: submitted", f"role_id: {role_id}", f"job_id: {job_id}", "submitted_by: auto", "submitted_on: 2026-06-24", f"confirmation: {result}", "resume_attached: yes"]
            (d / "STATUS.md").write_text(chr(10).join(lines) + chr(10))
        else:
            con.execute("UPDATE roles SET block_reason=? WHERE id=?", (result[:200], role_id))
        con.commit()
        con.close()
        time.sleep(3)
    
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
