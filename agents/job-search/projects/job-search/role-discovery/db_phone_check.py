import time, sys, json, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
from playwright.sync_api import sync_playwright
import gh_submit_remix as m

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    url = "https://job-boards.greenhouse.io/embed/job_app?for=databricks&token=8548986002"
    page.goto(url, wait_until="networkidle", timeout=45000)
    time.sleep(2)
    # Check phone field structure
    phone_info = page.evaluate("""() => {
        const phone = document.getElementById('phone');
        if (!phone) return {err: 'no phone'};
        return {
            type: phone.type,
            val: phone.value,
            iti: !!phone.closest('.iti'),
            placeholder: phone.placeholder,
            pattern: phone.pattern || 'none',
            required: phone.required,
        };
    }""")
    print("Phone info:", json.dumps(phone_info))
    # Set via ITI handler
    page.evaluate(m.PHONE_JS, ["phone", "United States", "3468040227"])
    phone_after = page.evaluate("""() => {
        const el = document.getElementById('phone');
        return {val: el ? el.value : 'none'};
    }""")
    print("Phone after set:", phone_after)
    # Fill remaining fields
    for fid, val in [("first_name","Cyrus"),("last_name","Shekari"),("email","cyshekari@gmail.com"),
                     ("question_36528739002","https://linkedin.com/in/cyshekari"),("question_36528741002","LinkedIn")]:
        page.evaluate(m.SET_VAL_JS, [fid, val])
    m.pw_typeahead(page, "country", "United", "United States")
    m.pw_fill_select(page, "question_36528742002", "Yes")
    m.pw_fill_select(page, "question_36528743002", "No")
    m.pw_fill_select(page, "question_36528744002", "No")
    page.locator("#resume").set_input_files("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/databricks-8548986002/Cyrus_Shekari_Resume_databricks_8548986002_v2.pdf")
    time.sleep(1)
    # Check all required fields
    empties = page.evaluate("""() => {
        const req = [...document.querySelectorAll('input[required],select[required],textarea[required]')].filter(e => e.offsetParent !== null && e.type !== 'file');
        return req.map(e => ({id: e.id, val: e.value.slice(0,30), name: e.name}));
    }""")
    print("All required fields:", json.dumps(empties, indent=2))
    page.close()
    br.close()
