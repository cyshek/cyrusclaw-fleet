"""Open a Greenhouse form, click each react-select dropdown, list its options."""
import sys
import time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://job-boards.greenhouse.io/scaleai/jobs/4670064005"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    # Click any "Apply" to open form
    for sel in ["a:has-text('Apply for this job')", "button:has-text('Apply')"]:
        try:
            b = page.locator(sel).first
            if b.count() and b.is_visible():
                b.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                break
        except Exception:
            pass
    time.sleep(3)

    # Find every react-select control
    inputs = page.locator("input[role='combobox'], input[id][aria-haspopup='true']").all()
    print(f"Found {len(inputs)} react-select-ish inputs.\n")

    for i, inp in enumerate(inputs):
        try:
            inp_id = inp.get_attribute("id") or "(no-id)"
            # Find associated label
            lbl = ""
            if inp_id and inp_id != "(no-id)":
                lblel = page.locator(f"label[for='{inp_id}']").first
                if lblel.count():
                    try:
                        lbl = lblel.inner_text(timeout=500).strip()[:100]
                    except Exception:
                        pass
            print(f"=== [{i}] id='{inp_id}' label='{lbl}' ===")
            inp.scroll_into_view_if_needed(timeout=2000)
            inp.click(timeout=2000)
            time.sleep(0.5)
            opts = page.locator("div[class*='option']").all()
            for o in opts[:15]:
                try:
                    t = o.inner_text(timeout=300).strip()
                    print(f"   - {t}")
                except Exception:
                    pass
            # Close menu
            page.keyboard.press("Escape")
            time.sleep(0.2)
        except Exception as e:
            print(f"  ERR: {e}")

    # Also check for native <select> elements
    selects = page.locator("select").all()
    print(f"\nFound {len(selects)} native <select> elements:")
    for s in selects:
        try:
            sid = s.get_attribute("id") or "?"
            lbl = ""
            if sid != "?":
                lblel = page.locator(f"label[for='{sid}']").first
                if lblel.count():
                    lbl = lblel.inner_text(timeout=500).strip()[:80]
            opts = s.evaluate("el => Array.from(el.options).map(o => o.text)")
            print(f"  id='{sid}' label='{lbl}' options={opts[:10]}")
        except Exception as e:
            print(f"  ERR: {e}")

    browser.close()
