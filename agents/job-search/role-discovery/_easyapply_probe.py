#!/usr/bin/env python3
"""Time-boxed LinkedIn Easy-Apply feasibility probe.
Attaches to the running OpenClaw Chromium over CDP (same as the resolver),
injects li_at, navigates to a job URL, and inspects the Easy-Apply path.
DRY-RUN by default: never clicks final Submit unless --submit passed.
"""
import sys, time, pathlib, json

PROJ = pathlib.Path(__file__).resolve().parents[1]
LI_AT_FILE = PROJ / ".linkedin-li-at"
CDP = "http://127.0.0.1:18800"
DBG = PROJ / "role-discovery" / ".easyapply-debug"
DBG.mkdir(parents=True, exist_ok=True)

def inject_li_at(ctx):
    try:
        ctx.clear_cookies()
        print("[probe] cleared existing context cookies")
    except Exception as e:
        print(f"[probe] clear_cookies failed: {e}")
    val = LI_AT_FILE.read_text().strip()
    exp = time.time() + 330*24*3600
    ctx.add_cookies([
        {"name":"li_at","value":val,"domain":dom,"path":"/","secure":True,
         "httpOnly":True,"sameSite":"None","expires":exp}
        for dom in (".www.linkedin.com",".linkedin.com")
    ])
    print(f"[probe] injected li_at len={len(val)}")

def shot(page, name):
    p = DBG / name
    try:
        page.screenshot(path=str(p), full_page=False)
        print(f"[probe] shot -> {p}")
    except Exception as e:
        print(f"[probe] shot fail {name}: {e}")

def main():
    url = sys.argv[1]
    do_submit = "--submit" in sys.argv
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    inject_li_at(ctx)
    page = ctx.new_page()
    try:
        print(f"[probe] goto {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(4)
        title = page.title()
        cur = page.url
        print(f"[probe] title={title!r}")
        print(f"[probe] url={cur}")
        # auth check
        body = page.inner_text("body")[:500]
        if "/authwall" in cur or "Sign in" in title or "Join LinkedIn" in body:
            print("[probe] !! AUTHWALL — li_at not honored")
            shot(page,"authwall.png")
            return
        shot(page,"01-jd.png")
        # find Easy Apply button
        ea = page.query_selector("button.jobs-apply-button, button[aria-label*='Easy Apply'], button:has-text('Easy Apply')")
        # broader scan
        btns = page.query_selector_all("button")
        labels = []
        for b in btns:
            try:
                t = (b.inner_text() or "").strip()
                al = b.get_attribute("aria-label") or ""
                if t or al:
                    if "apply" in (t+al).lower():
                        labels.append(f"text={t!r} aria={al!r}")
            except Exception:
                pass
        print("[probe] apply-ish buttons:")
        for l in labels[:15]:
            print("   ", l)
        # detect easy apply specifically
        is_easy = any("easy apply" in l.lower() for l in labels)
        print(f"[probe] EASY_APPLY_DETECTED={is_easy}")
        if not is_easy:
            print("[probe] no Easy Apply on this row — likely off-site Apply")
            return
        # click easy apply
        eab = None
        for sel in ["button.jobs-apply-button","button[aria-label*='Easy Apply']"]:
            eab = page.query_selector(sel)
            if eab: break
        if not eab:
            eab = page.query_selector("button:has-text('Easy Apply')")
        print(f"[probe] clicking Easy Apply (sel found={bool(eab)})")
        eab.click()
        time.sleep(3)
        shot(page,"02-modal-step1.png")
        # walk modal steps
        step = 0
        while step < 12:
            step += 1
            modal = page.query_selector("div.jobs-easy-apply-modal, div[role='dialog']")
            if not modal:
                print(f"[probe] step{step}: no modal found")
                break
            mtext = modal.inner_text()[:1500]
            print(f"\n===== MODAL STEP {step} =====")
            print(mtext)
            # inputs/selects in modal
            inps = modal.query_selector_all("input, select, textarea")
            print(f"[probe] step{step}: {len(inps)} input/select/textarea")
            for inp in inps[:25]:
                try:
                    typ = inp.get_attribute("type") or inp.evaluate("e=>e.tagName")
                    nm = inp.get_attribute("name") or inp.get_attribute("id") or ""
                    al = inp.get_attribute("aria-label") or ""
                    val = inp.get_attribute("value") or ""
                    req = inp.get_attribute("aria-required") or inp.get_attribute("required") or ""
                    print(f"     [{typ}] name={nm!r} aria={al!r} val={val!r} req={req}")
                except Exception:
                    pass
            # file inputs (resume)
            files = modal.query_selector_all("input[type=file]")
            print(f"[probe] step{step}: {len(files)} file inputs")
            # captcha probe
            cap = page.query_selector("iframe[src*='captcha'], iframe[src*='recaptcha'], iframe[src*='hcaptcha'], div[class*='captcha']")
            if cap:
                print(f"[probe] !! CAPTCHA element present: {cap.get_attribute('src')}")
            shot(page, f"step-{step:02d}.png")
            # find footer buttons
            fbtns = modal.query_selector_all("button")
            footer = []
            for b in fbtns:
                try:
                    t=(b.inner_text() or "").strip()
                    al=b.get_attribute("aria-label") or ""
                    if t or al: footer.append((t,al,b))
                except Exception: pass
            print("[probe] modal buttons:", [(t,al) for t,al,_ in footer])
            # decide next action
            nxt=None; submit=None; review=None
            for t,al,b in footer:
                low=(t+al).lower()
                if "submit application" in low: submit=b
                elif "review" in low: review=b
                elif "next" in low or "continue" in low: nxt=b
            if submit:
                print("[probe] *** REACHED SUBMIT BUTTON ***")
                if do_submit:
                    print("[probe] CLICKING SUBMIT FOR REAL")
                    submit.click(); time.sleep(4)
                    shot(page,"99-after-submit.png")
                    print("[probe] post-submit text:", page.inner_text("body")[:400])
                else:
                    print("[probe] DRY-RUN: not clicking submit. Full path reachable.")
                break
            target = nxt or review
            if not target:
                print("[probe] no Next/Review/Submit button — stuck or form needs input")
                break
            print(f"[probe] clicking advance button: {target.inner_text()!r}")
            target.click()
            time.sleep(2.5)
    finally:
        try: page.close()
        except Exception: pass
        print("[probe] done")

if __name__ == "__main__":
    main()
