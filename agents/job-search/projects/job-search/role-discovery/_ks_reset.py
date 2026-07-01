"""
Trigger password reset for cyshekari@gmail.com on Keysight iCIMS Auth0 tenant.
"""
import time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
EMAIL = "cyshekari@gmail.com"
DEBUG_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug"

def shot(page, name):
    path = f"{DEBUG_DIR}/ks-reset-{name}.png"
    try:
        page.screenshot(path=path)
        print(f"Screenshot: {path}")
    except Exception as e:\n        print(f"Screenshot error: {e}")

with sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp(CDP)\n    ctx = browser.contexts[0] if browser.contexts else browser.new_context()\n    page = ctx.new_page()\n    
    # Go to Keysight iCIMS login (iframe directly)
    page.goto("https://careers-keysight.icims.com/jobs/53104/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    shot(page, "00-initial")
    print(f"URL: {page.url}")
    print(f"Title: {page.title()}")
    
    # Accept GDPR checkbox in any frame
    for fr in page.frames:
        try:
            result = fr.evaluate("""()=>{
                const cb = document.querySelector('input[type=checkbox]');
                if (cb && !cb.checked) { cb.click(); return true; }
                return false;
            }""")
            if result:
                print(f"Clicked GDPR checkbox in frame: {fr.url[:60]}")
                time.sleep(0.5)
                break
        except:
            pass
    
    # Fill email in any frame
    email_filled = False
    for fr in page.frames:
        try:
            result = fr.evaluate(f"""(email) => {{
                const inp = document.querySelector('#email, input[type=email], input[name=email]');
                if (!inp) return false;
                const nv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                nv.set.call(inp, email);
                inp.dispatchEvent(new Event('input', {{bubbles:true}}));
                inp.dispatchEvent(new Event('change', {{bubbles:true}}));
                return true;
            }}""", EMAIL)
            if result:
                print(f"Filled email in frame: {fr.url[:60]}")
                email_filled = True
                break
        except:
            pass
    
    if not email_filled:
        print("ERROR: Could not find email input")
    
    page.wait_for_timeout(500)
    shot(page, "01-filled")
    
    # Enable and click Next button
    for fr in page.frames:
        try:
            clicked = fr.evaluate("""()=>{
                const btn = document.querySelector('#enterEmailSubmitButton, button[type=submit]');
                if (btn) {
                    btn.removeAttribute('disabled');
                    btn.click();
                    return true;
                }
                return false;
            }""")
            if clicked:
                print(f"Clicked Next button in frame: {fr.url[:60]}")
                break
        except:
            pass
    
    page.wait_for_timeout(8000)
    shot(page, "02-after-submit")
    print(f"URL after email submit: {page.url}")
    
    # Check all frames for the Auth0 password/blocked page
    for fr in page.frames:
        try:
            url = fr.url
            if not url:
                continue
            print(f"Frame: {url[:80]}")
            
            # Check if this is the Auth0 password page with blocked account message
            info = fr.evaluate("""()=>{
                const blocked = document.body ? document.body.innerText.includes('blocked') : false;
                const resetLink = document.querySelector('a[href*=reset], a[href*=forgot], a:contains("Reset")');
                const resetLinkHref = resetLink ? resetLink.href : null;
                const resetLinkText = resetLink ? resetLink.innerText : null;
                // Also try by text search
                const allLinks = [...document.querySelectorAll('a')];
                const resetByText = allLinks.find(a => /reset/i.test(a.innerText));
                return {
                    blocked,
                    resetLinkHref,
                    resetLinkText,
                    resetByText: resetByText ? resetByText.href : null,
                    bodyText: document.body ? document.body.innerText.slice(0, 500) : null
                };
            }""")
            print(f"  Info: blocked={info.get('blocked')}, resetHref={info.get('resetLinkHref')}, bodyText={info.get('bodyText','')[:100]}")
            
            if info.get('blocked') or info.get('resetLinkHref') or info.get('resetByText'):
                print(f"Found auth0 blocked/reset screen!")
                shot(page, "03-before-reset")
                
                # Click the reset link
                clicked = fr.evaluate("""()=>{
                    const allLinks = [...document.querySelectorAll('a')];
                    const resetLink = allLinks.find(a => /reset.*(your)?.*password|forgot.*(your)?.*password/i.test(a.innerText));
                    if (resetLink) {
                        resetLink.click();
                        return resetLink.href;
                    }
                    // Direct href approach
                    const byHref = document.querySelector('a[href*=reset], a[href*=forgot]');
                    if (byHref) {
                        byHref.click();
                        return byHref.href;
                    }
                    return null;
                }""")
                print(f"Reset link clicked: {clicked}")
                page.wait_for_timeout(5000)
                shot(page, "04-after-reset")
                print(f"URL after reset click: {page.url}")
                print("SUCCESS: Password reset initiated - check Gmail for reset email")
                break
        except Exception as e:\n            print(f"Frame error: {e}")
    
    page.close()
    print("Done")
