"""Probe Intel Workday Application Questions page to see all question texts + checkbox options."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent
CREDS = json.loads((ROOT / ".workday-creds.json").read_text())
EMAIL = CREDS["tenants"]["intel"]["email"]
PASS  = CREDS["shared_password"]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://intel.wd1.myworkdayjobs.com/External/job/US-Arizona-Phoenix/Advanced-Packaging-Supplier-Technology-Development-Program-Manager_JR0280825"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(ROOT / ".workday-browser-data" / "intel"),
        headless=True,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    # try go straight to apply
    try:
        page.click('[data-automation-id="adventureButton"]', timeout=5000)
        page.wait_for_timeout(1500)
    except Exception: pass
    try:
        page.click('[data-automation-id="applyManually"], button:has-text("Apply Manually")', timeout=5000)
        page.wait_for_timeout(1500)
    except Exception: pass
    # Maybe sign in
    try:
        page.click('[data-automation-id="SignInWithEmailButton"]', timeout=3000)
        page.wait_for_timeout(800)
    except Exception: pass
    # Fill sign-in if shown
    try:
        ein = page.locator('[data-automation-id="email"]').first
        if ein.count():
            ein.fill(EMAIL)
            page.locator('[data-automation-id="password"]').first.fill(PASS)
            # Click overlay sign in
            try:
                page.click('[data-automation-id="click_filter"][aria-label="Sign In"]', timeout=3000)
            except Exception:
                page.click('[data-automation-id="signInSubmitButton"]', timeout=3000)
            page.wait_for_timeout(3000)
    except Exception as e:
        print("signin step:", e)
    # Navigate to questions step: should be already there if resumed.
    # Let's wait for the current page label.
    page.wait_for_timeout(3000)
    print("URL:", page.url)
    # Dump body text shortened
    label = page.evaluate("() => document.querySelector('[data-automation-id=\"progressBarActiveStepLabel\"]')?.textContent?.trim()")
    print("Step label:", label)
    data = page.evaluate("""
() => {
  const out = [];
  document.querySelectorAll('div[data-automation-id^="formField-"]').forEach(ff => {
    const lg = ff.querySelector('legend');
    const qtext = lg ? lg.textContent.trim() : (ff.textContent.trim().slice(0,200));
    const dd = ff.querySelector('button[aria-haspopup="listbox"]');
    const cbs = Array.from(ff.querySelectorAll('input[type=checkbox]')).map(c => {
      const lab = document.querySelector(`label[for="${c.id}"]`);
      return {id:c.id, label: lab? lab.textContent.trim(): ''};
    });
    const radios = Array.from(ff.querySelectorAll('input[type=radio]')).map(r => {
      const lab = document.querySelector(`label[for="${r.id}"]`);
      return {id:r.id, label: lab? lab.textContent.trim(): '', name: r.name};
    });
    if (dd || cbs.length || radios.length) out.push({qtext, dd:dd?dd.id:null, cbs, radios});
  });
  return out;
}
    """)
    print(json.dumps(data, indent=2)[:8000])
    ctx.close()
