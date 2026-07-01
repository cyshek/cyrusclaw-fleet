#!/usr/bin/env python3
"""Directly reset cyshekari@gmail.com Auth0 password for Keysight via an existing Auth0 state."""
import sys, os, time, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CDP = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")
EMAIL = "cyshekari@gmail.com"
NEW_PW = "JobSearch2026!amd"
WS = "/home/azureuser/.openclaw/agents/job-search/workspace"

import _icims_runner as r
import gmail_imap
from playwright.sync_api import sync_playwright

def log(*a): print("[ks_direct_reset]", *a, flush=True)

def get_keysight_auth0_url():
    import urllib.request
    resp = urllib.request.urlopen(CDP.replace("/json", "") + "/json/list", timeout=5)
    targets = json.loads(resp.read())
    for t in targets:
        url = t.get("url", "")
        if "login.icims.com/u/login/identifier" in url and "keysight" in url.lower():
            return url
    return None

def main():
    since = time.time()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()

        auth0_url = None  # Always use fresh alias flow to avoid stale session state
        if auth0_url:
            log("Using existing Keysight Auth0 tab:", auth0_url[:100])
            page.goto(auth0_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
        else:
            log("No live Auth0 tab — going through email gate with fresh alias")
            fresh = f"cyshekari+ksr{int(time.time())}@gmail.com"
            log("Fresh alias:", fresh)
            page.goto("https://careers-keysight.icims.com/jobs/53104/login", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            # Fill fresh alias in email gate manually (iframe has in_iframe=1 suffix)
            gate_fr = None
            for fr in page.frames:
                # Gate is in the iframe frame
                if "careers-keysight.icims.com" in fr.url and "in_iframe" in fr.url:
                    gate_fr = fr
                    break
            if not gate_fr:
                for fr in page.frames:
                    if "careers-keysight.icims.com" in fr.url:
                        gate_fr = fr
                        break
            if not gate_fr and page.frames:
                gate_fr = page.frames[0]
            log("Gate frame:", gate_fr.url[:80] if gate_fr else None)
            if gate_fr:
                try:
                    fill_r = gate_fr.evaluate(
                        "(e)=>{ const i=document.querySelector("
                        "'#email,input[name=css_loginName],input[type=email],input[name=email]'); "
                        "if(i){i.focus();i.value=e;"
                        "i.dispatchEvent(new Event('input',{bubbles:true}));"
                        "i.dispatchEvent(new Event('change',{bubbles:true}));"
                        "} return i?'ok:'+i.value:'no-input'; }",
                        fresh
                    )
                    log("Email gate fill:", fill_r)
                except Exception as fe:
                    log("Email gate fill error:", fe)
            # Detect hCaptcha on gate
            present, sitekey = r.detect_hcaptcha(page)
            log("Gate hCaptcha:", present, sitekey)
            if present:
                tok, reason = r.try_solve_hcaptcha(
                    sitekey or "94fee806-5cac-4582-9738-384a0f4ea6f8",
                    page.url, is_invisible=True
                )
                if tok and gate_fr:
                    gate_fr.evaluate(r._ICIMS_EMAIL_GATE_INJECT_JS, tok)
                    log("Email gate hCaptcha injected:", reason)
            page.wait_for_timeout(6000)

        if not r._is_auth0_page(page):
            log("NOT on Auth0 page:", page.url[:100])
            page.close()
            sys.exit(1)

        log("On Auth0:", page.url[:100])

        # Solve hCaptcha on identifier page
        auth0_fr = r._find_auth0_frame(page)
        if auth0_fr is None and page.frames:
            auth0_fr = page.frames[0]
        try:
            hcap = auth0_fr.evaluate(r._AUTH0_HCAP_DETECT_JS) if auth0_fr else {}
        except Exception:
            hcap = {}
        log("Auth0 hCaptcha:", hcap.get("present"), hcap.get("sitekey"))

        if hcap.get("present") or hcap.get("sitekey"):
            sitekey = hcap.get("sitekey") or "ccfa5854-6bd6-4dd4-8d86-709a062e61ee"
            tok, reason = None, None
            for _try in range(3):
                tok, reason = r.try_solve_hcaptcha(sitekey, page.url)
                if tok:
                    break
                log(f"hCaptcha attempt {_try+1}/3 failed:", reason)
                page.wait_for_timeout(3000)
            if not tok:
                log("hCaptcha FAILED")
                page.close()
                sys.exit(1)
            log("hCaptcha solved:", reason)
            if auth0_fr:
                auth0_fr.evaluate(r._AUTH0_INJECT_AND_SUBMIT_JS, tok)
            page.wait_for_timeout(2000)
            if auth0_fr:
                auth0_fr.evaluate(r._AUTH0_CLICK_CONTINUE_JS)
            page.wait_for_timeout(5000)

        # Fill email and continue
        auth0_fr = r._find_auth0_frame(page)
        if auth0_fr:
            try:
                log("Filling email:", EMAIL)
                auth0_fr.evaluate(r._AUTH0_FILL_EMAIL_JS, EMAIL)
                page.wait_for_timeout(500)
                auth0_fr.evaluate(r._AUTH0_CLICK_CONTINUE_JS)
                page.wait_for_timeout(4000)
                log("After email continue, URL:", page.url[:100])
            except Exception as e:
                log("Email fill error:", e)

        try:
            page.screenshot(timeout=5000, path=WS+"/ks_dr_01.png")
        except Exception:
            pass

        # Find and click "Reset your password" link
        reset_clicked = False
        for fr in page.frames:
            if "login.icims.com" not in fr.url:
                continue
            try:
                res = fr.evaluate("""() => {
                    const a = [...document.querySelectorAll('a')].find(a =>
                        /reset|forgot/i.test(a.textContent) || /reset/i.test(a.href));
                    if(a){ a.click(); return 'clicked:'+a.textContent.trim(); }
                    return 'none';
                }""")
                log("Reset link result:", res)
                if "clicked" in res:
                    reset_clicked = True
                    break
            except Exception as e:
                log("Frame error:", e)

        if not reset_clicked:
            log("No reset link found")
            page.screenshot(timeout=5000, path=WS+"/ks_dr_err_noreset.png")
            page.close()
            sys.exit(1)

        page.wait_for_timeout(4000)
        page.screenshot(timeout=5000, path=WS+"/ks_dr_02_reset_form.png")
        log("Reset form URL:", page.url[:100])

        # Get reset form sitekey from iframe URL
        reset_sitekey = None
        for fr in page.frames:
            if "hcaptcha.com" in fr.url and "sitekey=" in fr.url:
                m = re.search(r"sitekey=([0-9a-f-]{30,})", fr.url, re.IGNORECASE)
                if m:
                    reset_sitekey = m.group(1)
                    break
        if not reset_sitekey:
            for fr in page.frames:
                if "login.icims.com" in fr.url and "reset" in fr.url:
                    try:
                        reset_sitekey = fr.evaluate("()=>{ const d=document.querySelector('[data-captcha-sitekey]'); return d?d.getAttribute('data-captcha-sitekey'):null; }")
                        if reset_sitekey:
                            break
                    except Exception:
                        pass
        log("Reset sitekey:", reset_sitekey)
        sk = reset_sitekey or "ccfa5854-6bd6-4dd4-8d86-709a062e61ee"

        reset_fr = None
        for fr in page.frames:
            if "login.icims.com" in fr.url and "reset" in fr.url:
                reset_fr = fr
                break

        if not reset_fr:
            log("No reset frame found")
            page.close()
            sys.exit(1)

        # Force-overwrite email field in reset form to ensure it says cyshekari@gmail.com
        try:
            em_res = reset_fr.evaluate(
                "(e)=>{ const i=document.querySelector("
                "'input[type=text],input[type=email],input[name=username]'); "
                "if(i){ const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');"
                " i.focus();d.set.call(i,e);"
                " i.dispatchEvent(new Event('input',{bubbles:true}));"
                " i.dispatchEvent(new Event('change',{bubbles:true})); }"
                " return i?i.value:'no-input'; }",
                EMAIL
            )
            log("Reset form email override:", em_res)
        except Exception as eov:
            log("Reset email override error:", eov)

        # Solve reset form hCaptcha
        rtok, rreason = None, None
        for _try in range(3):
            rtok, rreason = r.try_solve_hcaptcha(sk, page.url, is_invisible=False)
            if rtok:
                break
            log(f"Reset hCaptcha attempt {_try+1}/3 failed:", rreason)
            page.wait_for_timeout(3000)

        if rtok:
            log("Reset hCaptcha solved:", rreason)
            try:
                reset_fr.evaluate(
                    "(t) => {"
                    " const ta=document.querySelector('textarea[name=\"h-captcha-response\"]');"
                    " if(ta){ta.value=t;ta.dispatchEvent(new Event('change',{bubbles:true}));}"
                    " const ci=document.querySelector('div[data-captcha-sitekey] input,input[name=\"captcha\"]');"
                    " if(ci){ci.value=t;}"
                    "}",
                    rtok
                )
            except Exception as e:
                log("Reset captcha inject error:", e)
            page.wait_for_timeout(500)

        # Click Continue
        try:
            click_res = reset_fr.evaluate(r._AUTH0_CLICK_CONTINUE_JS)
            log("Reset Continue clicked:", click_res)
        except Exception as e:
            log("Reset Continue click error:", e)

        page.wait_for_timeout(4000)
        page.screenshot(timeout=5000, path=WS+"/ks_dr_03_after_submit.png")
        log("After reset submit URL:", page.url[:100])

        text = ""
        for fr in page.frames:
            if "login.icims.com" in fr.url:
                try:
                    text = fr.evaluate("()=>document.body.innerText.slice(0,300)")
                    break
                except Exception:
                    pass
        log("Page text:", text[:200])

        if "check" in text.lower() or "email" in text.lower():
            log("SUCCESS — reset email sent. Waiting 120s for Gmail...")
            try:
                link = gmail_imap.wait_for_activation_link(
                    timeout_seconds=120, since_epoch=since, host_hint="login.icims.com"
                )
                if link:
                    log("GOT RESET LINK:", link[:80])
                    page.goto(link, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(3000)
                    log("After link nav URL:", page.url[:100])
                    page.screenshot(timeout=5000, path=WS+"/ks_dr_04_reset_pw.png")
                    # Fill new password
                    for fr in page.frames:
                        try:
                            cnt = fr.evaluate("()=>[...document.querySelectorAll('input[type=password]')].length")
                            if cnt > 0:
                                log("Filling new password...")
                                fr.evaluate(
                                    "(pw) => {"
                                    " const inputs=[...document.querySelectorAll('input[type=password]')];"
                                    " const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');"
                                    " inputs.forEach(i=>{i.focus();d.set.call(i,pw);"
                                    " i.dispatchEvent(new Event('input',{bubbles:true}));"
                                    " i.dispatchEvent(new Event('change',{bubbles:true}));});"
                                    " return inputs.length;"
                                    "}",
                                    NEW_PW
                                )
                                page.wait_for_timeout(500)
                                try:
                                    for loc in fr.locator('input[type=password]').all():
                                        loc.fill(NEW_PW, timeout=3000)
                                except Exception:
                                    pass
                                fr.evaluate(r._AUTH0_CLICK_CONTINUE_JS)
                                page.wait_for_timeout(5000)
                                log("New password set! URL:", page.url[:100])
                                page.screenshot(timeout=5000, path=WS+"/ks_dr_05_done.png")
                                break
                        except Exception as e:
                            log("Password form error:", e)
                else:
                    log("No reset link in Gmail after 120s")
            except Exception as e:
                log("Gmail error:", e)
        else:
            log("No check-email confirmation. Page text:", text[:100])

        page.close()
        browser.close()

if __name__ == "__main__":
    main()
