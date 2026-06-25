"""Zscaler - check what happens immediately after submit"""
from playwright.sync_api import sync_playwright
import time, json, sys, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")

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

    for fid, val in PLAN.get("text_fields", {}).items():
        if val:
            page.evaluate(SET_VAL_JS, [fid, val])

    pw_typeahead(page, "country", "United", "United States")
    pw_select(page, "question_12295061007[]", "Linkedin")
    for dd in PLAN.get("dropdowns", []):
        pw_select(page, dd["id"], dd["label"])
    pw_select(page, "question_12295064007", "No")
    pw_select(page, "gender", "Decline To Self Identify")
    pw_select(page, "hispanic_ethnicity", "Decline To Self Identify")
    pw_select(page, "veteran_status", ["I don't wish to answer"])
    pw_select(page, "disability_status", ["I do not want to answer"])

    piti = PLAN.get("phone_iti", {})
    if piti:
        page.evaluate("""async (args) => {
            const [id, country, digits] = args;
            const sleep = ms => new Promise(r => setTimeout(r, ms));
            const setN = (el, v) => { const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value"); d.set.call(el, v); el.dispatchEvent(new Event("input", {bubbles: true})); el.dispatchEvent(new Event("change", {bubbles: true})); };
            const inp = document.getElementById(id); if (!inp) return;
            const iti = inp.closest(".iti"); if (iti) { const flag = iti.querySelector(".iti__selected-flag"); if (flag) { flag.click(); await sleep(250); const items = [...iti.querySelectorAll(".iti__country,li[class*=iti__country]")]; const t = items.find(li => li.textContent.toLowerCase().includes(country.toLowerCase())); if (t) { t.click(); await sleep(150); } } }
            setN(inp, String(digits).replace(/[^0-9]/g, ""));
        }""", [piti["id"], piti.get("country", "United States"), piti.get("digits", "3468040227")])

    if RESUME and os.path.exists(RESUME):
        rl = page.locator("#resume")
        if rl.count() > 0:
            rl.set_input_files(RESUME)
            time.sleep(1)

    # Look at the submit button more carefully
    btn_info = page.evaluate("""() => {
        const btn = document.querySelector('button[type=submit], button[class*=submit]');
        if (!btn) return 'no submit button';
        return {text: btn.textContent.trim(), disabled: btn.disabled, type: btn.type, classes: btn.className.slice(0,100)};
    }""")
    print(f"Submit button: {btn_info}")
    
    # Click submit and watch what happens
    sub = page.locator('button:has-text("Submit application")')
    if sub.count() == 0:
        sub = page.locator("button[type=submit]")
    print(f"Submit button count: {sub.count()}")
    
    # Check for any validation errors before clicking
    errors_before = page.evaluate("""() => {
        return [...document.querySelectorAll('.error, [class*=error], .invalid, [aria-invalid=true]')]
            .filter(e => e.offsetParent)
            .map(e => e.textContent.trim().slice(0, 60));
    }""")
    print(f"Errors before submit: {errors_before[:5]}")
    
    sub.first.click()
    time.sleep(1)
    
    # Immediately check for errors
    errors_after = page.evaluate("""() => {
        return [...document.querySelectorAll('.error, [class*=error], .invalid, [aria-invalid=true], [class*=ErrorMsg], [class*=errorMsg]')]
            .filter(e => e.offsetParent)
            .map(e => e.textContent.trim().slice(0, 80));
    }""")
    print(f"Errors after submit (1s): {errors_after[:10]}")
    
    # Check if OTP appeared
    has_otp = page.evaluate("() => !!document.getElementById('security-input-0')")
    print(f"OTP gate: {has_otp}")
    
    time.sleep(4)
    body = page.inner_text("body")
    print(f"URL after 5s: {page.url}")
    # Check for thank you or confirmation
    print(f"Contains 'thank you': {'thank you' in body.lower()}")
    print(f"Contains 'confirmation': {'confirmation' in page.url}")
    print(f"BODY 500: {body[:500]}")
    
    page.close()
    br.close()
