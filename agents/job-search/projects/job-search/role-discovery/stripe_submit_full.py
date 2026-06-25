import time, sys, json, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
from playwright.sync_api import sync_playwright
import gmail_imap as g
import gh_submit_remix as m

CDP = "http://127.0.0.1:18800"
PLAN_PATH = "output/inline-plan-stripe-7594208.json"

with open(PLAN_PATH) as fh:
    plan = json.load(fh)
with sync_playwright() as p:
    br = p.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0] if br.contexts else br.new_context()
    page = ctx.new_page()
    page.goto(plan["url"], wait_until="networkidle", timeout=45000)
    time.sleep(2)
    # Text fields
    for fid, val in plan.get("text_fields", {}).items():
        if val and fid not in ("location",):
            page.evaluate(m.SET_VAL_JS, [fid, val])
    # Country/location typeaheads
    m.pw_typeahead(page, "country", "United", "United States")
    m.pw_typeahead(page, "candidate-location", "Kirkland", "Kirkland, Washington")
    print("Typeaheads done")
    # Standard dropdowns
    for dd in plan.get("dropdowns", []):
        r = m.pw_fill_select(page, dd["id"], dd["label"])
        print(f"  DD {dd['id']}: {r}")
    # Needs review dropdowns
    for nr in plan.get("needs_review_dropdowns", []):
        q = nr.get("question", "").lower()
        labels = [nr["label"]] + nr.get("alternates", [])
        if "country" in q or "reside" in q:
            labels = ["US", "United States"] + labels
        r = m.pw_fill_select(page, nr["id"], labels)
        print(f"  NR {nr['id']}: {r}")
    # Handle Stripe-specific multiselect: question_63282213[] (countries to work in)
    # Find the checkbox labeled "US" and click it
    us_cb_result = page.evaluate("""() => {
        const fieldset = document.getElementById('question_63282213[]');
        if (!fieldset) return {err: 'no fieldset'};
        const labels = [...fieldset.querySelectorAll('label')];
        const us_label = labels.find(l => l.textContent.trim() === 'US' || l.textContent.trim().toLowerCase() === 'united states');
        if (!us_label) return {err: 'no US label', count: labels.length};
        const for_id = us_label.getAttribute('for');
        if (!for_id) return {err: 'no for_id'};
        const cb = document.getElementById(for_id);
        if (!cb) return {err: 'no checkbox', for_id};
        cb.scrollIntoView({block:'center'});
        cb.click();
        return {clicked: for_id, text: us_label.textContent.trim()};
    }""")
    print("Multiselect US:", us_cb_result)
    # Phone ITI
    piti = plan.get("phone_iti", {})
    if piti:
        page.evaluate(m.PHONE_JS, [piti["id"], piti.get("country", "United States"), piti.get("digits", "3468040227")])
        print("Phone set")
    # Resume upload
    resume = plan.get("pdf_path_staged") or plan.get("pdf_path_local")
    if resume and os.path.exists(resume):
        rl = page.locator("#resume")
        if rl.count() > 0:
            rl.set_input_files(resume)
            time.sleep(1)
            print("Resume uploaded")
    # Submit
    since_submit = time.time()
    page.locator('button:has-text("Submit application")').first.click()
    time.sleep(4)
    # OTP
    has_otp = page.evaluate("() => !!document.getElementById('security-input-0')")
    print("OTP gate:", has_otp)
    if has_otp:
        code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=5, since_epoch=since_submit)
        print("OTP:", code)
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
                    btn.first.click(); break
            except Exception:
                pass
            time.sleep(1.5)
    # Poll confirmation
    confirmed = False
    for _ in range(15):
        time.sleep(2)
        final_url = page.url
        body = page.inner_text("body")
        if ("thank you" in body.lower() and "apply" in body.lower()) or "/confirmation" in final_url:
            confirmed = True
            break
    print("CONFIRMED:", confirmed)
    print("URL:", page.url)
    print("BODY:", page.inner_text("body")[:300])
    page.close()
    br.close()
