"""Fill Scale AI PM Data Engine form, then SLOWLY submit and capture every state."""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")
from greenhouse import GreenhouseApplier
from base import load_profile, RUNS

URL = "https://job-boards.greenhouse.io/scaleai/jobs/4670064005"

OUT = RUNS / "submit-debug-scale-ai"
OUT.mkdir(parents=True, exist_ok=True)


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()

    # Capture network responses related to submission
    submissions = []

    def on_response(resp):
        url = resp.url
        if resp.status == 428 or "/scaleai/jobs/" in url and resp.request.method == "POST":
            try:
                body = resp.text()[:2000]
            except Exception as e:
                body = f"<err: {e}>"
            entry = {
                "url": url,
                "status": resp.status,
                "method": resp.request.method,
                "headers": {k: v for k, v in resp.headers.items() if k.lower() in
                            ('cf-ray', 'cf-mitigated', 'server', 'cf-cache-status',
                             'content-type', 'x-error', 'www-authenticate')},
                "body": body,
            }
            submissions.append(entry)
        elif any(k in url for k in ("greenhouse", "applications", "submit", "/api/")):
            submissions.append({
                "url": url,
                "status": resp.status,
                "method": resp.request.method,
            })

    page.on("response", on_response)

    # Use the adapter to fill, but skip its internal submit
    a = GreenhouseApplier(url=URL, company="Scale AI", role="dbg", dry_run=True, headless=True)
    profile = load_profile()
    a.apply(page, profile)

    # Now find the submit button and click it via JS to bypass any overlay
    print("\n=== Manual submit ===")
    page.screenshot(path=str(OUT / "before-submit.png"), full_page=True)
    print(f"URL before: {page.url}")

    btn = page.locator("button:has-text('Submit application'), button:has-text('Submit Application')").first
    print(f"Submit btn count: {btn.count()}")
    if btn.count():
        btn.scroll_into_view_if_needed()
        # Try regular click
        try:
            btn.click(timeout=5000)
            print("Click succeeded")
        except Exception as e:
            print(f"Click failed: {e}")
            # Try JS click
            try:
                btn.evaluate("el => el.click()")
                print("JS click succeeded")
            except Exception as e2:
                print(f"JS click failed: {e2}")

    print("\n=== Waiting 20s for submission to process ===")
    for i in range(4):
        time.sleep(5)
        print(f"  +{(i+1)*5}s URL: {page.url}")

    page.screenshot(path=str(OUT / "after-submit.png"), full_page=True)
    body_text = page.locator("body").inner_text(timeout=5000)
    (OUT / "body.txt").write_text(body_text, encoding="utf-8")
    print(f"\n--- Body length: {len(body_text)} ---")
    print(body_text[:1000])

    # Look for validation errors
    err_locs = page.locator("[class*='error' i]:visible, [role='alert']:visible").all()
    print(f"\n--- Error indicators visible: {len(err_locs)} ---")
    for e in err_locs[:10]:
        try:
            t = e.inner_text(timeout=300).strip()
            if t:
                print(f"  ! {t[:120]}")
        except Exception:
            pass

    print(f"\n--- Network responses ({len(submissions)}) ---")
    for s in submissions[-15:]:
        print(f"  {s['method']} {s['status']} {s['url'][:120]}")

    (OUT / "submissions.json").write_text(json.dumps(submissions, indent=2), encoding="utf-8")

    b.close()
print(f"\nOutput: {OUT}")
