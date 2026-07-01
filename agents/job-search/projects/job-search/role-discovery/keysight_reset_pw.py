#!/usr/bin/env python3
"""Reset Keysight iCIMS Auth0 password for cyshekari@gmail.com -> JobSearch2026!amd"""
import sys, os, time, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CDP = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")
EMAIL = "cyshekari@gmail.com"  # The REAL Keysight Auth0 account (NOT +keysight alias, that doesn't exist)
NEW_PW = "JobSearch2026!amd"
WS = "/home/azureuser/.openclaw/agents/job-search/workspace"
JOB_URL = "https://careers-keysight.icims.com/jobs/53104/login"
import _icims_runner as r
import gmail_imap

def log(*a): print("[ks_reset]", *a, flush=True)

def run():
    from playwright.sync_api import sync_playwright
    since_epoch = time.time()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        for pg in list(ctx.pages):
            if "keysight" in pg.url.lower():
                try: pg.close()
                except: pass
        log("Opening Keysight job URL...")
        page, term = r.open_apply(ctx, JOB_URL, debug=WS+"/.ks-reset-debug")
        page.set_default_timeout(20000)
        log("After open_apply URL:", page.url[:80], "term:", term)
        if term in ("already_applied", "closed"):
            log("Terminal state:", term); sys.exit(1)
        eg = r.email_gate(page, debug=WS+"/.ks-reset-debug")
        log("Email gate:", eg)
        if eg.get("hcaptcha"):
            log("hCaptcha detected, solving...")
            hcap_url = eg.get("frame") or page.url
            token, reason = r.try_solve_hcaptcha(eg.get("sitekey"), hcap_url, is_invisible=True)
            log("hCaptcha:", reason, "token:", token[:20] if token else None)
            if not token:
                log("hCaptcha FAILED"); sys.exit(1)
            r.inject_hcaptcha(page, token)
            page.wait_for_timeout(6000)
        else:
            r.submit_email(page)
            page.wait_for_timeout(5000)
        try:
            page.screenshot(path=WS+"/ks_reset_step2.png", timeout=5000)
        except Exception as _e:
            log("screenshot step2 skipped:", _e)
        log("After email gate URL:", page.url[:80])
        otp = r.handle_otp_gate(page, debug=WS+"/.ks-reset-debug", timeout=60)
        log("OTP:", otp)
        auth0_fr = r._find_auth0_frame(page)
        if not auth0_fr:
            page.wait_for_timeout(5000)
            auth0_fr = r._find_auth0_frame(page)
        if not auth0_fr:
            log("Auth0 frame NOT found")
            for f in page.frames: log("  frame:", f.url[:100])
            try: page.screenshot(path=WS+"/ks_reset_err_noauth0.png", timeout=5000)
            except Exception: pass
            sys.exit(1)
        log("Auth0 frame:", auth0_fr.url[:80])
        # Check if Auth0 identifier has its own hCaptcha (Keysight uses sitekey ccfa5854)
        # Fill email FIRST so it's present when hCaptcha token is injected/submitted
        try:
            auth0_fr.evaluate(r._AUTH0_FILL_EMAIL_JS, EMAIL)
            page.wait_for_timeout(300)
            log("Auth0 email pre-filled")
        except Exception as e: log("Auth0 email pre-fill err:", e)
        try:
            auth0_hcap = auth0_fr.evaluate(r._AUTH0_HCAP_DETECT_JS)
            log("Auth0 hCaptcha: present=%s sitekey=%s" % (auth0_hcap.get('present'), auth0_hcap.get('sitekey')))
            if auth0_hcap.get('present') or auth0_hcap.get('sitekey'):
                sk = auth0_hcap.get('sitekey') or 'ccfa5854-6bd6-4dd4-8d86-709a062e61ee'  # Keysight actual sitekey
                log("Solving Auth0 hCaptcha sitekey:", sk)
                atok, areason = r.try_solve_hcaptcha(sk, page.url, is_invisible=False)
                if atok:
                    log("Auth0 hCaptcha solved:", areason)
                    # Inject token into the h-captcha-response textarea
                    auth0_fr.evaluate(r._AUTH0_INJECT_AND_SUBMIT_JS, atok)
                    page.wait_for_timeout(1000)
                    # Auth0 reads input[name="captcha"] inside div[data-captcha-sitekey]
                    # Set that hidden input, then click Continue (not form.submit())
                    try:
                        inp_val = auth0_fr.evaluate(
                            "(tok) => { const el = document.querySelector('div[data-captcha-sitekey] input,input[name=\"captcha\"]'); "
                            "if (el) { el.value = tok; return 'captcha_input_set:'+tok.slice(0,10); } return 'no_captcha_input'; }",
                            atok
                        )
                        log("Auth0 hidden captcha input:", inp_val)
                    except Exception as e: log("Auth0 captcha hidden input err:", e)
                    # Click Continue button (triggers Auth0's submit handler which checks y.value)
                    try:
                        auth0_fr.evaluate(r._AUTH0_CLICK_CONTINUE_JS)
                        log("Auth0 hCaptcha: clicked Continue after inject")
                    except Exception as e: log("Auth0 hCaptcha continue-click err:", e)
                    page.wait_for_timeout(5000)
                    # Re-find Auth0 frame after captcha submit
                    auth0_fr = r._find_auth0_frame(page)
                    if not auth0_fr:
                        log("Auth0: navigated away after captcha")
                else:
                    log("Auth0 hCaptcha FAILED:", areason)
        except Exception as e: log("Auth0 hCaptcha check err:", e)
        if not auth0_fr:
            log("Auth0 frame lost after hCaptcha")
            sys.exit(1)
        try:
            auth0_fr.evaluate(r._AUTH0_FILL_EMAIL_JS, EMAIL)
            page.wait_for_timeout(500)
            auth0_fr.evaluate(r._AUTH0_CLICK_CONTINUE_JS)
            page.wait_for_timeout(4000)
            log("Auth0 identifier done")
        except Exception as e: log("Auth0 identifier err:", e)
        try:
            page.screenshot(path=WS+"/ks_reset_step3.png", timeout=5000)
        except Exception: pass
        reset_triggered = False
        for _attempt in range(3):
            for fr in page.frames:
                if "login.icims.com" in fr.url:
                    log("Auth0 frame:", fr.url[:80])
                    try:
                        cnt = fr.locator("a").filter(has_text="Reset").count()
                        log("Reset links:", cnt)
                        if cnt > 0:
                            fr.locator("a").filter(has_text="Reset").first.click()
                            log("Clicked Reset")
                            reset_triggered = True
                            break
                    except Exception as e:
                        log("Reset click err:", e)
                        m = re.search(r"state=([A-Za-z0-9_.\-]+)", fr.url)
                        if m:
                            fp = "https://login.icims.com/u/reset-password?state=" + m.group(1)
                            log("Direct navigate to:", fp)
                            page.goto(fp, wait_until="domcontentloaded", timeout=15000)
                            reset_triggered = True
                        break
            if reset_triggered: break
            page.wait_for_timeout(2000)
        if not reset_triggered:
            log("Could not trigger reset")
            for fr in page.frames: log("  frame:", fr.url[:100])
            try: page.screenshot(path=WS+"/ks_reset_err_noreset.png", timeout=5000)
            except Exception: pass
            sys.exit(1)
        page.wait_for_timeout(4000)
        try: page.screenshot(path=WS+"/ks_reset_step4.png", timeout=5000)
        except Exception: pass
        log("On forgot-pw form, clicking Continue to send email...")
        for fr in page.frames:
            if "login.icims.com" in fr.url and "reset-password" in fr.url:
                try:
                    # Check for hCaptcha on reset form
                    hcap_fr = None
                    for hfr in page.frames:
                        if "hcaptcha.com" in hfr.url and "checkbox" in hfr.url:
                            hcap_fr = hfr
                            break
                    if hcap_fr:
                            log("hCaptcha on reset form detected, solving...")
                            # Get sitekey from reset form
                            reset_sitekey = fr.evaluate("() => { const d = document.querySelector('[data-captcha-sitekey],[data-sitekey]'); if(!d)return null; return d.getAttribute('data-captcha-sitekey')||d.getAttribute('data-sitekey'); }")
                            if not reset_sitekey:
                                # Extract from iframe URL
                                for ifr in page.frames:
                                    if "hcaptcha.com" in ifr.url and "sitekey=" in ifr.url:
                                        import re as _re
                                        m2 = _re.search(r"sitekey=([0-9a-f-]{30,})", ifr.url, _re.IGNORECASE)
                                        if m2: reset_sitekey = m2.group(1); break
                            log("Reset form sitekey:", reset_sitekey)
                            sk = reset_sitekey or "ccfa5854-6bd6-4dd4-8d86-709a062e61ee"  # Keysight uses same sitekey on reset form
                            rtok, rreason = r.try_solve_hcaptcha(sk, fr.url, is_invisible=False)
                            if rtok:
                                log("Reset hCaptcha solved:", rreason)
                                # Inject into BOTH h-captcha-response textarea AND hidden captcha input
                                fr.evaluate(
                                    "(t) => {"
                                    " const ta = document.querySelector('textarea[name=\"h-captcha-response\"]');"
                                    " if(ta){ta.value=t;ta.dispatchEvent(new Event('change',{bubbles:true}));}"
                                    " const ci = document.querySelector('div[data-captcha-sitekey] input, input[name=\"captcha\"]');"
                                    " if(ci){ci.value=t;}"
                                    "}",
                                    rtok
                                )
                                page.wait_for_timeout(500)
                            else:
                                log("Reset hCaptcha FAILED:", rreason)
                    cnt = fr.locator("button[type=submit], button:has-text('Continue')").count()
                    log("Submit/Continue buttons in frame:", cnt, fr.url[:60])
                    if cnt > 0:
                        fr.locator("button[type=submit], button:has-text('Continue')").first.click()
                        log("Clicked Continue on forgot-pw form")
                        page.wait_for_timeout(4000)
                        break
                except Exception as e: log("Continue click err:", e)
        try: page.screenshot(path=WS+"/ks_reset_step4b.png", timeout=5000)
        except Exception: pass
        log("After Continue, waiting for Gmail email (90s)...")
        reset_url = None
        try: reset_url = gmail_imap.wait_for_activation_link(timeout_seconds=90, since_epoch=since_epoch)
        except Exception as e: log("Gmail err:", e)
        if not reset_url:
            try: reset_url = gmail_imap.wait_for_activation_link(timeout_seconds=30, since_epoch=since_epoch)
            except Exception as e2: log("Gmail retry err:", e2)
        if not reset_url:
            log("No reset link found. Screenshots at:", WS+"/ks_reset_step*.png"); sys.exit(1)
        log("Navigating to reset URL:", reset_url[:100])
        page.goto(reset_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        try: page.screenshot(path=WS+"/ks_reset_step5.png", timeout=5000)
        except Exception: pass
        log("Reset page URL:", page.url[:80])
        pw_filled = False
        for fr in page.frames:
            try:
                pwd = fr.locator("input[type=password]")
                cnt = pwd.count()
                log("Pw inputs:", cnt, fr.url[:60])
                if cnt > 0:
                    pwd.first.fill(NEW_PW)
                    if cnt > 1: pwd.nth(1).fill(NEW_PW)
                    page.wait_for_timeout(500)
                    sub = fr.locator("button[type=submit], input[type=submit]").first
                    sub.click()
                    log("Submitted new password")
                    page.wait_for_timeout(3000)
                    pw_filled = True
                    break
            except Exception as e: log("Pw fill err:", e)
        try: page.screenshot(path=WS+"/ks_reset_step6.png", timeout=5000)
        except Exception: pass
        log("Final URL:", page.url[:80])
        if pw_filled: log("SUCCESS: Password reset to", NEW_PW)
        else: log("FAIL: Could not fill password"); sys.exit(1)
        page.close()

run()
