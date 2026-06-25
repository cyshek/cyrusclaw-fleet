import time, sys
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
from playwright.sync_api import sync_playwright
import gh_submit_remix as m

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto("https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7594208", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    for fid, val in [("first_name","Cyrus"),("last_name","Shekari"),("email","cyshekari@gmail.com")]:
        page.evaluate(m.SET_VAL_JS, [fid, val])
    m.pw_typeahead(page, "country", "United", "United States")
    m.pw_typeahead(page, "candidate-location", "Kirkland", "Kirkland, Washington")
    m.pw_fill_select(page, "question_63282214", "Yes")
    m.pw_fill_select(page, "question_63282215", "No")
    m.pw_fill_select(page, "question_63282217", "No")
    m.pw_fill_select(page, "question_63282212", ["US", "United States"])
    m.pw_fill_select(page, "question_63282216", ["Yes", "Kirkland"])
    m.pw_fill_select(page, "question_63475032", "Yes")
    sentinels = page.evaluate("() => {const q=[...document.querySelectorAll('[class*=requiredInpu]')];return {count:q.length,vals:q.map(e=>e.value)};}")
    print("Sentinels after fill:", sentinels)
    page.locator('button:has-text("Submit application")').first.click()
    time.sleep(3)
    sentinels2 = page.evaluate("() => {const q=[...document.querySelectorAll('[class*=requiredInpu]')];return {count:q.length,vals:q.map(e=>e.value)};}")
    print("Sentinels after submit:", sentinels2)
    print("URL:", page.url)
    print("Body:", page.inner_text("body")[:500])
    page.close()
    br.close()
