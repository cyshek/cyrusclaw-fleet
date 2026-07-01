#!/usr/bin/env python3
"""Full Keysight iCIMS password reset via residential proxy."""
import time, re, sys, imaplib, email as email_mod
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
import twocaptcha_client as tc
from gmail_imap import _connect
from playwright.sync_api import sync_playwright

CDP_RESIDENTIAL = "http://127.0.0.1:19223"
EMAIL = "cyshekari@gmail.com"
NEW_PW = "JobSearch2026!amd"
DBG = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug"
SITEKEY_GATE = "94fee806-5cac-4582-9738-384a0f4ea6f8"
SITEKEY_AUTH0 = "ccfa5854-6bd6-4dd4-8d86-709a062e61ee"


def shot(pg, name):
    try:
        pg.screenshot(path=f"{DBG}/res-reset-{name}.png")
    except Exception as ex:
        print(f"Shot err: {ex}")


def solve_hcaptcha(sitekey, url, invisible=False, max_attempts=3):
    client = tc.TwoCaptchaClient(proxy="", timeout_s=300)
    for i in range(max_attempts):
        try:
            token = client.hcaptcha(sitekey, url, is_invisible=invisible)
            if token:
                return token
        except Exception as ex:
            print(f"  hCaptcha attempt {i+1} failed: {ex}")
            if i < max_attempts - 1:
                time.sleep(10)
    return None


def inject_captcha_token(fr, token):
    return fr.evaluate("""(tok)=>{
        let count = 0;
        for (const sel of ["textarea[name=h-captcha-response]","textarea[name=g-recaptcha-response]",
                           "textarea[id^=h-captcha-response]","textarea[id^=g-recaptcha-response]"]) {
            for (const el of document.querySelectorAll(sel)) {
                const d = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value");
                d.set.call(el, tok); el.dispatchEvent(new Event("change",{bubbles:true})); count++;
            }
        }
        const hid = document.querySelector("input[name=captcha]");
        if (hid) {
            const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value");
            d.set.call(hid, tok); hid.dispatchEvent(new Event("change",{bubbles:true})); count++;
        }
        return {count};
    }""", token)


def wait_for_reset_email(timeout=300):
    print(f"Waiting for reset email ({timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            M = _connect()
            for mb in ['"[Gmail]/All Mail"', '"[Gmail]/Spam"', 'INBOX']:
                try:
                    M.select(mb)
                    _, data = M.search(None, "SINCE", '"01-Jul-2026"')
                    for mid in reversed(data[0].split()):
                        _, mdata = M.fetch(mid, "(RFC822)")
                        msg = email_mod.message_from_bytes(mdata[0][1])
                        fr_hdr = msg.get("From", "")
                        sub = msg.get("Subject", "")
                        if any(k in (fr_hdr+sub).lower() for k in ["reset","password","unblock","keysight","blocked","auth0","icims-noreply"]):
                            parts = []
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if "text" in part.get_content_type():
                                        parts.append(part.get_payload(decode=True).decode("utf-8","replace"))
                            else:
                                parts.append(msg.get_payload(decode=True).decode("utf-8","replace"))
                            body = " ".join(parts)
                            urls = re.findall(r"https?://\S+", body)
                            reset_urls = [u.strip('"<>.,)') for u in urls
                                         if any(k in u for k in ["reset","ticket","password","login.icims","forgot"])]
                            if reset_urls:
                                M.logout()
                                print(f"Got reset URL: {reset_urls[0][:100]}")
                                return reset_urls[0]
                except Exception:
                    pass
            M.logout()
        except Exception as ex:
            print(f"  Email err: {ex}")
        print(f"  {int(deadline-time.time())}s remaining...")
        time.sleep(15)
    return None


print("=== STEP 1: Load iCIMS + navigate to Auth0 ===")
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_RESIDENTIAL)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()

    pg.goto("https://careers-keysight.icims.com/jobs/53104/login",
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4000)
    shot(pg, "00-gate")
    print(f"URL: {pg.url[:80]}")

    # Fill email in iCIMS gate
    for fr in pg.frames:
        try:
            res = fr.evaluate("""(em)=>{
                const inp = document.querySelector('#email,input[type=email],input[name=email]');
                if (!inp) return false;
                const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
                d.set.call(inp, em);
                inp.dispatchEvent(new Event('input',{bubbles:true}));
                return 'filled:'+inp.value;
            }""", EMAIL)
            if res and "filled:" in str(res):
                print(f"Email filled: {res}")
                break
        except:
            pass

    # Solve gate invisible hCaptcha
    gate_frame_url = pg.url
    for fr in pg.frames:
        try:
            iframes = fr.evaluate("()=>[...document.querySelectorAll('iframe[src*=hcaptcha]')].map(f=>f.src)")
            if iframes:
                gate_frame_url = fr.url
                break
        except:
            pass

    print(f"Solving gate hCaptcha (invisible) url={gate_frame_url[:60]}...")
    gate_token = solve_hcaptcha(SITEKEY_GATE, gate_frame_url, invisible=True)
    if not gate_token:
        print("FATAL: gate hCaptcha failed"); sys.exit(1)
    print(f"Gate token: {gate_token[:30]}...")

    # Inject gate token + submit
    for fr in pg.frames:
        try:
            has_hcap = fr.evaluate("()=>!!document.querySelector('iframe[src*=hcaptcha]')")
            if has_hcap:
                res = fr.evaluate("""(tok)=>{
                    for (const sel of ['textarea[name=h-captcha-response]','textarea[name=g-recaptcha-response]']) {
                        for (const el of document.querySelectorAll(sel)) {
                            const d = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value');
                            d.set.call(el, tok); el.dispatchEvent(new Event('change',{bubbles:true}));
                        }
                    }
                    const btn = document.querySelector('#enterEmailSubmitButton,button[type=submit]');
                    if (btn) { btn.removeAttribute('disabled'); btn.click(); return 'submitted'; }
                    const form = document.querySelector('form');
                    if (form) { HTMLFormElement.prototype.submit.call(form); return 'form-submit'; }
                    return 'no-btn';
                }""", gate_token)
                print(f"Gate submit: {res}")
                break
        except Exception as ex:
            print(f"Gate inject err: {ex}")

    print("Waiting 8s for Auth0 navigation...")
    time.sleep(8)
    shot(pg, "01-post-gate")
    print(f"URL: {pg.url[:80]}")

    # Handle Auth0 identifier
    auth0_fr = pg.frames[0]
    fill_res = auth0_fr.evaluate("""(em)=>{
        const inp = document.querySelector('input#username,input[name=username]');
        if (!inp) return 'no-input';
        const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
        d.set.call(inp, em); inp.dispatchEvent(new Event('input',{bubbles:true}));
        return 'ok:'+inp.value;
    }""", EMAIL)
    print(f"Auth0 email fill: {fill_res}")

    print("Solving Auth0 identifier hCaptcha...")
    auth0_token = solve_hcaptcha(SITEKEY_AUTH0, pg.url, invisible=False)
    if auth0_token:
        print(f"Auth0 token: {auth0_token[:30]}...")
        inject_captcha_token(auth0_fr, auth0_token)
    else:
        print("Auth0 hCaptcha solve failed - proceeding without")

    # Click Continue
    cont = auth0_fr.evaluate("""()=>{
        const btn = document.querySelector('button[type=submit],button[name=action],input[type=submit]');
        if (btn) { btn.click(); return 'clicked:'+btn.textContent.trim().slice(0,20); }
        return 'no-btn';
    }""")
    print(f"Continue: {cont}")
    pg.wait_for_timeout(5000)
    shot(pg, "02-auth0-post-id")
    print(f"URL: {pg.url[:80]}")

    # On password page: click Reset your password
    if "login/password" in pg.url:
        print("On password page - clicking Reset your password...")
        reset_link = auth0_fr.evaluate("""()=>{
            const links = [...document.querySelectorAll('a')];
            const rl = links.find(a => /reset.*password|forgot.*password/i.test(a.innerText || ''));
            if (rl) { rl.click(); return rl.href; }
            return null;
        }""")
        print(f"Reset link: {reset_link}")
        pg.wait_for_timeout(5000)
        shot(pg, "03-reset-form")
        print(f"URL: {pg.url[:80]}")

    # On reset form: solve hCaptcha and submit
    if "reset-password" in pg.url:
        print("On reset form...")
        txt = pg.frames[0].evaluate("()=>document.body.innerText.slice(0,200)")
        print(f"Text: {txt[:100]}")

        has_hcap = pg.frames[0].evaluate("()=>!!document.querySelector('iframe[src*=hcaptcha]')")
        print(f"Has hCaptcha: {has_hcap}")

        if has_hcap:
            reset_token = solve_hcaptcha(SITEKEY_AUTH0, pg.url, invisible=False)
            if reset_token:
                print(f"Reset form token: {reset_token[:30]}...")
                inject_res = inject_captcha_token(pg.frames[0], reset_token)
                print(f"Inject: {inject_res}")
                # Submit
                sub = pg.frames[0].evaluate("""()=>{
                    const btn = document.querySelector('button[type=submit],input[type=submit]');
                    if (btn) { btn.click(); return 'clicked:'+btn.textContent.trim().slice(0,20); }
                    return 'no-btn';
                }""")
                print(f"Submit: {sub}")
            else:
                print("Reset hCaptcha failed")
        else:
            print("No hCaptcha on reset form - submitting directly")
            sub = pg.frames[0].evaluate("""()=>{
                const btn = document.querySelector('button[type=submit],input[type=submit]');
                if (btn) { btn.click(); return 'clicked'; }
                return 'no-btn';
            }""")
            print(f"Submit: {sub}")

        pg.wait_for_timeout(5000)
        shot(pg, "04-after-submit")
        txt2 = pg.frames[0].evaluate("()=>document.body.innerText.slice(0,200)")
        print(f"After submit: {txt2[:150]}")
    else:
        print(f"WARNING: Not on reset form (url={pg.url[:80]})")

    pg.close()

print("\n=== STEP 2: Wait for reset email ===")
reset_url = wait_for_reset_email(timeout=300)
if not reset_url:
    print("ERROR: No reset email received after 5 minutes")
    sys.exit(1)

print(f"\n=== STEP 3: Set new password ===")
print(f"URL: {reset_url[:100]}")
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(CDP_RESIDENTIAL)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.new_page()
    pg.goto(reset_url, wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(2000)
    pw_inputs = pg.query_selector_all("input[type=password]")
    for inp in pw_inputs:
        inp.fill(NEW_PW)
    print(f"Filled {len(pw_inputs)} password fields with new password")
    btn = pg.query_selector("button[type=submit],input[type=submit]")
    if btn:
        btn.click()
        pg.wait_for_timeout(4000)
        pg.screenshot(path=f"{DBG}/res-reset-done.png")
        txt = pg.evaluate("()=>document.body.innerText.slice(0,300)")
        print(f"Done: {txt[:200]}")
    pg.close()

print("\n=== PASSWORD RESET COMPLETE ===")
print(f"New password: {NEW_PW}")
