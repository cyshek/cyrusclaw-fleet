from playwright.sync_api import sync_playwright
import json, time

APPLY_URL = "https://careers.starktech.com/us/en/apply?jobSeqNo=STNSTLUSP100275EXTERNALENUS"
RESUME = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/resume/Cyrus_Shekari_Resume.pdf"

def pw_fill(page, sel_id, val):
    try:
        page.fill("#" + sel_id, val)
        return sel_id + ":ok"
    except Exception as e:\n+        return sel_id + ":ERR:" + str(e)[:60]

def pw_select(page, sel_id, val):
    try:
        page.select_option("#" + sel_id, label=val)
        return sel_id + "=label:" + val
    except Exception:
        try:
            page.select_option("#" + sel_id, value=val)
            return sel_id + "=value:" + val
        except Exception as e2:
            return sel_id + ":ERR:" + str(e2)[:60]

with sync_playwright() as p:\n+    browser = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_default_timeout(20000)
    alerts = []
    page.on("dialog", lambda d: (alerts.append(d.message), d.accept()))
    page.goto(APPLY_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)

    page.set_input_files("input[type=file]", RESUME)
    page.wait_for_timeout(3000)
    upload_alerts = list(alerts)
    alerts.clear()
    print("upload_alerts:", upload_alerts)

    r = {}
    r["firstName"] = pw_fill(page, "firstName", "Cyrus")
    r["lastName"] = pw_fill(page, "lastName", "Shekari")
    r["email"] = pw_fill(page, "email", "cyshekari@gmail.com")
    r["phone"] = pw_fill(page, "phone", "3468040227")
    r["candidateAddress"] = pw_fill(page, "candidateAddress", "12420 NE 120th St #1437")
    r["city"] = pw_fill(page, "city", "Kirkland")
    r["zipCode"] = pw_fill(page, "zipCode", "98033")
    r["country"] = pw_select(page, "country", "United States of America")
    page.wait_for_timeout(800)
    r["state"] = pw_select(page, "state", "Washington")
    r["applicantSource"] = pw_select(page, "applicantSource", "Linkedin")
    page.wait_for_timeout(1500)
    print("fill_results:", json.dumps(r, indent=2))

    dom_check = page.evaluate("""(function() {
        var ids = ["firstName","lastName","email","state","city","zipCode"];
        var res = {};
        for (var i=0; i<ids.length; i++) {
            var el = document.getElementById(ids[i]);
            res[ids[i]] = el ? {v: el.value, inv: el.getAttribute("aria-invalid")} : "MISSING";
        }
        return res;
    })()""")
    print("dom_check:", json.dumps(dom_check, indent=2))

    try:
        review_btn = page.locator("button", has_text="Review").first
        review_btn.scroll_into_view_if_needed()
        review_btn.click()
        print("clicked: Review")
    except Exception as e:\n+        print("click_err:", e)
    page.wait_for_timeout(3000)

    step_url = page.evaluate("location.href")
    errors = page.evaluate("""(function() {
        var sel = '[aria-invalid="true"],[class*=error],[class*=Error]';
        return Array.from(document.querySelectorAll(sel)).map(function(e) {
            return {id: e.id, tag: e.tagName, txt: (e.textContent||'').trim().slice(0,100)};
        }).filter(function(x){ return x.txt; }).slice(0,10);
    })()""")

    print("step_url:", step_url)
    print("errors_after_next:", json.dumps(errors, indent=2))
    print("dialog_alerts:", alerts)
    page.close()
