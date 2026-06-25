"""Cato Networks GH Remix submission"""
from playwright.sync_api import sync_playwright
import time, json, sys, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
import gmail_imap as g

CDP = "http://127.0.0.1:18800"
PLAN = json.load(open("output/inline-plan-cato-networks-4898418101.json"))
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

    # How did you hear - multiselect, pick "LinkedIn"
    r = pw_select(page, "question_9115805101[]", "LinkedIn")
    print(f"How heard: {r}")

    # Standard dropdowns
    # question_9115806101: "I agree" (privacy policy)
    r = pw_select(page, "question_9115806101", "I agree")
    print(f"Privacy: {r}")

    # question_9115807101: Visa support - "No" (US citizen, no visa needed)
    r = pw_select(page, "question_9115807101", "No")
    print(f"Visa: {r}")

    # question_9115809101: Comfortable with demos - "Yes"
    r = pw_select(page, "question_9115809101", "Yes")
    print(f"Demos: {r}")

    # question_9115810101: RFI/RFP experience - "Yes"
    r = pw_select(page, "question_9115810101", "Yes")
    print(f"RFP: {r}")

    # question_9115811101: 4+ years pre-sales - "Yes"
    r = pw_select(page, "question_9115811101", "Yes")
    print(f"4yr presales: {r}")

    # question_9115812101: LAN/WAN hands-on - "Yes"
    r = pw_select(page, "question_9115812101", "Yes")
    print(f"LAN/WAN: {r}")

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
                or "/confirmation" in curr_url or "cv fo" in body.lower()
                or "we'd like to confirm" in body.lower()):
            confirmed = True
            break

    print(f"CONFIRMED: {confirmed}")
    print(f"URL: {page.url}")
    print(f"BODY: {page.inner_text('body')[:300]}")
    page.close()
    br.close()
    sys.exit(0 if confirmed else 1)
