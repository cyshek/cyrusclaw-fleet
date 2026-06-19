from playwright.sync_api import sync_playwright
import json, time

CDP_URL = "http://127.0.0.1:19223"
APPLY_URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315885533"

with sync_playwright() as p:\n+    browser = p.chromium.connect_over_cdp(CDP_URL)\n+    ctx = browser.contexts[0] if browser.contexts else browser.new_context()\n+    page = ctx.new_page()
    captured = []

    def on_request(req):
        if "api/" in req.url or "submit" in req.url:
            body = None
            try:
                pd = req.post_data
                if pd:
                    body = str(pd)[:300]
            except:
                pass
            captured.append({"url": req.url[:150], "method": req.method, "body": body})
            print("REQ:", req.method, req.url[:120])
            if body:
                print("  BODY:", body[:300])

    def on_response(resp):
        if "api/" in resp.url or "submit" in resp.url:
            captured.append({"url": resp.url[:150], "status": resp.status})
            print("RESP:", resp.status, resp.url[:120])

    page.on("request", on_request)
    page.on("response", on_response)
    page.goto(APPLY_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    try:
        page.evaluate("() => { var s = document.getElementById('onetrust-consent-sdk'); if (s) s.remove(); }")
    except:
        pass

    # Check contact fields state
    fields = page.evaluate("""() => {
        var ids = ['Contact_Information_email', 'Contact_Information_firstname',
                   'Contact_Information_lastname', 'Contact_Information_phone', 'Contact_Information_city'];
        return ids.map(function(id) { return {id: id, val: (document.getElementById(id)||{}).value||''}; });
    }""")
    print("Fields:", json.dumps(fields))

    # aria-required empty
    aria_empty = page.evaluate("""() => {
        var els = Array.from(document.querySelectorAll('[aria-required="true"]'));
        return els.filter(function(e) { return !e.value && e.tagName !== 'BUTTON'; })
            .map(function(e) { return {
                id: e.id, tag: e.tagName, role: e.getAttribute('role'),
                label: (e.getAttribute('aria-labelledby') || e.getAttribute('aria-label') || '').substring(0,60),
                val: e.value
            }; });
    }""")
    print("aria-required empty:", json.dumps(aria_empty[:20]))

    btn = page.locator("button:has-text('Submit application')").first
    print("Btn disabled:", btn.is_disabled())

    console_msgs = []
    page.on("console", lambda m: console_msgs.append(m.type + ": " + m.text[:200]))
    page.on("pageerror", lambda e: console_msgs.append("ERROR: " + str(e)[:200]))

    print("Clicking submit...")
    btn.click(timeout=5000)
    time.sleep(10)

    print("Console:", json.dumps(console_msgs[:20]))
    print("Network:", json.dumps(captured))

    invalid = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('[aria-invalid="true"]')).slice(0,10).map(function(e) {
            return {id: e.id, tag: e.tagName,
                    label: (e.getAttribute('aria-labelledby') || e.getAttribute('aria-label') || '').substring(0,60),
                    val: e.value};
        });
    }""")
    print("Invalid after click:", json.dumps(invalid))
    page.close()
