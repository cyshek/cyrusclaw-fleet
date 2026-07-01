#!/usr/bin/env python3
"""Test fresh-alias account creation path for Keysight iCIMS Auth0."""
import sys, os, time, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CDP = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")
FRESH_EMAIL = "cyshekari+ks2026@gmail.com"
NEW_PW = "JobSearch2026!ks26"
WS = "/home/azureuser/.openclaw/agents/job-search/workspace"
JOB_URL = "https://careers-keysight.icims.com/jobs/53104/login"
import _icims_runner as r

def log(*a): print("[ks_fresh]", *a, flush=True)

def run():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        # Close old Keysight tabs
        for pg in list(ctx.pages):
            if "keysight" in pg.url.lower():
                try: pg.close()
                except: pass
        log("Opening Keysight job URL with fresh email:", FRESH_EMAIL)
        page, term = r.open_apply(ctx, JOB_URL, debug=WS+"/.ks-fresh-debug")
        page.set_default_timeout(25000)
        log("URL:", page.url[:80], "term:", term)
        if term in ("already_applied", "closed"):
            log("Terminal:", term); sys.exit(1)

        # Email gate
        eg = r.email_gate(page, debug=WS+"/.ks-fresh-debug")
        log("Email gate:", eg)

        if eg.get("hcaptcha"):
            log("hCaptcha, solving...")
            hcap_url = eg.get("frame") or page.url
            token, reason = r.try_solve_hcaptcha(eg.get("sitekey"), hcap_url, is_invisible=True)
            log("hCaptcha:", reason, "token:", (token or "")[:20])
            if not token:
                page.screenshot(path=WS+"/ks_fresh_err_hcap.png")
                log("hCaptcha FAILED"); sys.exit(1)
            # Inject the fresh email AND the hcaptcha token, then submit
            frame_0 = page.frames[0] if page.frames else page
            try:
                frame_0.evaluate("""(args) => {
                    const [email, tok] = args;
                    const inp = document.querySelector('input[name=css_loginName]');
                    if(inp){inp.value=email;inp.dispatchEvent(new Event('input',{bubbles:true}));}
                    const hr = document.querySelector('[name=h-captcha-response]');
                    if(hr){hr.value=tok;hr.dispatchEvent(new Event('input',{bubbles:true}));}
                    const gr = document.querySelector('[name=g-recaptcha-response]');
                    if(gr){gr.value=tok;gr.dispatchEvent(new Event('input',{bubbles:true}));}
                    const frm = document.querySelector('form');
                    if(frm){frm.submit();}
                    return {email: inp?.value, hcr: !!hr, gcr: !!gr, frm: !!frm};
                }""", [FRESH_EMAIL, token])
                log("Injected fresh email + hcaptcha token, submitted form")
            except Exception as e:
                log("Inject err:", e)
                page.screenshot(path=WS+"/ks_fresh_err_inject.png")
                sys.exit(1)
            page.wait_for_timeout(8000)
        else:
            # No hCaptcha — just fill email and submit
            try:
                frame_0 = page.frames[0] if page.frames else page
                frame_0.evaluate("""(email) => {
                    const inp = document.querySelector('input[name=css_loginName]');
                    if(inp){inp.value=email;inp.dispatchEvent(new Event('input',{bubbles:true}));}
                    const frm = document.querySelector('form');
                    if(frm){frm.submit();}
                    return inp?.value;
                }""", FRESH_EMAIL)
            except Exception as e:
                log("Submit err:", e)
            page.wait_for_timeout(5000)

        page.screenshot(path=WS+"/ks_fresh_step2.png")
        log("After email gate URL:", page.url[:80])

        # Check what frames exist
        for fr in page.frames:
            log("  frame:", fr.url[:80])

        # Check if Auth0 appeared
        auth0_detected = r._is_auth0_page(page)
        log("Auth0 detected:", auth0_detected)

        if auth0_detected:
            auth0_fr = r._find_auth0_frame(page)
            if auth0_fr:
                # Check what Auth0 shows for fresh email
                body_text = auth0_fr.evaluate("()=>document.body.innerText.substring(0,500)")
                log("Auth0 body text:", body_text[:300])
                page.screenshot(path=WS+"/ks_fresh_auth0.png")

                # Check for signup fields vs password fields
                has_pw = auth0_fr.evaluate("()=>!!document.querySelector('input[type=password]')")
                has_signup = auth0_fr.evaluate("()=>!!document.querySelector('input[name=password][autocomplete=new-password]') || document.body.innerText.toLowerCase().includes('sign up') || document.body.innerText.toLowerCase().includes('create') || document.body.innerText.toLowerCase().includes('register')")
                log("Has password input:", has_pw)
                log("Has signup indicators:", has_signup)

                if has_pw and not has_signup:
                    log("AUTH0 showing PASSWORD step — fresh email already has an account!")
                    log("Trying password:", NEW_PW)
                    # Try to fill password for fresh email account
                    res = auth0_fr.handle_auth0_login if False else None
                    pw_el = auth0_fr.query_selector('input[type=password]')
                    if pw_el:
                        pw_el.fill(NEW_PW)
                        page.wait_for_timeout(300)
                        pw_el.press('Tab')
                        page.wait_for_timeout(300)
                        btn = auth0_fr.query_selector('button[type=submit]')
                        if btn: btn.click()
                        page.wait_for_timeout(4000)
                        page.screenshot(path=WS+"/ks_fresh_pw_attempt.png")
                        log("After pw attempt URL:", page.url[:80])
                elif has_signup:
                    log("AUTH0 showing SIGNUP/REGISTER — this is the path we want!")
                    page.screenshot(path=WS+"/ks_fresh_signup.png")
                    # Fill signup form
                    inputs = auth0_fr.query_selector_all('input')
                    for inp in inputs:
                        itype = inp.get_attribute('type')
                        iname = inp.get_attribute('name')
                        log(f"  signup input: type={itype} name={iname}")
        else:
            log("No Auth0 — on page:", page.url[:80])
            body_text = page.evaluate("()=>document.body.innerText.substring(0,500)")
            log("Body:", body_text[:300])
            page.screenshot(path=WS+"/ks_fresh_noauth0.png")

        log("Done. Screenshots at:", WS+"/ks_fresh_*.png")

run()
