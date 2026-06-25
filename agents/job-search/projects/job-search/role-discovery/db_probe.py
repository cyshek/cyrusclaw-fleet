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
        r = m.pw_fill_select(page, dd["id"], dd["label"])
        print(f"DD {dd['id']}: {r}")
    piti = plan.get("phone_iti", {})
    if piti:
        page.evaluate(m.PHONE_JS, [piti["id"], piti.get("country", "United States"), piti.get("digits", "3468040227")])
    resume = plan.get("pdf_path_staged") or plan.get("pdf_path_local")
    if resume and os.path.exists(resume):
        rl = page.locator("#resume")
        if rl.count() > 0:
            rl.set_input_files(resume)
            time.sleep(1)
            print("Resume uploaded")
    # Check required empty fields
    empties = page.evaluate("""() => {
        const req = [...document.querySelectorAll('input[required],select[required],textarea[required]')].filter(e => e.offsetParent !== null);
        return req.filter(e => !e.value).map(e => ({id: e.id, name: e.name, type: e.type}));
    }""")
    print("Empty required:", empties)
    # Submit and check
    page.locator('button:has-text("Submit application")').first.click()
    time.sleep(5)
    print("URL:", page.url)
    body = page.inner_text("body")
    print("Body:", body[:600])
    page.close()
    br.close()
