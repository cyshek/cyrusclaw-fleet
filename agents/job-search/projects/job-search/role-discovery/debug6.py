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
    # Check localStorage and sessionStorage for any submit state
    storage = page.evaluate("""() => {
        var ls = {};
        var ss = {};
        for (var i = 0; i < localStorage.length; i++) {
            var k = localStorage.key(i);
            ls[k] = localStorage.getItem(k);
        }
        for (var i = 0; i < sessionStorage.length; i++) {
            var k = sessionStorage.key(i);
            ss[k] = sessionStorage.getItem(k);
        }
        return {localStorage: ls, sessionStorage: ss};
    }""")
    print("localStorage keys:", list(storage["localStorage"].keys()))
    print("sessionStorage keys:", list(storage["sessionStorage"].keys()))
    # Check URL and if form is still present
    print("URL:", page.url)
    has_form = page.evaluate("() => !!document.getElementById(\"Contact_Information_email\")")
    print("Form present:", has_form)
    # Check if the apply page shows anything suspicious
    body_text = page.evaluate("() => document.body.innerText.substring(0, 500)")
    print("Body preview:", body_text)
    page.close()
