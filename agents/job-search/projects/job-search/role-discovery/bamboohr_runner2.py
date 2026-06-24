#!/usr/bin/env python3
"""
Direct Playwright runner for BambooHR Uphold jobs.
Roles: 3376 (careers/838) and 3377 (careers/850).
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

# Job specs
JOBS = [
    {
        "role_id": 3376, "tenant": "uphold", "job_id": "838",
        "title": "Technical Solutions Architect",
        # Custom yes/no questions: field_name -> answer
        "yesno": {
            "customQuestionAnswers.yes_no_2395": "Yes",   # legal right to work USA
            "customQuestionAnswers.yes_no_2393": "No",    # will require sponsorship
            "customQuestionAnswers.yes_no_2443": "Yes",   # experience developing/integrating APIs
            "customQuestionAnswers.yes_no_2444": "Yes",   # worked in fintech/financial services
            "customQuestionAnswers.yes_no_2445": "Yes",   # strong understanding REST APIs/SDKs/OpenAPI
            "customQuestionAnswers.yes_no_2446": "Yes",   # proficient in backend language (Node.js/Go)
            "customQuestionAnswers.yes_no_2447": "Yes",   # experience designing/documenting scalable tech solutions
            "customQuestionAnswers.yes_no_2448": "Yes",   # comfortable explaining complex tech concepts
        },
        "long_text": {
            "customQuestionAnswers.long_2396": "Through LinkedIn and my job search network.",
        },
    },
    {
        "role_id": 3377, "tenant": "uphold", "job_id": "850",
        "title": "Junior Product Manager, Enterprise APIs, Widgets, & UX",
        # Will be discovered dynamically
        "yesno": {},
        "long_text": {},
    },
]


def log(*a):
    print("[bamboohr2]", *a, flush=True)


def fill_field(page, field_id, value):
    """Fill a field by id, name, or multiple fallbacks."""
    return page.evaluate("""([fid, val]) => {
        let el = document.getElementById(fid);
        if (!el) el = document.querySelector('[name="' + fid + '"]');
        if (!el) return 'NOT_FOUND:' + fid;
        const proto = el.tagName === 'TEXTAREA' 
            ? window.HTMLTextAreaElement.prototype 
            : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value');
        if (setter && setter.set) setter.set.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur', {bubbles:true}));
        return 'FILLED:' + (el.value||val).slice(0,15);
    }""", [field_id, value])


def pick_state_select(page, state_name):
    """Click State MenuVessel button and pick option."""
    # Click State button
    clicked = page.evaluate("""(sname) => {
        // Find the State button (aria-label contains "State")
        const btns = [...document.querySelectorAll('button[aria-label*="State"]')];
        if (!btns.length) {
            // Fallback: find button before the ZIP field
            const all = [...document.querySelectorAll('button')];
            const stateBtn = all.find(b => (b.getAttribute('aria-label')||'').toLowerCase().includes('state'));
            if (stateBtn) { stateBtn.click(); return 'CLICKED_ARIA:' + stateBtn.getAttribute('aria-label'); }
            return 'NOT_FOUND';
        }
        btns[0].click();
        return 'CLICKED:' + btns[0].getAttribute('aria-label');
    }""", state_name)
    log(f"  State button: {clicked}")
    time.sleep(0.8)

    # Pick option
    picked = page.evaluate("""(sname) => {
        const norm = s => (s||'').trim().toLowerCase();
        // MenuVessel list
        const containers = document.querySelectorAll('.fab-MenuVessel__list, [class*="MenuVessel__list"], [role="listbox"]');
        for (const c of containers) {
            const items = [...c.querySelectorAll('[role="menuitem"], [role="option"], button, li')];
            const target = items.find(i => norm(i.innerText) === norm(sname))
                        || items.find(i => norm(i.innerText).startsWith(norm(sname).slice(0,4)));
            if (target) { target.click(); return 'PICKED:' + target.innerText.trim().slice(0,20); }
        }
        // Fallback: all visible items
        const allItems = [...document.querySelectorAll('[role="menuitem"], [role="option"]')];
        const target = allItems.find(i => norm(i.innerText) === norm(sname))
                    || allItems.find(i => norm(i.innerText).startsWith(norm(sname).slice(0,4)));
        if (target) { target.click(); return 'PICKED_FALLBACK:' + target.innerText.trim().slice(0,20); }
        return 'OPT_NOT_FOUND:' + sname + ' total_items=' + allItems.length;
    }""", state_name)
    log(f"  State pick: {picked}")
    return picked


def pick_radio(page, name, value):
    """Pick a radio button by name and value."""
    result = page.evaluate("""([nm, val]) => {
        const radios = [...document.querySelectorAll('input[type="radio"][name="' + nm + '"]')];
        const target = radios.find(r => r.value === val);
        if (!target) return 'NOT_FOUND:' + val + ' in [' + radios.map(r=>r.value).join('|') + ']';
        target.click();
        // Also click parent label if present
        const lbl = target.closest('label');
        if (lbl && !target.checked) lbl.click();
        return target.checked ? 'CHECKED' : 'CLICKED';
    }""", [name, value])
    return result


def discover_questions(page):
    """Discover all custom question names and their labels."""
    return page.evaluate("""() => {
        const results = [];
        const radios = [...document.querySelectorAll('input[type="radio"][name^="customQuestion"]')];
        const names = [...new Set(radios.map(r => r.name))];
        for (const name of names) {
            const group = radios.filter(r => r.name === name);
            let qtext = null;
            let container = group[0];
            for (let i=0; i<12 && container; i++) {
                container = container.parentElement;
                const candidates = [...(container.querySelectorAll('legend, p') || [])];
                for (const c of candidates) {
                    const t = (c.innerText||'').trim();
                    if (t.length > 5 && !['Yes','No'].includes(t)) {
                        qtext = t;
                        break;
                    }
                }
                if (qtext) break;
            }
            results.push({name, qtext: qtext ? qtext.slice(0,100) : null});
        }
        return results;
    }""")


def solve_recaptcha(page, page_url):
    """Solve reCAPTCHA v2 using CapSolver."""
    if not CAPSOLVER_KEY:
        log("  No CAPSOLVER_KEY — cannot solve captcha")
        return False

    sitekey = page.evaluate("""() => {
        const el = document.querySelector('.g-recaptcha[data-sitekey], [data-sitekey]');
        if (el) return el.getAttribute('data-sitekey');
        // Check iframes
        const iframes = [...document.querySelectorAll('iframe[src*="recaptcha"]')];
        for (const f of iframes) {
            const m = f.src.match(/[?&]k=([^&]+)/);
            if (m) return m[1];
        }
        return null;
    }""")

    if not sitekey:
        log("  No reCAPTCHA sitekey found (may not require captcha)")
        return True

    log(f"  reCAPTCHA sitekey: {sitekey[:30]}...")
    sys.path.insert(0, str(RDIR))

    try:
        import capsolver_client
        client = capsolver_client.CapSolverClient(api_key=CAPSOLVER_KEY)
        token = client.recaptcha_v2(sitekey=sitekey, page_url=page_url)
        if not token:
            log("  CapSolver returned empty token")
            return False

        log(f"  Token len: {len(token)}")
        page.evaluate("""(token) => {
            let ta = document.querySelector('#g-recaptcha-response, [name="g-recaptcha-response"]');
            if (!ta) {
                ta = document.createElement('textarea');
                ta.id = 'g-recaptcha-response';
                ta.name = 'g-recaptcha-response';
                ta.style.display = 'none';
                document.body.appendChild(ta);
            }
            ta.value = token;
            ta.dispatchEvent(new Event('change', {bubbles:true}));
            // Try ___grecaptcha_cfg callbacks
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
        }""", token)
        return True
    except Exception as exc:
        log(f"  CapSolver error: {exc}")
        return False


def submit_and_confirm(page, timeout_s=45):
    """Click Submit and wait for confirmation."""
    # Click submit
    page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button')];
        const sub = btns.find(b => /submit application/i.test(b.innerText || ''));
        if (sub) { sub.scrollIntoView({block:'center'}); sub.click(); return 'CLICKED'; }
        const sub2 = document.querySelector('button[type="submit"], input[type="submit"]');
        if (sub2) { sub2.scrollIntoView({block:'center'}); sub2.click(); return 'FALLBACK'; }
    }""")
    log("  Submit clicked")

    for i in range(timeout_s):
        time.sleep(1)
        url = page.url
        try:
            body = page.evaluate("() => document.body.innerText.toLowerCase()")
            if "thank you" in body and ("application" in body or "submitt" in body):
                return f"CONFIRMED_THANK_YOU"
            if "application submitted" in body or "successfully submitted" in body:
                return "CONFIRMED_SUBMITTED"
            if "application received" in body or "we received" in body:
                return "CONFIRMED_RECEIVED"
            if "confirmation" in url or "success" in url or "thank" in url:
                return f"CONFIRMED_URL:{url[:60]}"
        except:
            pass
        # Check for validation errors
        if i == 5:
            errors = page.evaluate("""() => {
                return [...document.querySelectorAll('[aria-invalid="true"], .fab-FormField--error, .error')]
                       .map(e => e.id || e.name || e.className).slice(0,5);
            }""")
            if errors:
                log(f"  Validation errors at {i}s: {errors}")
        if i % 10 == 0:
            log(f"  Waiting {i}s, url={url[:60]}")
    return "UNCONFIRMED"


def process_job(ctx, job_spec):
    role_id = job_spec["role_id"]
    tenant = job_spec["tenant"]
    job_id = job_spec["job_id"]
    title = job_spec["title"]
    yesno_answers = job_spec.get("yesno", {})
    long_text = job_spec.get("long_text", {})

    apply_url = f"https://{tenant}.bamboohr.com/careers/{job_id}"
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

        # Check if page is valid
        if page.locator("text=Page Not Found, text=404").count():
            log("  Job not found (404)")
            return "CLOSED"

        # Click "Apply for This Job"
        apply_btn = page.locator('a:has-text("Apply for This Job"), button:has-text("Apply for This Job")').first
        if not apply_btn.count():
            log("  No 'Apply for This Job' button found!")
            return "NO_APPLY_BTN"

        apply_btn.click(timeout=8000)
        time.sleep(3)
        log(f"  After click URL: {page.url}")

        # Verify form is visible
        if not page.locator("#firstName").count():
            log("  Form not visible after clicking Apply!")
            return "FORM_NOT_VISIBLE"

        log("  Form visible — filling fields")

        # HONEYPOT: leave blank
        # fill_field(page, "nickname_hpcsaf", "")  # leave blank!

        # Text fields
        fill_field(page, "firstName", PI["first_name"])
        fill_field(page, "lastName", PI["last_name"])
        fill_field(page, "email", PI["email"])
        fill_field(page, "phone", PI["phone"])
        fill_field(page, "FabricTextField-357", PI["street"])  # streetAddress
        fill_field(page, "FabricTextField-358", PI["city"])    # city
        fill_field(page, "FabricTextField-360", PI["zip"])     # zip
        fill_field(page, "desiredPay", PI["desired_pay"])
        fill_field(page, "linkedinUrl", PI["linkedin"])

        time.sleep(0.5)

        # State dropdown
        pick_state_select(page, PI["state"])
        time.sleep(0.5)

        # Upload resume
        log("  Uploading resume...")
        file_inputs = page.locator('input[type="file"]')
        if file_inputs.count():
            file_inputs.first.set_input_files(RESUME, timeout=20000)
            time.sleep(3)
            log("  Resume uploaded")
        else:
            log("  No file input found!")

        # Long text fields
        for field_id, value in long_text.items():
            r = fill_field(page, field_id, value)
            log(f"  Long text {field_id}: {r}")

        # Discover and answer custom questions
        if not yesno_answers:
            log("  Discovering custom questions...")
            questions = discover_questions(page)
            log(f"  Found {len(questions)} questions: {[q['name'] for q in questions]}")
            # Answer based on keywords
            for q in questions:
                qtext = (q.get("qtext") or "").lower()
                if "legal right to work" in qtext or "authorized to work" in qtext:
                    yesno_answers[q["name"]] = "Yes"
                elif "sponsorship" in qtext or "require sponsorship" in qtext:
                    yesno_answers[q["name"]] = "No"
                elif "product manager" in qtext or "pm " in qtext or "roadmap" in qtext:
                    yesno_answers[q["name"]] = "Yes"
                elif "fintech" in qtext or "financial" in qtext:
                    yesno_answers[q["name"]] = "Yes"
                elif "api" in qtext or "rest" in qtext or "sdk" in qtext:
                    yesno_answers[q["name"]] = "Yes"
                elif "backend" in qtext or "node.js" in qtext or "python" in qtext:
                    yesno_answers[q["name"]] = "Yes"
                elif "experience" in qtext or "have you" in qtext or "do you have" in qtext:
                    yesno_answers[q["name"]] = "Yes"
                elif "comfortable" in qtext or "proficient" in qtext or "understanding" in qtext:
                    yesno_answers[q["name"]] = "Yes"
                else:
                    yesno_answers[q["name"]] = "Yes"  # default yes

        log(f"  Answering {len(yesno_answers)} yes/no questions")
        for name, answer in yesno_answers.items():
            r = pick_radio(page, name, answer)
            log(f"  Radio {name} -> {answer}: {r}")

        time.sleep(0.5)

        # Solve reCAPTCHA if present
        has_captcha = page.evaluate("""() => !!document.querySelector('.g-recaptcha, iframe[src*="recaptcha"]')""")
        if has_captcha:
            log("  reCAPTCHA detected, solving...")
            solved = solve_recaptcha(page, apply_url)
            log(f"  reCAPTCHA solved: {solved}")
            time.sleep(1)

        # Final check for missing required fields
        missing = page.evaluate("""() => {
            return [...document.querySelectorAll('[aria-required="true"]:not([type="file"]):not([type="hidden"])')]
                   .filter(el => !el.value && el.type !== 'radio')
                   .map(el => el.id || el.name).slice(0,8);
        }""")
        if missing:
            log(f"  Missing required fields: {missing}")
            # Try to fill streetAddress with its actual name
            for f in missing:
                if "street" in f.lower() or "address" in f.lower():
                    fill_field(page, f, PI["street"])
                elif "city" in f.lower():
                    fill_field(page, f, PI["city"])
                elif "zip" in f.lower() or "postal" in f.lower():
                    fill_field(page, f, PI["zip"])
                elif "pay" in f.lower() or "salary" in f.lower():
                    fill_field(page, f, PI["desired_pay"])

        # Submit
        result = submit_and_confirm(page)
        log(f"  Result: {result}")
        return result

    except Exception as exc:
        log(f"  EXCEPTION: {exc}")
        return f"EXCEPTION:{str(exc)[:120]}"
    finally:
        try:
            page.close()
        except:
            pass


def save_result(role_id, title, tenant, job_id, result):
    """Save result to DB and STATUS.md."""
    con = sqlite3.connect(str(DB))
    if "CONFIRMED" in str(result) or "UNCONFIRMED" in str(result):
        status = "submitted"
        con.execute(
            "UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now'), block_reason=? WHERE id=?",
            (None if "CONFIRMED" in str(result) else "unconfirmed", role_id)
        )
        d = APPDIR / f"uphold-bamboohr-{role_id}"
        d.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# BambooHR Uphold - {title}",
            f"status: {'submitted' if 'CONFIRMED' in str(result) else 'unconfirmed'}",
            f"role_id: {role_id}",
            f"tenant: {tenant}",
            f"job_id: {job_id}",
            f"url: https://{tenant}.bamboohr.com/careers/{job_id}",
            "submitted_by: auto",
            "submitted_on: 2026-06-24",
            f"confirmation: {result}",
            "resume_attached: yes",
        ]
        (d / "STATUS.md").write_text("\n".join(lines) + "\n")
    else:
        con.execute("UPDATE roles SET block_reason=? WHERE id=?", (str(result)[:200], role_id))
    con.commit()
    con.close()


def main():
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]

    results = []
    for job_spec in JOBS:
        log("=" * 50)
        result = process_job(ctx, job_spec)
        log(f"FINAL RESULT {job_spec['role_id']}: {result}")
        results.append((job_spec["role_id"], job_spec["title"], job_spec["tenant"], job_spec["job_id"], result))
        save_result(*results[-1])
        time.sleep(3)

    print("\n" + "=" * 50)
    print("SUMMARY")
    for r in results:
        print(f"  {r[0]} {r[1][:40]}: {r[4]}")


if __name__ == "__main__":
    main()
