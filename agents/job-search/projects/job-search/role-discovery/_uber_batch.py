#!/usr/bin/env python3
"""Integrated Uber batch submitter.
One-shot: new tab -> sign-in -> upload -> fill -> fix -> submit -> verify.
Uses datacenter CDP 127.0.0.1:18800. Keeps fresh session for each job.
Usage: python3 _uber_batch.py [job_id ...]  (all open roles if no args)
"""
import sys, json, time, os, sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

RDIR = Path(__file__).parent
ROOT = RDIR.parent
DB_PATH = ROOT / "tracker.db"
RESUME = ROOT / "resume/Cyrus_Shekari_Resume.pdf"
CDP = "http://127.0.0.1:18800"

def log(*a):
    print("[uber_batch]", *a, flush=True)

# ------------------------------------------------------------------ helpers

def _fill(page, name, val, clear=True):
    loc = page.locator(f'input[name="{name}"], textarea[name="{name}"]').first
    if loc.count():
        try:
            if clear:
                loc.click(timeout=3000)
            loc.fill(val, timeout=5000)
            return True
        except Exception as e:
            log(f"fill-fail {name}: {e}")
    return False

def _radio(page, name, value):
    r = page.evaluate("""([nm, val]) => {
        const norm = s => (s||'').replace(/\\s+/g,' ').trim().toLowerCase();
        const rs = [...document.querySelectorAll(`input[name="${nm}"]`)];
        let t = rs.find(x => norm(x.value).startsWith(norm(val)))
              || rs.find(x => norm(x.value).includes(norm(val)));
        if (!t) return 'NO_OPT:' + rs.map(x => x.value).slice(0,4).join('|');
        t.scrollIntoView({block:'center'});
        const lbl = t.closest('label') || (t.id ? document.querySelector(`label[for="${t.id}"]`) : null);
        (lbl || t).click();
        if (!t.checked) t.click();
        return t.checked ? 'OK' : 'CLICKED_UNVERIFIED';
    }""", [name, value])
    ok = str(r).startswith('OK') or r == 'CLICKED_UNVERIFIED'
    if not ok:
        log(f"radio {name}={value} -> {r}")
    return ok

def _select(page, combo_id, option_text):
    r = page.evaluate("""(cid) => {
        const c = document.querySelector(`[role=combobox]#${cid}`);
        if (!c) return 'NO_COMBO';
        c.scrollIntoView({block:'center'}); c.click(); return 'OPEN';
    }""", combo_id)
    if r != 'OPEN':
        log(f"select {combo_id} -> {r}")
        return False
    time.sleep(0.5)
    r2 = page.evaluate("""(opt) => {
        const norm = s => (s||'').replace(/\\s+/g,' ').trim().toLowerCase();
        const opts = [...document.querySelectorAll('[role=option]')];
        const o = opts.find(x => norm(x.innerText) === norm(opt))
               || opts.find(x => norm(x.innerText).includes(norm(opt)));
        if (o) { o.scrollIntoView({block:'center'}); o.click(); return 'PICKED'; }
        return 'NO_OPT:' + opts.map(x => (x.innerText||'').trim()).slice(0,4).join('|');
    }""", option_text)
    return str(r2).startswith('PICKED')

def _remove_extra_exp_blocks(page):
    """Remove all experience blocks except index 0, re-querying after each removal."""
    for _ in range(10):
        removed = page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button')]
                .filter(b => /remove experience/i.test(b.innerText||''));
            if (btns.length >= 1) {
                // Remove the LAST one (avoid stale DOM issues)
                btns[btns.length - 1].scrollIntoView({block:'center'});
                btns[btns.length - 1].click();
                return true;
            }
            return false;
        }""")
        if not removed:
            break
        time.sleep(0.5)

def _set_current_role(page):
    """Tick 'Current role' checkbox for experiences.0."""
    page.evaluate("""() => {
        const anchor = document.querySelector('input[name="experiences.0.companyName"]');
        if (!anchor) return;
        let cur = anchor;
        for (let up = 0; up < 10 && cur; up++) {
            cur = cur.parentElement;
            if (!cur) break;
            const cb = cur.querySelector('input[type=checkbox]');
            if (cb) {
                if (!cb.checked) { cb.scrollIntoView({block:'center'}); (cb.closest('label')||cb).click(); }
                return;
            }
        }
    }""")

def _open_month_combo_for(page, year_field_name, month_val):
    """Open the month combobox adjacent to the year field and pick month_val."""
    page.evaluate("""(yearName) => {
        const anchor = document.querySelector(`input[name="${yearName}"]`);
        if (!anchor) return;
        let cur = anchor;
        for (let up = 0; up < 8 && cur; up++) {
            cur = cur.parentElement;
            const combos = [...cur.querySelectorAll('[role=combobox]')];
            if (combos.length > 0) { combos[0].scrollIntoView({block:'center'}); combos[0].click(); return; }
        }
    }""", year_field_name)
    time.sleep(0.4)
    page.evaluate("""(m) => {
        const o = [...document.querySelectorAll('[role=option]')].find(x => (x.innerText||'').trim() === m);
        if (o) { o.click(); }
    }""", month_val)
    time.sleep(0.3)

def upload_resume(page, resume_path):
    fn = os.path.basename(resume_path)

    def shows():
        try:
            b = page.inner_text("body")
            return (fn in b) or (fn.replace('_', ' ') in b)
        except Exception:
            return False

    fis = page.locator('input[type=file]')
    for i in range(fis.count()):
        if "pdf" in (fis.nth(i).get_attribute("accept") or "").lower():
            try:
                fis.nth(i).set_input_files(resume_path, timeout=15000)
                break
            except Exception as e:
                log(f"set_input_files err: {e}")
    time.sleep(3)
    if not shows():
        log("resume not shown after set_input_files, trying filechooser")
        try:
            with page.expect_file_chooser(timeout=8000) as fc_info:
                page.get_by_role("button", name="Browse files").first.click()
            fc_info.value.set_files(resume_path)
            time.sleep(3)
        except Exception as e:
            log(f"filechooser err: {e}")
    time.sleep(2)
    log(f"resume shows={shows()}")
    return shows()

def fill_form(page, job_id):
    """Fill all form fields after resume upload."""
    _fill(page, "firstName", "Cyrus")
    _fill(page, "lastName", "Shekari")
    _fill(page, "mobileNumber", "3468040227")

    # Remove junk blocks first
    _remove_extra_exp_blocks(page)
    time.sleep(0.3)

    # Experience 0: Microsoft TPM
    _fill(page, "experiences.0.companyName", "Microsoft")
    _fill(page, "experiences.0.title", "Technical Program Manager")
    _set_current_role(page)
    _open_month_combo_for(page, "experiences.0.startDate.year", "03")
    _fill(page, "experiences.0.startDate.year", "2024")

    # Education 0
    _fill(page, "educations.0.schoolName", "University of Houston")
    _fill(page, "educations.0.degree", "Bachelor of Science")
    _fill(page, "educations.0.fieldOfStudy", "Computer Science")
    _open_month_combo_for(page, "educations.0.startDate.year", "08")
    _fill(page, "educations.0.startDate.year", "2021")
    _open_month_combo_for(page, "educations.0.endDate.year", "12")
    _fill(page, "educations.0.endDate.year", "2024")

    # Screening
    _radio(page, "driverPartnerQuestion", "No")
    _radio(page, "openRolesQuestion", "Yes")
    _radio(page, "inUSA", "Yes")
    _select(page, "subsidiaryQuestion", "No")
    _radio(page, "legalRightToWork", "Yes")
    _radio(page, "requireVisaSponsorship", "No")

    # Demographics
    _radio(page, "gender", "Prefer not to say")
    _radio(page, "race", "Prefer not to say")
    _radio(page, "disability", "Prefer not to say")
    _radio(page, "veteran", "I prefer not to say")
    _radio(page, "sexualOrientation", "Prefer not to say")

    # Arbitration
    _radio(page, "arbitrationAgreement", "Yes, I agree")

    # zipCode + disabilityAccomodation
    _fill(page, "zipCode", "98033")
    _radio(page, "disabilityAccomodation", "No")

    time.sleep(0.8)
    log("form filled")

def create_account_fresh(page, email, password):
    """Create a new Uber Careers account and wait for form. Returns 'form' or 'failed'."""
    # Click Create account link
    ca = page.locator("a:has-text('Create account')").first
    if ca.count():
        try:
            ca.click(timeout=8000)
            time.sleep(1.5)
        except Exception as e:
            log(f"create-account click error: {e}")
    # Fill email
    email_inp = page.locator('input[name="email"], input[type="email"]').first
    if not email_inp.count():
        log("no email input for create account")
        return "failed"
    email_inp.fill(email, timeout=5000)
    time.sleep(0.3)
    # Fill password
    pw_inp = page.locator('input[type="password"]').first
    if not pw_inp.count():
        log("no password input for create account")
        return "failed"
    pw_inp.fill(password, timeout=5000)
    time.sleep(0.3)
    # Submit
    sub = page.locator('button[name="submit-button"]').first
    if not sub.count():
        sub = page.locator("button:has-text('Create account')").last
    if sub.count():
        sub.click(timeout=10000)
        log("create account submitted")
    # Wait for form
    for _ in range(20):
        time.sleep(1.5)
        if page.locator("input[name=firstName]").count():
            log("created account -> form visible")
            return "form"
        body = page.inner_text("body").lower()
        if "application limit" in body:
            log("application limit on new account")
            return "limit"
    log(f"create-account timeout, url={page.url}")
    return "failed"


def sign_in_fresh(page, email, password, job_id):
    """Sign in to Uber Careers account. Returns 'form' or 'failed'."""
    # Try clicking Sign in
    for _ in range(3):
        btn = page.locator("button:has-text('Sign in')").first
        if btn.count():
            try:
                btn.click(timeout=5000)
                time.sleep(1.5)
                break
            except Exception:
                pass
        time.sleep(1)

    # Fill email
    email_inp = page.locator('input[name="email"], input[type="email"]').first
    if not email_inp.count():
        log("no email input found")
        return "failed"
    email_inp.fill(email, timeout=5000)
    time.sleep(0.3)

    # Fill password
    pw_inp = page.locator('input[name="password"], input[type="password"]').first
    if not pw_inp.count():
        log("no password input found")
        return "failed"
    pw_inp.fill(password, timeout=5000)
    time.sleep(0.3)

    # Submit sign-in — use dialog-scoped selector to avoid clicking wrong button
    # The modal has [role=dialog] button[type=submit] as the correct target
    # .last on page-level was hitting a blank-text submit outside the dialog
    submitted = page.evaluate("""() => {
        const dialog = document.querySelector('[role=dialog]');
        if (dialog) {
            const btn = dialog.querySelector('button[type=submit]');
            if (btn) { btn.click(); return 'clicked-dialog'; }
        }
        // fallback: find the 'Sign in' labeled submit button
        const subs = [...document.querySelectorAll('button[type=submit]')];
        const mBtn = subs.find(b => b.innerText.trim() === 'Sign in');
        if (mBtn) { mBtn.click(); return 'clicked-signin-text'; }
        return 'no-submit-found';
    }""")
    log(f"sign-in submit click: {submitted}")
    if submitted == 'no-submit-found':
        log("no submit button found for sign-in")
        return "failed"

    # Wait for form — also check for backend-outage error in console or DOM
    for _ in range(20):
        time.sleep(1.2)
        if page.locator("input[name=firstName]").count():
            log("signed in -> form visible")
            return "form"
        url = page.url
        if "/careers/apply/form/" in url:
            try:
                page.wait_for_selector("input[name=firstName]", timeout=8000)
                return "form"
            except Exception:
                pass
        body = page.inner_text("body").lower()
        if "captcha" in body or "verify" in body:
            log("captcha/verify detected after sign-in")
            return "captcha"
        # Detect Uber backend outage: modal stays open + sign-in button still present = API failed
        # The modal doesn't dismiss when TchannelDeclinedError occurs
        dialog_still_open = page.evaluate("() => !!document.querySelector('[role=dialog]')")
        signin_wall_still_visible = "uber careers account" in body and "sign in" in body
        if dialog_still_open and signin_wall_still_visible:
            log("sign-in modal still open after submit — backend error (TchannelDeclined or similar)")
            return "backend-outage"

    log(f"sign-in timeout, url={page.url}")
    return "failed"

def apply_one_role(ctx, job_id, role_id, role_title, email, password, do_create=False):
    """Apply to one Uber role. Returns (confirmed:bool, reason:str)."""
    log(f"--- Starting job {job_id} ({role_title}, DB id={role_id}) ---")
    page = ctx.new_page()

    try:
        # Navigate directly to the apply form (skip /list/ which can lose CDP context)
        page.goto(f"https://www.uber.com/careers/apply/form/{job_id}",
                  wait_until="domcontentloaded", timeout=45000)
        time.sleep(2)

        try:
            body = page.inner_text("body").lower()
        except Exception as e:
            log(f"body read failed (page may have closed): {e}")
            page.close()
            return False, "page-closed-on-nav"
        if "no longer available" in body or "couldn't find that page" in body:
            log(f"job {job_id} is CLOSED")
            page.close()
            return False, "closed"

        # Click Apply Now -> interstitial -> form
        clicked = False
        for sel in [f"a[href*='/careers/apply/interstitial/{job_id}']",
                    "a:has-text('Apply Now')", "text=Apply Now"]:
            loc = page.locator(sel).first
            if loc.count():
                try:
                    loc.click(timeout=8000)
                    clicked = True
                    break
                except Exception:
                    continue

        if not clicked:
            page.goto(f"https://www.uber.com/careers/apply/interstitial/{job_id}",
                      wait_until="domcontentloaded", timeout=45000)

        # Follow redirects to form
        for _ in range(12):
            time.sleep(1.2)
            u = page.url
            if "/careers/apply/form/" in u:
                break
        time.sleep(2)

        # Check if form is visible (already signed in) or account wall
        if page.locator("input[name=firstName]").count():
            log("form visible without login (cookie still active)")
        elif (page.locator("button:has-text('Sign in')").count()
              or page.locator("text=Uber Careers account").count()):
            if do_create:
                log("account wall detected, creating new account")
                result = create_account_fresh(page, email, password)
            else:
                log("account wall detected, signing in")
                result = sign_in_fresh(page, email, password, job_id)
            if result != "form":
                log(f"auth failed: {result}")
                page.close()
                return False, f"signin-{result}"
        else:
            # Navigate directly to form
            log("navigating directly to apply form")
            page.goto(f"https://www.uber.com/careers/apply/form/{job_id}",
                      wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)
            if not page.locator("input[name=firstName]").count():
                body2 = page.inner_text("body")
                log(f"form still not visible after direct nav, body={body2[:150]}")
                page.close()
                return False, "form-not-visible"

        # Make sure we're on the form
        try:
            page.wait_for_selector("input[name=firstName]", timeout=10000)
        except PWTimeout:
            log("form not visible after all attempts")
            page.close()
            return False, "form-not-visible"

        log(f"form visible at {page.url}")

        # Upload resume (this may reset some fields — fill after)
        resume_ok = upload_resume(page, str(RESUME))
        if not resume_ok:
            log("WARNING: resume upload not confirmed by filename check")
        time.sleep(1)

        # Fill all fields
        fill_form(page, job_id)
        time.sleep(1)

        # Final check before submit
        chk = page.evaluate("""() => {
            const r = {};
            ['legalRightToWork','requireVisaSponsorship','arbitrationAgreement','inUSA'].forEach(nm => {
                const t = [...document.querySelectorAll(`input[name="${nm}"]`)].find(x => x.checked);
                r[nm] = t ? t.value.slice(0,20) : null;
            });
            r.zip = (document.querySelector('input[name="zipCode"]')||{}).value;
            r.firstName = (document.querySelector('input[name="firstName"]')||{}).value;
            r.expYear = (document.querySelector('input[name="experiences.0.startDate.year"]')||{}).value;
            r.eduEndYear = (document.querySelector('input[name="educations.0.endDate.year"]')||{}).value;
            r.eduEndDisabled = (document.querySelector('input[name="educations.0.endDate.year"]')||{}).disabled;
            r.subText = (document.querySelector('[role=combobox]#subsidiaryQuestion')||{}).innerText;
            // First experience month combo text
            const allCombos = [...document.querySelectorAll('[role=combobox]')].map(c => (c.innerText||'').trim().slice(0,20));
            r.allCombos = allCombos;
            return r;
        }""")
        log(f"pre-submit check: {chk}")

        # Find and click Submit
        submit_responses = []
        def on_resp(resp):
            if 'graphql' in resp.url or '/apply' in resp.url:
                try:
                    ct = resp.headers.get('content-type', '')
                    if 'json' in ct:
                        body_txt = resp.text()
                        if 'submitApplication' in body_txt or '"success"' in body_txt.lower():
                            submit_responses.append(body_txt)
                except Exception:
                    pass
        page.on('response', on_resp)

        submit_btn = page.locator(
            'button:has-text("Submit application"), button:has-text("Submit Application")'
        ).first
        if not submit_btn.count():
            log("no submit button found!")
            page.close()
            return False, "no-submit-button"

        submit_btn.scroll_into_view_if_needed(timeout=5000)
        time.sleep(0.5)
        submit_btn.click(timeout=10000)
        log("submit clicked")

        # Wait for success
        for _ in range(25):
            time.sleep(1)
            url = page.url
            if _ == 1:
                # Check for validation errors
                errs = page.evaluate("""() => {
                    const msgs = [...document.querySelectorAll('[aria-live], [role=alert], [class*=toast], [class*=Toast], [class*=error], [class*=Error]')]
                        .map(e => (e.innerText||'').trim()).filter(t => t.length>1 && t.length<200);
                    const inv = [...document.querySelectorAll('[aria-invalid=\"true\"]')]
                        .map(e => e.name||e.placeholder||e.id);
                    return {msgs: [...new Set(msgs)].slice(0,5), invalidFields: inv.slice(0,10)};
                }""")
                log(f"post-submit errors: {errs}")
                page.screenshot(path=f'/tmp/uber_submit_{job_id}.png')
            if '/careers/apply/success' in url:
                try:
                    body_txt = page.inner_text("body")
                    if 'Application submitted' in body_txt:
                        log(f"SUCCESS confirmed: /careers/apply/success + 'Application submitted'")
                        page.close()
                        return True, "success"
                except Exception:
                    pass
            # Check graphql response
            for r_txt in submit_responses:
                if '"submitApplication"' in r_txt:
                    try:
                        data = json.loads(r_txt)
                        token = data.get('data', {}).get('submitApplication', '')
                        if token and len(token) > 10:
                            log(f"SUCCESS: graphql submitApplication token confirmed")
                            page.close()
                            return True, "success"
                    except Exception:
                        pass

        url_final = page.url
        body_final = page.inner_text("body")[:200]
        log(f"submit timeout - url={url_final}, body={body_final}")
        page.close()
        return False, "submit-timeout"

    except Exception as e:
        log(f"ERROR in apply_one_role: {e}")
        try:
            page.close()
        except Exception:
            pass
        return False, str(e)[:80]


def db_mark_submitted(role_id, job_id):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE roles SET status='submitted', applied_by='auto', applied_on=? WHERE id=?",
        (time.strftime("%Y-%m-%d"), role_id)
    )
    conn.commit()
    conn.close()
    log(f"DB updated: role {role_id} = submitted")


def db_mark_blocked(role_id, reason):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE roles SET status='blocked', block_reason=? WHERE id=?",
        (reason, role_id)
    )
    conn.commit()
    conn.close()
    log(f"DB updated: role {role_id} = blocked ({reason})")


def write_status(role_id, job_id, role_title, confirmed, reason=""):
    slug = f"uber-{job_id}"
    sdir = ROOT / "applications/submitted" / slug
    sdir.mkdir(parents=True, exist_ok=True)
    status_line = "SUBMITTED ✅" if confirmed else f"FAILED ❌ ({reason})"
    content = f"""# {slug} — {role_title} (row {role_id})

STATUS: {status_line}
submitted_at: {time.strftime("%Y-%m-%d")}
submitted_by: auto (_uber_batch.py)
ats: uber
url: https://www.uber.com/careers/apply/form/{job_id}
account: .uber-creds.json (cyshekari+wd-uber-202606081753@gmail.com alias)
resume: {RESUME.name}

## Form contents
- Basic: Cyrus Shekari, 346-804-0227, US
- Resume: {RESUME.name}
- Experience: Microsoft — Technical Program Manager (current, from 03/2024)
- Education: University of Houston, BS Computer Science, 08/2021–12/2024
- Screening: driver=No, openRoles=Yes, inUSA=Yes, subsidiary=No, legalRight=Yes, sponsor=No
- Demographics/veteran/arbitration: Prefer not to say / I prefer not to say / Yes, I agree
- zipCode=98033, disabilityAccomodation=No
"""
    (sdir / "STATUS.md").write_text(content)


def main():
    force_signin = '--signin' in sys.argv
    if force_signin:
        sys.argv.remove('--signin')
    fresh_path = RDIR / ".uber-creds-fresh.json"
    creds_file = fresh_path if fresh_path.exists() else RDIR / ".uber-creds.json"
    creds = json.load(open(creds_file))["account"]
    email = creds["email"]
    pw_val = creds["password"]
    log(f"account: {email}")
    log(f"resume: {RESUME}")

    # Get roles from DB or argv
    if len(sys.argv) > 1:
        job_ids = sys.argv[1:]
        # Look up role info
        conn = sqlite3.connect(str(DB_PATH))
        roles = []
        for jid in job_ids:
            row = conn.execute(
                "SELECT id, role FROM roles WHERE source_key LIKE ?",
                (f"%uber.com/careers/list/{jid}%",)
            ).fetchone()
            if row:
                roles.append({"id": row[0], "job": jid, "role": row[1]})
            else:
                roles.append({"id": 0, "job": jid, "role": f"Uber job {jid}"})
        conn.close()
    else:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("""
            SELECT id, role, source_key FROM roles
            WHERE source_key LIKE '%uber.com%'
              AND status NOT IN ('applied','submitted','closed','skip')
              AND (applied_by IS NULL OR applied_by='')
            ORDER BY id
        """).fetchall()
        conn.close()
        roles = []
        for row in rows:
            job_id = row[2].rstrip('/').split('/')[-1]
            roles.append({"id": row[0], "job": job_id, "role": row[1]})

    log(f"Roles to submit: {len(roles)}")
    for r in roles:
        log(f"  {r['id']} job={r['job']} {r['role']}")

    results = []
    pw_inst = sync_playwright().start()
    try:
        br = pw_inst.chromium.connect_over_cdp(CDP)
        ctx = br.contexts[0]

        for i, role in enumerate(roles):
            do_create = (i == 0) and creds_file == RDIR / ".uber-creds-fresh.json" and not force_signin
            confirmed, reason = apply_one_role(
                ctx, role["job"], role["id"], role["role"], email, pw_val,
                do_create=do_create
            )
            results.append({**role, "confirmed": confirmed, "reason": reason})

            if confirmed:
                db_mark_submitted(role["id"], role["job"])
                write_status(role["id"], role["job"], role["role"], True)
                log(f"✅ SUBMITTED {role['id']} {role['role']}")
            else:
                write_status(role["id"], role["job"], role["role"], False, reason)
                if reason in ("closed",):
                    db_mark_blocked(role["id"], f"uber-job-closed:{role['job']}")
                elif reason.startswith("signin-captcha"):
                    db_mark_blocked(role["id"], "uber-captcha-signin")
                elif reason == "signin-backend-outage":
                    db_mark_blocked(role["id"], "uber-backend-outage-tchannel-declined-2026-06-30")
                    log(f"⚠️  BACKEND OUTAGE on {role['id']} — Uber careers tchannel service down, retry later")
                else:
                    log(f"❌ FAILED {role['id']} {role['role']}: {reason}")
            
            # Brief pause between submissions
            if confirmed:
                time.sleep(4)

    finally:
        pw_inst.stop()

    log("\n=== SUMMARY ===")
    submitted = [r for r in results if r["confirmed"]]
    failed = [r for r in results if not r["confirmed"]]
    log(f"Submitted: {len(submitted)}")
    for r in submitted:
        log(f"  ✅ {r['id']} {r['role'][:60]}")
    log(f"Failed: {len(failed)}")
    for r in failed:
        log(f"  ❌ {r['id']} {r['role'][:60]}: {r['reason']}")
    return len(submitted), len(failed)


if __name__ == "__main__":
    main()
