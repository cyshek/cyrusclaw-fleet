#!/usr/bin/env python3
"""
_uber_apply.py — Uber Careers fresh-account apply driver (CDP, shared OpenClaw chrome).

Cyrus directive 2026-06-08: "needs login" is NOT a blocker. Uber's apply form is gated
behind an "Uber Careers account" card (Sign in | Create account, email+password, pw>=6
chars w/ >=1 number; NO guest path). We resolve it ourselves with a fresh throwaway
account using a gmail '+' alias (verification, if any, lands in the inbox gmail_imap
reads). Creating the account logs us straight into the FULL apply form (basic info,
resume upload, experience, education, links, screening radios, demographics, arbitration,
Submit application).

OBSERVED (2026-06-08, req 158309): signup required NO email verification and NO captcha;
it logged in directly to the rendered form. We still handle verification + captcha-detect
defensively (bank `uber-signup-captcha` if a real captcha wall appears).

Account is PERSISTED to projects/job-search/role-discovery/.uber-creds.json (chmod 600)
so the SECOND req signs into the SAME account (one account, both apps) and Cyrus can
reuse/sign-in later.

Selectors (verified live):
  Account card:   button "Sign in"  /  link "Create account" (opens dialog)
  Dialog:         input[name=email], input[name=password], button[name=submit-button]
  Form basic:     input[name=firstName], input[name=lastName], input[name=email](disabled),
                  input[name=mobileNumber], country combobox (aria "Selected United States...")
  Resume:         button "Browse files" -> hidden <input type=file> (set_input_files)
  Experience.0:   experiences.0.companyName/.title/.startDate.year/.endDate.year/.description
                  + "Current" checkbox + Start/End month comboboxes
  Education.0:    educations.0.schoolName/.degree/.fieldOfStudy/.startDate.year/.endDate.year
                  + month comboboxes
  Links:          linkedin / github / portfolio textboxes
  Screening radios (Yes/No unless noted) + truthful answers:
     "Are you currently or have you ever been a Driver / Uber Eats / Uber Freight?" -> No
     "Are you open to being considered for other roles?"                            -> Yes
     "Do you reside in the United States?"                                          -> Yes
     "Are you currently employed by one of Uber's subsidiaries?" (combobox)         -> No
     "Do you have the legal right to work in the country...?"                       -> Yes
     "Will you now or in the future require our sponsorship...?"                     -> No
     Arbitration Agreement                                                          -> Yes, I agree
     Demographics (gender/race/disability/veteran/orientation)                      -> Prefer not to say (voluntary)
  Submit:         button "Submit application"

Usage:
  _uber_apply.py --id <roleId> --job <uberJobId> --resume <pdf> [--dry-run] [--no-verify]
  e.g. _uber_apply.py --id 1882 --job 158309 \
        --resume applications/queued/uber-158309/Cyrus_Shekari_Resume_uber_158309_v2.pdf

Exit codes:
  0 = submitted (real confirmation reached)  | 0 + DRYRUN tag if --dry-run (review only)
  2 = signup captcha / akamai wall (bank uber-signup-captcha)
  3 = req closed/removed (bank uber-req-closed)
  4 = could not reach/submit form for another reason (bank uber-apply-<detail>)
  5 = email verification required but code never arrived (bank uber-signup-verify-timeout)
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # projects/job-search
RDIR = Path(__file__).resolve().parent              # role-discovery
WS = ROOT.parent.parent                             # workspace
CDP = os.environ.get("OPENCLAW_CDP", "http://127.0.0.1:18800")
CREDS_PATH = RDIR / ".uber-creds.json"
DBG = RDIR / "_uber_debug"
DBG.mkdir(exist_ok=True)

sys.path.insert(0, str(RDIR))
from _workday_runner import _gmail_base_inbox, _gen_fresh_alias, _gen_strong_password  # reuse helpers
import gmail_imap

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


def log(*a):
    print("[uber]", *a, flush=True)


# ---------------- creds persistence (.uber-creds.json) ----------------
def load_creds() -> dict:
    if CREDS_PATH.exists():
        try:
            return json.load(open(CREDS_PATH))
        except Exception:
            pass
    return {}


def persist_creds(**account_fields):
    """Merge account_fields into creds['account'] and write (chmod 600)."""
    d = load_creds()
    d.setdefault("shared_email", _gmail_base_inbox())
    acct = d.get("account") or {}
    acct.update({k: v for k, v in account_fields.items() if v is not None})
    d["account"] = acct
    d.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    d["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = str(CREDS_PATH) + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(d, fh, indent=2)
    os.replace(tmp, CREDS_PATH)
    try:
        os.chmod(CREDS_PATH, 0o600)
    except Exception:
        pass


def get_or_make_account() -> tuple[str, str, str]:
    """Return (email, password, mode) where mode is 'reuse' or 'create'.
    Reuse a persisted, non-polluted account if present; else mint a fresh alias+pw and
    PERSIST immediately (recoverable even on mid-flow crash)."""
    d = load_creds()
    acct = d.get("account") or {}
    if acct.get("email") and acct.get("password") and not acct.get("polluted"):
        log(f"account: REUSE persisted alias {acct['email']} (created={acct.get('created')})")
        return acct["email"], acct["password"], "reuse"
    alias = _gen_fresh_alias("uber")
    pw = _gen_strong_password()
    # Uber pw policy: >=6 chars + >=1 digit. _gen_strong_password guarantees both.
    persist_creds(email=alias, password=pw, verified=False, created=False,
                  note="fresh throwaway Uber Careers account, gmail + alias")
    log(f"account: MINT fresh alias {alias} (persisted)")
    return alias, pw, "create"


# ---------------- browser plumbing (CDP attach to managed chrome) ----------------
def attach():
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    if not br.contexts:
        raise RuntimeError("no browser contexts on CDP endpoint")
    ctx = br.contexts[0]
    return pw, br, ctx


def shot(page, tag):
    try:
        p = str(DBG / f"{tag}.png")
        page.screenshot(path=p, full_page=True)
        return p
    except Exception:
        return None


def detect_captcha(page) -> str | None:
    """Return a short reason string if an Akamai/hCaptcha/recaptcha challenge is present."""
    try:
        html = page.content().lower()
    except Exception:
        return None
    markers = [
        ("hcaptcha", "hcaptcha"),
        ("g-recaptcha", "recaptcha"),
        ("recaptcha/api", "recaptcha"),
        ("ak_bmsc", "akamai"),
        ("access denied", "akamai-access-denied"),
        ("/akam/", "akamai"),
        ("please verify you are a human", "captcha-human"),
        ("are you a robot", "captcha-robot"),
    ]
    for needle, reason in markers:
        if needle in html:
            # hcaptcha/recaptcha scripts are sometimes present-but-dormant; only flag if a
            # visible challenge iframe/box exists.
            if reason in ("hcaptcha", "recaptcha"):
                try:
                    if page.locator("iframe[src*=hcaptcha], iframe[src*=recaptcha], "
                                    "div.h-captcha, div.g-recaptcha").count() == 0:
                        continue
                except Exception:
                    pass
            return reason
    return None


# ---------------- the apply flow ----------------
def open_form(page, job_id: str) -> str:
    """Navigate JD -> Apply Now -> account/apply form. Returns 'form'|'account'|'closed'."""
    url = f"https://www.uber.com/careers/list/{job_id}/"
    log("goto", url)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    body = ""
    try:
        body = page.inner_text("body").lower()
    except Exception:
        pass
    if ("no longer available" in body or "couldn't find that page" in body
            or "could not find" in body or "position has been filled" in body):
        return "closed"
    # Click Apply Now (link to /careers/apply/interstitial/<id>)
    clicked = False
    for sel in [f"a[href*='/careers/apply/interstitial/{job_id}']", "a:has-text('Apply Now')",
                "text=Apply Now"]:
        loc = page.locator(sel).first
        if loc.count():
            try:
                loc.click(timeout=8000)
                clicked = True
                break
            except Exception:
                continue
    if not clicked:
        # maybe already on interstitial; try direct nav
        page.goto(f"https://www.uber.com/careers/apply/interstitial/{job_id}",
                  wait_until="domcontentloaded", timeout=60000)
    # follow to form URL
    for _ in range(12):
        page.wait_for_timeout(1200)
        u = page.url
        if "/careers/apply/form/" in u:
            break
    page.wait_for_timeout(2000)
    # account card vs form
    if page.locator("input[name=firstName]").count():
        return "form"
    if (page.locator("button:has-text('Sign in')").count()
            or page.locator("text=Uber Careers account").count()
            or page.locator("a:has-text('Create account')").count()):
        return "account"
    # last chance: form may still be loading
    page.wait_for_timeout(3000)
    if page.locator("input[name=firstName]").count():
        return "form"
    return "account"


def create_account(page, email: str, password: str, no_verify: bool) -> str:
    """Open Create-account dialog, fill, submit, handle verification. Returns
    'form' (signed in, form visible) | 'captcha' | 'verify_timeout' | 'unknown'."""
    # open dialog
    link = page.locator("a:has-text('Create account')").first
    if link.count():
        try:
            link.click(timeout=8000)
        except Exception:
            pass
    page.wait_for_timeout(1500)
    if not page.locator("input[name=email]").count():
        # maybe sign-in form rendered instead; try a 'Create account' toggle text
        for sel in ["text=Create account", "button:has-text('Create account')"]:
            l = page.locator(sel).first
            if l.count():
                try:
                    l.click(timeout=5000); page.wait_for_timeout(1200)
                except Exception:
                    pass
    if not page.locator("input[name=email]").count():
        return "unknown"
    since = time.time() - 5
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    shot(page, "account-dialog-filled")
    # submit
    btn = page.locator("button[name=submit-button]").first
    if not btn.count():
        btn = page.locator("button:has-text('Create account')").last
    btn.click(timeout=10000)
    log("submitted create-account")
    # wait for one of: form, verification prompt, captcha
    for _ in range(20):
        page.wait_for_timeout(1500)
        cap = detect_captcha(page)
        if cap:
            shot(page, "signup-captcha")
            log("CAPTCHA detected on signup:", cap)
            return "captcha"
        if page.locator("input[name=firstName]").count():
            log("signed in -> apply form visible (no verification needed)")
            persist_creds(email=email, password=password, created=True, verified=True,
                          note="signup logged in directly; no email-verify/captcha")
            return "form"
        # verification prompt? look for a code input
        if _verification_prompt(page):
            log("email verification prompt detected")
            if no_verify:
                log("--no-verify set; not polling email")
                return "verify_timeout"
            ok = _complete_verification(page, since)
            if ok == "captcha":
                return "captcha"
            if ok and page.locator("input[name=firstName]").count():
                persist_creds(email=email, password=password, created=True, verified=True)
                return "form"
            if not ok:
                return "verify_timeout"
    # final check
    if page.locator("input[name=firstName]").count():
        persist_creds(email=email, password=password, created=True, verified=True)
        return "form"
    return "unknown"


def sign_in(page, email: str, password: str) -> str:
    """Sign into an existing account from the account card. Returns 'form'|'captcha'|'unknown'."""
    btn = page.locator("button:has-text('Sign in')").first
    if btn.count():
        try:
            btn.click(timeout=8000); page.wait_for_timeout(1500)
        except Exception:
            pass
    if not page.locator("input[name=email]").count():
        return "unknown"
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    # sign-in submit
    for sel in ["button[type=submit]:has-text('Sign in')", "button:has-text('Sign in')",
                "button[name=submit-button]"]:
        l = page.locator(sel).first
        if l.count():
            try:
                l.click(timeout=8000); break
            except Exception:
                continue
    for _ in range(16):
        page.wait_for_timeout(1500)
        cap = detect_captcha(page)
        if cap:
            shot(page, "signin-captcha"); return "captcha"
        if page.locator("input[name=firstName]").count():
            return "form"
    return "unknown"


def _verification_prompt(page) -> bool:
    try:
        txt = page.inner_text("body").lower()
    except Exception:
        return False
    if ("verification code" in txt or "verify your email" in txt or "enter the code" in txt
            or "we sent a code" in txt or "check your email" in txt):
        # and a code-ish input present
        return (page.locator("input[autocomplete=one-time-code]").count() > 0
                or page.locator("input[name*=code i]").count() > 0
                or page.locator("input[inputmode=numeric]").count() > 0
                or "verification code" in txt)
    return False


def _complete_verification(page, since: float):
    """Poll gmail for the Uber code, type it, submit. Returns True/False or 'captcha'."""
    code = None
    try:
        # Uber codes are typically 4-6 digits; use a tailored reader first, fall back to
        # gmail_imap's generic extractor.
        code = _wait_uber_code(timeout_s=180, since_epoch=since)
    except Exception as e:
        log("verification poll error:", str(e)[:120])
    if not code:
        try:
            code = gmail_imap.wait_for_verification_code(timeout_seconds=60, since_epoch=since)
        except Exception:
            code = None
    if not code:
        log("no verification code arrived in budget")
        return False
    log("got verification code:", code)
    # type into code field(s)
    typed = False
    for sel in ["input[autocomplete=one-time-code]", "input[inputmode=numeric]",
                "input[name*=code i]"]:
        loc = page.locator(sel)
        if loc.count() == 1:
            loc.first.fill(code); typed = True; break
        if loc.count() > 1:
            # per-digit boxes
            for i, ch in enumerate(code):
                if i < loc.count():
                    loc.nth(i).fill(ch)
            typed = True; break
    if not typed:
        return False
    page.wait_for_timeout(800)
    for sel in ["button:has-text('Verify')", "button:has-text('Continue')",
                "button:has-text('Submit')", "button[type=submit]"]:
        l = page.locator(sel).first
        if l.count():
            try:
                l.click(timeout=6000); break
            except Exception:
                continue
    for _ in range(12):
        page.wait_for_timeout(1500)
        if detect_captcha(page):
            return "captcha"
        if page.locator("input[name=firstName]").count():
            return True
    return False


def _wait_uber_code(timeout_s=180, since_epoch=None):
    """Uber-tailored IMAP code reader (numeric 4-6 or alnum). Reuses gmail_imap connection
    plumbing but with a looser code regex than the Greenhouse 8-char one."""
    import imaplib, email as _email, re, ssl, time as _t
    from email.utils import parsedate_to_datetime
    if since_epoch is None:
        since_epoch = _t.time() - 300
    user = gmail_imap.GMAIL_USER
    host = gmail_imap.IMAP_HOST
    port = gmail_imap.IMAP_PORT
    pw = gmail_imap._load_password()
    deadline = _t.time() + timeout_s
    code_re = re.compile(r"\b(\d{4,8})\b")
    while _t.time() < deadline:
        try:
            ctx = ssl.create_default_context()
            M = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
            M.login(user, pw)
            try:
                for mbox in gmail_imap.MAILBOXES:
                    typ, _ = M.select(mbox)
                    if typ != "OK":
                        continue
                    since_str = _t.strftime("%d-%b-%Y", _t.gmtime(since_epoch - 86400))
                    typ, data = M.search(None, f'(SINCE {since_str})')
                    if typ != "OK" or not data or not data[0]:
                        continue
                    ids = list(reversed(data[0].split()))[:30]
                    for mid in ids:
                        typ, md = M.fetch(mid, "(RFC822)")
                        if typ != "OK" or not md or not md[0]:
                            continue
                        msg = _email.message_from_bytes(md[0][1])
                        try:
                            dt = parsedate_to_datetime(msg.get("Date"))
                            if dt and dt.timestamp() < since_epoch - 5:
                                break
                        except Exception:
                            pass
                        frm = (msg.get("From") or "").lower()
                        subj = (msg.get("Subject") or "").lower()
                        if "uber" not in frm and "uber" not in subj:
                            continue
                        body = gmail_imap._msg_text(msg)
                        hay = subj + "\n" + re.sub(r"<[^>]+>", " ", body)
                        # prefer a code near the word 'code'
                        m = re.search(r"code[^0-9]{0,30}(\d{4,8})", hay, re.I) or code_re.search(hay)
                        if m:
                            return m.group(1)
            finally:
                try:
                    M.logout()
                except Exception:
                    pass
        except Exception:
            pass
        _t.sleep(5)
    return None


# ---------------- form fill ----------------
PERSONAL = json.load(open(ROOT / "personal-info.json"))


def _pick_radio(page, question_substr: str, option_text: str) -> bool:
    """Find the radiogroup whose nearby text contains question_substr, click the option
    whose label contains option_text."""
    # Strategy: locate a label/element with the question text, then the following radio
    # whose accessible name matches option_text.
    js = """([qsub, opt]) => {
      const norm = s => (s||'').replace(/\\s+/g,' ').trim().toLowerCase();
      const groups = [...document.querySelectorAll('[role=radiogroup]')];
      for (const g of groups) {
        // build question context from ancestors
        let ctx='';
        let cur=g;
        for(let up=0; up<6 && cur; up++){ cur=cur.parentElement; if(!cur) break; const t=norm(cur.innerText); if(t.includes(norm(qsub))){ ctx=t; break; } }
        if(!ctx) continue;
        // find clickable radio option matching opt
        const cands=[...g.querySelectorAll('label,[role=radio],button,input[type=radio]')];
        for(const c of cands){
          const name=norm(c.innerText)||norm(c.getAttribute('aria-label'))||norm(c.value);
          if(name && name.includes(norm(opt))){ c.scrollIntoView({block:'center'}); c.click(); return 'OK'; }
        }
      }
      return 'MISS';
    }"""
    try:
        r = page.evaluate(js, [question_substr, option_text])
        return r == "OK"
    except Exception as e:
        log("radio pick err", question_substr[:30], str(e)[:80])
        return False


def _pick_month_combobox(page, name_prefix: str, month_label: str) -> bool:
    """Open the month combobox next to a date field group and choose month_label.
    The comboboxes are unnamed inputs/buttons; we find by the date group container."""
    # Best-effort: comboboxes render as listboxes on click. We locate via the year input's
    # sibling structure. Returns True if a matching option was clicked.
    js_open = """(prefix) => {
      const yi=document.querySelector
  return null;
    }"""
    return False
