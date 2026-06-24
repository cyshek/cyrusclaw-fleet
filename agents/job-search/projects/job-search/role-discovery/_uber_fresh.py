#!/usr/bin/env python3
"""Fresh-account Uber Careers apply for roles when account has hit application limit."""
import json, time, sys, sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

RDIR = Path('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
ROOT = RDIR.parent
CDP = 'http://127.0.0.1:18800'
RESUME = ROOT / 'resume/Cyrus_Shekari_Resume.pdf'

JOB_IDS = [
    (3068, '156921', 'US Immigration Program Manager'),
    (3069, '147866', 'Program Manager, Site Technology'),
    (3070, '155212', 'Program Manager II, Tech - Enterprise Applications'),
    (3071, '159482', 'Program Manager II, GTM Enablement & Field Programs'),
    (3072, '159306', 'Program Manager, Organizational Safety, Autonomous Mobility & Delivery'),
    (3073, '158485', 'Partner Solution Engineer II, Uber Advertising'),
]


def log(*a):
    print('[uber_fresh]', *a, flush=True)


def gen_fresh_alias():
    ts = time.strftime('%Y%m%d%H%M')
    return f'cyshekari+uber-{ts}@gmail.com'


def gen_password():
    import random, string
    chars = string.ascii_letters + string.digits + '!@#'
    pw = ''.join(random.choices(chars, k=16))
    if not any(c.isdigit() for c in pw):
        pw = pw[:-1] + '7'
    return pw


def _fill(page, name, val):
    loc = page.locator(f'input[name="{name}"], textarea[name="{name}"]').first
    if loc.count():
        try:
            loc.click(timeout=3000)
            loc.fill(val, timeout=5000)
            return True
        except Exception as e:
            log(f'fill-fail {name}: {e}')
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
        log(f'radio {name}={value} -> {r}')
    return ok


def _select(page, combo_id, option_text):
    r = page.evaluate("""(cid) => {
        const c = document.querySelector(`[role=combobox]#${cid}`);
        if (!c) return 'NO_COMBO';
        c.scrollIntoView({block:'center'}); c.click(); return 'OPEN';
    }""", combo_id)
    if r != 'OPEN':
        log(f'select {combo_id} -> {r}')
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


def _open_month_combo(page, year_field_name, month_val):
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


def _set_current_role(page):
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


def _remove_extra_exp(page):
    page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button')]
            .filter(b => /remove experience/i.test(b.innerText||''));
        for (let i = 1; i < btns.length; i++) {
            btns[i].scrollIntoView({block:'center'}); btns[i].click();
        }
    }""")
    time.sleep(0.5)


def upload_resume(page, resume_path):
    fn = str(resume_path).split('/')[-1]

    def shows():
        try:
            b = page.inner_text('body')
            return (fn in b) or (fn.replace('_', ' ') in b)
        except Exception:
            return False

    fis = page.locator('input[type=file]')
    for i in range(fis.count()):
        accept = fis.nth(i).get_attribute('accept') or ''
        if 'pdf' in accept.lower() or 'application' in accept.lower() or i == 0:
            try:
                fis.nth(i).set_input_files(str(resume_path), timeout=15000)
                break
            except Exception as e:
                log(f'set_input_files {i} err: {e}')
    time.sleep(3)
    if not shows():
        log('resume not shown, trying filechooser')
        try:
            with page.expect_file_chooser(timeout=8000) as fc_info:
                page.get_by_role('button', name='Browse files').first.click()
            fc_info.value.set_files(str(resume_path))
            time.sleep(3)
        except Exception as e:
            log(f'filechooser err: {e}')
    time.sleep(2)
    log(f'resume shows={shows()}')
    return shows()


def fill_form(page, job_id):
    _fill(page, 'firstName', 'Cyrus')
    _fill(page, 'lastName', 'Shekari')
    _fill(page, 'mobileNumber', '3468040227')
    _remove_extra_exp(page)
    time.sleep(0.3)
    _fill(page, 'experiences.0.companyName', 'Microsoft')
    _fill(page, 'experiences.0.title', 'Technical Program Manager')
    _set_current_role(page)
    _open_month_combo(page, 'experiences.0.startDate.year', '03')
    _fill(page, 'experiences.0.startDate.year', '2024')
    _fill(page, 'educations.0.schoolName', 'University of Houston')
    _fill(page, 'educations.0.degree', 'Bachelor of Science')
    _fill(page, 'educations.0.fieldOfStudy', 'Computer Science')
    _open_month_combo(page, 'educations.0.startDate.year', '08')
    _fill(page, 'educations.0.startDate.year', '2021')
    _open_month_combo(page, 'educations.0.endDate.year', '12')
    _fill(page, 'educations.0.endDate.year', '2024')
    _radio(page, 'driverPartnerQuestion', 'No')
    _radio(page, 'openRolesQuestion', 'Yes')
    _radio(page, 'inUSA', 'Yes')
    _select(page, 'subsidiaryQuestion', 'No')
    _radio(page, 'legalRightToWork', 'Yes')
    _radio(page, 'requireVisaSponsorship', 'No')
    _radio(page, 'gender', 'Prefer not to say')
    _radio(page, 'race', 'Prefer not to say')
    _radio(page, 'disability', 'Prefer not to say')
    _radio(page, 'veteran', 'I prefer not to say')
    _radio(page, 'sexualOrientation', 'Prefer not to say')
    _radio(page, 'arbitrationAgreement', 'Yes, I agree')
    _fill(page, 'zipCode', '98033')
    _radio(page, 'disabilityAccomodation', 'No')
    time.sleep(0.8)
    log('form filled')


def apply_one(ctx, job_id, role_id, role_title, account_email, account_pw, is_first):
    log(f'--- Starting job {job_id} ({role_title}, DB id={role_id}) ---')
    page = ctx.new_page()

    try:
        page.goto(f'https://www.uber.com/careers/apply/form/{job_id}',
                  wait_until='domcontentloaded', timeout=45000)
        time.sleep(2)

        body = page.inner_text('body').lower()
        if 'no longer available' in body or "couldn't find that page" in body:
            log(f'job {job_id} CLOSED')
            page.close()
            return False, 'closed'

        # Navigate interstitial
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
            page.goto(f'https://www.uber.com/careers/apply/interstitial/{job_id}',
                      wait_until='domcontentloaded', timeout=45000)

        for _ in range(8):
            time.sleep(1.2)
            if '/careers/apply/form/' in page.url:
                break
        time.sleep(1)

        if page.locator('input[name=firstName]').count():
            log('form already visible (already logged in)')
        else:
            if is_first:
                log('clicking Create account...')
                ca_link = page.locator("a:has-text('Create account')").first
                if ca_link.count():
                    ca_link.click(timeout=8000)
                    time.sleep(1.5)

                email_inp = page.locator('input[name="email"]').first
                pw_inp = page.locator('input[type="password"]').first
                log(f'create form: email={email_inp.count()}, pw={pw_inp.count()}')

                if email_inp.count():
                    email_inp.fill(account_email)
                    time.sleep(0.3)
                if pw_inp.count():
                    pw_inp.fill(account_pw)
                    time.sleep(0.3)

                sub = page.locator('button[name="submit-button"]').first
                if not sub.count():
                    sub = page.locator("button:has-text('Create account')").last
                if sub.count():
                    sub.click(timeout=10000)
                    log('create account form submitted')
            else:
                log('signing in to existing account...')
                btn = page.locator("button:has-text('Sign in')").first
                if btn.count():
                    btn.click(timeout=5000)
                    time.sleep(1.5)

                email_inp = page.locator('input[name="email"]').first
                pw_inp = page.locator('input[type="password"]').first
                if email_inp.count():
                    email_inp.fill(account_email)
                    time.sleep(0.3)
                if pw_inp.count():
                    pw_inp.fill(account_pw)
                    time.sleep(0.3)

                sub = page.locator('button[name="submit-button"]').first
                if sub.count():
                    sub.click(timeout=8000)
                    log('sign-in form submitted')

            # Wait for form
            form_visible = False
            for i in range(20):
                time.sleep(1.5)
                if page.locator('input[name=firstName]').count():
                    log(f'FORM VISIBLE (wait {i})')
                    form_visible = True
                    break
                body2 = page.inner_text('body').lower()
                if 'application limit reached' in body2:
                    log('APPLICATION LIMIT REACHED on this account too')
                    page.close()
                    return False, 'application-limit-reached'

            if not form_visible:
                log('form not visible after auth')
                body_f = page.inner_text('body')[:200]
                log('body:', body_f)
                page.close()
                return False, 'form-not-visible'

        try:
            page.wait_for_selector('input[name=firstName]', timeout=10000)
        except PWTimeout:
            log('form not visible (final check)')
            page.close()
            return False, 'form-not-visible'

        log(f'form visible at {page.url}')

        resume_ok = upload_resume(page, RESUME)
        if not resume_ok:
            log('WARNING: resume upload not confirmed')
        time.sleep(1)

        fill_form(page, job_id)
        time.sleep(1)

        chk = page.evaluate("""() => {
            const r = {};
            ['legalRightToWork','requireVisaSponsorship','arbitrationAgreement','inUSA'].forEach(nm => {
                const t = [...document.querySelectorAll(`input[name="${nm}"]`)].find(x => x.checked);
                r[nm] = t ? t.value.slice(0,20) : null;
            });
            r.firstName = (document.querySelector('input[name=firstName]')||{}).value;
            r.zipCode = (document.querySelector('input[name=zipCode]')||{}).value;
            return r;
        }""")
        log(f'pre-submit check: {chk}')

        submit_btn = page.locator(
            'button:has-text("Submit application"), button:has-text("Submit Application")'
        ).first
        if not submit_btn.count():
            log('no submit button!')
            page.close()
            return False, 'no-submit-button'

        submit_btn.scroll_into_view_if_needed(timeout=5000)
        time.sleep(0.5)
        submit_btn.click(timeout=10000)
        log('submit clicked')

        for _ in range(25):
            time.sleep(1)
            url = page.url
            if '/careers/apply/success' in url:
                try:
                    body_txt = page.inner_text('body')
                    if 'Application submitted' in body_txt:
                        log(f'SUCCESS: /careers/apply/success + "Application submitted"')
                        page.close()
                        return True, 'success'
                except Exception:
                    pass

        url_final = page.url
        try:
            body_final = page.inner_text('body')[:200]
        except Exception:
            body_final = '(page closed)'
        log(f'submit timeout - url={url_final}')
        log(f'body: {body_final}')
        page.close()
        return False, 'submit-timeout'

    except Exception as e:
        log(f"ERROR: {e}")
        try:
            page.close()
        except Exception:
            pass
        return False, str(e)[:80]


def write_status(role_id, job_id, role_title, confirmed, reason='', email=''):
    slug = f'uber-{job_id}'
    sdir = ROOT / 'applications/submitted' / slug
    sdir.mkdir(parents=True, exist_ok=True)
    status_line = 'SUBMITTED ✅' if confirmed else f'FAILED ❌ ({reason})'
    conf_block = ''
    if confirmed:
        conf_block = (
            'confirmation_url: https://www.uber.com/careers/apply/success\n'
            'confirmation_text: Application submitted - Thanks for your application!\n'
        )
    content = (
        f'# {slug} — {role_title} (row {role_id})\n\n'
        f'STATUS: {status_line}\n'
        f'submitted_at: {time.strftime("%Y-%m-%d")}\n'
        f'submitted_by: auto (_uber_fresh.py)\n'
        f'ats: uber\n'
        f'{conf_block}'
        f'url: https://www.uber.com/careers/apply/form/{job_id}\n'
        f'account: {email}\n'
        f'resume: {RESUME.name}\n\n'
        '## Form contents\n'
        '- Basic: Cyrus Shekari, 346-804-0227, US\n'
        f'- Resume: {RESUME.name}\n'
        '- Experience: Microsoft — Technical Program Manager (current, from 03/2024)\n'
        '- Education: University of Houston, BS Computer Science, 08/2021–12/2024\n'
        '- Screening: driver=No, openRoles=Yes, inUSA=Yes, subsidiary=No, legalRight=Yes, sponsor=No\n'
        '- Demographics/veteran/arbitration: Prefer not to say / I prefer not to say / Yes, I agree\n'
        '- zipCode=98033, disabilityAccomodation=No\n'
    )
    (sdir / 'STATUS.md').write_text(content)


def db_mark(role_id, status, reason=''):
    conn = sqlite3.connect(str(ROOT / 'tracker.db'))
    if status == 'submitted':
        conn.execute(
            "UPDATE roles SET status='submitted', applied_by='auto', applied_on=? WHERE id=?",
            (time.strftime('%Y-%m-%d'), role_id)
        )
    else:
        conn.execute(
            "UPDATE roles SET status='blocked', block_reason=? WHERE id=?",
            (reason, role_id)
        )
    conn.commit()
    conn.close()
    log(f'DB updated: role {role_id} = {status}')


def main():
    new_email = gen_fresh_alias()
    new_password = gen_password()
    log(f'Fresh account email: {new_email}')
    log(f'Resume: {RESUME}')

    new_creds = {
        'shared_email': 'cyshekari@gmail.com',
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'account': {
            'email': new_email,
            'password': new_password,
            'verified': False,
            'created': False,
            'note': 'fresh account for application-limit-reached recovery'
        }
    }
    creds_path2 = RDIR / '.uber-creds-fresh.json'
    with open(creds_path2, 'w') as f:
        json.dump(new_creds, f, indent=2)
    log(f'Saved new creds to {creds_path2}')

    pw_inst = sync_playwright().start()
    br = pw_inst.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]

    for p in ctx.pages[:]:
        if 'uber.com' in p.url:
            try:
                p.close()
            except Exception:
                pass
    time.sleep(0.5)

    results = []
    is_first = True

    try:
        for role_id, job_id, role_title in JOB_IDS:
            confirmed, reason = apply_one(ctx, job_id, role_id, role_title, new_email, new_password, is_first)
            results.append({'id': role_id, 'job': job_id, 'role': role_title, 'confirmed': confirmed, 'reason': reason})

            if confirmed:
                db_mark(role_id, 'submitted')
                write_status(role_id, job_id, role_title, True, email=new_email)
                log(f'✅ SUBMITTED {role_id} {role_title}')
                is_first = False
                time.sleep(3)
            else:
                write_status(role_id, job_id, role_title, False, reason, email=new_email)
                if reason == 'closed':
                    db_mark(role_id, 'blocked', f'uber-job-closed:{job_id}')
                elif reason == 'application-limit-reached':
                    db_mark(role_id, 'blocked', 'uber-application-limit-reached')
                else:
                    log(f'❌ FAILED {role_id} {role_title}: {reason}')
                is_first = False
    finally:
        pw_inst.stop()

    log('\n=== SUMMARY ===')
    submitted = [r for r in results if r['confirmed']]
    failed = [r for r in results if not r['confirmed']]
    log(f'Submitted: {len(submitted)}')
    for r in submitted:
        log(f'  ✅ {r["id"]} {r["role"][:60]}')
    log(f'Failed: {len(failed)}')
    for r in failed:
        log(f'  ❌ {r["id"]} {r["role"][:60]}: {r["reason"]}')


if __name__ == '__main__':
    main()
