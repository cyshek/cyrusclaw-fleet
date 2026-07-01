"""Probe Contentful form options."""
from playwright.sync_api import sync_playwright
import json, sys, time

CDP = "http://127.0.0.1:19223"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    context = browser.contexts[0]
    page = context.pages[0]
    print("Current URL:", page.url)

    url = "https://job-boards.greenhouse.io/contentful/jobs/7875317"
    page.goto(url)
    time.sleep(3)

    # Click Apply
    page.evaluate(r"""() => {
        const b = [...document.querySelectorAll('button,a')]
            .find(x => /^apply$/i.test((x.textContent || '').trim()));
        if (b) b.click();
    }""")
    time.sleep(2)

    # Get all select controls with their labels
    result = page.evaluate(r"""() => {
        const allControls = [...document.querySelectorAll('.select__control')].map(ctrl => {
            const inp = ctrl.querySelector('input[role=combobox]');
            const sv = ctrl.querySelector('.select__single-value');
            let lbl = "";
            let n = ctrl;
            for (let i = 0; i < 8 && n; i++) {
                n = n.parentElement;
                if (!n) break;
                const labelEl = n.querySelector ? n.querySelector('label, legend') : null;
                if (labelEl) { lbl = labelEl.textContent || ""; break; }
            }
            return {id: inp ? inp.id : null, value: sv ? sv.textContent : null, label: lbl.slice(0, 80)};
        });
        return { url: location.href, controls: allControls };
    }""")
    print(json.dumps(result, indent=2))

    browser.close()
print("Done")
