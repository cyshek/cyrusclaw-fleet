"""Re-enter Salesforce flow and dump the 'Regarding future positions' question DOM/options."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright

CREDS = json.loads(Path(__file__).resolve().parent.parent.joinpath('.workday-creds.json').read_text())
EMAIL = CREDS['tenants']['salesforce']['email']
PASS = CREDS['shared_password']
URL = "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site/job/Illinois---Chicago/Solution-Engineer--Pre-Sales---Small--Medium---Growth-Business_JR318273/apply"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(Path(__file__).resolve().parent.parent / ".workday-browser-data" / "salesforce"),
        headless=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    print('URL after goto:', page.url)
    # Take snapshot of body to see what we landed on
    body = page.evaluate("() => document.body.innerText.slice(0, 1500)")
    print("BODY:", body[:600])
    page.screenshot(path='/tmp/sf-restate.png', full_page=True)
    # If we landed in app questions, dump it; otherwise click apply manually
    if 'Application Questions' in body and ('Regarding future' in body or 'future positions' in body):
        # try advancing if needed
        pass
    else:
        for sel in ['[data-automation-id="adventureButton"]', '[data-automation-id="applyManually"]']:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible(timeout=1500):
                    loc.click(); page.wait_for_timeout(2500)
            except Exception: pass
    page.wait_for_timeout(2000)
    print('URL now:', page.url)
    # Dump the 'Regarding future positions' question DOM
    info = page.evaluate("""() => {
      // Find legend/text containing 'Regarding future positions' or 'future positions at Salesforce'
      const legends = Array.from(document.querySelectorAll('legend, label, h3, h4, span, div'));
      const lt = legends.find(n => /Regarding future positions/i.test(n.innerText||''));
      if (!lt) return {found:false, body: document.body.innerText.slice(0, 2000)};
      // walk up to nearest fieldset or card
      let container = lt.closest('fieldset') || lt.closest('[role=group]') || lt.parentElement.parentElement;
      const opts = Array.from(container.querySelectorAll('input, label, [role=radio], [role=checkbox], [data-automation-id]')).slice(0, 40).map(n => ({
        tag: n.tagName, id: n.id, type: n.type, role: n.getAttribute('role'),
        automation: n.getAttribute('data-automation-id'), aria: n.getAttribute('aria-label'),
        text: (n.innerText||'').slice(0,80), forAttr: n.getAttribute('for')
      }));
      // also dump the container's outerHTML truncated
      return {found:true, html: container.outerHTML.slice(0, 4000), opts};
    }""")
    print(json.dumps(info, indent=2))
    ctx.close()
