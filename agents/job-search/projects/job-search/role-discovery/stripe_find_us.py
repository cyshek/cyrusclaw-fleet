import time, sys, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto("https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7594208", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    # Find US checkbox in multiselect
    us_cb = page.evaluate("""() => {
        // Look for label elements that contain "United States" within the q63282213 multiselect
        const fieldset = document.getElementById('question_63282213[]');
        if (!fieldset) return {err: 'no fieldset'};
        const labels = [...fieldset.querySelectorAll('label')];
        const us_label = labels.find(l => l.textContent.trim().toLowerCase().includes('united states') || l.textContent.trim() === 'US');
        if (!us_label) {
            // Try to list all labels
            return {err: 'no US label', all_labels: labels.slice(0, 30).map(l => l.textContent.trim().slice(0, 30))};
        }
        const for_id = us_label.getAttribute('for');
        return {label_text: us_label.textContent.trim(), for_id: for_id};
    }""")
    print("US checkbox info:", json.dumps(us_cb, indent=2))
    page.close()
    br.close()
