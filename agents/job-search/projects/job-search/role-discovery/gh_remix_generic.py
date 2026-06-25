"""Generic GH Remix submitter - handles sentinel inputs via Playwright native clicks"""
from playwright.sync_api import sync_playwright
import time, json, sys, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
import gmail_imap as g

PLAN_PATH = sys.argv[1]
CDP = "http://127.0.0.1:18800"

with open(PLAN_PATH) as f:
    plan = json.load(f)

URL = plan["url"]
RESUME = plan.get("pdf_path_staged") or plan.get("pdf_path_local")

OPEN_MENU_JS = """async (qid) => {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const inp = document.getElementById(qid);
    if (!inp) return "noinp";
    const ctrl = inp.closest(".select__control");
    if (!ctrl) return "noctrl";
    ctrl.scrollIntoView({block:"center"});
    const r = ctrl.getBoundingClientRect();
    const fire = (el,t,x,y) => el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));
    fire(ctrl,"mousedown",r.left+5,r.top+5);
    fire(ctrl,"mouseup",r.left+5,r.top+5);
    fire(ctrl,"click",r.left+5,r.top+5);
    await sleep(500);
    return "ok";
}"""

SET_VAL_JS = """(args) => {
    const [id, val] = args;
    const el = document.getElementById(id);
    if (!el) return "noel";
    const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
    d.set.call(el, String(val));
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
    return el.value;
}"""

PHONE_JS = """async (args) => {
    const [id, country, digits] = args;
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const setN = (el, v) => {
        const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
        d.set.call(el, v);
        el.dispatchEvent(new Event("input", {bubbles: true}));
        el.dispatchEvent(new Event("change", {bubbles: true}));
    };
    const inp = document.getElementById(id);
    if (!inp) return {err: "nophone"};
    const iti = inp.closest(".iti");
    if (iti) {
        const flag = iti.querySelector(".iti__selected-flag");
        if (flag) {
            flag.click();
            await sleep(250);
            const items = [...iti.querySelectorAll(".iti__country,li[class*=iti__country]")];
            const t = items.find(li => li.textContent.toLowerCase().includes(country.toLowerCase()));
            if (t) { t.click(); await sleep(150); }
        }
    }
    const clean = String(digits || "").replace(/[^0-9]/g, "");
    setN(inp, clean);
    return {phone: inp.value};
}"""


def pw_fill_select(page, qid, labels):
    if isinstance(labels, str):
        labels = [labels]
    result = page.evaluate(OPEN_MENU_JS, qid)
    if result in ("noinp", "noctrl"):
        print(f"  [WARN] no select control for {qid}")
        return None
    opts = page.locator(".select__option").all()
    for opt in opts:
        try:
            text = opt.text_content(timeout=3000)
            for lab in labels:
                ll = lab.strip().lower()
                tl = text.strip().lower()
                if ll == tl or ll in tl:
                    opt.click()
                    time.sleep(0.3)
                    return text
        except Exception:
            pass
    page.keyboard.press("Escape")
    return None


def pw_typeahead(page, qid, type_text, match_text):
    result = page.evaluate(OPEN_MENU_JS, qid)
    if result in ("noinp", "noctrl"):
        return None
    time.sleep(0.2)
    page.keyboard.type(type_text)
    time.sleep(1.5)
    opts = page.locator(".select__option").all()
    for opt in opts:
        try:
            text = opt.text_content(timeout=3000)
            if match_text.lower() in text.lower():
                opt.click()
                time.sleep(0.3)
                return text
        except Exception:
            pass
    page.keyboard.press("Escape")
    return None


with sync_playwright() as p:
    br = p.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0] if br.contexts else br.new_context()
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=45000)
    time.sleep(2)

    # Fill text fields
    for fid, val in plan.get("text_fields", {}).items():
        if val and fid not in ("location",):
            page.evaluate(SET_VAL_JS, [fid, val])

    # Country / location typeaheads
    for cd in plan.get("country_dropdowns", []):
        if cd["id"] == "country":
            r = pw_typeahead(page, "country", "United", "United States")
            print(f"  Country: {r}")
        elif cd["id"] == "candidate-location":
            r = pw_typeahead(page, "candidate-location", "Kirkland", "Kirkland, Washington")
            print(f"  Location: {r}")

    # Standard dropdowns (Playwright native clicks)
    for dd in plan.get("dropdowns", []):
        r = pw_fill_select(page, dd["id"], dd["label"])
        print(f"  DD {dd['id']}: {r}")

    # Needs review dropdowns
    for nr in plan.get("needs_review_dropdowns", []):
        labels_to_try = [nr["label"]] + nr.get("alternates", [])
        r = pw_fill_select(page, nr["id"], labels_to_try)
        print(f"  NR {nr['id']}: {r}")

    # Phone ITI
    phone_iti = plan.get("phone_iti", {})
    if phone_iti:
        page.evaluate(PHONE_JS, [phone_iti["id"], phone_iti.get("country", "United States"), phone_iti.get("digits", "3468040227")])
        print("  Phone set")

    # Resume
    if RESUME and os.path.exists(RESUME):
        rl = page.locator("#resume")
        if rl.count() > 0:
            rl.set_input_files(RESUME)
            time.sleep(1)
            print("  Resume uploaded")

    # Handle export-control checkboxes (Databricks-style)
    cb_result = page.evaluate("""() => {
        const fieldsets = [...document.querySelectorAll('fieldset[id*="question_"]')];
        const clicked = [];
        for (const fs of fieldsets) {
            const checkboxes = [...fs.querySelectorAll('input[type=checkbox]')];
            if (!checkboxes.length) continue;
            const any_checked = checkboxes.some(cb => cb.checked);
            if (any_checked) continue;
            const labels = [...fs.querySelectorAll('label')];
            const target_texts = ['none of the above', 'not applicable', 'none of these'];
            for (const lab of labels) {
                const txt = lab.textContent.trim().toLowerCase();
                if (target_texts.some(t => txt.startsWith(t))) {
                    const cb = document.getElementById(lab.getAttribute('for'));
                    if (cb) {
                        cb.scrollIntoView({block:'center'});
                        cb.click();
                        clicked.push({fs: fs.id, id: lab.getAttribute('for'), text: lab.textContent.trim().slice(0,40)});
                        break;
                    }
                }
            }
        }
        return clicked;
    }""")
    if cb_result:
        print(f"  Checkboxes: {cb_result}")

    print("  Clicking Submit...")
    since_submit = time.time()
    sub_btn = page.locator('button:has-text("Submit application")')
    if sub_btn.count() == 0:
        sub_btn = page.locator("button[type=submit]")
    sub_btn.first.click()
    time.sleep(3)

    # OTP handling
    has_otp = page.evaluate("() => !!document.getElementById('security-input-0')")
    print(f"  OTP gate: {has_otp}")
    if has_otp:
        code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=5, since_epoch=since_submit)
        print(f"  OTP: {code}")
        for i, ch in enumerate(code):
            el = page.locator(f"#security-input-{i}")
            if el.count() > 0:
                el.focus()
                page.keyboard.press(ch)
                time.sleep(0.1)
        time.sleep(0.5)
        for _ in range(4):
            try:
                btn = page.locator('button:has-text("Submit application")')
                if btn.count() == 0:
                    btn = page.locator("button[type=submit]")
                if btn.count() > 0 and not btn.first.is_disabled():
                    btn.first.click()
                    break
            except Exception:
                pass
            time.sleep(1.5)

    confirmed = False
    for _ in range(12):
        time.sleep(2)
        curr_url = page.url
        body = page.inner_text("body")
        if ("thank you" in body.lower() or "received your application" in body.lower()
                or "application submitted" in body.lower() or "mappy to know" in body.lower()
                or "/confirmation" in curr_url):
            confirmed = True
            break

    print(f"\nCONFIRMED: {confirmed}")
    print(f"URL: {page.url}")
    print(f"BODY: {page.inner_text('body')[:300]}")
    page.close()
    br.close()
    sys.exit(0 if confirmed else 1)
