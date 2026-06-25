import time, sys, json, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
from playwright.sync_api import sync_playwright
import gh_submit_remix as m

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    url = "https://job-boards.greenhouse.io/embed/job_app?for=databricks&token=8548986002"
    plan = json.load(open("output/inline-plan-databricks-8548986002.json"))
    page.goto(url, wait_until="networkidle", timeout=45000)
    time.sleep(2)
    for fid, val in plan.get("text_fields", {}).items():
        if val and fid not in ("location",):
            page.evaluate(m.SET_VAL_JS, [fid, val])
    m.pw_typeahead(page, "country", "United", "United States")
    for dd in plan.get("dropdowns", []):
        m.pw_fill_select(page, dd["id"], dd["label"])
    piti = plan.get("phone_iti", {})
    if piti:
        page.evaluate(m.PHONE_JS, [piti["id"], piti.get("country", "United States"), piti.get("digits", "3468040227")])
    resume = plan.get("pdf_path_staged") or plan.get("pdf_path_local")
    if resume and os.path.exists(resume):
        rl = page.locator("#resume")
        if rl.count() > 0:
            rl.set_input_files(resume)
            time.sleep(1)
    # Set up response interceptor to catch the submit request
    submit_responses = []
    def handle_response(response):
        if "greenhouse.io" in response.url and response.status not in [200, 304, 301, 302]:
            submit_responses.append(f"{response.status} {response.url[:80]}")
        elif "apply" in response.url.lower() or "submit" in response.url.lower():
            submit_responses.append(f"{response.status} {response.url[:80]}")
    page.on("response", handle_response)
    # Submit
    page.locator('button:has-text("Submit application")').first.click()
    time.sleep(6)
    print("Submit responses:", submit_responses[:10])
    # Check for any security gate
    body = page.inner_text("body")
    otp0 = page.evaluate("() => !!document.getElementById('security-input-0')")
    print("OTP gate (security-input-0):", otp0)
    # Check for email verify text
    verify_text = "verify" in body.lower() or "code" in body.lower() or "confirm your email" in body.lower()
    print("Verify text in body:", verify_text)
    if verify_text:
        pass
    print("URL:", page.url)
    print("Body first 400:", body[:400])
    page.close()
    br.close()
