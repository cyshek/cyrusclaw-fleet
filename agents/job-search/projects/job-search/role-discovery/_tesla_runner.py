#!/usr/bin/env python3
"""
_tesla_runner.py — Tesla custom-ATS ("cua" candidate-user-area) apply runner.

Tesla careers (tesla.com/careers/search/job/<id>) is behind **Akamai**, which
returns 403/"Access Denied" to curl AND to headless Playwright chromium. Only a
REAL headful browser passes. So this runner does NOT launch its own browser — it
**connects over CDP to the already-running OpenClaw browser** (which passes
Akamai), opens the job there, and drives the 3-step guest apply form.

Apply flow (learned 2026-06-02, dryrun on job 270702 Tesla AI TPM):
  JD page  ->  "Apply" link opens a NEW TAB at /careers/search/job/apply/<id>
  Step 1 "Personal Information": name/phone/email/country + resume upload +
         evidence-of-excellence textarea + profile link. Gate: "provide at least
         one item" (resume OR evidence OR profile link).
  Step 2 "Legal Acknowledgment": notice period, sponsorship(No), consider-other(Yes),
         former-employee(No), former-intern(No), receive-notifications(Yes),
         acknowledgment checkbox + legal name.
  Step 3 "Equal Employee Opportunities Disclosure": EEO ack checkbox + gender /
         veteran / race / disability selects (all support choose_not_to_disclose)
         + legal name. Final **Submit**.
  NO email-OTP gate observed — pure guest submit. Confirmation = on-page text.

All form fields use STABLE `name` attributes (the element `id`s are random UUIDs
that change per page-load, so NEVER select by id). Selects + inputs are React-
controlled, so values must be set via the native value-setter + input/change
events (a plain `.value=` won't update React state).

Answer heuristics (Cyrus: US citizen, no sponsorship, authorized, open to
relocate/onsite). Mirrors TOOLS.md Workday heuristics: SPON=No, AFFIRM
willingness=Yes, former-employer questions=No.

Usage:
  python3 _tesla_runner.py --url <jobUrl> [--dryrun] [--debug DIR] [--cdp http://127.0.0.1:18800]
  --dryrun : fill ALL 3 steps, print the answers it WOULD submit, stop before final Submit.
"""
import sys, os, time, json, argparse, re

_PI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "personal-info.json")
with open(_PI_PATH) as _f:
    _PI = json.load(_f)

EMAIL = _PI["contact"]["email"]
FIRST = _PI["identity"]["first_name"]
LAST = _PI["identity"]["last_name"]
PHONE = _PI["contact"]["phone"].replace("-", "")  # 10-digit no-dash
LINKEDIN = "https://www.linkedin.com/in/cyrus-shekari"
EVIDENCE = ("Led 0-to-1 Resilience Automation Platform at Microsoft Azure, driving 14M-plus "
            "dollars business impact; scaled recovery validation into a platformized system "
            "across the org. Prior: zero-downtime 2,000-plus unit OS migration at Amazon Robotics.")
RESUME_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "resume", "Cyrus_Shekari_Resume.pdf")
# Playwright set_input_files needs a path the browser process can read; the
# OpenClaw browser runs as the same user, so the workspace path works directly.
RESUME = os.path.abspath(RESUME_SRC)

CDP_DEFAULT = "http://127.0.0.1:18800"

# ---- Answer heuristics (single source of truth; tested in test_tesla_runner.py) ----
# Cyrus: US citizen, NO sponsorship, authorized to work, open to relocate/onsite.
# Mirrors TOOLS.md Workday heuristics: SPON=No, AFFIRM willingness=Yes,
# former-employer questions=No.
# Step-2 "Legal Acknowledgment" radio answers (name -> 'yes'/'no'):
LEGAL_RADIO_ANSWERS = {
    "legal.legalImmigrationSponsorship": "no",        # SPON -> No (no sponsorship needed)
    "legal.legalConsiderOtherPositions": "yes",       # willingness/open to other roles -> Yes
    "legal.legalFormerTeslaEmployee": "no",           # former employer Q -> No
    "legal.legalFormerTeslaInternOrContractor": "no", # former intern/contractor -> No
    "legal.legalReceiveNotifications": "yes",         # consent to notifications -> Yes
}
LEGAL_NOTICE_PERIOD = "immediately"  # availability: ready now
# Step-3 EEO selects -> decline to self-identify (privacy-respecting standard):
EEO_SELECT_ANSWERS = {
    "eeo.eeoGender": "choose_not_to_disclose",
    "eeo.eeoVeteranStatus": "choose_not_to_disclose",
    "eeo.eeoRaceEthnicity": "choose_not_to_disclose",
    "eeo.eeoDisabilityStatus": "choose_not_to_disclose",
}


def log(*a):
    print("[tesla]", *a, file=sys.stderr, flush=True)


# ---- React-aware field setters (run in-page) -------------------------------
JS_SET_INPUT = r"""([sel,val])=>{
  const el=document.querySelector(sel);
  if(!el) return sel+':MISSING';
  const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype
              : el.tagName==='SELECT'?HTMLSelectElement.prototype
              : HTMLInputElement.prototype;
  const d=Object.getOwnPropertyDescriptor(proto,'value');
  el.focus(); d.set.call(el,val);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.blur(); return sel+':ok';
}"""

JS_PICK_SELECT = r"""([name,val])=>{
  const el=document.querySelector('select[name="'+name+'"]');
  if(!el) return name+':MISSING';
  const opt=[...el.options].find(o=>o.value===val) ||
            [...el.options].find(o=>o.textContent.trim().toLowerCase()===String(val).toLowerCase());
  if(!opt) return name+':NOOPT:'+[...el.options].map(o=>o.value).join('|');
  const d=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value');
  el.focus(); d.set.call(el,opt.value);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.blur(); return name+'='+opt.value;
}"""

JS_RADIO = r"""([name,val])=>{
  const el=[...document.querySelectorAll('input[type=radio][name="'+name+'"]')]
            .find(x=>x.value===val);
  if(!el) return name+':NORADIO';
  el.click(); return name+'='+val+':'+el.checked;
}"""

JS_CHECK = r"""(name)=>{
  const el=document.querySelector('input[type=checkbox][name="'+name+'"]');
  if(!el) return name+':NOCHK';
  if(el.checked) return name+':'+el.checked;
  // Try direct click first.
  el.click();
  if(el.checked) return name+':'+el.checked;
  // Custom-styled checkbox: the real input is often visually hidden and the
  // click target is its <label> (by for=id) or a wrapping label/sibling.
  let lbl = el.id ? document.querySelector('label[for="'+el.id+'"]') : null;
  if(!lbl){ let p=el.parentElement; for(let i=0;i<4&&p&&!lbl;i++){ if(p.tagName==='LABEL'){lbl=p;break;} lbl=p.querySelector('label'); p=p.parentElement; } }
  if(lbl){ lbl.click(); }
  if(el.checked) return name+':'+el.checked;
  // Last resort: set checked + fire React events.
  const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'checked');
  d.set.call(el,true);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.dispatchEvent(new Event('click',{bubbles:true}));
  return name+':'+el.checked;
}"""


def set_input(page, sel, val):
    return page.evaluate(JS_SET_INPUT, [sel, val])

def pick_select(page, name, val):
    return page.evaluate(JS_PICK_SELECT, [name, val])

def set_radio(page, name, val):
    return page.evaluate(JS_RADIO, [name, val])

def set_check(page, name):
    return page.evaluate(JS_CHECK, name)


def shot(page, debug_dir, name):
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    try:
        page.screenshot(path=os.path.join(debug_dir, name + ".png"), full_page=True)
    except Exception as e:
        log("shot fail", name, e)


def click_next(page, btn_name="next"):
    """Click a step's Next/Submit submit-button by name attr (or text fallback)."""
    return page.evaluate(r"""(bn)=>{
      let b=[...document.querySelectorAll('button[name="'+bn+'"]')][0];
      if(!b){
        const want = bn==='' ? /^submit$/i : new RegExp('^'+bn+'$','i');
        b=[...document.querySelectorAll('button[type=submit],button')].find(x=>want.test((x.textContent||'').trim()));
      }
      if(b){ b.scrollIntoView({block:'center'}); b.click(); return (b.textContent||'').trim()||'clicked'; }
      return null;
    }""", btn_name)


def upload_resume(page):
    """Set the hidden file input. set_input_files works on hidden inputs where the
    browser-tool file-chooser flow times out (the input is custom-rendered, no
    native chooser fires)."""
    inp = page.query_selector('input[name="personal.resume"]')
    if not inp:
        return "no-input"
    if not os.path.exists(RESUME):
        return "resume-missing:" + RESUME
    inp.set_input_files(RESUME)
    page.wait_for_timeout(1500)
    n = page.evaluate("""()=>{const f=document.querySelector('input[name="personal.resume"]');return f?f.files.length:-1;}""")
    return "files=" + str(n)


def step1_personal(page, debug):
    log("step1 personal")
    set_input(page, 'input[name="personal.firstName"]', FIRST)
    set_input(page, 'input[name="personal.lastName"]', LAST)
    set_input(page, 'input[name="personal.phone"]', PHONE)
    set_input(page, 'input[name="personal.email"]', EMAIL)
    set_input(page, 'textarea[name="personal.evidenceOfExcellence"]', EVIDENCE)
    set_input(page, 'input[name="personal.profileLinks[0].link"]', LINKEDIN)
    pick_select(page, "personal.phoneType", "Mobile")
    pick_select(page, "personal.country", "United States")
    pick_select(page, "personal.profileLinks[0].type", "LinkedIn")
    up = upload_resume(page)
    log("resume upload:", up)
    shot(page, debug, "01-step1-filled")
    return {"resume": up}


def step2_legal(page, debug):
    log("step2 legal")
    answers = {
        "select:legal.legalNoticePeriod": pick_select(page, "legal.legalNoticePeriod", LEGAL_NOTICE_PERIOD),
    }
    for name, val in LEGAL_RADIO_ANSWERS.items():
        answers[name] = set_radio(page, name, val)
    answers["legal.legalAcknowledgment"] = set_check(page, "legal.legalAcknowledgment")
    answers["legal.legalAcknowledgmentName"] = set_input(
        page, 'input[name="legal.legalAcknowledgmentName"]', f"{FIRST} {LAST}")
    shot(page, debug, "02-step2-filled")
    return answers


def step3_eeo(page, debug):
    log("step3 eeo")
    answers = {"eeo.eeoAcknowledgment": set_check(page, "eeo.eeoAcknowledgment")}
    for name, val in EEO_SELECT_ANSWERS.items():
        answers[name] = pick_select(page, name, val)
    answers["eeo.eeoDisabilityStatusName"] = set_input(
        page, 'input[name="eeo.eeoDisabilityStatusName"]', f"{FIRST} {LAST}")
    shot(page, debug, "03-step3-filled")
    return answers


def detect_step(page):
    """Return the step number (1/2/3) by which step-marker text is on the page,
    or 0 if none / confirmation."""
    return page.evaluate(r"""()=>{
      const t=document.body.innerText;
      if(/Step 1 of 3/.test(t)) return 1;
      if(/Step 2 of 3/.test(t)) return 2;
      if(/Step 3 of 3/.test(t)) return 3;
      return 0;
    }""")


def detect_confirmation(page):
    return page.evaluate(r"""()=>{
      const t=document.body.innerText;
      const url=location.href;
      const conf=/thank you for applying|application (has been|was) (received|submitted)|we.{0,3}ve received your application|your application has been submitted|successfully submitted|application submitted|thank you for your interest|we have received your application|received your application/i.test(t);
      return JSON.stringify({confirmed:conf, url, head:t.slice(0,300)});
    }""")


def detect_otp(page):
    return page.evaluate(r"""()=>/verification code (was|has been) sent|enter the .{0,12}code|verify your (email|identity)/i.test(document.body.innerText)""")


def open_apply_page(ctx, job_url, debug):
    """Open job, click Apply, return the apply-form page."""
    jd = ctx.new_page()
    jd.goto(job_url, wait_until="domcontentloaded", timeout=60000)
    jd.wait_for_timeout(3500)
    title = jd.title()
    log("jd title:", title)
    if "Access Denied" in title:
        raise RuntimeError("Akamai Access Denied on JD page (browser not passing). Use the real OpenClaw browser via CDP.")
    shot(jd, debug, "00-jd")
    # The Apply link target is /careers/search/job/apply/<id>. It opens a new tab.
    # Match both JD URLs (/job/<id>) and apply URLs (/job/apply/<id>).
    job_id = re.search(r"/job/(?:apply/)?(\d+)", job_url)
    apply_url = None
    if job_id:
        apply_url = f"https://www.tesla.com/careers/search/job/apply/{job_id.group(1)}"
    else:
        apply_url = job_url
    # Prefer direct nav to the apply URL on a fresh page (avoids popup-handling races),
    # but it must come from the same context so Akamai/session cookies carry over.
    ap = ctx.new_page()
    ap.goto(apply_url, wait_until="domcontentloaded", timeout=60000)
    ap.wait_for_timeout(3500)
    if "Access Denied" in ap.title() or detect_step(ap) == 0:
        # Fallback: click the Apply link on the JD page and grab the popup.
        log("direct apply-url nav did not land on step1; trying Apply-link click")
        try:
            with ctx.expect_page(timeout=15000) as pinfo:
                jd.evaluate("""()=>{const a=[...document.querySelectorAll('a,button')].find(x=>/^apply$/i.test((x.textContent||'').trim()));if(a)a.click();}""")
            ap2 = pinfo.value
            ap2.wait_for_timeout(3500)
            if detect_step(ap2):
                ap.close(); ap = ap2
        except Exception as e:
            log("apply-link click fallback failed:", e)
    jd.close()
    return ap


def run(args):
    from playwright.sync_api import sync_playwright
    result = {"url": args.url, "status": "unknown", "dryrun": args.dryrun}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = open_apply_page(ctx, args.url, args.debug)
        page.set_default_timeout(20000)
        step = detect_step(page)
        log("landed on step", step, "url", page.url)
        if step != 1:
            result["status"] = "blocked-no-step1"
            result["detail"] = "Did not land on Step 1 of 3 apply form"
            result["page_head"] = page.evaluate("()=>document.body.innerText.slice(0,300)")
            print(json.dumps(result)); 
            if not args.keep_open: page.close()
            return result

        s1 = step1_personal(page, args.debug)
        result["step1"] = s1
        if click_next(page, "next") is None:
            result["status"] = "blocked-step1-next"; print(json.dumps(result)); return result
        page.wait_for_timeout(2500)
        if detect_step(page) != 2:
            # likely a validation error on step1
            result["status"] = "blocked-step1-validation"
            result["page_head"] = page.evaluate("()=>document.body.innerText.slice(0,400)")
            shot(page, args.debug, "ERR-step1")
            print(json.dumps(result)); return result

        s2 = step2_legal(page, args.debug)
        result["step2"] = s2
        if click_next(page, "next") is None:
            result["status"] = "blocked-step2-next"; print(json.dumps(result)); return result
        page.wait_for_timeout(2500)
        if detect_step(page) != 3:
            result["status"] = "blocked-step2-validation"
            result["page_head"] = page.evaluate("()=>document.body.innerText.slice(0,400)")
            shot(page, args.debug, "ERR-step2")
            print(json.dumps(result)); return result

        s3 = step3_eeo(page, args.debug)
        result["step3"] = s3

        if args.dryrun:
            result["status"] = "dryrun-ready"
            result["note"] = "All 3 steps filled; STOPPED before final Submit."
            shot(page, args.debug, "04-dryrun-final")
            print(json.dumps(result, indent=1))
            if not args.keep_open:
                page.close()
            return result

        # REAL SUBMIT
        clicked = click_next(page, "")  # final Submit button has no name
        log("submit clicked:", clicked)
        result["submit_btn"] = clicked

        # OTP gate? (none observed in recon, but handle defensively)
        page.wait_for_timeout(3000)
        if detect_otp(page):
            log("OTP gate detected; fetching code")
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import gmail_imap as g
            since = time.time() - 30
            try:
                code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=5, since_epoch=since)
            except Exception as e:
                result["status"] = "blocked-otp-fetch-fail"; result["err"] = str(e)
                shot(page, args.debug, "ERR-otp")
                print(json.dumps(result)); return result
            result["otp_code"] = code
            page.evaluate(r"""(code)=>{const inputs=[...document.querySelectorAll('input')].filter(e=>/code|otp|verif/i.test((e.name||'')+(e.getAttribute('aria-label')||'')));const setN=(el,v)=>{const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');el.focus();d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};if(inputs.length===1){setN(inputs[0],code);}else{inputs.forEach((el,i)=>setN(el,code[i]||''));}}""", code)
            page.wait_for_timeout(1200)
            click_next(page, "")
            page.wait_for_timeout(3000)

        # Poll for confirmation
        final = None
        for _ in range(12):
            page.wait_for_timeout(2000)
            final = json.loads(detect_confirmation(page))
            if final["confirmed"]:
                break
        result["final"] = final
        if final and final["confirmed"]:
            result["status"] = "applied"
            shot(page, args.debug, "05-confirmation")
        else:
            result["status"] = "uncertain"
            shot(page, args.debug, "05-uncertain")
        print(json.dumps(result, indent=1))
        if not args.keep_open:
            page.close()
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--dryrun", action="store_true")
    ap.add_argument("--debug", default=None, help="screenshot dir")
    ap.add_argument("--cdp", default=CDP_DEFAULT)
    ap.add_argument("--keep-open", action="store_true", help="don't close the apply tab on exit")
    args = ap.parse_args()
    r = run(args)
    _ok = r.get("status") in ("applied", "dryrun-ready")
    # Debug-shot lifecycle: prune step shots on clean success, keep 05-confirmation.
    try:
        from debug_shots import prune_step_shots_on_success
        if args.debug:
            prune_step_shots_on_success(args.debug, None, 0 if _ok else 2, success_codes=(0,))
    except Exception as _e:
        print(f"[tesla] debug-shot prune skipped: {_e}")
    sys.exit(0 if _ok else 2)


if __name__ == "__main__":
    main()
