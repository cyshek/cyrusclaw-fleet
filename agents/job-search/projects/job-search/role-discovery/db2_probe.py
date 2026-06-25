import time, sys, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto("https://job-boards.greenhouse.io/embed/job_app?for=databricks&token=8595123002", wait_until="networkidle", timeout=45000)
    time.sleep(2)
    # Find all checkbox fieldsets
    info = page.evaluate("""() => {
        const fieldsets = [...document.querySelectorAll('fieldset[id*="question_"]')];
        return fieldsets.map(fs => {
            const labels = [...fs.querySelectorAll('label')];
            return {
                id: fs.id,
                labels: labels.map(l => ({for_id: l.getAttribute('for'), text: l.textContent.trim().slice(0, 60)}))
            };
        });
    }""")
    print(json.dumps(info, indent=2))
    page.close()
    br.close()
