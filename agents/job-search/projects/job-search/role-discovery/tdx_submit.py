"""TeamDynamix Ashby submission - fixing skipped fields and salary"""
from playwright.sync_api import sync_playwright
import time, json, sys, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")

CDP = "http://127.0.0.1:18800"

PLAN_PATH = "output/inline-plan-teamdynamix-c829dfb1-d293-4710-9d13-33ace86c2df7.json"
PLAN = json.load(open(PLAN_PATH))
RESUME = PLAN.get("pdf_path_staged") or PLAN.get("pdf_path_local")

# Field IDs for skipped items
CITIZENSHIP_ID = "5ad80564-4e19-44cc-bf2e-dcc0ba17f70a"  # short part
EDUCATION_ID = "b49820ba-a480-4104-a290-9d46e9363662"   # short part
SALARY_ID = "198af127-f703-4414-9320-e850808d296a"     # short part
NON_COMPETE_NAME = "7292da8a-5a5e-4f85-b396-6b7ebf1c6da9_cf8d7ccd-dc47-44dd-b48c-5e17a1e5f0f9"

OPEN_SELECT_JS = """async (short_id) => {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    // Find button with this ID suffix
    const btn = [...document.querySelectorAll('button')].find(b => b.id && b.id.endsWith(short_id));
    if (btn) { btn.scrollIntoView({block:'center'}); btn.click(); await sleep(500); return 'btn-ok'; }
    // Try combobox
    const combo = document.querySelector('[id*="' + short_id + '"][role=combobox], [id*="' + short_id + '"]');
    if (combo) { combo.scrollIntoView({block:'center'}); combo.click(); await sleep(500); return 'combo-ok'; }
    return 'noel';
}"""

SET_VAL_JS = """(args) => {
    const [id_suffix, val] = args;
    const el = document.querySelector('[id$="' + id_suffix + '"]');
    if (!el) return "noel";
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement : HTMLInputElement;
    const d = Object.getOwnPropertyDescriptor(proto.prototype, "value");
    d.set.call(el, typeof val === 'number' ? String(val) : val);
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
    return el.value;
}"""

def click_ashby_radio(page, radio_name, option_text):
    """Click an Ashby labeled-radio option by name pattern + label text"""
    result = page.evaluate(f"""() => {{
        const name = '{radio_name}';
        const target = '{option_text}'.toLowerCase();
        const labels = [...document.querySelectorAll('label')].filter(l => {{
            const inp = document.querySelector('[name="' + name + '"]');
            if (!inp) return false;
            const labelFor = l.getAttribute('for');
            const relatedInp = document.getElementById(labelFor);
            if (!relatedInp) return false;
            if (relatedInp.getAttribute('name') !== name && !relatedInp.id.startsWith(name.slice(-20))) return false;
            return l.textContent.trim().toLowerCase() === target;
        }});
        if (labels.length > 0) {{
            labels[0].click();
            return labels[0].textContent.trim();
        }}
        // Try finding radio inputs with matching name and labels
        const radios = [...document.querySelectorAll('input[type=radio]')].filter(r => {{
            return r.name && r.name.endsWith(name.slice(-30));
        }});
        for (const r of radios) {{
            const lbl = document.querySelector('label[for="' + r.id + '"]');
            if (lbl && lbl.textContent.trim().toLowerCase() === target) {{
                r.click();
                lbl.click();
                return lbl.textContent.trim();
            }}
        }}
        return 'nomatch';
    }}""")
    return result

def click_ashby_select_option(page, option_text):
    """Click an option in an open Ashby listbox"""
    result = page.evaluate(f"""() => {{
        const target = '{option_text}'.toLowerCase();
        const opts = [...document.querySelectorAll('[role=option], li[data-radix-select-item], [class*=SelectItem], [class*=dropdown-item]')]
            .filter(e => e.offsetParent);
        for (const opt of opts) {{
            if (opt.textContent.trim().toLowerCase().includes(target)) {{
                opt.click();
                return opt.textContent.trim();
            }}
        }}
        return 'nomatch';
    }}""")
    return result

with sync_playwright() as p:
    br = p.chromium.connect_over_cdp(CDP)
    ctx = br.contexts[0]
    page = ctx.new_page()
    page.goto(PLAN["url"], wait_until="networkidle", timeout=45000)
    time.sleep(2)

    # Fill text fields
    for fid, val in PLAN.get("text_fields", {}).items():
        short = fid.split("_")[-1]
        r = page.evaluate(SET_VAL_JS, [short, val])
    print("Text fields set")

    # Click radio buttons from plan
    for radio in PLAN.get("radios", []):
        rname = radio["name"]
        rval = radio["value"]
        # Try using Playwright native locator
        name_end = rname.split("_")[-1][:30]
        inputs = page.locator(f'input[type=radio]').all()
        clicked = False
        for inp in inputs:
            try:
                iname = inp.get_attribute("name") or ""
                if name_end.lower() in iname.lower():
                    # Find the label for this radio group with matching text
                    iid = inp.get_attribute("id") or ""
                    lbl = page.locator(f'label[for="{iid}"]')
                    if lbl.count() > 0:
                        ltxt = lbl.first.text_content(timeout=2000).strip()
                        if ltxt.lower() == rval.lower():
                            inp.click(force=True)
                            clicked = True
                            print(f"Radio {name_end}: clicked '{ltxt}'")
                            break
            except Exception:
                pass

    # Handle Desired Salary (number field)
    r = page.evaluate(SET_VAL_JS, [SALARY_ID, "160000"])
    print(f"Salary: {r}")

    # Handle citizenship - probe and select
    r = page.evaluate(OPEN_SELECT_JS, "5ad80564-4e19-44cc-bf2e-dcc0ba17f70a")
    print(f"Citizenship open: {r}")
    time.sleep(0.5)
    # Try selecting "U.S. Citizen"
    r = click_ashby_select_option(page, "U.S. Citizen")
    print(f"Citizenship select: {r}")
    if r == "nomatch":
        page.keyboard.press("Escape")
        # Try by clicking on the element and typing
        r2 = page.evaluate(OPEN_SELECT_JS, "b49820ba-a480-4104-a290-9d46e9363662")
        print(f"Education open: {r2}")
        time.sleep(0.5)

    # Handle education - probe options
    r = page.evaluate(OPEN_SELECT_JS, "b49820ba-a480-4104-a290-9d46e9363662")
    print(f"Education open: {r}")
    time.sleep(0.5)
    r = click_ashby_select_option(page, "Bachelor")
    print(f"Education select: {r}")
    if r == "nomatch":
        page.keyboard.press("Escape")

    # Resume upload
    if RESUME and os.path.exists(RESUME):
        rl = page.locator("#_systemfield_resume")
        if rl.count() > 0:
            rl.set_input_files(RESUME)
            time.sleep(3)
            print("Resume uploaded")

    # Check form state
    form_state = page.evaluate("""() => {
        const errs = [...document.querySelectorAll('[class*=error], [aria-invalid=true]')]
            .filter(e => e.offsetParent && e.textContent.trim())
            .map(e => e.textContent.trim().slice(0,60));
        return {errors: errs};
    }""")
    print(f"Form state: {form_state}")

    # Submit
    print("Submitting...")
    sub = page.locator('button:has-text("Submit Application")')
    if sub.count() == 0:
        sub = page.locator("button[type=submit]")
    if sub.count() == 0:
        sub = page.locator('button:has-text("Submit")')
    sub.first.click()
    time.sleep(5)

    body = page.inner_text("body")
    confirmed = ("SuccessYour application was successfully submitted" in body
                 or "successfully submitted" in body.lower()
                 or "application received" in body.lower())
    print(f"CONFIRMED: {confirmed}")
    print(f"URL: {page.url}")
    print(f"BODY: {body[:400]}")
    page.close()
    br.close()
    sys.exit(0 if confirmed else 1)
