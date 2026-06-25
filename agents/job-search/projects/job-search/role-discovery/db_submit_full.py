import time, sys, json, os
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
from playwright.sync_api import sync_playwright
import gh_submit_remix as m
import gmail_imap as g

CDP = "http://127.0.0.1:18800"

def submit_databricks(plan_path, role_id):
    with open(plan_path) as fh:
        plan = json.load(fh)
    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp(CDP)
        ctx = br.contexts[0] if br.contexts else br.new_context()
        page = ctx.new_page()
        try:
            page.goto(plan["url"], wait_until="networkidle", timeout=45000)
            time.sleep(2)
            for fid, val in plan.get("text_fields", {}).items():
                if val and fid not in ("location",):
                    page.evaluate(m.SET_VAL_JS, [fid, val])
            m.pw_typeahead(page, "country", "United", "United States")
            for dd in plan.get("dropdowns", []):
                r = m.pw_fill_select(page, dd["id"], dd["label"])
                print(f"  DD {dd['id']}: {r}")
            piti = plan.get("phone_iti", {})
            if piti:
                page.evaluate(m.PHONE_JS, [piti["id"], piti.get("country","United States"), piti.get("digits","3468040227")])
            resume = plan.get("pdf_path_staged") or plan.get("pdf_path_local")
            if resume and os.path.exists(resume):
                rl = page.locator("#resume")
                if rl.count() > 0:
                    rl.set_input_files(resume)
                    time.sleep(1)
            # Click export control checkboxes
            cb_result = page.evaluate("""() => {
                const results = [];
                const toClick = [
                    'question_36528745002[]_241733898002',
                    'question_36528746002[]_241733907002'
                ];
                for (const cbid of toClick) {
                    const cb = document.getElementById(cbid);
                    if (cb) {
                        cb.scrollIntoView({block:'center'});
                        cb.click();
                        results.push({id: cbid, checked: cb.checked});
                    } else {
                        results.push({id: cbid, err: 'not found'});
                    }
                }
                return results;
            }""")
            print("Checkboxes:", cb_result)
            time.sleep(0.5)
            # Submit
            since_submit = time.time()
            page.locator('button:has-text("Submit application")').first.click()
            time.sleep(4)
            # OTP
            has_otp = page.evaluate("() => !!document.getElementById('security-input-0')")
            print("OTP gate:", has_otp)
            if has_otp:
                code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=5, since_epoch=since_submit)
                print("OTP:", code)
                for i, ch in enumerate(code):
                    el = page.locator(f"#security-input-{i}")
                    if el.count() > 0:
                        el.focus()
                        page.keyboard.press(ch)
                        time.sleep(0.1)
                time.sleep(0.5)
                for _ in range(4):
                    try:
                        btn = page.locator('button:has-text("Submit application")')
                        if btn.count() > 0 and not btn.first.is_disabled():
                            btn.first.click(); break
                    except Exception:
                        pass
                    time.sleep(1.5)
            confirmed = False
            for _ in range(15):
                time.sleep(2)
                final_url = page.url
                body = page.inner_text("body")
                if ("thank you" in body.lower() and "apply" in body.lower()) or "/confirmation" in final_url:
                    confirmed = True
                    break
            print("CONFIRMED:", confirmed)
            print("URL:", page.url)
            print("BODY:", page.inner_text("body")[:300])
            page.close()
            br.close()
            return confirmed, page.url
        except Exception as e:
            print("ERROR:", e)
            try:
                page.close()
                br.close()
            except Exception:
                pass
            return False, ""

if __name__ == "__main__":
    plan_path = sys.argv[1]
    confirmed, url = submit_databricks(plan_path, None)
    sys.exit(0 if confirmed else 1)
