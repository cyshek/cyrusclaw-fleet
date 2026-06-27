#!/usr/bin/env python3
"""_adp_wfn_runner.py — Reusable ADP WorkforceNow (workforcenow.adp.com) job-application runner.

Drives the WFN recruitment SPA over CDP (Playwright sync) because the SPA times out the
OpenClaw browser tool on navigation. Handles the email-OTP gate via fetch_adp_code.py.

Wizard flow:
  Apply -> Privacy Policy modal (Consent & Continue)
        -> "Tell us about yourself" (first/last/email/phone) -> Continue
        -> choose EMAIL for verification code -> Send code
        -> fetch_adp_code.py -> enter code -> Verify
        -> Wizard: Personal Information -> Resume (upload PDF) -> Questions
                   -> Voluntary Self-ID -> Review -> Self-Attest & Submit

Usage:
  _adp_wfn_runner.py --url <jobUrl> --resume <pdf> [--role-id N] [--phase all|apply|otp|wizard]
                     [--dump] [--no-submit]

Exit codes:
  0  submitted (confirmation observed)
  2  OTP fetch/verify failed
  3  submit attempted, no confirmation
  4  apply/consent/contact step failed
  5  generic / unexpected wall
  6  req closed / already applied
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = Path(__file__).resolve().parents[1]              # projects/job-search
RD = Path(__file__).resolve().parent                    # role-discovery
PERSONAL = json.loads((ROOT / "personal-info.json").read_text())

CDP_CANDIDATES = [
    os.environ.get("JOBSEARCH_CDP"),
    "http://127.0.0.1:18800",
    "http://[::1]:18800",
    "http://127.0.0.1:18900",
    "http://[::1]:18900",
]

DEFAULT_URL = ("https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html"
               "?cid=8720f224-b740-4129-895f-4c2f0dce1359&ccId=19000101_000001&type=MP&lang=en_US&jobId=543016")


def log(*a):
    print("[adp]", *a, flush=True)


def connect():
    pw = sync_playwright().start()
    last = None
    for cdp in CDP_CANDIDATES:
        if not cdp:
            continue
        try:
            br = pw.chromium.connect_over_cdp(cdp)
            if br.contexts:
                log("connected via %s contexts=%d" % (cdp, len(br.contexts)))
                return pw, br
        except Exception as e:
            last = e
    raise RuntimeError("no CDP endpoint worked; last=%s" % last)


def get_page(ctx, url):
    """Reuse a page already on workforcenow, else a blank tab, else new."""
    page = None
    for p in ctx.pages:
        try:
            if "workforcenow.adp.com" in p.url:
                page = p
                break
        except Exception:
            pass
    if not page:
        for p in ctx.pages:
            try:
                if p.url in ("about:blank", "") or "new-tab-page" in p.url or "newtab" in p.url:
                    page = p
                    break
            except Exception:
                pass
    if not page:
        page = ctx.new_page()
    return page


def goto(page, url, tries=2):
    for i in range(tries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            return True
        except Exception as e:
            log("goto attempt %d exc: %s" % (i + 1, str(e)[:120]))
            time.sleep(3)
    return False


# ---------- DOM helpers ----------

DUMP_JS = r"""
() => {
  const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };
  const out = {buttons:[], inputs:[], headings:[], dialogs:[], body:''};
  document.querySelectorAll('button, a[role=button], [role=button], input[type=submit], input[type=button]').forEach(b=>{
    if(!vis(b)) return;
    const t=(b.innerText||b.value||b.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ');
    if(t) out.buttons.push(t.slice(0,70));
  });
  document.querySelectorAll('input, select, textarea').forEach(el=>{
    if(!vis(el)) return;
    out.inputs.push({tag:el.tagName.toLowerCase(), type:el.type||'', name:el.name||'', id:el.id||'',
      ph:el.placeholder||'', aria:(el.getAttribute('aria-label')||'').slice(0,50), req:el.required||el.getAttribute('aria-required')==='true'});
  });
  document.querySelectorAll('h1,h2,h3,h4,[role=heading],legend,label.section,.step-title').forEach(h=>{
    if(!vis(h)) return; const t=(h.innerText||'').trim(); if(t&&t.length<90) out.headings.push(t);});
  document.querySelectorAll('[role=dialog],.modal,.modal-content').forEach(d=>{
    if(!vis(d)) return; out.dialogs.push((d.innerText||'').replace(/\s+/g,' ').slice(0,200));});
  out.body=(document.body.innerText||'').replace(/\s+/g,' ').slice(0,1200);
  out.url=location.href;
  return out;
}
"""


def dump(page, label=""):
    try:
        d = page.evaluate(DUMP_JS)
    except Exception as e:
        log("dump failed:", str(e)[:120])
        return {}
    log("==== STATE %s ====" % label)
    log("url:", d.get("url", "")[:140])
    if d.get("headings"):
        log("headings:", " | ".join(d["headings"][:12]))
    if d.get("dialogs"):
        log("dialogs:", " || ".join(d["dialogs"][:3]))
    if d.get("buttons"):
        log("buttons:", " | ".join(d["buttons"][:25]))
    if d.get("inputs"):
        for inp in d["inputs"][:30]:
            log("  input", inp)
    if d.get("body"):
        log("body:", d["body"][:600])
    return d


def click_text(page, *texts, timeout=8000, exact=False):
    """Click the first visible button/link matching any of the given texts."""
    for t in texts:
        for sel in (
            "button:has-text(\"%s\")" % t,
            "a[role=button]:has-text(\"%s\")" % t,
            "[role=button]:has-text(\"%s\")" % t,
            "input[type=submit][value=\"%s\" i]" % t,
            "input[type=button][value=\"%s\" i]" % t,
        ):
            try:
                loc = page.locator(sel).filter(visible=True).first
                if loc.count() > 0:
                    loc.scroll_into_view_if_needed(timeout=2000)
                    loc.click(timeout=timeout)
                    log("clicked:", t)
                    return True
            except Exception:
                continue
    return False


def fill_by(page, value, *selectors):
    for sel in selectors:
        try:
            loc = page.locator(sel).filter(visible=True).first
            if loc.count() > 0:
                loc.fill(value, timeout=4000)
                return sel
        except Exception:
            continue
    return None


# ---------- OTP ----------

def fetch_otp(since_epoch, timeout=180, poll=6):
    cmd = [str(RD / ".venv" / "bin" / "python"), str(RD / "fetch_adp_code.py"),
           str(since_epoch), "--timeout", str(timeout), "--poll", str(poll)]
    log("fetch_adp_code:", " ".join(cmd[-4:]))
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    log("fetch_adp_code rc=%d out=%r err=%r" % (r.returncode, out[:40], err[:80]))
    if r.returncode == 0 and re.fullmatch(r"\d{4,8}", out):
        return out
    return None


# ---------- phase: apply + consent + contact ----------

def phase_apply(page):
    """Click Apply, dismiss Privacy modal, return after landing on contact form."""
    # Click Apply (there may be two Apply buttons; click first visible)
    if not click_text(page, "Apply"):
        log("could not find Apply button")
        return False
    time.sleep(5)
    # Privacy / Data Privacy / consent modal
    for _ in range(3):
        if click_text(page, "Consent & Continue", "Consent and Continue", "I Consent",
                      "Agree", "Accept", "Continue", timeout=4000):
            time.sleep(4)
            break
        time.sleep(2)
    return True


def phase_contact(page):
    """Fill 'Tell us about yourself' name/email/phone, click Continue."""
    ident = PERSONAL["identity"]; contact = PERSONAL["contact"]
    first = ident["first_name"]; last = ident["last_name"]
    email = contact["email"]; phone = contact["phone"]
    time.sleep(2)
    # field selectors are flexible: match by id/name/placeholder/aria substrings
    fill_by(page, first,
            "input[id*='irst' i]", "input[name*='irst' i]", "input[placeholder*='First' i]",
            "input[aria-label*='First' i]")
    fill_by(page, last,
            "input[id*='ast' i]", "input[name*='ast' i]", "input[placeholder*='Last' i]",
            "input[aria-label*='Last' i]")
    fill_by(page, email,
            "input[type=email]", "input[id*='mail' i]", "input[name*='mail' i]",
            "input[placeholder*='mail' i]", "input[aria-label*='mail' i]")
    fill_by(page, phone,
            "input[type=tel]", "input[id*='hone' i]", "input[name*='hone' i]",
            "input[placeholder*='hone' i]", "input[aria-label*='hone' i]")
    time.sleep(1)
    if not click_text(page, "Continue", "Next", "Submit", timeout=6000):
        log("contact: could not click Continue")
        return False
    time.sleep(4)
    return True


def phase_otp(page, timeout=200):
    """Choose EMAIL, send code, fetch it, enter, verify."""
    # Pick EMAIL delivery option if a choice is presented (radio/button/label)
    for sel in ("input[type=radio][value*='mail' i]", "label:has-text('Email')",
                "button:has-text('Email')", "[role=radio]:has-text('Email')"):
        try:
            loc = page.locator(sel).filter(visible=True).first
            if loc.count() > 0:
                loc.click(timeout=3000)
                log("selected EMAIL delivery via", sel)
                break
        except Exception:
            continue
    time.sleep(1)
    # Capture epoch immediately before sending
    since = int(time.time())
    if not click_text(page, "Send code", "Send Code", "Send", "Send verification code",
                      "Email me", "Get code", timeout=6000):
        log("otp: could not click Send code")
        return False
    log("sent code at epoch", since)
    code = fetch_otp(since, timeout=timeout, poll=6)
    if not code:
        log("otp: fetch failed/timeout")
        return False
    log("got OTP", code)
    # Enter code: prefer split inputs (one digit each) else single field
    entered = enter_otp(page, code)
    if not entered:
        log("otp: could not enter code")
        return False
    time.sleep(1)
    if not click_text(page, "Verify", "Submit", "Continue", "Confirm", timeout=6000):
        log("otp: could not click Verify")
        # Some flows auto-verify on last digit; check progress anyway
    time.sleep(5)
    return True


def enter_otp(page, code):
    """Type OTP into either split single-digit boxes or a single input."""
    # Split inputs heuristic: several maxlength=1 text inputs
    try:
        boxes = page.locator("input[maxlength='1']").filter(visible=True)
        n = boxes.count()
        if n >= len(code):
            for i, ch in enumerate(code):
                boxes.nth(i).fill(ch, timeout=2000)
            log("entered OTP into %d split boxes" % len(code))
            return True
    except Exception:
        pass
    sel = fill_by(page, code,
                  "input[autocomplete='one-time-code']", "input[id*='ode' i]",
                  "input[name*='ode' i]", "input[placeholder*='ode' i]",
                  "input[aria-label*='ode' i]", "input[type=text]:visible")
    if sel:
        log("entered OTP into single input", sel)
        return True
    return False


# ---- phase_wizard helpers ----

REACT_FIBER_JS = r"""
(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  // Walk up fibers to find memoizedProps with currencyValidation or similar
  let fiber = el._reactFiber || el.__reactFiber || null;
  if (!fiber) {
    for (const k of Object.keys(el)) {
      if (k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance')) {
        fiber = el[k]; break;
      }
    }
  }
  let f = fiber, depth = 0;
  while (f && depth < 25) {
    const p = f.memoizedProps;
    if (p && (typeof p.onDesiredSalaryValue === 'function' || typeof p.currencyValidation !== 'undefined')) {
      return {
        hasDesiredSalary: typeof p.onDesiredSalaryValue === 'function',
        hasCurrencyChange: typeof p.onCurrencyChange === 'function',
        keys: Object.keys(p).slice(0, 40)
      };
    }
    f = f.return; depth++;
  }
  return {found: false};
}
"""

DESIRED_SALARY_JS = r"""
(salary) => {
  const el = document.querySelector('#question_0');
  if (!el) return 'no-q0-anchor';
  let fiber = null;
  for (const k of Object.keys(el)) {
    if (k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance')) {
      fiber = el[k]; break;
    }
  }
  let f = fiber, depth = 0;
  while (f && depth < 30) {
    const p = f.memoizedProps;
    if (p && typeof p.onDesiredSalaryValue === 'function') {
      try { p.onDesiredSalaryValue(String(salary)); } catch(e) { return 'err-dsv:'+e; }
      try { p.onDesiredSalaryType({detail:{value:'Annually'}}); } catch(e) {}
      const usd = {detail:{codeValue:'USD',label:'United States Dollar ( USD )',shortName:'SYS:5:420',value:'USD'}};
      try { p.onCurrencyChange(usd); } catch(e) {}
      try { p.onCurrencyValueChange(usd); } catch(e) {}
      return 'ok';
    }
    f = f.return; depth++;
  }
  return 'no-desired-salary-handler';
}
"""


def _sdf_select(page, field_id, option_text, timeout=5000):
    """Click an sdf-select-simple and pick an option by text."""
    try:
        page.click(f'#{field_id}', timeout=timeout)
        page.wait_for_timeout(800)
        loc = page.locator(f'[role=option]:has-text("{option_text}")').first
        if loc.count() > 0:
            loc.click(timeout=timeout)
            log(f"sdf_select #{field_id} -> {option_text}")
            return True
        # fallback: any visible option containing the text
        loc2 = page.locator(f'[role=listbox] [role=option], [role=option]').filter(has_text=option_text).first
        if loc2.count() > 0:
            loc2.click(timeout=timeout)
            log(f"sdf_select #{field_id} -> {option_text} (fallback)")
            return True
    except Exception as e:
        log(f"sdf_select #{field_id} err: {e}")
    return False


def _wait_for_step(page, heading_re, timeout_s=15):
    """Poll until a heading matching heading_re appears or timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            txt = page.evaluate("()=>document.body.innerText").lower()
            if re.search(heading_re, txt, re.I):
                return True
        except Exception:
            pass
        time.sleep(0.8)
    return False


def phase_wizard(page, resume, no_submit=False):
    """Drive the post-OTP ADP WFN wizard: Personal Info -> Resume -> Questions ->
    Voluntary Self-ID -> Review -> Self-Attest & Submit.
    Returns exit code: 0=submitted, 3=no-confirmation, 4=step-failed, 5=unexpected.
    Based on proven recipe in STATUS-adp-otp.md (2026-06-10).
    """
    addr = PERSONAL["address"]
    phone_raw = PERSONAL["contact"].get("phone", "346-804-0227")
    phone_e164 = "+1 " + phone_raw.replace("-", " ")  # '+1 346 804 0227'

    dump(page, "wizard-entry")

    # ----------------------------------------------------------------
    # Step 1: Personal Information
    # ----------------------------------------------------------------
    if not _wait_for_step(page, r"personal information|complete your application"):
        log("wizard: personal-info step not found")
        dump(page, "wizard-pi-miss")
        return 4

    log("wizard: filling Personal Information")

    # 1a. Country FIRST (MDF combobox)
    try:
        page.click("#PersonalAddress_country", timeout=5000)
        page.wait_for_timeout(600)
        page.type("#PersonalAddress_country", "United States", delay=60)
        page.wait_for_timeout(1200)
        loc = page.locator("[role=option]:has-text('United States')").first
        if loc.count() > 0:
            loc.click(timeout=6000, force=True)  # force=True bypasses animation stability check
        page.wait_for_timeout(800)
        log("personal_info: country set")
    except Exception as e:
        log("personal_info: country err", e)

    page.wait_for_timeout(600)

    # 1b. Address (Google Places autocomplete — must mouse-click first pac-item)
    try:
        full_addr = addr["street"]  # '12420 NE 120th St #1437'
        addr_sel = "#PersonalAddress_address_line1, input.pac-target-input"
        page.click(addr_sel, timeout=8000, force=True)  # force=True bypasses animation stability
        page.wait_for_timeout(400)
        page.fill(addr_sel, full_addr, timeout=4000)
        page.wait_for_timeout(2800)
        # Click first pac suggestion (required for place_changed event)
        first_item = page.locator(".pac-container .pac-item").first
        if first_item.count() > 0:
            # Use JS mousedown+click to fire place_changed (pac-item may not be visible in headless)
            clicked = page.evaluate("""
                () => {
                    const items = document.querySelectorAll('.pac-container .pac-item');
                    if (!items.length) return 'no-items';
                    const item = items[0];
                    // Simulate mouse events required for Google Places
                    ['mousedown', 'mouseenter', 'mousemove', 'mouseup', 'click'].forEach(evt => {
                        item.dispatchEvent(new MouseEvent(evt, {bubbles: true, cancelable: true, view: window}));
                    });
                    return 'fired-on:' + item.textContent.slice(0, 60);
                }
            """)
            log("personal_info: pac-item JS click:", clicked)
            page.wait_for_timeout(1500)
            # Try Playwright click as fallback
            if 'no-items' not in (clicked or ''):
                try:
                    first_item.click(timeout=2000, force=True)
                except Exception:
                    pass
            page.wait_for_timeout(1200)
            log("personal_info: address place picked")
        else:
            # No autocomplete — fill fields manually
            log("personal_info: no pac items, filling manually")
            for fill_sel, fill_val in [
                ("#PersonalAddress_city", addr["city"]),
                ("#PersonalAddress_postalCode", addr["zip"]),
            ]:
                try:
                    page.click(fill_sel, timeout=3000, force=True)
                    page.fill(fill_sel, fill_val, timeout=3000)
                    log(f"personal_info: filled {fill_sel}")
                except Exception as fe:
                    log("personal_info: fill err", fe)
            log("personal_info: address manual fill")
    except Exception as e:
        log("personal_info: address err", e)

    page.wait_for_timeout(400)

    # 1c. Phone (fill BOTH phone inputs)
    for phone_sel in [
        "#personalInfomationMobileNumberError",
        "#personalInfomationMobileNumberErrorMessage",
        "input[aria-label*='phone' i]",
        "input[type='tel']",
    ]:
        try:
            locs = page.locator(phone_sel).all()
            for loc in locs:
                if loc.is_visible():
                    loc.fill(phone_e164, timeout=3000)
                    loc.press("Tab")
        except Exception:
            pass

    log("personal_info: phone filled")
    page.wait_for_timeout(600)

    # 1d. Click Next
    if not click_text(page, "Next", "Continue", "next"):
        log("personal_info: Next button not found")
        dump(page, "wizard-pi-next-fail")
        return 4
    page.wait_for_timeout(3000)
    dump(page, "wizard-after-pi")

    # ----------------------------------------------------------------
    # Step 2: Resume Upload
    # ----------------------------------------------------------------
    if not _wait_for_step(page, r"resume|upload", timeout_s=12):
        log("wizard: resume step not detected; proceeding anyway")

    log("wizard: uploading resume")
    try:
        file_inputs = page.locator("input[type=file]").all()
        uploaded = False
        for fi in file_inputs:
            if fi.is_visible() or True:  # set_input_files works even if not visible
                fi.set_input_files(resume, timeout=10000)
                page.wait_for_timeout(2500)
                log("wizard: resume set_input_files done")
                uploaded = True
                break
        if not uploaded:
            log("wizard: no file input found for resume")
            return 4
        # Wait for Bravo/confirmation text
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                body = page.evaluate("()=>document.body.innerText").lower()
                if "bravo" in body or "resume" in body:
                    break
            except Exception:
                pass
            time.sleep(0.8)
    except Exception as e:
        log("wizard: resume upload err", e)
        return 4

    dump(page, "wizard-after-resume")

    if not click_text(page, "Next", "Continue"):
        log("wizard: resume Next not found")
        dump(page, "wizard-resume-next-fail")
        return 4
    page.wait_for_timeout(3000)
    dump(page, "wizard-after-resume-next")

    # ----------------------------------------------------------------
    # Step 3: Questions
    # ----------------------------------------------------------------
    if not _wait_for_step(page, r"question|questionnaire|referral", timeout_s=12):
        log("wizard: questions step not detected; proceeding")

    log("wizard: filling Questions")

    # Q0: referral text (required text)
    try:
        q0 = page.locator("#question_0").first
        if q0.count() > 0 and q0.is_visible():
            q0.fill("Not Applicable", timeout=3000)
            q0.press("Tab")
            log("wizard: Q0 filled")
    except Exception as e:
        log("wizard: Q0 err", e)

    # Q1: how-heard (sdf-select-simple -> LinkedIn)
    _sdf_select(page, "question_1", "LinkedIn")
    page.wait_for_timeout(400)

    # Q2: total-comp (plain text input)
    try:
        q2 = page.locator("#question_2").first
        if q2.count() > 0:
            q2.fill("150000", timeout=3000)
            q2.press("Tab")
        # Q2 currency
        try:
            page.click("#question_currency_type_2", timeout=3000)
            page.wait_for_timeout(600)
            cur_opt = page.locator(".MDFSelectBox__option, [role=option]").filter(has_text="United States Dollar").first
            if cur_opt.count() > 0:
                cur_opt.click(timeout=3000)
        except Exception:
            pass
    except Exception as e:
        log("wizard: Q2 err", e)

    # Q3: VISA sponsorship (sdf-select-simple -> No)
    _sdf_select(page, "question_3", "No")
    page.wait_for_timeout(400)

    # Desired salary block (required — must use React fiber approach)
    try:
        res = page.evaluate(DESIRED_SALARY_JS, "150000")
        log("wizard: desired_salary react handler:", res)
    except Exception as e:
        log("wizard: desired_salary err", e)
        # Fallback: fill visible salary text input
        try:
            sal_inp = page.locator("#desiredSalaryId").first
            if sal_inp.count() > 0:
                sal_inp.fill("150000", timeout=3000)
                sal_inp.press("Tab")
        except Exception:
            pass

    page.wait_for_timeout(600)
    dump(page, "wizard-questions-prefill")

    if not click_text(page, "Next", "Continue"):
        log("wizard: questions Next not found")
        dump(page, "wizard-questions-next-fail")
        return 4
    page.wait_for_timeout(3000)
    dump(page, "wizard-after-questions")

    # ----------------------------------------------------------------
    # Step 4: Voluntary Self-ID (decline all)
    # ----------------------------------------------------------------
    if not _wait_for_step(page, r"voluntary|self.?id|diversity|demographic", timeout_s=12):
        log("wizard: self-id step not detected; proceeding")
    else:
        log("wizard: declining Voluntary Self-ID")
        # Decline options: 'I decline to identify', 'Decline to self-identify', etc.
        for decline_text in ["decline", "prefer not", "choose not", "do not wish"]:
            try:
                opts = page.locator(f"[role=option]:has-text('{decline_text}')").all()
                opts += page.locator(f"label:has-text('{decline_text}')").all()
                opts += page.locator(f"button:has-text('{decline_text}')").all()
                for opt in opts:
                    if opt.is_visible():
                        opt.click(timeout=3000)
                        page.wait_for_timeout(300)
            except Exception:
                pass
        page.wait_for_timeout(600)
        dump(page, "wizard-selfid")

        if not click_text(page, "Next", "Continue"):
            log("wizard: self-id Next not found; trying to proceed")

        page.wait_for_timeout(3000)
        dump(page, "wizard-after-selfid")

    # ----------------------------------------------------------------
    # Step 5: Review
    # ----------------------------------------------------------------
    if _wait_for_step(page, r"review|summary", timeout_s=10):
        log("wizard: on Review step")
        dump(page, "wizard-review")
        if not click_text(page, "Next", "Continue", "Submit"):
            log("wizard: review Next/Submit not found")
        page.wait_for_timeout(3000)

    # ----------------------------------------------------------------
    # Step 6: Self-Attest & Submit
    # ----------------------------------------------------------------
    if _wait_for_step(page, r"attest|signature|certify|agree", timeout_s=10):
        log("wizard: on Self-Attest step")
        dump(page, "wizard-attest")
        # Fill signature if present
        try:
            fname = PERSONAL["identity"]["first_name"]
            lname = PERSONAL["identity"]["last_name"]
            full_name = f"{fname} {lname}"
            for sig_sel in ["#signature", "input[aria-label*='signature' i]",
                            "input[aria-label*='name' i]", "#attestation"]:
                try:
                    sig = page.locator(sig_sel).first
                    if sig.count() > 0 and sig.is_visible():
                        sig.fill(full_name, timeout=3000)
                        sig.press("Tab")
                        log("wizard: signature filled")
                        break
                except Exception:
                    pass
        except Exception:
            pass
        # Check checkbox if present
        for chk_sel in ["#attestationCheckbox", "input[type=checkbox]"]:
            try:
                chk = page.locator(chk_sel).first
                if chk.count() > 0 and chk.is_visible() and not chk.is_checked():
                    chk.check(timeout=3000)
                    log("wizard: attest checkbox checked")
                    break
            except Exception:
                pass

    if no_submit:
        log("wizard: --no-submit flag set; stopping before final Submit")
        dump(page, "wizard-no-submit")
        return 0

    dump(page, "wizard-before-submit")

    # Final Submit
    if not click_text(page, "Submit", "Submit Application", "Apply", "Finish"):
        log("wizard: Submit button not found")
        dump(page, "wizard-submit-fail")
        return 4

    log("wizard: clicked Submit; waiting for confirmation")
    page.wait_for_timeout(5000)
    dump(page, "wizard-after-submit")

    # Detect confirmation
    for _ in range(6):
        try:
            body = page.evaluate("()=>document.body.innerText").lower()
            if re.search(
                r"thank you|application (submitted|received|complete)|successfully (submitted|applied)"
                r"|your application has been|we.{0,4}ve received your application|submission complete",
                body
            ):
                log("wizard: CONFIRMATION detected")
                return 0
        except Exception:
            pass
        time.sleep(2)

    log("wizard: no confirmation after submit")
    dump(page, "wizard-no-confirm")
    return 3



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--resume", required=True)
    ap.add_argument("--role-id", default="")
    ap.add_argument("--phase", default="all", choices=["all", "recon", "apply", "otp", "wizard"])
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--no-submit", action="store_true")
    args = ap.parse_args()

    resume = str((ROOT / args.resume).resolve()) if not os.path.isabs(args.resume) else args.resume
    if not os.path.exists(resume):
        # try as given relative to cwd
        if os.path.exists(args.resume):
            resume = os.path.abspath(args.resume)
        else:
            log("RESUME NOT FOUND:", resume)
            sys.exit(5)
    log("resume:", resume)

    pw, br = connect()
    ctx = br.contexts[0]
    page = get_page(ctx, args.url)

    if args.phase in ("all", "recon", "apply"):
        log("navigating to job url")
        goto(page, args.url)
        time.sleep(7)

    if args.dump or args.phase == "recon":
        dump(page, "initial")
        if args.phase == "recon":
            return

    # Detect terminal: already applied / closed
    try:
        body0 = page.evaluate("() => (document.body.innerText||'')").lower()
        if "you have already applied" in body0 or "already applied" in body0:
            log("TERMINAL: already applied")
            sys.exit(6)
        if "no longer accepting" in body0 or "this position is closed" in body0 or "requisition is closed" in body0:
            log("TERMINAL: req closed")
            sys.exit(6)
    except Exception:
        pass

    if args.phase in ("all", "apply"):
        if not phase_apply(page):
            log("phase_apply failed")
            dump(page, "apply-fail")
            sys.exit(4)
        dump(page, "after-apply")
        if not phase_contact(page):
            log("phase_contact failed")
            dump(page, "contact-fail")
            sys.exit(4)
        dump(page, "after-contact")
        if args.phase == "apply":
            return

    if args.phase in ("all", "otp"):
        if not phase_otp(page):
            log("phase_otp failed")
            dump(page, "otp-fail")
            sys.exit(2)
        dump(page, "after-otp")
        if args.phase == "otp":
            return

    if args.phase in ("all", "wizard"):
        rc = phase_wizard(page, resume, no_submit=args.no_submit)
        sys.exit(rc)


if __name__ == "__main__":
    main()
