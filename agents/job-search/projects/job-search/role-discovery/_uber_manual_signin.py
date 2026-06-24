from playwright.sync_api import sync_playwright
import json, time

CDP='http://127.0.0.1:18800'
pw=sync_playwright().start()
br=pw.chromium.connect_over_cdp(CDP)
creds=json.load(open('.uber-creds.json'))['account']
email=creds['email']
password=creds['password']

page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if '160295' in p.url:
            page=p
            break
    if page:
        break

if not page:
    print("NO PAGE"); exit(1)

print("URL:", page.url)
print("Email input count:", page.locator('input[name=email]').count())
print("Password input count:", page.locator('input[name=password]').count())

# Fill and submit the sign-in form
try:
    em = page.locator('input[name=email]').first
    pw_input = page.locator('input[name=password]').first
    if em.count() > 0 and pw_input.count() > 0:
        em.fill(email)
        pw_input.fill(password)
        print("Filled email and password")
        time.sleep(0.5)
        # find submit button
        for sel in ["button[type=submit]", "button:has-text('Sign in')"]:
            btn = page.locator(sel).first
            if btn.count() > 0:
                btn.click()
                print(f"Clicked submit: {sel}")
                break
        # Wait for form
        for i in range(20):
            time.sleep(1.5)
            if page.locator('input[name=firstName]').count() > 0:
                print(f"FORM VISIBLE after {i+1} polls")
                break
            body = page.inner_text('body').lower()
            if 'verification' in body or 'verify' in body:
                print("VERIFICATION REQUIRED")
                break
            print(f"  poll {i+1}: {page.url[:60]}")
        print("Final state:", "FORM" if page.locator('input[name=firstName]').count() > 0 else "NOT_FORM")
        print("Body:", page.inner_text('body')[:200])
    else:
        print("INPUTS NOT FOUND")
except Exception as e:\n    print(f"ERROR: {e}")

pw.stop()
