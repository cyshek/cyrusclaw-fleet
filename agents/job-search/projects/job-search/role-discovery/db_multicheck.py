import time, sys, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto("https://job-boards.greenhouse.io/embed/job_app?for=databricks&token=8548986002", wait_until="networkidle", timeout=45000)
    time.sleep(2)
    info = page.evaluate("""() => {
        const res = {};
        for (const qn of ['question_36528745002[]', 'question_36528746002[]']) {
            const fs = document.getElementById(qn);
            if (!fs) { res[qn] = 'not found'; continue; }
            const header = fs.previousElementSibling || fs.parentElement?.querySelector('label, h4, legend');
            const checkboxes = [...fs.querySelectorAll('input[type=checkbox]')];
            const labels = [...fs.querySelectorAll('label')].map(l => ({
                for_id: l.getAttribute('for'),
                text: l.textContent.trim().slice(0, 60)
            }));
            res[qn] = {
                header: header ? header.textContent.trim().slice(0, 80) : 'unknown',
                checkboxes: checkboxes.length,
                labels: labels.slice(0, 15)
            };
        }
        return res;
    }""")
    print(json.dumps(info, indent=2))
    page.close()
    br.close()
