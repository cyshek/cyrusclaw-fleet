import os, json
from playwright.sync_api import sync_playwright
CDP_URL = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")
URL = "https://explore.jobs.netflix.net/careers/apply?pid=790315472265"
GROUPS = ['Self_ID_Questions_US_genderIdentity','Self_ID_Questions_US_raceEthnicity','Self_ID_Questions_US_sexualOrientation']
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    page = browser.contexts[0].new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    try:
        page.evaluate("()=>{const s=document.getElementById('onetrust-consent-sdk'); if(s) s.remove();}")
    except Exception:
        pass
    results = {}
    for gid in GROUPS:
        cb_id = gid + "-I choose not to disclose-4"
        # raceEthnicity 'I choose not to disclose' is index 4 per earlier probe; gender is 4; sexual is 4
        try:
            loc = page.locator('input[id="' + cb_id + '"]')
            cnt = loc.count()
            if cnt == 0:
                results[gid] = {"err": "checkbox id not found", "id": cb_id}
                continue
            loc.check(timeout=5000)
            page.wait_for_timeout(400)
            checked = page.evaluate("(id)=>{const e=document.getElementById(id); return e? e.checked: null;}", cb_id)
            results[gid] = {"clicked": True, "checked_after": checked}
        except Exception as e:
            results[gid] = {"err": str(e)[:160]}
    # final: how many checked per group
    final = page.evaluate("""(groups)=>{ return groups.map(gid=>{ const g=document.getElementById(gid); const c=g?g.querySelectorAll('input[type=checkbox]:checked').length:-1; return {gid, checked:c}; }); }""", GROUPS)
    print("PER-CLICK RESULTS:", json.dumps(results, indent=2))
    print("FINAL CHECKED COUNTS:", json.dumps(final, indent=2))
    page.close()
