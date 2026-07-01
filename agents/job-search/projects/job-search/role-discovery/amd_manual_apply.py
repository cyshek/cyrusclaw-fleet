#!/usr/bin/env python3
"""
Manual AMD iCIMS apply script.
Handles: email fill → privacy checkbox → hCaptcha (2Captcha) → Next → form fill → resume → submit
"""
import sys, os, time, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CDP = "http://127.0.0.1:18800"
RESUME = os.path.abspath(os.path.join(HERE, "..", "resume", "Cyrus_Shekari_Resume.pdf"))
_PI_PATH = os.path.join(HERE, "..", "personal-info.json")
with open(_PI_PATH) as f:
    PI = json.load(f)

EMAIL = PI["contact"]["email"]
FIRST = PI["identity"]["first_name"]
LAST = PI["identity"]["last_name"]
PHONE = PI["contact"]["phone"].replace("-", "")
PHONE_FORMATTED = PI["contact"]["phone"]
ADDR1 = PI["address"]["street"]
CITY = PI["address"]["city"]
STATE = PI["address"]["state"]
ZIP = PI["address"]["zip"]
LINKEDIN = PI["contact"].get("linkedin", "")

JOB_URL = "https://careers-amd.icims.com/jobs/79813/product-manager---network-infrastructure/job?mode=apply&apply=yes"

TWOCAPTCHA_KEY = os.environ.get("TWOCAPTCHA_API_KEY", "")
HCAPTCHA_SITEKEY = "94fee806-5cac-4582-9738-384a0f4ea6f8"

def log(*a):
    print("[amd]", *a, flush=True)

def solve_hcaptcha_twocaptcha(sitekey, page_url):
    """Solve hCaptcha via 2Captcha REST API. Returns token or None."""
    if not TWOCAPTCHA_KEY:
        log("ERROR: TWOCAPTCHA_API_KEY not set")
        return None
    import urllib.request, urllib.parse
    base = "https://2captcha.com"
    # Submit task
    data = urllib.parse.urlencode({
        "key": TWOCAPTCHA_KEY,
        "method": "hcaptcha",
        "sitekey": sitekey,
        "pageurl": page_url,
        "json": 1,
    }).encode()
    log("Submitting hCaptcha to 2Captcha...")
    req = urllib.request.Request(f"{base}/in.php", data=data)
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    log("2Captcha submit:", resp)
    if resp.get("status") != 1:
        log("ERROR submitting to 2Captcha:", resp)
        return None
    task_id = resp["request"]
    # Poll for result (up to 3 min)
    for i in range(36):
        time.sleep(5)
        poll_url = f"{base}/res.php?key={TWOCAPTCHA_KEY}&action=get&id={task_id}&json=1"
        pr = json.loads(urllib.request.urlopen(poll_url, timeout=30).read())
        if pr.get("status") == 1:
            token = pr["request"]
            log(f"hCaptcha solved! token={token[:20]}...")
            return token
        if pr.get("request") != "CAPCHA_NOT_READY":
            log("ERROR from 2Captcha:", pr)
            return None
        if i % 6 == 0:
            log(f"  2Captcha: still solving (attempt {i+1}/36)...")
    log("ERROR: 2Captcha timed out")
    return None


async def run():
    from playwright.async_api import async_playwright

    log("Connecting to browser at", CDP)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Open new page for AMD
        page = await ctx.new_page()
        await page.goto(JOB_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4000)
        log("Loaded:", page.url)

        # --- Step 1: Find and fill email in the iframe ---
        email_frame = None
        for fr in page.frames:
            try:
                has_email = await fr.evaluate("()=>!!document.querySelector('#email,input[type=email]')")
                if has_email:
                    email_frame = fr
                    log("Email form in frame:", fr.url[:80])
                    break
            except Exception:
                pass

        if not email_frame:
            log("ERROR: No email form found. Page frames:")
            for fr in page.frames:
                log("  Frame:", fr.url[:80])
            return

        # Fill email
        email_inp = await email_frame.query_selector('#email, input[type="email"]')
        if email_inp:
            await email_inp.fill(EMAIL)
            log("Email filled:", EMAIL)

        # Accept privacy checkbox
        checkbox = await email_frame.query_selector('input[type="checkbox"]')
        if checkbox:
            checked = await checkbox.evaluate("el=>el.checked")
            if not checked:
                await checkbox.click()
                await page.wait_for_timeout(300)
                log("Privacy checkbox accepted")

        await page.wait_for_timeout(500)

        # --- Step 2: Inject hCaptcha token ---
        log("Checking for hCaptcha...")
        has_hcap = False
        for fr in page.frames:
            try:
                has_hcap = await fr.evaluate("()=>!!(window.hcaptcha||document.querySelector('iframe[src*=hcaptcha]'))")
                if has_hcap:
                    log("hCaptcha detected in frame:", fr.url[:60])
                    break
            except Exception:
                pass

        if has_hcap:
            token = solve_hcaptcha_twocaptcha(HCAPTCHA_SITEKEY, JOB_URL)
            if not token:
                log("FATAL: Could not solve hCaptcha")
                return

            # Inject token
            injected = False
            for fr in page.frames:
                try:
                    has_resp = await fr.evaluate(
                        "()=>!!document.querySelector('[name=\"h-captcha-response\"],textarea[id^=\"h-captcha-response\"]')"
                    )
                    if has_resp:
                        await fr.evaluate(f"""(tok) => {{
                            const ta = document.querySelector('[name="h-captcha-response"],textarea[id^="h-captcha-response"]');
                            if (ta) {{
                                const nv = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value');
                                nv.set.call(ta, tok);
                                ta.dispatchEvent(new Event('input', {{bubbles:true}}));
                                ta.dispatchEvent(new Event('change', {{bubbles:true}}));
                            }}
                        }}""", token)
                        log("Injected hCaptcha token into frame:", fr.url[:60])
                        injected = True
                        break
                except Exception:
                    pass

            if not injected:
                # Try parent page
                try:
                    await page.evaluate(f"""(tok) => {{
                        const ta = document.querySelector('[name="h-captcha-response"],textarea[id^="h-captcha-response"]');
                        if (ta) {{
                            const nv = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value');
                            nv.set.call(ta, tok);
                            ta.dispatchEvent(new Event('input', {{bubbles:true}}));
                        }} else {{
                            // hCaptcha callback
                            if (window.hcaptcha) window.hcaptcha.execute();
                        }}
                    }}""", token)
                    log("Injected into parent page")
                except Exception as e:
                    log("Inject warning:", e)

            await page.wait_for_timeout(1000)
        else:
            log("No hCaptcha detected, proceeding")

        # --- Step 3: Click Next ---
        next_clicked = False
        for fr in page.frames:
            try:
                next_btn = await fr.query_selector('#enterEmailSubmitButton, input[type="submit"], button[type="submit"]')
                if next_btn:
                    disabled = await next_btn.evaluate("el=>el.disabled")
                    btn_text = await next_btn.evaluate("el=>(el.value||el.textContent||'').trim()")
                    log(f"Next button: text='{btn_text}' disabled={disabled}")
                    if not disabled:
                        await next_btn.click()
                        next_clicked = True
                        log("Clicked Next/Submit email button")
                        break
                    else:
                        log("Button is disabled - trying force click")
                        await fr.evaluate("""()=>{
                            const b = document.querySelector('#enterEmailSubmitButton')||
                            [...document.querySelectorAll('input[type=submit],button[type=submit],button')]
                            .find(x=>/next|continue|submit/i.test((x.value||x.textContent||'').trim()));
                            if(b){b.removeAttribute('disabled');b.click();}
                        }""")
                        next_clicked = True
                        log("Force-clicked Next")
                        break
            except Exception:
                pass

        if not next_clicked:
            log("ERROR: Could not click Next")
            return

        await page.wait_for_timeout(6000)
        log("After Next:", page.url)

        # --- Step 4: Check if we got an OTP page ---
        for fr in page.frames:
            try:
                body_text = await fr.evaluate("()=>document.body.innerText.substring(0,300)")
                if "verification" in body_text.lower() or "code" in body_text.lower() or "otp" in body_text.lower():
                    log("OTP gate detected:", body_text[:100])
                    # Fetch OTP from Gmail
                    sys.path.insert(0, HERE)
                    from gmail_imap import wait_for_icims_otp
                    otp = wait_for_icims_otp(timeout=90)
                    if otp:
                        log("OTP:", otp)
                        otp_inp = await fr.query_selector('input[type="text"], input[name*="otp"], input[name*="code"]')
                        if otp_inp:
                            await otp_inp.fill(otp)
                            await page.wait_for_timeout(500)
                            verify_btn = await fr.query_selector('button[type="submit"], input[type="submit"]')
                            if verify_btn:
                                await verify_btn.click()
                                await page.wait_for_timeout(4000)
                                log("OTP submitted, URL:", page.url)
            except Exception as e:
                log("OTP check error:", e)

        # --- Step 5: Check what form we're on now ---
        log("Current URL:", page.url)
        all_text = []
        for fr in page.frames:
            try:
                t = await fr.evaluate("()=>document.body.innerText.substring(0,400)")
                if t.strip():
                    all_text.append(f"[{fr.url[:50]}]: {t[:200]}")
            except Exception:
                pass
        log("Page state:", " | ".join(all_text[:5]))

        # --- Step 6: Fill application form if we got past email gate ---
        # Check for common form fields
        await page.wait_for_timeout(2000)

        # Check if we're on a form with first/last name
        form_frame = None
        for fr in page.frames:
            try:
                has_name = await fr.evaluate(
                    "()=>!!(document.querySelector('#firstname,#lastName,#css_respApplicant_firstName,input[name*=first]'))"
                )
                if has_name:
                    form_frame = fr
                    log("Found application form in frame:", fr.url[:80])
                    break
            except Exception:
                pass

        if form_frame:
            log("Filling application form fields...")
            # Name fields
            await _fill_if_exists(form_frame, '#firstname,#css_respApplicant_firstName', FIRST)
            await _fill_if_exists(form_frame, '#lastname,#css_respApplicant_lastName', LAST)
            await _fill_if_exists(form_frame, '#css_respApplicant_phone', PHONE_FORMATTED)
            await _fill_if_exists(form_frame, '#address1,#css_respApplicant_address1', ADDR1)
            await _fill_if_exists(form_frame, '#city,#css_respApplicant_city', CITY)
            await _fill_if_exists(form_frame, '#zip,#css_respApplicant_zip', ZIP)

            # Upload resume
            file_inp = await form_frame.query_selector('input[type="file"]')
            if file_inp:
                await file_inp.set_input_files(RESUME)
                log("Resume uploaded")
                await page.wait_for_timeout(2000)
            else:
                # Check all frames
                for fr in page.frames:
                    try:
                        fi = await fr.query_selector('input[type="file"]')
                        if fi:
                            await fi.set_input_files(RESUME)
                            log("Resume uploaded in frame:", fr.url[:60])
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass
                else:
                    log("WARNING: No file input found for resume")

            await page.wait_for_timeout(1000)

            # Submit form
            for fr in page.frames:
                try:
                    submit = await fr.query_selector(
                        '#submitButton, input[type="submit"], button[type="submit"]'
                    )
                    if submit:
                        btn_text = await submit.evaluate("el=>(el.value||el.textContent||'').trim()")
                        log("Submit button:", btn_text)
                        await submit.click()
                        await page.wait_for_timeout(5000)
                        log("After submit:", page.url)
                        break
                except Exception:
                    pass
        else:
            log("No application form found (maybe still on email gate or different page)")
            # Dump all frames for debugging
            for fr in page.frames:
                try:
                    txt = await fr.evaluate("()=>document.body.innerText.substring(0,300)")
                    log(f"  Frame {fr.url[:60]}: {txt[:150]}")
                except Exception:
                    pass

        # --- Step 7: Check for confirmation ---
        await page.wait_for_timeout(3000)
        log("Final URL:", page.url)
        for fr in page.frames:
            try:
                txt = await fr.evaluate("()=>document.body.innerText.substring(0,500)")
                if any(kw in txt.lower() for kw in ["applied", "confirmation", "thank you", "submitted", "application received"]):
                    log("CONFIRMATION DETECTED:", txt[:200])
                    return "submitted"
            except Exception:
                pass

        log("No confirmation detected. Final page text:")
        for fr in page.frames:
            try:
                txt = await fr.evaluate("()=>document.body.innerText.substring(0,300)")
                if txt.strip():
                    log(f"  [{fr.url[:50]}]:", txt[:200])
            except Exception:
                pass

        await page.wait_for_timeout(2000)
        return "uncertain"


async def _fill_if_exists(frame, selector, value):
    try:
        inp = await frame.query_selector(selector)
        if inp:
            await inp.fill(value)
            log(f"Filled '{selector[:30]}' = {value[:30]}")
    except Exception as e:
        log(f"Fill warning for '{selector[:30]}':", e)


if __name__ == "__main__":
    result = asyncio.run(run())
    log("Result:", result)
