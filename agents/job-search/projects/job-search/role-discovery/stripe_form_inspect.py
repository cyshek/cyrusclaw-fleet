import time, sys, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto("https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7594208", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    # Get all select inputs with their labels
    fields = page.evaluate("""() => {
        const results = [];
        const selects = [...document.querySelectorAll('input[id^="question_"]')];
        for (const s of selects) {
            const ctrl = s.closest('.select__control');
            const container = s.closest('[class*=field], .application-field, .field-container, .question, form > div');
            let label = '';
            if (container) {
                const lbl = container.querySelector('label, h4, .question-label');
                if (lbl) label = lbl.textContent.trim().slice(0, 80);
            }
            results.push({id: s.id, label: label, has_ctrl: !!ctrl});
        }
        return results;
    }""")
    for f in fields:
        print(f"  ID={f['id']} LABEL={f['label'][:60]}")
    page.close()
    br.close()
