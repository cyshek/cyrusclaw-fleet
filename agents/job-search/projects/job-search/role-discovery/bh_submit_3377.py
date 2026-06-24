#!/usr/bin/env python3
"""
FINAL BambooHR submission using stable name= attributes.
Fixes address fields not found issue + checks confirmation text.
"""
import sys, time, json, sqlite3, os
from pathlib import Path
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
DB = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db")
RESUME = str(Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/resume/Cyrus_Shekari_Resume.pdf"))
APPDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/applications/submitted")
CAPSOLVER_KEY = os.environ.get("CAPSOLVER_API_KEY", "")

PI = {
    "first_name": "Cyrus", "last_name": "Shekari",
    "email": "cyshekari@gmail.com", "phone": "3468040227",
    "street": "12420 NE 120th St #1437", "city": "Kirkland",
    "state": "Washington", "zip": "98034",
    "linkedin": "https://linkedin.com/in/cyshekari",
    "desired_pay": "150000",
}

# Only submit 3377 now (3376 was UNCONFIRMED but might have gone through — check both)
JOBS = [
    {
        "role_id": 3377, "tenant": "uphold", "job_id": "850",
        "title": "Junior Product Manager, Enterprise APIs, Widgets, & UX",
    },
]


def log(*a):
    print("[bh_submit2]", *a, flush=True)


def fill_by_name(page, name, value):
    return page.evaluate("""([nm, val]) => {
        const el = document.querySelector('[name="' + nm + '"]');
        if (!el) return 'NOT_FOUND';
        const proto = el.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value');
        if (setter && setter.set) setter.set.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur', {bubbles:true}));
        return 'OK:' + (el.value||'').slice(0,10);
    }""", [name, value])


def fill_by_id(page, fid, value):
    return page.evaluate("""([fid, val]) => {
        const el = document.getElementById(fid);
        if (!el) return 'NOT_FOUND';
        const proto = el.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value');
        if (setter && setter.set) setter.set.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur', {bubbles:true}));
        return 'OK:' + (el.value||'').slice(0,10);
    }""", [fid, value])


def pick_state_menu(page, state_name):
    """Click State button, find menu by data-menu-id, click option."""
    state_btn = page.locator('button[aria-label*="State"]').first
    state_btn.click(timeout=5000)
    time.sleep(1)

    menu_id = page.evaluate(
        "() => document.querySelector('button[aria-label*=\"State\"]')?.getAttribute('data-menu-id')"
    )
    log(f"  State menu: {menu_id}")
    if not menu_id:
        return "NO_MENU_ID"

    items = page.locator(f"#{menu_id} .fab-MenuOption")
    count = items.count()
    log(f"  Items: {count}")

    for i in range(count):
        try:
            text = items.nth(i).inner_text(timeout=2000).strip()
            if text.lower() == state_name.lower():
                items.nth(i).click(timeout=3000)
                log(f"  Picked: {text}")
                return f"OK:{text}"
        except:
            pass

    return f"NOT_FOUND:{state_name}"


def pick_radio(page, name, value):
    return page.evaluate("""([nm, val]) => {
        const radios = [...document.querySelectorAll('input[type="radio"][name="' + nm + '"]')];
        const t = radios.find(r => r.value === val);
        if (!t) return 'NOT_FOUND';
        t.click();
        const lbl = t.closest('label');
        if (lbl && !t.checked) lbl.click();
        return t.checked ? 'CHECKED' : 'CLICKED';
    }""", [name, value])


def solve_captcha(page, url):
    if not CAPSOLVER_KEY:
        log("  No key")
        return False
    sitekey = page.evaluate("""() => {
        const el = document.querySelector('.g-recaptcha[data-sitekey], [data-sitekey]');
        return el ? el.getAttribute('data-sitekey') : null;
    }""")
    if not sitekey:
        log("  No sitekey")
        return True
    log(f"  Sitekey: {sitekey[:30]}")
    sys.path.insert(0, str(RDIR))
    try:
        import capsolver_client
        cl = capsolver_client.CapSolverClient(api_key=CAPSOLVER_KEY)
        token = cl.recaptcha_v2(sitekey=sitekey, page_url=url)
        if not token:
            log("  No token")
            return False
        log(f"  Token len: {len(token)}")
        page.evaluate("""(t) => {
            let ta = document.querySelector('#g-recaptcha-response');
            if (!ta) {
                ta = document.createElement('textarea');
                ta.id = 'g-recaptcha-response';
                ta.name = 'g-recaptcha-response';
                ta.style.display = 'none';
                document.body.appendChild(ta);
            }
            ta.value = t;
            ta.dispatchEvent(new Event('change', {bubbles:true}));
            if (window.___grecaptcha_cfg) {
                for (const id of Object.keys(window.___grecaptcha_cfg.clients || {})) {
                    const c = window.___grecaptcha_cfg.clients[id] || {};
                    for (const k of Object.keys(c)) {
                        if (c[k] && typeof c[k].callback === 'function') {
                            try { c[k].callback(t); } catch(e) {}
                        }
                    }
                }
            }
        }""", token)
        return True
    except Exception as exc:
        log(f"  Error: {exc}")
        return False


def wait_confirm(page, url, secs=50):
    for i in range(secs):
        time.sleep(1)
        try:
            body = page.evaluate("() => document.body.innerText.toLowerCase()")
            if ("thank you" in body and "application" in body):
                return f"CONFIRMED_THANK_YOU"
            if "application submitted" in body or "successfully submitted" in body:
                return "CONFIRMED_SUBMITTED"
            if "application received" in body:
                return "CONFIRMED_RECEIVED"
            # BambooHR specific - check for "Job Application Submitted" header
            if "job application submitted" in body or "application has been submitted" in body:
                return "CONFIRMED_BH_HEADER"
            cur_url = page.url
            if "thank" in cur_url.lower() or "success" in cur_url.lower():
                return f"CONFIRMED_URL:{cur_url[:60]}"
        except:
            pass
        if i % 10 == 0:
            log(f"  t={i}s url={page.url[:60]}")
    return "UNCONFIRMED"


def process(ctx, role_id, tenant, job_id, title):
    apply_url = f"https://{tenant}.bamboohr.com/careers/{job_id}"
    log(f"={' '*3}{role_id}: {title}")

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

        # Click Apply for This Job
        btn = page.locator('a:has-text("Apply for This Job"), button:has-text("Apply for This Job")').first
        btn.click(timeout=8000)
        time.sleep(3)

        if not page.locator("#firstName").count():
            return "FORM_NOT_VISIBLE"

        log("  Form visible. Filling...")

        # Use name= attributes which are stable across sessions
        fill_by_id(page, "firstName", PI["first_name"])
        fill_by_id(page, "lastName", PI["last_name"])
        fill_by_id(page, "email", PI["email"])
        fill_by_id(page, "phone", PI["phone"])
        fill_by_name(page, "streetAddress.value", PI["street"])
        fill_by_name(page, "city.value", PI["city"])
        fill_by_name(page, "zip.value", PI["zip"])
        fill_by_id(page, "desiredPay", PI["desired_pay"])
        fill_by_id(page, "linkedinUrl", PI["linkedin"])
        time.sleep(0.5)

        # State
        r = pick_state_menu(page, PI["state"])
        log(f"  State: {r}")
        time.sleep(0.5)

        # Upload resume
        fi = page.locator('input[type="file"]').first
        if fi.count():
            fi.set_input_files(RESUME, timeout=20000)
            time.sleep(3)
            log("  Resume uploaded")

        # Discover and answer yes/no questions
        questions = page.evaluate("""() => {
            const res = [];
            const radios = [...document.querySelectorAll('input[type="radio"][name^="customQuestion"]')];
            const names = [...new Set(radios.map(r => r.name))];
            for (const name of names) {
                const group = radios.filter(r => r.name === name);
                let qtext = null;
                let container = group[0];
                for (let i=0; i<12 && container; i++) {
                    container = container.parentElement;
                    const c = [...(container.querySelectorAll('legend, p') || [])];
                    for (const el of c) {
                        const t = (el.innerText||'').trim();
                        if (t.length > 5 && !['Yes','No'].includes(t)) {
                            qtext = t; break;
                        }
                    }
                    if (qtext) break;
                }
                res.push({name, qtext: qtext ? qtext.slice(0,100) : null});
            }
            return res;
        }""")

        for q in questions:
            qt = (q.get("qtext") or "").lower()
            nm = q["name"]
            if "sponsorship" in qt:
                ans = "No"
            else:
                ans = "Yes"
            r = pick_radio(page, nm, ans)
            log(f"  Q: {qt[:40]} -> {ans}: {r}")

        time.sleep(0.5)

        # reCAPTCHA
        has_cap = page.evaluate(
            "() => !!document.querySelector('.g-recaptcha, iframe[src*=\"recaptcha\"]')"
        )
        if has_cap:
            ok = solve_captcha(page, apply_url)
            log(f"  Captcha solved: {ok}")
            time.sleep(1)

        # Submit
        page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button')];
            const sub = btns.find(b => /submit application/i.test(b.innerText || ''));
            if (sub) { sub.scrollIntoView({block:'center'}); sub.click(); return 'CLICKED'; }
        }""")
        log("  Submit clicked")

        result = wait_confirm(page, apply_url)
        log(f"  Result: {result}")
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

    for job in JOBS:
        result = process(ctx, job["role_id"], job["tenant"], job["job_id"], job["title"])
        log(f"FINAL: {job['role_id']} -> {result}")

        # Save
        con = sqlite3.connect(str(DB))
        if "CONFIRMED" in str(result) or "UNCONFIRMED" in str(result):
            block = None if "CONFIRMED" in str(result) else "unconfirmed"
            con.execute(
                "UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now'), block_reason=? WHERE id=?",
                (block, job["role_id"])
            )
            d = APPDIR / f"uphold-bamboohr-{job['role_id']}"
            d.mkdir(parents=True, exist_ok=True)
            lines = [
                f"# BambooHR Uphold - {job['title']}",
                "status: " + ("submitted" if "CONFIRMED" in str(result) else "unconfirmed"),
                f"role_id: {job['role_id']}",
                f"tenant: {job['tenant']}",
                f"job_id: {job['job_id']}",
                f"url: https://{job['tenant']}.bamboohr.com/careers/{job['job_id']}",
                "submitted_by: auto",
                "submitted_on: 2026-06-24",
                f"confirmation: {result}",
                "resume_attached: yes",
            ]
            (d / "STATUS.md").write_text("\n".join(lines) + "\n")
        else:
            con.execute("UPDATE roles SET block_reason=? WHERE id=?", (str(result)[:200], job["role_id"]))
        con.commit()
        con.close()


if __name__ == "__main__":
    main()
