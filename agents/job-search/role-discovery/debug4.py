from playwright.sync_api import sync_playwright
import json

CDP_URL = "http://127.0.0.1:19223"
APPLY_URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315885533"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.goto(APPLY_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    try:
        page.evaluate('() => { var s = document.getElementById("onetrust-consent-sdk"); if (s) s.remove(); }')
    except Exception as e:
        print("OT:", e)
    combos = page.evaluate('''() => {
        return Array.from(document.querySelectorAll('[role="combobox"]')).map(function(c) {
            return {lb: c.getAttribute("aria-labelledby"), v: c.value};
        });
    }''')
    print("ALL COMBOS:", json.dumps(combos, indent=2))
    q1 = page.locator('[aria-labelledby="Application_Questions_QUESTION_SETUP_6_656_label"]').first
    if q1.count() > 0:
        print("Found Q1")
        q1.click(timeout=5000)
        page.wait_for_timeout(2000)
        opts = page.evaluate('''() => {
            return Array.from(document.querySelectorAll('[role="option"]')).map(function(o) { return o.textContent.trim(); });
        }''')
        print("Q1 OPTIONS:", opts)
        no_opt = page.locator('[role="option"]').filter(has_text="No").first
        if no_opt.count() > 0:
            no_opt.click(timeout=3000)
            print("Clicked No")
        else:
            print("No option not found")
            page.keyboard.press("Escape")
    else:
        print("Q1 NOT Found")
    page.wait_for_timeout(500)
    vals2 = page.evaluate('''() => {
        return Array.from(document.querySelectorAll('[role="combobox"]')).map(function(c) {
            return {lb: c.getAttribute("aria-labelledby"), v: c.value};
        });
    }''')
    appq_vals = [v for v in vals2 if v.get("lb") and "Application" in (v.get("lb") or "")]
    print("APP_Q VALS:", appq_vals)
    btns = page.evaluate('''() => {
        return Array.from(document.querySelectorAll("button")).filter(function(b) {
            return b.textContent.includes("Submit");
        }).map(function(b) {
            return {t: b.textContent.trim().substring(0,40), dis: b.disabled};
        });
    }''')
    print("SUBMIT:", btns)
    page.close()
    print("Done")
