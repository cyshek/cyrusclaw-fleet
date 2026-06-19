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
    # Check reCAPTCHA
    info = page.evaluate("""() => {
        var scripts = Array.from(document.querySelectorAll("script[src*=recaptcha]"));
        var sitekey = null;
        var is_enterprise = !!document.querySelector("script[src*="recaptcha"]");
        try {
            var cfg = window.___grecaptcha_cfg;
            if (cfg && cfg.clients) {
                for (var k in cfg.clients) {
                    var cl = cfg.clients[k];
                    for (var ck in cl) {
                        if (cl[ck] && cl[ck].sitekey) { sitekey = cl[ck].sitekey; break; }
                    }
                }
            }
        } catch(e) {}
        return {enterprise: is_enterprise, sitekey: sitekey, scripts: scripts.map(function(s) { return s.src.substring(0,100); })};
    }""")
    print("reCAPTCHA info:", json.dumps(info, indent=2))
    page.close()
