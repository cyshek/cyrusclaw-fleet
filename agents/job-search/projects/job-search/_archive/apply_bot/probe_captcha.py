"""Probe the Scale AI form for captcha widgets."""
from playwright.sync_api import sync_playwright

URL = "https://job-boards.greenhouse.io/scaleai/jobs/4670064005"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    p = b.new_context().new_page()
    p.goto(URL, wait_until="domcontentloaded")
    p.wait_for_timeout(4000)

    # Find anything captcha-like
    js = """
    () => {
        const out = [];
        // iframes
        document.querySelectorAll('iframe').forEach(f => {
            out.push({tag:'iframe', src:f.src, id:f.id, name:f.name, title:f.title});
        });
        // common captcha class/id markers
        ['turnstile', 'hcaptcha', 'recaptcha', 'cf-', 'g-recaptcha', 'h-captcha'].forEach(k => {
            document.querySelectorAll(`[class*="${k}"], [id*="${k}"], [data-sitekey]`).forEach(e => {
                out.push({key:k, tag:e.tagName, id:e.id, cls:e.className.toString().slice(0,100), sitekey:e.getAttribute('data-sitekey')});
            });
        });
        // scripts
        document.querySelectorAll('script[src]').forEach(s => {
            if (/turnstile|hcaptcha|recaptcha|captcha/i.test(s.src)) out.push({tag:'script', src:s.src});
        });
        return out;
    }
    """
    items = p.evaluate(js)
    print(f"Found {len(items)} captcha-related elements:")
    for i in items:
        print(" ", i)
    b.close()
