"""Zscaler GH Remix submission"""
from playwright.sync_api import sync_playwright
import time, json, sys, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
import gmail_imap as g

CDP = "http://127.0.0.1:18800"
PLAN = json.load(open("output/inline-plan-zscaler-5165541007.json"))
RESUME = PLAN.get("pdf_path_staged") or PLAN.get("pdf_path_local")

OPEN_MENU_JS = """async (qid) => {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const inp = document.getElementById(qid);
    if (!inp) return "noinp";
    const ctrl = inp.closest(".select__control");
    if (!ctrl) return "noctrl";
    ctrl.scrollIntoView({block:"center"});
    const r = ctrl.getBoundingClientRect();
    const fire = (el,t,x,y) => el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));
    fire(ctrl,"mousedown",r.left+5,r.top+5); fire(ctrl,"mouseup",r.left+5,r.top+5); fire(ctrl,"click",r.left+5,r.top+5);
    await sleep(600); return "ok";
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

def pw_select(page, qid, labels):
    if isinstance(labels, str):
        labels = [labels]
    page.evaluate(OPEN_MENU_JS, qid)
    opts = page.locator(".select__option").all()
    for opt in opts:
        try:
            t = opt.text_content(timeout=3000).strip()
            for lab in labels:
                ll = lab.strip().lower()
                if ll == t.lower() or ll in t.lower():
                    opt.click()
                    time.sleep(0.3)
                    return t
        except Exception:
            pass
    page.keyboard.press("Escape")
    return None

def pw_typeahead(page, qid, type_text, match):
    page.evaluate(OPEN_MENU_JS, qid)
    time.sleep(0.2)
    page.keyboard.type(type_text)
    time.sleep(1.5)
    opts = page.locator(".select__option").all()
    for opt in opts:
        try:
            t = opt.text_content(timeout=3000)
            if match.lower() in t.lower():
                opt.click()
                time.sleep(0.3)
                return t
        except Exception:
            pass
    page.keyboard.press("Escape")
    return None

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto(PLAN["url"], wait_until="networkidle", timeout=45000)
    time.sleep(2)

    # Text fields
    for fid, val in PLAN.get("text_fields", {}).items():
        if val:
            page.evaluate(SET_VAL_JS, [fid, val])

    # Country typeahead
    r = pw_typeahead(page, "country", "United", "United States")
    print(f"Country: {r}")

    # How did you hear (multiselect) - pick "LinkedIn"
    r = pw_select(page, "question_12295061007[]", "Linkedin")
    print(f"How heard: {r}")

    # Standard dropdowns from plan
    for dd in PLAN.get("dropdowns", []):
        r = pw_select(page, dd["id"], dd["label"])
        print(f"DD {dd['id']}: {r}")

    # Needs review - visa/sponsorship
    for nr in PLAN.get("needs_review_dropdowns", []):
        # question_12295064007: work permit/visa - "No" (US citizen)
        if nr["id"] == "question_12295064007":
            r = pw_select(page, nr["id"], ["No", "United States", "Yes"])
        else:
            r = pw_select(page, nr["id"], [nr["label"]] + nr.get("alternates", []))
        print(f"NR {nr['id']}: {r}")

    # EEO demographic fields
    r = pw_select(page, "gender", "Decline To Self Identify")
    print(f"Gender: {r}")
    r = pw_select(page, "hispanic_ethnicity", "Decline To Self Identify")
    print(f"Hispanic: {r}")
    r = pw_select(page, "veteran_status", ["I don't wish to answer", "Decline"])
    print(f"Veteran: {r}")
    r = pw_select(page, "disability_status", ["I do not want to answer", "Decline"])
    print(f"Disability: {r}")

    # Phone
    piti = PLAN.get("phone_iti", {})
    if piti:
        page.evaluate("""async (args) => {
            const [id, country, digits] = args;
            const sleep = ms => new Promise(r => setTimeout(r, ms));
            const setN = (el, v) => {
                const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
                d.set.call(el, v);
                el.dispatchEvent(new Event("input", {bubbles: true}));
                el.dispatchEvent(new Event("change", {bubbles: true}));
            };
            const inp = document.getElementById(id);
            if (!inp) return;
            const iti = inp.closest(".iti");
            if (iti) {
                const flag = iti.querySelector(".iti__selected-flag");
                if (flag) {
                    flag.click(); await sleep(250);
                    const items = [...iti.querySelectorAll(".iti__country,li[class*=iti__country]")];
                    const t = items.find(li => li.textContent.toLowerCase().includes(country.toLowerCase()));
                    if (t) { t.click(); await sleep(150); }
                }
            }
            setN(inp, String(digits).replace(/[^0-9]/g, ""));
        }""", [piti["id"], piti.get("country", "United States"), piti.get("digits", "3468040227")])
        print("Phone set")

    # Resume
    if RESUME and os.path.exists(RESUME):
        rl = page.locator("#resume")
        if rl.count() > 0:
            rl.set_input_files(RESUME)
            time.sleep(1)
            print("Resume uploaded")

    # Check empty sentinels
    sentinels = page.evaluate("""() => {
        return [...document.querySelectorAll('.remix-css-1a0ro4n-requiredInput[required]')].filter(e => !e.value).length;
    }""")
    print(f"Empty sentinels: {sentinels}")

    print("Submitting...")
    since_submit = time.time()
    sub = page.locator('button:has-text("Submit application")')
    if sub.count() == 0:
        sub = page.locator("button[type=submit]")
    sub.first.click()
    time.sleep(3)

    has_otp = page.evaluate("() => !!document.getElementById('security-input-0')")
    print(f"OTP gate: {has_otp}")
    if has_otp:
        code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=5, since_epoch=since_submit)
        print(f"OTP: {code}")
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
                if btn.count() > 0:
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
                or "/confirmation" in curr_url or "application submitted" in body.lower()):
            confirmed = True
            break

    print(f"CONFIRMED: {confirmed}")
    print(f"URL: {page.url}")
    print(f"BODY: {page.inner_text('body')[:300]}")
    page.close()
    br.close()
    sys.exit(0 if confirmed else 1)
