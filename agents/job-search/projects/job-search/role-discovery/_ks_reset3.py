"""Trigger password reset for Keysight iCIMS Auth0."""
import time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
EMAIL = "cyshekari@gmail.com"
DBG = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug"


def shot(page, name):
    try:
        page.screenshot(path=f"{DBG}/ks-reset-{name}.png")
        print(f"Shot: ks-reset-{name}.png")
    except Exception as ex:
        print(f"Shot error: {ex}")


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    page.goto("https://careers-keysight.icims.com/jobs/53104/login",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    shot(page, "00")
    print(f"URL: {page.url}")

    # Accept GDPR checkbox in any frame
    for fr in page.frames:
        try:
            result = fr.evaluate("""()=>{
                const cb = document.querySelector("input[type=checkbox]");
                if (cb && !cb.checked) { cb.click(); return true; }
                return false;
            }""")
            if result:
                print(f"GDPR checkbox clicked in: {fr.url[:60]}")
                time.sleep(0.5)
                break
        except Exception:
            pass

    # Fill email
    email_filled = False
    for fr in page.frames:
        try:
            result = fr.evaluate("""(email) => {
                const inp = document.querySelector("#email, input[type=email], input[name=email]");
                if (!inp) return false;
                const nv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
                nv.set.call(inp, email);
                inp.dispatchEvent(new Event("input", {bubbles:true}));
                inp.dispatchEvent(new Event("change", {bubbles:true}));
                return true;
            }""", EMAIL)
            if result:
                print(f"Email filled in: {fr.url[:60]}")
                email_filled = True
                break
        except Exception:
            pass

    if not email_filled:
        print("ERROR: could not fill email")

    page.wait_for_timeout(500)
    shot(page, "01")

    # Click Next (enable if disabled)
    for fr in page.frames:
        try:
            clicked = fr.evaluate("""()=>{
                const btn = document.querySelector("#enterEmailSubmitButton, button[type=submit]");
                if (btn) {
                    btn.removeAttribute("disabled");
                    btn.click();
                    return true;
                }
                return false;
            }""")
            if clicked:
                print(f"Next clicked in: {fr.url[:60]}")
                break
        except Exception:
            pass

    page.wait_for_timeout(8000)
    shot(page, "02")
    print(f"URL after email submit: {page.url}")

    # Scan all frames for Auth0 blocked/reset screen
    found = False
    for fr in page.frames:
        try:
            url = fr.url or ""
            if not url:
                continue
            print(f"Frame: {url[:80]}")
            info = fr.evaluate("""()=>{
                const bt = document.body ? document.body.innerText : "";
                const blocked = /blocked after multiple/i.test(bt);
                const all = [...document.querySelectorAll("a")];
                const rl = all.find(a => /reset.*password|forgot.*password/i.test(a.innerText || ""));
                return {
                    blocked: blocked,
                    resetHref: rl ? rl.href : null,
                    resetText: rl ? rl.innerText.trim() : null,
                    urlSnip: location.href.slice(0, 80),
                    bodySnip: bt.slice(0, 300)
                };
            }""")
            print(f"  blocked={info.get("blocked")}, resetHref={info.get("resetHref")}, body={info.get("bodySnip","")[:100]}")

            if info.get("blocked") or info.get("resetHref"):
                shot(page, "03-blocked")
                href = fr.evaluate("""()=>{
                    const all = [...document.querySelectorAll("a")];
                    const rl = all.find(a => /reset.*password|forgot.*password/i.test(a.innerText || ""));
                    if (rl) { rl.click(); return rl.href; }
                    return null;
                }""")
                print(f"Reset link clicked: {href}")
                page.wait_for_timeout(5000)
                shot(page, "04-after-reset")
                print(f"Final URL: {page.url}")
                print("SUCCESS: password reset flow initiated")
                found = True
                break
        except Exception as ex:
            print(f"Frame error: {ex}")

    if not found:
        print("WARNING: Did not find blocked/reset screen")
        shot(page, "99-no-reset")

    page.close()
    print("Done")

