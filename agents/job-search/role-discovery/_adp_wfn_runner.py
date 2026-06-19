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


def phase_wizard(page, resume, no_submit=False):
    """Drive the post-OTP wizard. Returns exit code.
    Built adaptively; for now dumps state so the structure can be mapped.
    """
    dump(page, "wizard-entry")
    log("phase_wizard: not yet implemented (mapping)")
    return 5


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
