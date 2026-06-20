"""Run greenhouse adapter in dry mode, then read back all react-select values
from the .select__single-value DOM nodes to verify dropdowns are truly set."""
import sys
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")
from greenhouse import GreenhouseApplier
from base import load_profile

URL = sys.argv[1]
COMPANY = sys.argv[2]
ROLE = sys.argv[3]


class VerifyApplier(GreenhouseApplier):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

    def apply(self, page, profile):
        super().apply(page, profile)
        time.sleep(1)
        # Read back every react-select container's selected value
        print("\n--- React-select values on form ---")
        controls = page.locator(".select__control").all()
        for c in controls:
            try:
                sv = c.locator(".select__single-value").first
                ph = c.locator(".select__placeholder").first
                inp = c.locator("input[id]").first
                cid = inp.get_attribute("id") if inp.count() else "?"
                sv_text = sv.inner_text(timeout=300).strip() if sv.count() else "(empty)"
                ph_text = ph.inner_text(timeout=300).strip() if ph.count() else ""
                # Find label by 'for' on the input id
                lbl = ""
                if cid != "?":
                    le = page.locator(f"label[for='{cid}']").first
                    if le.count():
                        lbl = le.inner_text(timeout=300).strip()[:80]
                tag = "OK" if sv_text != "(empty)" else "MISSING"
                print(f"  [{tag}] {cid}: '{sv_text}' (ph='{ph_text}') label='{lbl}'")
            except Exception as e:
                print(f"  ERR: {e}")


with sync_playwright() as _:
    pass

a = VerifyApplier(url=URL, company=COMPANY, role=ROLE, dry_run=True, headless=True)
a.run()
