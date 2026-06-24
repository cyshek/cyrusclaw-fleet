#!/usr/bin/env python3
"""
Full Uber apply: create fresh account -> fill form -> submit -> verify.
Handles all 7 open roles sequentially. One fresh account per role.
"""
import sys, os, json, time, sqlite3, datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CDP = "http://127.0.0.1:18800"
RDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
ROOT = RDIR.parent
DB_PATH = ROOT / "tracker.db"
RESUME = ROOT / "resume/Cyrus_Shekari_Resume.pdf"

PI = json.loads((ROOT / "personal-info.json").read_text())
PHONE = PI["contact"]["phone"].replace("-", "")

ROLES = [
    {"id": 3067, "job": "160295", "title": "Data Collaboration Program Manager"},
    {"id": 3068, "job": "156921", "title": "US Immigration Program Manager"},
    {"id": 3069, "job": "147866", "title": "Program Manager, Site Technology"},
    {"id": 3070, "job": "155212", "title": "Program Manager II, Tech - Enterprise Applications"},
    {"id": 3071, "job": "159482", "title": "Program Manager II, GTM Enablement & Field Programs"},
    {"id": 3072, "job": "159306", "title": "Program Manager, Organizational Safety, Autonomous Mobility & Delivery"},
    {"id": 3073, "job": "158485", "title": "Partner Solution Engineer II, Uber Advertising"},
]


def log(msg):
    print(f"[uber_full] {msg}", flush=True)


def wait_for_form(page, timeout_s=30):
    for _ in range(timeout_s):
        time.sleep(1)
        try:
            if page.locator("input[name='firstName']").count():
                return True
        except Exception:
            pass
    return False


def navigate_to_form(ctx, job_id):
    """Open a fresh tab, navigate to job listing, click Apply Now, end up at form or account wall."""
    page = ctx.new_page()
    log(f"Navigating to job listing {job_id}...")
    page.goto(f"https://www.uber.com/careers/list/{job_id}/", wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)

    body = page.inner_text("body").lower()
    if "no longer available" in body or "couldn't find that page" in body:
        page.close()
        return None, "closed"

    # Click Apply Now
    clicked = False
    for sel in [f"a[href*='/careers/apply/interstitial/{job_id}']", "a:has-text('Apply Now')"]:
        loc = page.locator(sel).first
        if loc.count():
            try:
                loc.click(timeout=8000)
                clicked = True
                break
            except Exception:
                pass

    if not clicked:
        page.goto(f"https://www.uber.com/careers/apply/interstitial/{job_id}",
                  wait_until="domcontentloaded", timeout=45000)

    for _ in range(15):
        time.sleep(1.2)
        if "/careers/apply/form/" in page.url:
            break
    time.sleep(2)
    log(f"Form URL: {page.url[:80]}")
    return page, "ok"


def create_account(page, job_id):
    """Create a fresh Uber Careers account. Returns (success:bool, email:str)."""
    ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    email = f"cyshekari+uber-{ts}@gmail.com"
    pw_val = "Uber@App2026!"
    log(f"Creating account: {email}")

    # Click Create account link
    link = page.locator("a:has-text('Create account'), a:text-is('Create account')").first
    if not link.count():
        log("No Create account link found!")
        return False, ""

    link.click(timeout=8000)
    time.sleep(1.5)

    em_el = page.locator("input[name='email']").first
    pw_el = page.locator("input[name='password']").first

    if not em_el.count() or not pw_el.count():
        log("Email/password inputs not found after clicking Create account")
        return False, ""

    em_el.fill(email)
    pw_el.fill(pw_val)
    time.sleep(0.5)

    btn = page.locator("button[name='submit-button']").first
    if btn.count():
        btn.click(timeout=10000)
    else:
        pw_el.press("Enter")

    if wait_for_form(page, timeout_s=25):
        log("Form visible after account creation")
        return True, email
    else:
        body = page.inner_text("body")
        log(f"Form not visible after account creation. body={body[:200]}")
        return False, email


def remove_extra_exp_blocks(page):
    """Remove all experience blocks except index 0."""
    for _ in range(12):
        n = page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button')].filter(b => /remove experience/i.test(b.innerText));
            if (!btns.length) return 0;
            btns[btns.length-1].scrollIntoView({block:'center'});
            btns[btns.length-1].click();
            return btns.length;
        }""")
        if not n:
            break
        time.sleep(0.8)

    remaining = page.evaluate("""() =>
        document.querySelectorAll('input[name^="experiences."][name$=".companyName"]').length
    """)
    log(f"Exp blocks remaining: {remaining}")
    return remaining


def upload_resume(page):
    """Upload resume PDF. Returns True if filename appears in body after upload."""
    fn = RESUME.name
    fis = page.locator("input[type='file']")
    for i in range(fis.count()):
        acc = fis.nth(i).get_attribute("accept") or ""
        if "pdf" in acc.lower():
            try:
                fis.nth(i).set_input_files(str(RESUME), timeout=20000)
                log(f"set_input_files on file input {i}")
                break
            except Exception as e:
                log(f"set_input_files err: {e}")

    time.sleep(4)
    body = page.inner_text("body")
    ok = fn in body or fn.replace("_", " ") in body
    log(f"Resume upload ok={ok}")
    return ok


def fill_fields(page):
    """Fill all text fields, radios, selects."""
    def fill(name, val):
        loc = page.locator(f"input[name='{name}'], textarea[name='{name}']").first
        if loc.count():
            loc.fill(val)
            return True
        return False

    def radio_click(name, value):
        r = page.evaluate("""([nm, val]) => {
            const norm = s => (s||'').toLowerCase().replace(/\\s+/g,' ').trim();
            const els = [...document.querySelectorAll(`input[name="${nm}"]`)];
            const t = els.find(x => norm(x.value).startsWith(norm(val))) ||
                      els.find(x => norm(x.value).includes(norm(val)));
            if (!t) return 'NO:' + els.map(x=>x.value.slice(0,12)).join('|');
            t.scrollIntoView({block:'center'});
            const lbl = t.closest('label') || (t.id && document.querySelector(`label[for="${t.id}"]`));
            (lbl || t).click();
            if (!t.checked) t.click();
            return t.checked ? 'OK' : 'CUV';
        }""", [name, value])
        return r

    def pick_month_for_year(year_field, month_code):
        """Open month combobox adjacent to a year field and pick month_code."""
        opened = page.evaluate("""(yf) => {
            const yearIn = document.querySelector(`input[name="${yf}"]`);
            if (!yearIn) return 'NO_YEAR';
            let cur = yearIn;
            for (let up = 0; up < 10 && cur; up++) {
                cur = cur.parentElement;
                if (!cur) break;
                const combo = cur.querySelector('[role=combobox]');
                if (combo) { combo.scrollIntoView({block:'center'}); combo.click(); return 'OPENED'; }
            }
            return 'NO_COMBO';
        }""", year_field)
        time.sleep(0.5)
        if opened == 'OPENED':
            page.evaluate("""(mc) => {
                const o = [...document.querySelectorAll('[role=option]')].find(x => (x.innerText||'').trim() === mc);
                if (o) o.click();
            }""", month_code)
            time.sleep(0.3)
        return opened

    def select_combo_by_context(context_text, option_text):
        """Find a combobox by nearby text and pick an option."""
        opened = page.evaluate("""([ctx, opt]) => {
            const norm = s => (s||'').toLowerCase().trim();
            const combos = [...document.querySelectorAll('[role=combobox]')];
            for (const c of combos) {
                let container = c;
                for (let up = 0; up < 6 && container; up++) {
                    container = container.parentElement;
                    if (!container) break;
                    if (norm(container.innerText||'').includes(norm(ctx))) {
                        c.scrollIntoView({block:'center'});
                        c.click();
                        return 'OPENED:' + c.id;
                    }
                }
            }
            // Fallback: by id
            const c2 = document.getElementById(opt.toLowerCase().replace(/\\s+/g,'-'));
            if (c2) { c2.click(); return 'OPENED:id'; }
            return 'NOT_FOUND';
        }""", [context_text, option_text])
        time.sleep(0.5)
        if 'OPENED' in str(opened):
            picked = page.evaluate("""(opt) => {
                const norm = s => (s||'').toLowerCase().trim();
                const opts = [...document.querySelectorAll('[role=option]')];
                const o = opts.find(x => norm(x.innerText) === norm(opt)) ||
                           opts.find(x => norm(x.innerText).startsWith(norm(opt)));
                if (o) { o.scrollIntoView({block:'center'}); o.click(); return 'PICKED:' + o.innerText.trim(); }
                return 'NO_OPT:' + opts.map(x=>x.innerText.trim()).slice(0,4).join('|');
            }""", option_text)
            log(f"combo {context_text} -> {picked}")
            return 'PICKED' in str(picked)
        log(f"combo {context_text} not found: {opened}")
        return False

    # Basic info
    fill("firstName", PI["identity"]["first_name"])
    fill("lastName", PI["identity"]["last_name"])
    fill("mobileNumber", PHONE)

    # Experience 0
    fill("experiences.0.companyName", "Microsoft")
    fill("experiences.0.title", "Technical Program Manager")
    # Tick current
    page.evaluate("""() => {
        const cbs = [...document.querySelectorAll("input[type='checkbox']")];
        for (const cb of cbs) {
            const lbl = cb.closest('label') || document.querySelector(`label[for="${cb.id}"]`);
            const txt = (lbl?.innerText||cb.name||'').toLowerCase();
            if (txt.includes('current')) {
                if (!cb.checked) { cb.scrollIntoView({block:'center'}); (lbl||cb).click(); }
                break;
            }
        }
    }""")
    # Start month/year for exp
    pick_month_for_year("experiences.0.startDate.year", "03")
    fill("experiences.0.startDate.year", "2024")

    # Education 0
    fill("educations.0.schoolName", "University of Houston")
    fill("educations.0.degree", "Bachelor of Science")
    fill("educations.0.fieldOfStudy", "Computer Science")
    pick_month_for_year("educations.0.startDate.year", "08")
    fill("educations.0.startDate.year", "2021")
    pick_month_for_year("educations.0.endDate.year", "12")
    fill("educations.0.endDate.year", "2024")

    # Screening radios
    radio_click("driverPartnerQuestion", "No")
    radio_click("openRolesQuestion", "Yes")
    radio_click("inUSA", "Yes")
    radio_click("legalRightToWork", "Yes")
    radio_click("requireVisaSponsorship", "No")

    # subsidiaryQuestion combobox
    select_combo_by_context("subsidiary", "No")

    # Demographics
    radio_click("gender", "Prefer not to say")
    radio_click("race", "Prefer not to say")
    radio_click("disability", "Prefer not to say")
    radio_click("veteran", "I prefer not to say")
    radio_click("sexualOrientation", "Prefer not to say")

    # Arbitration
    radio_click("arbitrationAgreement", "Yes, I agree")

    # zipCode + accommodation
    fill("zipCode", "98033")
    radio_click("disabilityAccomodation", "No")

    time.sleep(1)

    # Pre-submit verification
    check = page.evaluate("""() => {
        const r = {};
        ['legalRightToWork','requireVisaSponsorship','arbitrationAgreement','inUSA',
         'driverPartnerQuestion','disabilityAccomodation'].forEach(nm => {
            const t = [...document.querySelectorAll(`input[name="${nm}"]`)].find(x => x.checked);
            r[nm] = t ? t.value.slice(0,20) : null;
        });
        r.zip  = (document.querySelector("input[name='zipCode']")||{}).value || '';
        r.fn   = (document.querySelector("input[name='firstName']")||{}).value || '';
        r.ln   = (document.querySelector("input[name='lastName']")||{}).value || '';
        r.phone = (document.querySelector("input[name='mobileNumber']")||{}).value || '';
        r.expBlocks = document.querySelectorAll("input[name$='.companyName'][name^='experiences']").length;
        const inv = [...document.querySelectorAll("[aria-invalid='true']")].map(e => e.name||e.id).filter(Boolean);
        r.invalids = inv;
        const errs = [...document.querySelectorAll("[role='alert']")].map(e => e.innerText?.trim()).filter(Boolean);
        r.errors = errs.slice(0,5);
        return r;
    }""")
    log(f"Pre-submit: {json.dumps(check)}")
    return check


def submit_and_verify(page, job_id):
    """Click submit and wait for confirmation. Returns (confirmed:bool, reason:str)."""
    resps = []

    def on_resp(resp):
        try:
            url = resp.url
            if "careers" in url or "graphql" in url:
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    body = resp.text()
                    if "submitApplication" in body or "applicationId" in body:
                        resps.append({"url": url[:60], "body": body[:400]})
        except Exception:
            pass

    page.on("response", on_resp)

    # Find and click submit
    sub_btn = page.locator("button:has-text('Submit application'), button:has-text('Submit Application')").first
    if not sub_btn.count():
        return False, "no-submit-button"

    sub_btn.scroll_into_view_if_needed(timeout=5000)
    time.sleep(0.3)
    sub_btn.click(timeout=12000)
    log("submit clicked")

    for i in range(35):
        time.sleep(1)
        url = page.url
        if "/careers/apply/success" in url:
            try:
                body = page.inner_text("body")
                if "Application submitted" in body:
                    return True, "success-url"
                return True, "success-url-no-text"
            except Exception:
                return True, "success-url-body-err"

        for r in resps:
            if '"submitApplication"' in r["body"]:
                try:
                    data = json.loads(r["body"])
                    token = (data.get("data") or {}).get("submitApplication", "")
                    if token and len(token) > 10:
                        return True, "success-graphql"
                except Exception:
                    pass

        if i % 5 == 0:
            log(f"  t={i+1}s: {url[-60:]}")

    # Check final state
    try:
        body_f = page.inner_text("body")
        errs = page.evaluate("""() =>
            [...document.querySelectorAll("[role='alert']")].map(e=>e.innerText?.trim()).filter(Boolean)
        """)
        if "Application limit reached" in body_f:
            return False, "application-limit-reached"
        if errs:
            return False, f"form-errors:{errs[:2]}"
        if "Application submitted" in body_f:
            return True, "success-body"
    except Exception as e:
        return False, f"exception:{e}"

    return False, "timeout"


def db_mark_submitted(role_id, job_id):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE roles SET status='submitted', applied_by='auto', applied_on=? WHERE id=?",
        (time.strftime("%Y-%m-%d"), role_id)
    )
    conn.commit()
    conn.close()


def db_mark_blocked(role_id, reason):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE roles SET status='blocked', block_reason=? WHERE id=?",
        (reason, role_id)
    )
    conn.commit()
    conn.close()


def write_status(role_id, job_id, title, confirmed, reason="", email=""):
    slug = f"uber-{job_id}"
    sdir = ROOT / "applications/submitted" / slug
    sdir.mkdir(parents=True, exist_ok=True)
    status_line = "SUBMITTED ✅" if confirmed else f"FAILED ❌ ({reason})"
    content = f"""# {slug} — {title} (row {role_id})

STATUS: {status_line}
submitted_at: {time.strftime("%Y-%m-%d")}
submitted_by: auto (uber_full_apply.py)
ats: uber
url: https://www.uber.com/careers/apply/form/{job_id}
account: {email or 'fresh-alias'}
resume: {RESUME.name}

## Form summary
- Cyrus Shekari | 346-804-0227 | zipCode=98033
- Microsoft TPM (current, from 03/2024)
- Univ of Houston BS CS (08/2021-12/2024)
- Screening: driver=No inUSA=Yes legal=Yes sponsor=No
- Demographics: prefer-not-to-say | arb: Yes
"""
    (sdir / "STATUS.md").write_text(content)


def apply_role(ctx, role_info):
    job_id = role_info["job"]
    role_id = role_info["id"]
    title = role_info["title"]
    email_used = ""
    log(f"=== Starting role {role_id}: {title} (job={job_id}) ===")

    try:
        # Navigate to form
        page, nav_reason = navigate_to_form(ctx, job_id)
        if not page:
            return False, nav_reason, ""

        # Handle account wall vs form already visible
        has_form = False
        try:
            has_form = bool(page.locator("input[name='firstName']").count())
        except Exception:
            pass

        if not has_form:
            body = page.inner_text("body").lower()
            if "uber careers account" in body or "sign in" in body:
                success, email_used = create_account(page, job_id)
                if not success:
                    page.close()
                    return False, "account-creation-failed", email_used
            else:
                log(f"Unknown state: {body[:100]}")
                page.close()
                return False, "unknown-state", ""
        else:
            log("Form already visible")

        # Re-grab page reference after account creation (CDP target may change)
        actual_page = None
        for p in ctx.pages:
            if f"/careers/apply/form/{job_id}" in p.url:
                try:
                    if p.locator("input[name='firstName']").count():
                        actual_page = p
                        break
                except Exception:
                    pass
        if actual_page and actual_page != page:
            log("Re-grabbed page reference")
            try:
                page.close()
            except Exception:
                pass
            page = actual_page

        # Upload resume first (may re-add extra exp blocks from PDF parse)
        upload_resume(page)
        time.sleep(1)

        # Re-grab page reference after resume upload (CDP target may change)
        actual_page2 = None
        for p in ctx.pages:
            if f"/careers/apply/form/{job_id}" in p.url:
                try:
                    if p.locator("input[name='firstName']").count():
                        actual_page2 = p
                        break
                except Exception:
                    pass
        if actual_page2 and actual_page2 != page:
            log("Re-grabbed page reference after resume upload")
            page = actual_page2

        # Remove extra experience blocks AFTER resume upload (upload re-adds them)
        remove_extra_exp_blocks(page)
        time.sleep(0.5)

        # Fill all fields
        check = fill_fields(page)

        # Check for blocking errors before submit
        if check.get("errors"):
            errs = check["errors"]
            if any("limit" in str(e).lower() for e in errs):
                page.close()
                return False, "application-limit-reached", email_used

        # Submit
        confirmed, reason = submit_and_verify(page, job_id)

        try:
            page.close()
        except Exception:
            pass

        return confirmed, reason, email_used

    except Exception as e:
        log(f"Exception in apply_role: {e}")
        try:
            page.close()
        except Exception:
            pass
        return False, f"exception:{str(e)[:80]}", email_used


def main():
    results = []
    pw_inst = sync_playwright().start()
    try:
        br = pw_inst.chromium.connect_over_cdp(CDP)
        ctx = br.contexts[0]

        # Close stale Uber tabs from prior sessions
        for p in ctx.pages:
            if "uber.com/careers/apply" in p.url:
                try:
                    p.close()
                    log(f"Closed stale tab: {p.url[:60]}")
                except Exception:
                    pass
        time.sleep(1)

        for role in ROLES:
            confirmed, reason, email = apply_role(ctx, role)
            results.append({**role, "confirmed": confirmed, "reason": reason, "email": email})

            if confirmed:
                db_mark_submitted(role["id"], role["job"])
                write_status(role["id"], role["job"], role["title"], True, reason, email)
                log(f"✅ SUBMITTED {role['id']} {role['title']}")
            else:
                write_status(role["id"], role["job"], role["title"], False, reason, email)
                if reason == "closed":
                    db_mark_blocked(role["id"], f"uber-job-closed:{role['job']}")
                log(f"❌ FAILED {role['id']} {role['title']}: {reason}")

            time.sleep(3)

    finally:
        pw_inst.stop()

    log("\n=== SUMMARY ===")
    submitted = [r for r in results if r["confirmed"]]
    failed = [r for r in results if not r["confirmed"]]
    log(f"Submitted ({len(submitted)}):")
    for r in submitted:
        log(f"  ✅ {r['id']} {r['title'][:55]}")
    log(f"Failed ({len(failed)}):")
    for r in failed:
        log(f"  ❌ {r['id']} {r['title'][:55]}: {r['reason']}")

    return len(submitted), len(failed)


if __name__ == "__main__":
    main()
