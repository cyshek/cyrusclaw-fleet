#!/usr/bin/env python3
"""warm_profile.py — seed the persistent warmed Chrome profile with ORGANIC
state so reCAPTCHA-v3 assigns a non-zero behavioral/profile trust score.

What "warming" does (the genuinely-untested lever for the residential-RESISTANT
strict-Ashby cohort — Tavus 891 etc. that stay RECAPTCHA_SCORE_BELOW_THRESHOLD
even through verified residential egress):
  - visit google.com, accept the consent (sets NID / SOCS Google cookies)
  - run a couple of real searches, click into a result, dwell + human-like scroll
  - browse a few mainstream high-trust sites with dwell
  - load a public page that embeds reCAPTCHA so Google sets its _GRECAPTCHA cookie
    against THIS profile from THIS (residential) egress

Connects to the warmed headful Chrome over CDP (JOBSEARCH_CDP, default :19333).
Idempotent-ish: safe to re-run to refresh/age the profile. Prints the cookies
acquired so you can confirm NID/_GRECAPTCHA landed.

Run AFTER `source warmed_profile_chrome.sh`:
    .venv/bin/python warm_profile.py
"""
import os, sys, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

CDP = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:19333")

def human_dwell(page, lo=1.2, hi=3.0):
    page.wait_for_timeout(int(random.uniform(lo, hi) * 1000))

def human_scroll(page, steps=None):
    steps = steps or random.randint(3, 7)
    for _ in range(steps):
        dy = random.randint(180, 520)
        try:
            page.mouse.wheel(0, dy)
        except Exception:
            page.evaluate("(y)=>window.scrollBy(0,y)", dy)
        page.wait_for_timeout(int(random.uniform(0.3, 0.9) * 1000))

def human_mouse(page):
    # a few organic mouse moves
    for _ in range(random.randint(3, 6)):
        try:
            page.mouse.move(random.randint(80, 1800), random.randint(120, 950),
                            steps=random.randint(5, 15))
        except Exception:
            pass
        page.wait_for_timeout(int(random.uniform(0.2, 0.6) * 1000))

def accept_google_consent(page):
    # Google EU/consent interstitial; click an Accept-all-ish button if present.
    for sel in [
        'button:has-text("Accept all")', 'button:has-text("Alle akzeptieren")',
        'button:has-text("I agree")', 'button:has-text("Accept")',
        '#L2AGLb', 'button[aria-label*="Accept"]',
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=3000)
                page.wait_for_timeout(1200)
                return True
        except Exception:
            continue
    return False

def main():
    print(f"[warm] connecting to {CDP}")
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0] if b.contexts else b.new_context()
        page = ctx.new_page()
        try:
            page.set_viewport_size({"width": 1920, "height": 1080})
        except Exception:
            pass

        # sanity: confirm egress + clean fingerprint
        try:
            page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded", timeout=30000)
            print("[warm] egress:", page.inner_text("body"))
            print("[warm] UA:", page.evaluate("()=>navigator.userAgent"))
            print("[warm] webdriver:", page.evaluate("()=>navigator.webdriver"))
        except Exception as e:
            print("[warm] egress check failed:", e)

        # 1) Google + consent
        try:
            page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=40000)
            human_dwell(page)
            accepted = accept_google_consent(page)
            print("[warm] google consent accepted:", accepted)
            human_mouse(page)
        except Exception as e:
            print("[warm] google load failed:", e)

        # 2) a couple of real searches with dwell + a result click
        queries = ["solutions engineer interview tips", "what is reCAPTCHA v3", "ashby applicant tracking system"]
        for q in random.sample(queries, 2):
            try:
                page.goto("https://www.google.com/search?q=" + q.replace(" ", "+"),
                          wait_until="domcontentloaded", timeout=40000)
                human_dwell(page, 1.5, 3.5)
                human_scroll(page)
                # click first organic result if reachable
                link = None
                for sel in ['a h3', 'div#search a[href^="http"]']:
                    link = page.query_selector(sel)
                    if link:
                        break
                if link:
                    try:
                        link.click(timeout=4000)
                        page.wait_for_load_state("domcontentloaded", timeout=20000)
                        human_dwell(page, 2.0, 4.0)
                        human_scroll(page)
                        human_mouse(page)
                        print(f"[warm] searched + clicked result for: {q!r} -> {page.url[:80]}")
                    except Exception as e:
                        print(f"[warm] result click failed for {q!r}: {e}")
                else:
                    print(f"[warm] searched (no clickable result captured): {q!r}")
            except Exception as e:
                print(f"[warm] search failed for {q!r}: {e}")

        # 3) a few mainstream high-trust sites with dwell
        for url in ["https://en.wikipedia.org/wiki/Recaptcha",
                    "https://www.bbc.com/news",
                    "https://news.ycombinator.com/"]:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                human_dwell(page, 1.5, 3.5)
                human_scroll(page)
                human_mouse(page)
                print(f"[warm] browsed {url[:60]}")
            except Exception as e:
                print(f"[warm] browse failed {url[:40]}: {e}")

        # 4) load a public reCAPTCHA demo so Google sets _GRECAPTCHA for this profile
        for url in ["https://www.google.com/recaptcha/api2/demo",
                    "https://patrickhlauke.github.io/recaptcha/"]:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                human_dwell(page, 2.0, 4.0)
                human_mouse(page)
                print(f"[warm] reCAPTCHA seed page: {url[:60]}")
            except Exception as e:
                print(f"[warm] recaptcha seed failed {url[:40]}: {e}")

        # report cookies acquired (the trust-signal evidence)
        try:
            cookies = ctx.cookies()
            interesting = [c for c in cookies if c.get("name") in
                           ("NID", "SOCS", "_GRECAPTCHA", "AEC", "1P_JAR", "CONSENT", "DV")]
            print(f"[warm] total cookies in profile: {len(cookies)}")
            for c in interesting:
                print(f"[warm]   trust-cookie {c['name']} domain={c.get('domain')} "
                      f"len={len(str(c.get('value','')))}")
            doms = {}
            for c in cookies:
                doms[c.get("domain","?")] = doms.get(c.get("domain","?"),0)+1
            top = sorted(doms.items(), key=lambda kv:-kv[1])[:12]
            print("[warm] cookie domains:", top)
        except Exception as e:
            print("[warm] cookie report failed:", e)

        page.close()
    print("[warm] done. profile warmed.")

if __name__ == "__main__":
    main()
