from playwright.sync_api import sync_playwright
import json

CDP = "http://127.0.0.1:19223"
URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315885533"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    try:
        page.evaluate("() => { var s=document.getElementById('onetrust-consent-sdk'); if(s) s.remove(); }")
    except:
        pass

    # Inspect the radio group divs
    radio_info = page.evaluate("""
() => {
    var groups = ['Self_ID_Questions_US_genderIdentity', 'Self_ID_Questions_US_raceEthnicity', 'Self_ID_Questions_US_sexualOrientation'];
    return groups.map(function(id) {
        var el = document.getElementById(id);
        if (!el) return {id: id, found: false};
        // Find all radio inputs or buttons within
        var inputs = Array.from(el.querySelectorAll('input[type="radio"]'));
        var btns = Array.from(el.querySelectorAll('button, [role="radio"]'));
        var labels = Array.from(el.querySelectorAll('label'));
        return {
            id: id,
            tag: el.tagName,
            role: el.getAttribute('role'),
            aria_invalid: el.getAttribute('aria-invalid'),
            input_count: inputs.length,
            btn_count: btns.length,
            label_count: labels.length,
            inputs: inputs.slice(0,5).map(function(i) { return {id: i.id, name: i.name, val: i.value, checked: i.checked, label: (document.querySelector('label[for="'+i.id+'"]')||{}).innerText||''}; }),
            btns: btns.slice(0,5).map(function(b) { return {tag: b.tagName, role: b.getAttribute('role'), val: b.value, arialabel: b.getAttribute('aria-label'), text: b.innerText.substring(0,40)}; }),
            labels: labels.slice(0,5).map(function(l) { return {for: l.htmlFor, text: l.innerText.substring(0,40)}; }),
            outer_html: el.outerHTML.substring(0,500)
        };
    });
}
""")
    for r in radio_info:
        print(json.dumps(r, indent=2))
        print("---")
    page.close()
