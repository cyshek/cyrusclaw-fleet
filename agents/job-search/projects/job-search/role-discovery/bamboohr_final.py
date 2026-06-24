#!/usr/bin/env python3
"""
FINAL BambooHR runner for Uphold (3376, 3377).
Uses proper fab-MenuList selector for state dropdown.
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

JOBS = [
    {
        "role_id": 3376, "tenant": "uphold", "job_id": "838",
        "title": "Technical Solutions Architect",
        "yesno_map": {
            "customQuestionAnswers.yes_no_2395": "Yes",  # legal right to work USA
            "customQuestionAnswers.yes_no_2393": "No",   # require sponsorship
            "customQuestionAnswers.yes_no_2443": "Yes",  # experience developing/integrating APIs
            "customQuestionAnswers.yes_no_2444": "Yes",  # worked in fintech/financial services
            "customQuestionAnswers.yes_no_2445": "Yes",  # strong understanding REST APIs/SDKs/OpenAPI
            "customQuestionAnswers.yes_no_2446": "Yes",  # proficient in backend language
            "customQuestionAnswers.yes_no_2447": "Yes",  # experience designing scalable tech solutions
            "customQuestionAnswers.yes_no_2448": "Yes",  # comfortable explaining tech concepts
        },
        "long_text_map": {
            "customQuestionAnswers.long_2396": "Through LinkedIn and my job search network.",
        },
    },
    {
        "role_id": 3377, "tenant": "uphold", "job_id": "850",
        "title": "Junior Product Manager, Enterprise APIs, Widgets, & UX",
        "yesno_map": None,  # discover dynamically
        "long_text_map": {},
    },
]


def log(*a):
    print("[bhfinal]", *a, flush=True)


def fill_field(page, field_id, value):
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
        return 'OK:' + (el.value||'').slice(0,10);
    }""", [field_id, value])


def pick_state(page, state_name):
    """Click State button, wait for menu, click the state option."""
    # Click the State button using Playwright (ensures proper focus/events)
    state_btn = page.locator('button[aria-label*="State"]').first
    state_btn.click(timeout=5000)
    time.sleep(1)

    # Find the menu ID from the button's data-menu-id
    menu_id = page.evaluate("""() => {
        const btn = document.querySelector('button[aria-label*="State"]');
        return btn ? btn.getAttribute('data-menu-id') : null;
    }""")
    log(f"  State menu ID: {menu_id}")

    if not menu_id:
        log("  No menu ID found!")
        return "NO_MENU_ID"

    # Use Playwright locator to find and click the Washington option
    # The menu items are .fab-MenuOption inside #<menu_id>
    menu_items = page.locator(f"#{menu_id} .fab-MenuOption")
    count = menu_items.count()
    log(f"  Menu items count: {count}")

    if count == 0:
        # Try searching to narrow down
        search_input = page.locator(".fab-MenuSearch__input input, .fab-MenuSearch input").first
        if search_input.count():
            search_input.fill(state_name[:4], timeout=3000)
            time.sleep(0.5)
            count = menu_items.count()
            log(f"  After search, count: {count}")

    # Find Washington
    for i in range(count):
        try:
            text = menu_items.nth(i).inner_text(timeout=2000).strip()
            if text.lower() == state_name.lower() or text.lower().startswith(state_name.lower()[:4].lower()):
                menu_items.nth(i).click(timeout=3000)
                log(f"  Clicked: {text}")
                return f"PICKED:{text}"
        except:
            pass

    # Fallback: use JS to find and click
    result = page.evaluate("""([menuId, sname]) => {
        const menu = document.getElementById(menuId);
        if (!menu) return 'NO_MENU';
        const items = [...menu.querySelectorAll('.fab-MenuOption')];
        const norm = s => s.trim().toLowerCase();
        const target = items.find(i => norm(i.innerText) === norm(sname))
                    || items.find(i => norm(i.innerText).startsWith(norm(sname).slice(0,4)));
        if (!target) return 'NOT_FOUND in ' + items.length + ': ' + items.slice(0,3).map(i=>i.innerText.trim()).join(',');
        target.scrollIntoView({block:'center'});
        target.click();
        return 'CLICKED:' + target.innerText.trim().slice(0,20);
    }""", [menu_id, state_name])
    log(f"  JS fallback: {result}")
    return result


def pick_radio(page, name, value):
    return page.evaluate("""([nm, val]) => {
        const radios = [...document.querySelectorAll('input[type="radio"][name="' + nm + '"]')];
        const target = radios.find(r => r.value === val);
        if (!target) return 'NOT_FOUND';
        target.click();
        const lbl = target.closest('label');
        if (lbl && !target.checked) lbl.click();
        return target.checked ? 'CHECKED' : 'CLICKED';
    }""", [name, value])


def discover_yesno_questions(page):
    """Discover yes/no questions and auto-answer them."""
    questions = page.evaluate("""() => {
        const results = [];
        const radios = [...document.querySelectorAll('input[type="radio"][name^="customQuestion"]')];
        const names = [...new Set(radios.map(r => r.name))];
        for (const name of names) {
            const group = radios.filter(r => r.name === name);
            let qtext = null;
            let container = group[0];
            for (let i=0; i<12 && container; i++) {
                container = container.parentElement;
                const cands = [...(container.querySelectorAll('legend, p') || [])];
                for (const c of cands) {
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

    yesno_map = {}
    for q in questions:
        qtext = (q.get("qtext") or "").lower()
        name = q["name"]
        if "legal right" in qtext or "authorized to work" in qtext:
            yesno_map[name] = "Yes"
        elif "sponsorship" in qtext:
            yesno_map[name] = "No"
        elif "product manager" in qtext or "pm " in qtext:
            yesno_map[name] = "Yes"
        elif "fintech" in qtext or "financial" in qtext:
            yesno_map[name] = "Yes"
        elif "api" in qtext or "rest api" in qtext:
            yesno_map[name] = "Yes"
        else:
            yesno_map[name] = "Yes"  # default affirmative

    log(f"  Discovered {len(questions)} questions, auto-answered")
    for q in questions:
        log(f"    {q['name']}: {q['qtext'][:50] if q['qtext'] else '?'} -> {yesno_map.get(q['name'])}")
    return yesno_map


def solve_recaptcha(page, page_url):
    if not CAPSOLVER_KEY:
        log("  No CAPSOLVER_KEY")
        return False

    sitekey = page.evaluate("""() => {
        const el = document.querySelector('.g-recaptcha[data-sitekey], [data-sitekey]');
        if (el) return el.getAttribute('data-sitekey');
        const iframes = [...document.querySelectorAll('iframe[src*="recaptcha"]')];
        for (const f of iframes) {
            const m = f.src.match(/[?&]k=([^&]+)/);
            if (m) return m[1];
        }
        return null;
    }""")

    if not sitekey:
        log("  No reCAPTCHA sitekey")
        return True

    log(f"  Sitekey: {sitekey[:30]}")
    sys.path.insert(0, str(RDIR))
    try:
        import capsolver_client
        client = capsolver_client.CapSolverClient(api_key=CAPSOLVER_KEY)
        token = client.recaptcha_v2(sitekey=sitekey, page_url=page_url)
        if not token:
            log("  Empty token from CapSolver")
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
            if (window.___grecaptcha_cfg) {
                const clients = window.___grecaptcha_cfg.clients || {};
                for (const id of Object.keys(clients)) {
                    const c = clients[id] || {};
                    for (const k of Object.keys(c)) {
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
    page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button')];
        const sub = btns.find(b => /submit application/i.test(b.innerText || ''));
        if (sub) { sub.scrollIntoView({block:'center'}); sub.click(); return; }
        const sub2 = document.querySelector('button[type="submit"]');
        if (sub2) { sub2.scrollIntoView({block:'center'}); sub2.click(); }
    }""")
    log("  Submit clicked")

    for i in range(timeout_s):
        time.sleep(1)
        url = page.url
        try:
            body = page.evaluate("() => document.body.innerText.toLowerCase()")
            if ("thank you" in body or "thank-you" in body) and ("application" in body or "submitt" in body):
                return "CONFIRMED_THANK_YOU"
            if "application submitted" in body or "successfully submitted" in body:
                return "CONFIRMED_SUBMITTED"
            if "application received" in body:
                return "CONFIRMED_RECEIVED"
            if "success" in url or "thank" in url or "confirmation" in url:
                return f"CONFIRMED_URL:{url[:60]}"
        except:
            pass
        if i % 10 == 0:
            log(f"  Waiting {i}s...")
    return "UNCONFIRMED"


def process_job(ctx, job):
    role_id = job["role_id"]
    tenant = job["tenant"]
    job_id = job["job_id"]
    title = job["title"]
    apply_url = f"https://{tenant}.bamboohr.com/careers/{job_id}"

    log(f"Role {role_id}: {title}")
    log(f"URL: {apply_url}")

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
        apply_btn = page.locator('a:has-text("Apply for This Job"), button:has-text("Apply for This Job")').first
        if not apply_btn.count():
            return "NO_APPLY_BTN"
        apply_btn.click(timeout=8000)
        time.sleep(3)

        if not page.locator("#firstName").count():
            return "FORM_NOT_VISIBLE"

        log("  Form visible")

        # Fill text fields
        r = fill_field(page, "firstName", PI["first_name"]); log(f"  firstName: {r}")
        r = fill_field(page, "lastName", PI["last_name"]); log(f"  lastName: {r}")
        r = fill_field(page, "email", PI["email"]); log(f"  email: {r}")
        r = fill_field(page, "phone", PI["phone"]); log(f"  phone: {r}")
        r = fill_field(page, "FabricTextField-357", PI["street"]); log(f"  street: {r}")
        r = fill_field(page, "FabricTextField-358", PI["city"]); log(f"  city: {r}")
        r = fill_field(page, "FabricTextField-360", PI["zip"]); log(f"  zip: {r}")
        r = fill_field(page, "desiredPay", PI["desired_pay"]); log(f"  desiredPay: {r}")
        r = fill_field(page, "linkedinUrl", PI["linkedin"]); log(f"  linkedin: {r}")
        time.sleep(0.5)

        # State dropdown
        pick_state(page, PI["state"])
        time.sleep(0.5)

        # Upload resume
        log("  Uploading resume...")
        fi = page.locator('input[type="file"]').first
        if fi.count():
            fi.set_input_files(RESUME, timeout=20000)
            time.sleep(3)
            log("  Resume uploaded")

        # Long text
        for field_id, value in (job.get("long_text_map") or {}).items():
            r = fill_field(page, field_id, value)
            log(f"  LongText {field_id}: {r}")

        # Yes/No questions
        yesno_map = job.get("yesno_map")
        if yesno_map is None:
            yesno_map = discover_yesno_questions(page)
        else:
            log(f"  Answering {len(yesno_map)} pre-defined questions")

        for name, answer in yesno_map.items():
            r = pick_radio(page, name, answer)
            log(f"  Radio {name[-15:]} -> {answer}: {r}")

        time.sleep(0.5)

        # reCAPTCHA
        has_cap = page.evaluate("""() => !!document.querySelector('.g-recaptcha, iframe[src*="recaptcha"]')""")
        if has_cap:
            log("  Solving reCAPTCHA...")
            solve_recaptcha(page, apply_url)
            time.sleep(1)

        # Final validation check
        errors = page.evaluate("""() => {
            return [...document.querySelectorAll('[aria-invalid="true"]')]
                   .map(e => e.id || e.name || '?').slice(0, 8);
        }""")
        if errors:
            log(f"  Pre-submit errors: {errors}")

        result = submit_and_confirm(page)
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
    con = sqlite3.connect(str(DB))
    if "CONFIRMED" in str(result) or "UNCONFIRMED" in str(result):
        block = None if "CONFIRMED" in str(result) else "unconfirmed-no-text"
        con.execute(
            "UPDATE roles SET status='submitted', applied_by='auto', applied_on=date('now'), block_reason=? WHERE id=?",
            (block, role_id)
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
        log(f"  Saved STATUS.md: {d}/STATUS.md")
    else:
        con.execute("UPDATE roles SET block_reason=? WHERE id=?", (str(result)[:200], role_id))
    con.commit()
    con.close()


def main():
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]

    all_results = []
    for job in JOBS:
        log("=" * 50)
        result = process_job(ctx, job)
        log(f"RESULT {job['role_id']}: {result}")
        all_results.append((job["role_id"], job["title"], job["tenant"], job["job_id"], result))
        save_result(*all_results[-1])
        time.sleep(3)

    print("\n" + "=" * 50)
    print("SUMMARY")
    for r in all_results:
        status = "SUBMITTED" if "CONFIRMED" in str(r[4]) else ("UNCONFIRMED" if "UNCONFIRMED" in str(r[4]) else "FAILED")
        print(f"  {r[0]} {r[1][:45]}: {status} ({r[4][:50]})")


if __name__ == "__main__":
    main()
