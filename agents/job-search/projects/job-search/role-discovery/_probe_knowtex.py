import json, sys
sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:19223"
URL = "https://jobs.ashbyhq.com/knowtex/7c657d94-b72a-4af8-9933-4591f2a57cb7/application"

PROBE = """() => {
  const out = [];
  const fields = document.querySelectorAll('[class*=_fieldEntry_], .ashby-application-form-field-entry');
  fields.forEach(c => {
    const lblEl = c.querySelector('label');
    const lbl = lblEl ? (lblEl.textContent || '').trim() : '';
    const inp = c.querySelector('input[type=text], input:not([type]), textarea, input[type=tel], input[type=email]');
    if (inp) {
      out.push({label: lbl.slice(0, 80), tag: inp.tagName, type: inp.type || '', id: inp.id || '', name: inp.name || '', value: (inp.value || '').slice(0, 30)});
    }
  });
  return out;
}"""

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp(CDP)
    page = b.contexts[0].new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3500)
    for f in page.evaluate(PROBE):
        print(json.dumps(f))
    page.close()
