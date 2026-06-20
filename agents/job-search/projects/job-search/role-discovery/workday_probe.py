"""Quick probe: open a tenant's apply URL headless, dump entry-point state.

Reports:
- Whether the URL needs "/apply" appended.
- Whether "Apply" button is present, whether "Apply Manually" anonymous flow is offered,
  or whether sign-in/account creation is required.

Usage:
    .venv/bin/python role-discovery/workday_probe.py --url <jd-or-apply-url>
"""
import argparse, sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def probe(url: str) -> dict:
    out = {"url": url, "transitions": []}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, user_agent=UA)
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            out["transitions"].append({"label": "initial", "url": page.url})
            out["has_apply_button"] = page.locator('[data-automation-id="adventureButton"], a:has-text("Apply"):visible, button:has-text("Apply"):visible').count()
            # Try clicking Apply (top-of-page primary)
            for sel in ['[data-automation-id="adventureButton"]', 'a[role="button"]:has-text("Apply")', 'button:has-text("Apply")']:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible(timeout=500):
                    out["clicked_apply_selector"] = sel
                    try:
                        loc.click()
                        page.wait_for_timeout(3500)
                    except Exception as e:
                        out["apply_click_error"] = str(e)
                    break
            out["transitions"].append({"label": "after-apply", "url": page.url})
            out["has_apply_manually"] = page.locator('[data-automation-id="applyManually"]').count()
            out["has_apply_with_indeed"] = page.locator('[data-automation-id="applyWithIndeed"]').count()
            out["has_apply_with_linkedin"] = page.locator('[data-automation-id="applyWithLinkedIn"]').count()
            out["has_sign_in"] = page.locator('button:has-text("Sign In"), [data-automation-id="signInLink"], a:has-text("Sign In")').count()
            out["has_create_account"] = page.locator('button:has-text("Create Account"), [data-automation-id="createAccountLink"], a:has-text("Create Account")').count()
            out["has_email_input"] = page.locator('input[type=email]:visible, [data-automation-id="email"]:visible').count()
            out["has_password_input"] = page.locator('input[type=password]:visible').count()
            body = (page.locator("body").text_content() or "")[:600]
            out["body_excerpt"] = body
            # Try Apply Manually if available
            if out["has_apply_manually"]:
                try:
                    page.click('[data-automation-id="applyManually"]')
                    page.wait_for_timeout(3500)
                    out["transitions"].append({"label": "after-applyManually", "url": page.url})
                    out["post_am_has_email"] = page.locator('input[type=email]:visible, [data-automation-id="email"]:visible').count()
                    out["post_am_has_password"] = page.locator('input[type=password]:visible').count()
                    out["post_am_body"] = (page.locator("body").text_content() or "")[:600]
                except Exception as e:
                    out["am_click_error"] = str(e)
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"
        finally:
            ctx.close(); b.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    args = ap.parse_args()
    res = probe(args.url)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
