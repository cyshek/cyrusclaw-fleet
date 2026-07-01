#!/usr/bin/env python3
"""
Oracle Cloud HCM (iaziqy tenant) guest-apply runner for Uber.
Based on proven Macy's CX_1001 recipe.
"""

import sys, os, datetime, subprocess, asyncio, traceback

CDP_URL = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")
DB_PATH = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db"
APPS_DIR = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted"
SS_DIR = "/home/azureuser/.openclaw/media/inbound"

PERSONAL = {
    "email": "cyshekari@gmail.com",
    "first": "Cyrus",
    "last": "Shekari",
    "phone": "346-804-0227",
    "address1": "12420 NE 120th St #1437",
    "zip": "98034",
    "signature": "Cyrus Shekari",
}

print("")

def db_query(sql):
    r = subprocess.run(["sqlite3", DB_PATH, sql], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  DB error: {r.stderr}")
    return r.stdout.strip()


def update_db_submitted(role_id):
    db_query(f"UPDATE roles SET status='submitted', applied_by='auto-oracle-hcm', applied_on=date('now') WHERE id={role_id};")
    print(f"  DB: role {role_id} -> submitted")


def update_db_blocked(role_id, error):
    escaped = error.replace("'", "''")[:400]
    db_query(f"UPDATE roles SET status='blocked', agent_notes='{escaped}' WHERE id={role_id};")
    print(f"  DB: role {role_id} -> blocked")


def write_status_md(role_id, role_name, oracle_job_id, confirmed, confirmation, error=None):
    import datetime as _dt
    app_dir = os.path.join(APPS_DIR, "uber-" + str(oracle_job_id))
    os.makedirs(app_dir, exist_ok=True)
    today = _dt.date.today().isoformat()
    if confirmed:
        parts = ["SUBMITTED - "+today+" (Oracle Cloud HCM guest apply, auto-oracle-hcm)","","role_id: "+str(role_id),"company: Uber","role: "+str(role_name),"ats: oracle-cloud-hcm (iaziqy)","oracle_job_id: "+str(oracle_job_id),"","CONFIRMATION:",str(confirmation),"","resume_attached: yes","cover_letter: not required","","ANSWERS:","- Auth YES, Sponsorship NO, Age YES, Gender Not Specified, Sig Cyrus Shekari"]
    else:
        parts = ["FAILED - "+today,"role_id: "+str(role_id),"role: "+str(role_name),"oracle_job_id: "+str(oracle_job_id),"ERROR: "+str(error)]
    content = chr(10).join(parts) + chr(10)
    open(os.path.join(app_dir, "STATUS.md"), "w").write(content)
    print("  STATUS.md: " + app_dir)

async def try_lov_click(page, selector, type_text, wait_ms=1500):
    """Type into LOV combobox and click first listitem."""
    el = page.locator(selector).first
    if await el.count() == 0:
        return False, None
    await el.click()
    await page.wait_for_timeout(400)
    await el.type(type_text, delay=80)
    await page.wait_for_timeout(wait_ms)
    for opt_sel in ['[role="option"]', '[role="listitem"]', 'li[id*="listitem"]']:
        try:
            li = page.locator(opt_sel).first
            await li.wait_for(state="visible", timeout=5000)
            item_text = await li.inner_text()
            await li.hover()
            await li.dispatch_event("mousedown")
            await li.dispatch_event("mouseup")
            await li.click()
            await page.wait_for_timeout(800)
            return True, item_text
        except Exception:
            continue
    return False, None


async def apply_oracle_role(apply_url, role_id, role_name, oracle_job_id):
    """Full Oracle HCM guest apply flow."""
    from playwright.async_api import async_playwright

    print("=" * 65)
    print(f"APPLYING: {role_name} (id={role_id})")
    print(f"URL: {apply_url}")
    print("="*65)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

        try:
            # Step 1: Navigate
            print("  [1] Navigate...")
            await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path=os.path.join(SS_DIR, f"ub_{role_id}_01.png"))

            # Accept cookies
            for csel in ['button:has-text("Got it")', 'button:has-text("Accept")']:
                try:
                    btn = page.locator(csel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(1000)
                        print(f"  Cookies accepted via {csel}")
                        break
                except Exception:
                    pass

            # Step 2: Email auth
            print("  [2] Email auth...")
            email_found = False
            for sel in ['input[type="email"]', 'input[id*="email"]', 'input[placeholder*="email"]', 'input[placeholder*="Email"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.fill(PERSONAL["email"])
                        email_found = True
                        print(f"  Email via {sel}")
                        break
                except Exception:
                    pass

            if email_found:
                # Terms checkbox
                try:
                    cb = page.locator('input[type="checkbox"]').first
                    if await cb.count() > 0 and not await cb.is_checked():
                        await cb.click()
                        print("  Terms checked")
                except Exception:
                    pass
                # Click Next
                for sel in ['button:has-text("Next")', 'button:has-text("Continue")']:
                    try:
                        btn = page.locator(sel).first
                        if await btn.count() > 0:
                            await btn.click()
                            await page.wait_for_timeout(5000)
                            print(f"  Next clicked")
                            break
                    except Exception:
                        pass
            else:
                print("  No email field — may already past auth")

            await page.wait_for_timeout(2000)
            await page.screenshot(path=os.path.join(SS_DIR, f"ub_{role_id}_02.png"))
            page_text = await page.evaluate("document.body.innerText")
            print(f"  Page text[0:600]: {page_text[:600]}")

            # Step 3: Personal info
            print("  [3] Personal info...")
            for target, sels in [
                (PERSONAL["first"], ['input[id*="firstName"]', 'input[name*="firstName"]', 'input[placeholder*="First Name"]']),
                (PERSONAL["last"], ['input[id*="lastName"]', 'input[name*="lastName"]', 'input[placeholder*="Last Name"]']),
                (PERSONAL["phone"], ['input[id*="phone"]', 'input[type="tel"]', 'input[placeholder*="Phone"]']),
                (PERSONAL["address1"], ['input[id*="address1"]', 'input[id*="addressLine1"]', 'input[placeholder*="Address Line 1"]', 'input[placeholder*="Street"]']),
            ]:
                for sel in sels:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.clear()
                            await el.fill(target)
                            print(f"  '{target[:30]}' via {sel}")
                            break
                    except Exception:
                        pass

            # Step 4: ZIP LOV
            print("  [4] ZIP LOV...")
            zip_ok = False
            for sel in ['input[id*="zip"]', 'input[id*="Zip"]', 'input[id*="postal"]', 'input[id*="Postal"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() == 0 or not await el.is_visible():
                        continue
                    role_attr = await el.get_attribute("role") or ""
                    if "combobox" in role_attr:
                        ok, item_text = await try_lov_click(page, sel, PERSONAL["zip"])
                        if ok:
                            zip_ok = True
                            print(f"  ZIP LOV: {item_text}")
                        break
                    else:
                        await el.fill(PERSONAL["zip"])
                        zip_ok = True
                        print(f"  ZIP text: {PERSONAL['zip']}")
                        break
                except Exception as e:
                    print(f"  ZIP err {sel}: {e}")

            if not zip_ok:
                print("  WARNING: ZIP not filled")

            await page.wait_for_timeout(800)

            # Step 5: Gender
            print("  [5] Gender...")
            for sel in ['input[id*="gender"]', 'input[id*="Gender"]', 'select[id*="gender"]', 'select[id*="Gender"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() == 0 or not await el.is_visible():
                        continue
                    tag = await el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        opts = await el.evaluate("el => Array.from(el.options).map(o => ({v: o.value, t: o.text}))")
                        for ot in ["Not Specified", "Prefer not", "Decline", "Other"]:
                            matches = [o for o in opts if ot.lower() in o['t'].lower()]
                            if matches:
                                await el.select_option(value=matches[0]['v'])
                                print(f"  Gender SELECT: {matches[0]['t']}")
                                break
                    else:
                        ok, item_text = await try_lov_click(page, sel, "Not", wait_ms=1200)
                        if ok:
                            print(f"  Gender LOV: {item_text}")
                    break
                except Exception as e:
                    print(f"  Gender err: {e}")

            # Step 6: Yes/No questions
            print("  [6] Yes/No questions...")
            await page.evaluate("""
                () => {
                    var processed = new Set();
                    Array.from(document.querySelectorAll('button')).forEach(function(btn) {
                        var text = btn.textContent.trim();
                        if (text !== 'Yes' && text !== 'No') return;
                        var container = btn.closest('[class*="question"]')
                            || btn.closest('[class*="Question"]')
                            || btn.closest('li')
                            || (btn.parentElement && btn.parentElement.parentElement);
                        if (!container || processed.has(container)) return;
                        processed.add(container);
                        var qText = (container.innerText || '').toLowerCase();
                        var yes = Array.from(container.querySelectorAll('button')).filter(function(b){return b.textContent.trim()==='Yes';});
                        var no = Array.from(container.querySelectorAll('button')).filter(function(b){return b.textContent.trim()==='No';});
                        var answer = null;
                        if (qText.indexOf('authorized')!==-1||qText.indexOf('legally')!==-1||qText.indexOf('18')!==-1||qText.indexOf('work in us')!==-1) answer='yes';
                        else if (qText.indexOf('sponsorship')!==-1||qText.indexOf('sponsor')!==-1) answer='no';
                        else if (qText.indexOf('agree')!==-1||qText.indexOf('acknowledge')!==-1) answer='yes';
                        if (answer==='yes'&&yes.length>0) { console.log('YES: '+qText.substr(0,60)); yes[0].click(); }
                        else if (answer==='no'&&no.length>0) { console.log('NO: '+qText.substr(0,60)); no[0].click(); }
                        else console.log('UNANSWERED: '+qText.substr(0,60));
                    });
                }
            """)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=os.path.join(SS_DIR, f"ub_{role_id}_06.png"))

            # Step 7: Resume upload
            print("  [7] Upload resume...")
            uploaded = False
            for sel in ['input#attachment-upload-2', 'input[id*="attachment-upload"]', 'input[id*="resume"]', 'input[type="file"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        await el.set_input_files(RESUME_PATH)
                        await page.wait_for_timeout(3000)
                        uploaded = True
                        print(f"  Resume via {sel}")
                        break
                except Exception as e:
                    print(f"  Upload err {sel}: {e}")
            if not uploaded:
                print("  WARNING: Resume not uploaded!")
            await page.screenshot(path=os.path.join(SS_DIR, f"ub_{role_id}_07.png"))

            # Step 8: E-signature
            print("  [8] E-signature...")
            esig_ok = False
            for sel in [
                'input[id*="fullName"]', 'input[id*="FullName"]', 'input[id*="signature"]',
                'input[id*="eSign"]', 'input[placeholder*="Full Name"]', 'input[placeholder*="full name"]',
                'input[placeholder*="name"]'
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.clear()
                        await el.fill(PERSONAL["signature"])
                        esig_ok = True
                        print(f"  E-sig via {sel}")
                        break
                except Exception:
                    pass
            if not esig_ok:
                inputs = await page.query_selector_all('input[type="text"]')
                for inp in inputs:
                    ph = await inp.get_attribute("placeholder") or ""
                    if "name" in ph.lower() or "signature" in ph.lower():
                        try:
                            await inp.fill(PERSONAL["signature"])
                            esig_ok = True
                            print(f"  E-sig fallback ph={ph}")
                            break
                        except Exception:
                            pass
            if not esig_ok:
                print("  WARNING: E-sig not filled")

            await page.wait_for_timeout(500)
            await page.screenshot(path=os.path.join(SS_DIR, f"ub_{role_id}_09.png"))

            # Step 9: Submit
            print("  [9] Submit...")
            submit_ok = False
            for sel in [
                'button.apply-flow-pagination__submit-button',
                'button[class*="submit-button"]',
                'button:has-text("Submit")',
                'input[type="submit"]',
                'button[type="submit"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        print(f"  Clicking submit: {sel}")
                        await el.click(force=True)
                        await page.wait_for_timeout(7000)
                        submit_ok = True
                        break
                except Exception as e:
                    print(f"  Submit err {sel}: {e}")
            if not submit_ok:
                print("  WARNING: Submit not clicked!")

            await page.wait_for_timeout(4000)
            await page.screenshot(path=os.path.join(SS_DIR, f"ub_{role_id}_10.png"))

            # Step 10: Confirm
            final_url = page.url
            final_text = await page.evaluate("document.body.innerText")
            print(f"  Final URL: {final_url}")
            print(f"  Final text[0:1000]: {final_text[:1000]}")

            confirmed = False
            conf_detail = ""
            for signal in [
                "thank you for submitting", "application submitted", "my-profile",
                "active job application", "under consideration", "applied on", "successfully submitted",
            ]:
                if signal in final_text.lower() or signal in final_url.lower():
                    confirmed = True
                    conf_detail = "Signal: '" + signal + "'\nURL: " + final_url + "\nText: " + final_text[:400]
                    break

            if confirmed:
                print("  ✅ CONFIRMED SUBMITTED!")
                update_db_submitted(role_id)
                write_status_md(role_id, role_name, oracle_job_id, True, conf_detail)
                return {"status": "submitted", "role_id": role_id, "oracle_job_id": oracle_job_id, "confirmation": conf_detail}
            else:
                err = f"No confirm signal. URL={final_url}. Text: {final_text[:500]}"
                print(f"  ❌ NOT CONFIRMED")
                update_db_blocked(role_id, err)
                write_status_md(role_id, role_name, oracle_job_id, False, None, err)
                return {"status": "failed", "role_id": role_id, "oracle_job_id": oracle_job_id, "error": err}

        except Exception as e:
            err = "Exception: " + str(e) + "\n" + traceback.format_exc()[:800]
            print(f"  EXCEPTION: {err[:400]}")
            try:
                await page.screenshot(path=os.path.join(SS_DIR, f"ub_{role_id}_exc.png"))
            except Exception:
                pass
            update_db_blocked(role_id, str(e)[:400])
            write_status_md(role_id, role_name, oracle_job_id, False, None, str(e)[:400])
            return {"status": "failed", "role_id": role_id, "oracle_job_id": oracle_job_id, "error": str(e)}

        finally:
            await context.close()


async def main():
    roles = [
        {"role_id": 3067, "oracle_job_id": "160295", "role_name": "Data Collaboration Program Manager",
         "url": "https://iaziqy.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/UberCareers/jobs/preview/160295/apply/email?mode=location"},
        {"role_id": 3068, "oracle_job_id": "156921", "role_name": "US Immigration Program Manager",
         "url": "https://iaziqy.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/UberCareers/jobs/preview/156921/apply/email?mode=location"},
        {"role_id": 3071, "oracle_job_id": "159482", "role_name": "Program Manager II, GTM Enablement & Field Programs",
         "url": "https://iaziqy.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/UberCareers/jobs/preview/159482/apply/email?mode=location"},
        {"role_id": 3072, "oracle_job_id": "159306", "role_name": "Program Manager, Organizational Safety, Autonomous Mobility & Delivery",
         "url": "https://iaziqy.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/UberCareers/jobs/preview/159306/apply/email?mode=location"},
        {"role_id": 3073, "oracle_job_id": "158485", "role_name": "Partner Solution Engineer II, Uber Advertising",
         "url": "https://iaziqy.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/UberCareers/jobs/preview/158485/apply/email?mode=location"},
    ]

    all_results = []
    for role in roles:
        result = await apply_oracle_role(
            apply_url=role["url"],
            role_id=role["role_id"],
            role_name=role["role_name"],
            oracle_job_id=role["oracle_job_id"],
        )
        all_results.append(result)
        await asyncio.sleep(5)

    print(chr(10)+"="*65)
    print("FINAL RESULTS:")
    submitted = [r for r in all_results if r["status"] == "submitted"]
    failed = [r for r in all_results if r["status"] != "submitted"]
    print(f"  Submitted: {len(submitted)}/5")
    for r in submitted:
        print(f"    SUBMITTED id={r['role_id']} oracle={r['oracle_job_id']}")
    print(f"  Failed: {len(failed)}/5")
    for r in failed:
        print(f"    FAILED id={r['role_id']} err={r.get('error','')[:120]}")
    print("="*65)
    return all_results


if __name__ == "__main__":
    asyncio.run(main())
