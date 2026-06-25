import time, sys, json
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
from playwright.sync_api import sync_playwright
import gh_submit_remix as m

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    url = "https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7594208"
    page.goto(url, wait_until="networkidle", timeout=30000)
    time.sleep(2)
    # Fill all fields
    plan = json.load(open("output/inline-plan-stripe-7594208.json"))
    for fid, val in plan.get("text_fields", {}).items():
        if val and fid not in ("location",):
            page.evaluate(m.SET_VAL_JS, [fid, val])
    for cd in plan.get("country_dropdowns", []):
        if cd["id"] == "country":
            m.pw_typeahead(page, "country", "United", "United States")
        elif cd["id"] == "candidate-location":
            m.pw_typeahead(page, "candidate-location", "Kirkland", "Kirkland, Washington")
    for dd in plan.get("dropdowns", []):
        m.pw_fill_select(page, dd["id"], dd["label"])
    for nr in plan.get("needs_review_dropdowns", []):
        q = nr.get("question", "").lower()
        labels = [nr["label"]] + nr.get("alternates", [])
        if "country" in q or "reside" in q or "right to work" in q:
            labels = ["US", "United States", "Yes", "I am authorized"] + labels
        if "state" in q or "region" in q:
            labels = ["Another State"] + labels
        m.pw_fill_select(page, nr["id"], labels)
    piti = plan.get("phone_iti", {})
    if piti:
        page.evaluate(m.PHONE_JS, [piti["id"], piti.get("country", "United States"), piti.get("digits", "3468040227")])
    resume = plan.get("pdf_path_staged") or plan.get("pdf_path_local")
    if resume:
        rl = page.locator("#resume")
        if rl.count() > 0:
            rl.set_input_files(resume)
            time.sleep(1)
    # Check recaptcha
    rc = page.evaluate("() => typeof grecaptcha !== 'undefined'")
    print("has grecaptcha:", rc)
    rc_resp = page.evaluate("() => { const el = document.querySelector('input[name=\"g-recaptcha-response\"]'); return el ? el.value.slice(0,20) : 'none'; }")
    print("g-recaptcha-response:", rc_resp)
    # Check resume upload
    ru = page.evaluate("() => { const el = document.querySelector('#resume, input[type=\"file\"]'); if (!el) return 'no input'; return {files: el.files ? el.files.length : -1}; }")
    print("resume upload:", ru)
    # Submit and check error
    page.locator('button:has-text("Submit application")').first.click()
    time.sleep(5)
    # Check what happened
    err_els = page.locator("[class*=error], .field--error, [aria-invalid]").all()
    errs = []
    for el in err_els[:10]:
        try:
            errs.append(el.text_content(timeout=2000))
        except:
            pass
    print("Errors:", errs)
    print("URL:", page.url)
    print("Body:", page.inner_text("body")[:600])
    page.close()
    br.close()
