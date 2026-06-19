from playwright.sync_api import sync_playwright
import json, time

CDP = "http://127.0.0.1:19223"
URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315885533"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    try:
        page.evaluate("() => { var s=document.getElementById('onetrust-consent-sdk'); if(s) s.remove(); }")
    except:
        pass

    fields = page.evaluate("""
() => {
    var ids = ['Contact_Information_email','Contact_Information_firstname',
               'Contact_Information_lastname','Contact_Information_phone','Contact_Information_city'];
    return ids.map(function(id){ var e=document.getElementById(id); return {id:id,val:e?e.value:''}; });
}
""")
    print("FIELDS:", json.dumps(fields))

    aria_empty = page.evaluate("""
() => {
    var els = Array.from(document.querySelectorAll('[aria-required="true"]'));
    return els.filter(function(e){ return !e.value && e.tagName !== 'BUTTON'; })
        .map(function(e){ return {id:e.id, tag:e.tagName,
            label:(e.getAttribute('aria-labelledby')||e.getAttribute('aria-label')||'').substring(0,60),
            val:e.value}; });
}
""")
    print("ARIA_REQ_EMPTY:", json.dumps(aria_empty[:20]))

    btn = page.locator("button:has-text('Submit application')").first
    print("BTN_DISABLED:", btn.is_disabled())

    console_msgs = []
    page.on("console", lambda m: console_msgs.append(m.type + ": " + m.text[:150]))

    net = []
    def _on_req(r):
        if "api/" in r.url or "submit" in r.url:
            net.append("REQ: " + r.method + " " + r.url[:100])
    def _on_resp(r):
        if "api/" in r.url or "submit" in r.url:
            net.append("RESP: " + str(r.status) + " " + r.url[:100])
    page.on("request", _on_req)
    page.on("response", _on_resp)

    btn.click(timeout=5000)
    time.sleep(10)

    print("CONSOLE:", json.dumps(console_msgs[:20]))
    print("NET:", json.dumps(net))

    invalid = page.evaluate("""
() => {
    return Array.from(document.querySelectorAll('[aria-invalid="true"]')).slice(0,10).map(function(e){
        return {id:e.id, tag:e.tagName,
            label:(e.getAttribute('aria-labelledby')||e.getAttribute('aria-label')||'').substring(0,60),
            val:e.value};
    });
}
""")
    print("INVALID_AFTER:", json.dumps(invalid))
    page.close()
