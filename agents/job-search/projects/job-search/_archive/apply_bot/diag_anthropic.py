"""One-off: re-attempt Anthropic submit and capture any validation errors."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://job-boards.greenhouse.io/anthropic/jobs/4985877008"
PROFILE = json.loads(Path("assets/personal-info.json").read_text(encoding="utf-8"))
RESUME = Path("assets/Cyrus_Shekari_Resume.pdf").resolve()
OUT = Path("runs/diag-anthropic")
OUT.mkdir(parents=True, exist_ok=True)


def fill_first(page, value, selectors):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count():
                loc.fill(value, timeout=3000)
                return True
        except Exception:
            continue
    return False


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    time.sleep(2)
    page.locator("button:has-text('Apply'), a:has-text('Apply')").first.click()
    time.sleep(3)
    page.wait_for_selector("input[id^='first_name']", timeout=10000)

    fill_first(page, PROFILE["identity"]["first_name"], ["input[id^='first_name']"])
    fill_first(page, PROFILE["identity"]["last_name"], ["input[id^='last_name']"])
    fill_first(page, PROFILE["contact"]["email"], ["input[type='email']"])
    fill_first(page, PROFILE["contact"]["phone"], ["input[type='tel']"])
    fill_first(page, PROFILE["address"]["city"] + ", " + PROFILE["address"]["state"],
               ["input[id*='location']"])
    page.locator("input[type='file']").first.set_input_files(str(RESUME))
    time.sleep(2)

    # Print all visible REQUIRED fields and their current state
    print("\n=== ALL VISIBLE FORM CONTROLS ===")
    controls = page.locator("input, select, textarea").all()
    for c in controls:
        try:
            tag = c.evaluate("el => el.tagName.toLowerCase()")
            ctype = c.get_attribute("type") or ""
            name = c.get_attribute("name") or ""
            cid = c.get_attribute("id") or ""
            required = c.get_attribute("required") is not None or c.get_attribute("aria-required") == "true"
            value = c.input_value() if tag in ("input", "textarea") and ctype not in ("file", "checkbox", "radio", "submit", "button") else ""
            visible = c.is_visible()
            if not visible or ctype in ("hidden", "submit", "button"):
                continue
            mark = "*" if required else " "
            print(f"  {mark} <{tag} type={ctype}> id='{cid}' name='{name}' value={value!r}")
        except Exception:
            pass

    # Try to click submit and capture error messages
    print("\n=== ATTEMPTING SUBMIT ===")
    submit = page.locator("button[type='submit']").first
    submit.scroll_into_view_if_needed()
    submit.click()
    time.sleep(4)

    # Look for error messages
    print("\n=== ERROR MESSAGES POST-SUBMIT ===")
    for sel in ["[role='alert']", ".error", ".field-error", "[class*='error' i]",
                "[aria-invalid='true']", "p[class*='error' i]"]:
        try:
            errs = page.locator(sel).all()
            for e in errs:
                if e.is_visible():
                    txt = e.inner_text(timeout=1000).strip()
                    if txt:
                        print(f"  [{sel}] {txt[:300]}")
        except Exception:
            pass

    page.screenshot(path=str(OUT / "after-submit.png"), full_page=True)
    Path(OUT / "html.txt").write_text(page.content(), encoding="utf-8")
    print(f"\nSaved: {OUT}")
    browser.close()
