import sys
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
from playwright.sync_api import sync_playwright
import time

CDP = "http://127.0.0.1:18800"
EMAIL = "cyshekari@gmail.com"
PASSWORD = "JobSearch2026!amd"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    page.goto("https://login.icims.com/u/login/identifier", wait_until="domcontentloaded", timeout=30000)
    import time; time.sleep(2)
    print("Initial URL:", page.url)

    email_inp = page.query_selector("input[name='username'], input[type='email']")
    if email_inp:
        email_inp.fill(EMAIL)
        print("Email filled")
        cont_btn = page.query_selector("button[type='submit'], button[name='action']")
        if cont_btn:
            cont_btn.click()
            time.sleep(3)
            print("After continue:", page.url)
            pwd_inp = page.query_selector("input[type='password']")
            if pwd_inp:
                pwd_inp.fill(PASSWORD)
                submit = page.query_selector("button[type='submit']")
                if submit:
                    submit.click()
                    time.sleep(5)
                    print("After submit:", page.url)
                    body_text = page.evaluate("document.body.innerText")
                    for line in body_text.split(chr(10)):
                        line = line.strip()
                        if line and len(line) < 200:
                            print("PAGE:", line[:150])
            else:
                print("NO PASSWORD INPUT:")
                body_text = page.evaluate("document.body.innerText")
                for line in body_text.split(chr(10)):
                    line = line.strip()
                    if line and len(line) < 200:
                        print("PAGE:", line[:150])
    else:
        print("NO EMAIL INPUT")

    page.close()
