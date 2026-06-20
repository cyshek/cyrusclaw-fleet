"""Recon Peterson info-page using existing handle_account_prompt."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from workday_playwright import (
    BROWSER_DATA_ROOT, UA, handle_account_prompt, load_creds,
    maybe_handle_email_verification, detect_step, classify_step,
)

APPLY_URL = "https://petersonholding.wd1.myworkdayjobs.com/PetersonJobs/job/San-Leandro-CA/Sales-Engineer_REQ-2023-1770/apply"
TENANT = "petersonholding"
SLUG = "peterson-recon"

OUT = HERE.parent / "applications" / "_peterson-recon"
OUT.mkdir(parents=True, exist_ok=True)


def dump_page(page, label):
    info = page.evaluate("""
        () => {
          const out = {inputs: [], buttons: [], radios: [], moniker_buttons: [], labels: []};
          document.querySelectorAll('input, textarea, select').forEach(el => {
            const r = el.getBoundingClientRect();
            out.inputs.push({
              tag: el.tagName, type: el.type || '', id: el.id || '',
              name: el.name || '', aria: el.getAttribute('aria-label') || '',
              aid: el.getAttribute('data-automation-id') || '',
              placeholder: el.placeholder || '', value_len: (el.value||'').length,
              visible: !!el.offsetParent, y: Math.round(r.y),
            });
          });
          document.querySelectorAll('button').forEach(el => {
            const txt = (el.innerText||'').trim().slice(0,60);
            const aid = el.getAttribute('data-automation-id') || '';
            if (txt || aid) out.buttons.push({text: txt, aid: aid, aria: el.getAttribute('aria-label')||''});
          });
          document.querySelectorAll('input[type=radio]').forEach(el => {
            out.radios.push({name: el.name, value: el.value, id: el.id, aria: el.getAttribute('aria-label')||''});
          });
          document.querySelectorAll('label, legend').forEach(el => {
            const t = (el.innerText||'').trim();
            if (t && t.length < 200) out.labels.push({tag: el.tagName, for: el.getAttribute('for')||'', text: t.slice(0,200)});
          });
          return out;
        }
    """)
    (OUT / f"dump-{label}.json").write_text(json.dumps(info, indent=2))
    return info


def main():
    creds = load_creds(TENANT)
    if not creds:
        print("no creds"); return
    email = creds["email"]; password = creds["password"]
    udd = BROWSER_DATA_ROOT / TENANT
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(udd), headless=True,
            viewport={"width": 1400, "height": 900}, user_agent=UA,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.goto(APPLY_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        print(f"after-goto url: {page.url}")
        for _ in range(20):
            if (page.locator('[data-automation-id="adventureButton"]').count() or
                page.locator('[data-automation-id="applyManually"]').count() or
                page.locator('input[type="password"]').count() or
                page.locator('input[id*="firstName"]').count()):
                break
            page.wait_for_timeout(500)
        try:
            adv = page.locator('[data-automation-id="adventureButton"]').first
            if adv.count(): adv.click(timeout=3000); page.wait_for_timeout(3000)
        except Exception as e: print(f"adv: {e}")
        try:
            am = page.locator('[data-automation-id="applyManually"]').first
            if am.count(): am.click(); page.wait_for_timeout(4000); print("applyManually")
        except Exception: pass
        ap = handle_account_prompt(page, email, password, SLUG, tenant=TENANT, prefer_signin=True)
        print(f"account-prompt: {ap}")
        page.wait_for_timeout(4000)
        maybe_handle_email_verification(page, email, SLUG, {"blockers": []})
        page.wait_for_timeout(3000)
        # post-auth, may need to click applyManually again
        try:
            am2 = page.locator('[data-automation-id="applyManually"]').first
            if am2.count() and am2.is_visible(timeout=500):
                am2.click(); page.wait_for_timeout(4000); print("applyManually-postauth")
        except Exception: pass
        page.wait_for_timeout(3000)
        step_text = detect_step(page)
        print(f"step_text: {step_text[:120]!r}")
        print(f"step_kind: {classify_step(step_text)}")
        page.screenshot(path=str(OUT / "after-signin.png"), full_page=True)
        dump = dump_page(page, "after-signin")
        print(f"inputs={len(dump['inputs'])} buttons={len(dump['buttons'])} radios={len(dump['radios'])} labels={len(dump['labels'])}")
        # If we have source--source dropdown probe it
        if page.locator('#source--source').count():
            try:
                page.evaluate("() => document.getElementById('source--source').click()")
                page.wait_for_timeout(1500)
                opts = page.evaluate("""() => Array.from(document.querySelectorAll('[data-automation-id="promptOption"]')).filter(n => n.offsetParent).map(n => ({label: n.getAttribute('data-automation-label')||'', id: n.id||''}))""")
                (OUT / "source-options-L1.json").write_text(json.dumps(opts, indent=2))
                print(f"source L1: {[o['label'] for o in opts]}")
                # Pick first L1 option, see L2
                if opts:
                    first = opts[0]['label']
                    page.evaluate(f"""() => {{
                      const els = Array.from(document.querySelectorAll('[data-automation-id="promptOption"]'));
                      const t = els.find(n => (n.getAttribute('data-automation-label')||'') === {json.dumps(first)});
                      if (t) t.click();
                    }}""")
                    page.wait_for_timeout(1500)
                    l2 = page.evaluate("""(prev) => Array.from(document.querySelectorAll('[data-automation-id="promptOption"]')).filter(n=>n.offsetParent).map(n=>n.getAttribute('data-automation-label')||'').filter(x=>!prev.includes(x))""", [o['label'] for o in opts])
                    print(f"L2 under {first!r}: {l2}")
                    (OUT / "source-options-L2.json").write_text(json.dumps({first: l2}, indent=2))
                page.keyboard.press("Escape")
            except Exception as e:
                print(f"src probe: {e}")
        # previousWorker DOM
        pw = page.evaluate("""
            () => Array.from(document.querySelectorAll('[id*="reviousWorker"], [data-automation-id*="reviousWorker"], [name*="candidateIsPrev"]')).map(el => ({tag:el.tagName, id:el.id||'', name:el.name||'', aid:el.getAttribute('data-automation-id')||'', type:el.type||'', aria:el.getAttribute('aria-label')||'', text:(el.innerText||'').slice(0,150)}))
        """)
        (OUT / "previousWorker-dom.json").write_text(json.dumps(pw, indent=2))
        print(f"previousWorker DOM count: {len(pw)}")
        for el in pw[:8]: print("  ", el)
        ctx.close()
        print("done")


if __name__ == "__main__":
    main()
