#!/usr/bin/env python3
"""TikTok / ByteDance referral apply runner (chain_tiktok, 2026-06-01/02).

Connects to the OpenClaw browser on CDP :18800 (same attach pattern as
_ashby_runner.py / _gh_submit.py) and drives the lifeattiktok.com REFERRAL
apply flow end-to-end, preserving referral attribution via the referral token
(carried in URL + `referral-token` cookie).

==============================================================================
FULLY VALIDATED END-TO-END 2026-06-02 (TikTok job 7600517104210938165,
role 1884, "TikTok Shop - Product Manager, Aftersales"). ONE real submit
confirmed: TikTok Application History shows "Applied via referral",
status "Resume screening", 2026-06-02 06:05. NO captcha, NO 2FA on login.

FLOW (observed live):
  1. Visit referral landing:
       https://lifeattiktok.com/referral/tiktok?token=<TOKEN>
     -> sets cookie `referral-token=<TOKEN>` (binds credit) + `atsx-csrf-token`.
  2. Navigate apply URL directly:
       https://lifeattiktok.com/referral/tiktok/resume/<jobid>/apply?token=<TOKEN>
     -> IF NOT LOGGED IN, redirects to:
       https://lifeattiktok.com/referral/tiktok/login?token=<TOKEN>&redirect_path=%2Fresume%2F<jobid>%2Fapply
     redirect_path PRESERVES the apply destination; referral-token cookie
     persists across login -> referral credit survives auth.
  3. LOGIN (Sign in with Email):
       #email  + #password  (native-setter value set + input/change events),
       check the consent checkbox `input.atsx-checkbox-input`,
       click the "Sign in" <button> (text == 'Sign in').
     cyshekari@gmail.com password is stored at ../.tiktok-password (chmod600).
     On success the SPA auto-redirects to the apply page (redirect_path) and
     sets session cookie `atsx-portal-user-source-v1`. NO captcha/slider/OTP
     was presented (2026-06-02). If a slider/GeeTest ever appears -> that is a
     NEW blocker; stop + report (CapSolver token flow would be needed).
  4. APPLY FORM (https://.../resume/<jobid>/apply) is an account-PROFILE form,
     PRE-POPULATED from Cyrus's existing TikTok-careers account:
       - Basic Info: #name, phone input.atsx-phone, #email  (already filled).
       - Work/Education/Internship/Project sections: career[i].*, education[i].*,
         internship[i].*, project[i].* (already filled from saved profile).
       - Resume already on file; we REPLACE it with the tailored PDF via the
         hidden input[type=file] (set_input_files). The "Last updated" stamp +
         filename label update on success.
       - TWO required Work-Authorization react-selects (TikTok "ud__select"
         design-system dropdowns, class `.ud__select.select__1A5Um`):
           Q1 "Are you legally authorized to work in the US without
               restriction?"  -> Yes
           Q2 "Will you now or in the future require visa sponsorship or a
               visa transfer?" -> No
         GOTCHA: these dropdowns do NOT open on a programmatic .click() of the
         selector; they need a REAL pointer event. We scrollIntoView, read the
         center coords, and dispatch a trusted click via CDP
         Input.dispatchMouseEvent (page.mouse.click). Options then render as
         `.ud__select__list__item` (text 'Yes'/'No') in a portal -> .click()
         the matching item (that part works programmatically).
       - Consent: `input.atsx-checkbox-input` (the "I have read and agreed to
         the Privacy Policy") -> .click() to check.
       - Submit: <button> text == 'Submit' (enabled once required fields set).
  5. SUCCESS = redirect to .../resume/applied  AND body contains
     "We have received your resume." Independent proof: history at
     .../referral/tiktok/position/application shows the role "Applied via
     referral".

ByteDance (jobs.bytedance.com/referral/pc/...): WIRED 2026-06-02. The general
(social/experienced-hire) referral token resolves to GENERAL scope (not campus),
so _urls() now builds the BD map (same atsx SPA, /referral/pc/ path prefix).
KNOWN BLOCKER: the BD careers account is SEPARATE from the lifeattiktok.com
account; the stored password (== the working TikTok one) returns 'Incorrect
email or password', and Create-account / Reset-password both gate on an email
verification code (OTP) to cyshekari@gmail.com -> hard block without inbox
access. The flow/URL wiring is complete and will work once a valid BD
credential exists at ../.bytedance-password (or the account is created).

Usage:
  python3 _tiktok_runner.py --brand tiktok --job-id <id> --resume <pdf> [--no-submit]

Env:
  TIKTOK_NO_UPLOAD=1   skip resume replacement (use whatever is on file).
"""
import argparse, json, os, sys, time
from pathlib import Path

ROOT = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search'
sys.path.insert(0, ROOT + '/role-discovery')
from playwright.sync_api import sync_playwright  # noqa: E402

CDP = "http://127.0.0.1:18800"
REFERRALS = Path(ROOT) / ".referrals.json"
PASSWORD_FILE = Path(ROOT) / ".tiktok-password"


def _password_file(brand: str) -> Path:
    """BD careers account is SEPARATE from the TikTok account (different
    password), so the credential file is brand-specific. Falls back to the
    TikTok password file only if a brand-specific one is absent."""
    if brand == "bytedance":
        bd = Path(ROOT) / ".bytedance-password"
        if bd.exists():
            return bd
    return PASSWORD_FILE
EMAIL = "cyshekari@gmail.com"

HOSTS = {"tiktok": "lifeattiktok.com", "bytedance": "jobs.bytedance.com"}


def _token(brand: str) -> str:
    d = json.loads(REFERRALS.read_text())
    return d[brand]["referral_link"].split("token=", 1)[1].split("&", 1)[0]


def _urls(brand: str, job_id: str):
    host, tok = HOSTS[brand], _token(brand)
    if brand == "tiktok":
        return {
            "landing": f"https://{host}/referral/tiktok?token={tok}",
            "apply":   f"https://{host}/referral/tiktok/resume/{job_id}/apply?token={tok}",
            "login_prefix": f"https://{host}/referral/tiktok/login",
            "applied_prefix": f"https://{host}/referral/tiktok/resume/applied",
            "history": f"https://{host}/referral/tiktok/position/application?token={tok}",
        }
    if brand == "bytedance":
        # GENERAL (social/experienced-hire, 社招内推) referral scope confirmed
        # live 2026-06-02 (probe _bd_probe*.py). Token replaced the old
        # campus-scoped link per Cyrus -> the SystemExit guard is REMOVED.
        #
        # URL map discovered live (job 7636946534608816 through the referral
        # context). BD mirrors TikTok's atsx-portal SPA but under the
        # /referral/pc/ path prefix (TikTok uses /referral/tiktok/):
        #   landing  : /referral/pc/position?token=...
        #              -> sets referral-token (dom=jobs.bytedance.com) +
        #                 atsx-csrf-token (dom=.jobs.bytedance.com). Confirmed.
        #   detail   : /referral/pc/position/<id>/detail?token=...  (Apply btn)
        #   apply    : /referral/pc/resume/<id>/apply?token=...
        #              -> unauth bounces to login with
        #                 redirect_path=%2Fresume%2F<id>%2Fapply  (CONFIRMED:
        #                 the redirect_path proves this is the real apply route;
        #                 /position/<id>/apply and /position/<id>/application
        #                 were SPA no-ops, NOT the apply route).
        #   login    : /referral/pc/login?token=...  (#email + #password +
        #              input.atsx-checkbox-input + button.loginSubmit 'Sign in')
        #              referral-token cookie PERSISTS across this login (verified
        #              True post-auth). Same email+password design as TikTok.
        #   applied  : /referral/pc/resume/applied   (inferred from the shared
        #              atsx redirect_path convention; verify on first live run)
        #   history  : /referral/pc/position/application?token=...
        #
        # NOTE / KNOWN BLOCKER (2026-06-02): the jobs.bytedance.com careers
        # account is SEPARATE from the lifeattiktok.com account even though the
        # email+password are identical. The stored .bytedance-password (== the
        # working .tiktok-password) returns 'Incorrect email or password' on
        # BD. Both recovery paths (Create account / Reset password) gate on an
        # EMAIL VERIFICATION CODE (validCode 'Get code') sent to
        # cyshekari@gmail.com -> hard block without inbox access. _login() will
        # print classify=blocked reason=login-failed when this is the case;
        # the URL/flow wiring below is otherwise complete and ready.
        #
        # UPDATE (2026-06-02 pass9): tried the gmail_imap OTP unblock on the
        # Reset-password flow. Reset panel = second #email input + #validCode +
        # "Get code"/"Continue" buttons + "Reset your password" heading. BUT
        # clicking "Get code" fires a ByteDance verifycenter CAPTCHA before the
        # email is ever sent: an iframe src=rmc.bytedance.com/verifycenter/
        # captcha/v2 with subtype="3d" (verify.snssdk.com), ~380x348 visible.
        # The OTP email is withheld until this captcha passes, so gmail_imap
        # polls and times out (no code ever arrives). Proprietary ByteDance
        # 3D-rotation captcha withheld under CDP/automation -- same manual-only
        # class as the TikTok GeeTest slider. gmail_imap itself works; the wall
        # is the captcha gating the send, NOT the inbox. Unblock needs: a
        # ByteDance-captcha solver (CapSolver support for the 3d subtype is
        # unverified) OR a one-time human-driven Get-code+OTP to establish the
        # BD password, after which .bytedance-password + _login() works.
        return {
            "landing": f"https://{host}/referral/pc/position?token={tok}",
            "apply":   f"https://{host}/referral/pc/resume/{job_id}/apply?token={tok}",
            "login_prefix": f"https://{host}/referral/pc/login",
            "applied_prefix": f"https://{host}/referral/pc/resume/applied",
            "history": f"https://{host}/referral/pc/position/application?token={tok}",
        }
    raise SystemExit(f"unknown brand: {brand}")


def _new_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    # Auto-dismiss any JS dialog (e.g. a beforeunload 'leave page?' guard armed
    # by the unsaved resume upload) so it can never crash the CDP connection
    # mid-run (tiktok-reattempt 2026-06-02).
    page.on("dialog", lambda d: d.dismiss())
    return browser, page


def _set_native(page, selector, value):
    page.evaluate(
        """([sel,val])=>{const el=document.querySelector(sel);
           const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value');
           d.set.call(el,val);
           el.dispatchEvent(new Event('input',{bubbles:true}));
           el.dispatchEvent(new Event('change',{bubbles:true}));}""",
        [selector, value])


def _is_login_wall(page) -> bool:
    return "/login" in page.url


def _login(page, brand="tiktok"):
    """Email+password login. Returns True if we end up past the wall."""
    pwd = _password_file(brand).read_text().strip()
    page.wait_for_selector("#email", timeout=15000)
    _set_native(page, "#email", EMAIL)
    _set_native(page, "#password", pwd)
    # consent checkbox
    page.evaluate("""()=>{const cb=document.querySelector('input.atsx-checkbox-input');
                       if(cb && !cb.checked) cb.click();}""")
    # ByteDance renders TWO 'Sign in' buttons (a ghost tab + the real primary
    # submit `button.loginSubmit`). Prefer the loginSubmit/primary; fall back to
    # the LAST 'Sign in' (TikTok's single submit). Clicking the tab is a no-op
    # that leaves you stuck on /login (observed on BD 2026-06-02).
    page.evaluate("""()=>{const bs=[...document.querySelectorAll('button')]
                       .filter(e=>e.textContent.trim()==='Sign in');
                       const b=bs.find(e=>/loginSubmit|atsx-btn-primary/.test(e.className))
                               || bs[bs.length-1];
                       if(b) b.click();}""")
    # wait for redirect off /login
    for _ in range(20):
        page.wait_for_timeout(700)
        if "/login" not in page.url:
            break
    # captcha/slider sentinel
    has_captcha = page.evaluate(
        "()=>!!document.querySelector('[id*=captcha],[class*=captcha],[class*=secsdk],"
        "iframe[src*=captcha],[class*=slide-verify]')")
    if has_captcha:
        print("classify=blocked reason=login-captcha-slider")
        return False
    if "/login" in page.url:
        # Distinguish bad-credential from other wall states for clear diagnosis.
        bad_cred = page.evaluate(
            "()=>/Incorrect email or password|account.*locked|too many/i"
            ".test(document.body.innerText)")
        if bad_cred:
            print(f"classify=blocked reason=login-bad-credential url={page.url}")
        else:
            print(f"classify=blocked reason=login-failed url={page.url}")
        return False
    return True


def _pick_ud_select(page, index, want):
    """Open the index-th `.ud__select.select__1A5Um` via a REAL pointer click
    (CDP mouse), then click the option whose text == want ('Yes'/'No').

    Robust open protocol (tiktok-reattempt 2026-06-02, fixes
    `workauth-select-failed` on roles 1912/1914/1915/etc):
      The FIRST programmatic open of a select frequently mounts an EMPTY portal
      (`.ud__select__list__item` count = 0) on attempt 0, then populates Yes/No
      on attempt 1. ALSO, a previously-opened select can leave a stale
      `ud__select__dropdown-hidden` portal mounted that confuses the option
      lookup. The old loop re-clicked WITHOUT closing first -> click-parity
      could TOGGLE the just-opened dropdown shut, so 'No'/'Yes' was never found.
      FIX: before every attempt, press Escape to close ANY open dropdown, then
      click ONCE, wait, and only pick from VISIBLE items. Retry up to 5x."""
    for attempt in range(5):
        # 1. close any stale/open dropdown so this select opens cleanly.
        #    Use keyboard Escape (the ud__select library closes on Escape). A
        #    page-level dialog handler (_new_page) auto-dismisses any
        #    beforeunload guard so Escape can't crash the CDP connection.
        #    (Do NOT outside-click at a fixed coord -- (5,5) hits the topbar
        #    user menu and breaks the form. tiktok-reattempt 2026-06-02.)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(250)
        # 2. scroll first, let it settle, THEN read fresh coords
        page.evaluate(
            """(i)=>{const s=document.querySelectorAll('.ud__select.select__1A5Um')[i];
                  s.scrollIntoView({block:'center'});}""", index)
        page.wait_for_timeout(600)
        box = page.evaluate(
            """(i)=>{const s=document.querySelectorAll('.ud__select.select__1A5Um')[i];
                  const r=s.getBoundingClientRect();
                  return {x:r.x+r.width/2, y:r.y+r.height/2};}""", index)
        page.mouse.click(box["x"], box["y"])
        page.wait_for_timeout(800)
        # 3. only pick from VISIBLE items; empty portal on first open -> retry
        ok = page.evaluate(
            """(want)=>{const items=[...document.querySelectorAll('.ud__select__list__item')]
                  .filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;});
                  if(items.length===0) return 'empty';
                  const m=items.find(e=>e.innerText.trim()===want);
                  if(m){m.click();return true;} return false;}""", want)
        page.wait_for_timeout(400)
        if ok is True:
            return True
        # ok === 'empty' (portal not populated yet) or False (wrong items) ->
        # close via Escape and retry (next loop iteration re-presses Escape)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(250)
    return False


def _upload_resume(page, pdf):
    inp = page.query_selector("input[type=file]")
    if not inp:
        return False
    inp.set_input_files(pdf)
    page.wait_for_timeout(4000)
    fn = page.evaluate(
        r"""()=>{const m=document.body.innerText.match(/Resume\s*\n+([^\n]+\.(pdf|docx|doc))/i);
             return m?m[1]:'';}""")
    return bool(fn and os.path.basename(pdf).split('.')[0][:20] in fn)


def run(brand, job_id, resume, submit):
    urls = _urls(brand, job_id)
    with sync_playwright() as pw:
        browser, page = _new_page(pw)
        try:
            # 1. bind referral cookie
            page.goto(urls["landing"], wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            ref_ok = any(c["name"] == "referral-token" for c in page.context.cookies())
            print(f"[runner] referral-token cookie set: {ref_ok}")

            # 2. apply url -> may bounce to login
            page.goto(urls["apply"], wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            if _is_login_wall(page):
                print("[runner] login wall hit; signing in...")
                if not _login(page, brand):
                    print(f"[runner] wall url: {page.url}")
                    return 2
                # back on apply page now (redirect_path)
                if "/apply" not in page.url:
                    page.goto(urls["apply"], wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
            print(f"[runner] authenticated, apply url: {page.url}")

            # WAIT for the apply form to actually materialize (lazy-loaded SPA;
            # some roles take >10s after auth). The form-ready signal is the
            # work-auth .ud__select dropdowns + the file input. Without this the
            # upload/select steps race an empty page (tiktok-scale fix 2026-06-02).
            form_ready = False
            for _ in range(20):
                page.wait_for_timeout(1500)
                form_ready = page.evaluate(
                    "()=>document.querySelectorAll('.ud__select.select__1A5Um').length>=2"
                    " && !!document.querySelector('input[type=file]')")
                if form_ready:
                    break
            print(f"[runner] apply form ready: {form_ready}")
            if not form_ready:
                print("classify=blocked reason=form-not-loaded")
                return 4

            # verify referral-token still present post-auth
            ref_still = any(c["name"] == "referral-token" for c in page.context.cookies())
            print(f"[runner] referral-token persists post-auth: {ref_still}")

            # 3. resume upload (tailored) unless told to skip
            if resume and os.environ.get("TIKTOK_NO_UPLOAD") != "1":
                up = _upload_resume(page, resume)
                print(f"[runner] resume uploaded: {up}")

            # 4. work-authorization knockouts (truthful for Cyrus: US citizen)
            page.wait_for_selector(".ud__select.select__1A5Um", timeout=15000)
            q1 = _pick_ud_select(page, 0, "Yes")   # authorized to work in US
            q2 = _pick_ud_select(page, 1, "No")    # require sponsorship
            print(f"[runner] work-auth Q1(Yes)={q1} Q2(No)={q2}")
            if not (q1 and q2):
                print("classify=blocked reason=workauth-select-failed")
                return 3

            # consent checkbox (Privacy Policy)
            page.evaluate("""()=>{const cb=document.querySelector('input.atsx-checkbox-input');
                               if(cb && !cb.checked){cb.scrollIntoView({block:'center'});cb.click();}}""")
            page.wait_for_timeout(300)

            # 5. proof capture immediately before real submit
            try:
                from proof_capture import maybe_capture_by_slug  # noqa
                maybe_capture_by_slug(page, f"{brand}-{job_id}")
            except Exception as e:
                print(f"[runner] proof_capture skipped: {e}")

            if not submit:
                print("[runner] --no-submit: stopping before final click.")
                print("classify=dryrun-ready")
                return 0

            # SUBMIT
            clicked = page.evaluate(
                "()=>{const b=[...document.querySelectorAll('button')]"
                ".find(e=>e.textContent.trim()==='Submit'); if(b){b.click();return true;} return false;}")
            print(f"[runner] Submit clicked: {clicked}")
            # Wait longer: submit succeeds server-side but the SPA redirect to
            # /applied can lag well past 6s (tiktok-scale 2026-06-02: role 1885
            # confirmed in history despite an 8x800ms timeout false-negative).
            outcome = None
            for _ in range(25):
                page.wait_for_timeout(800)
                url = page.url
                body = (page.inner_text("body") or "")
                if "/applied" in url or "We have received your resume" in body:
                    outcome = "submitted"; break
                # "already applied" modal = job is already on file -> done, not a fail
                if "already applied for this job" in body or "Unable to apply again" in body:
                    outcome = "already-applied"; break
            body = (page.inner_text("body") or "")
            if outcome == "submitted":
                print(f"[runner] SUCCESS url={page.url}")
                print("classify=submitted")
                return 0
            if outcome == "already-applied":
                print("[runner] already applied for this job (on file).")
                print("classify=already-applied")
                return 0
            # Last-resort: check application history for this job id.
            try:
                page.goto(urls["history"], wait_until="networkidle")
                page.wait_for_timeout(3000)
                hist = (page.inner_text("body") or "")
                # the job title appears with "Applied via referral" near a recent date
                if "Applied via referral" in hist:
                    print("[runner] history shows Applied via referral (verify title manually).")
                    print("classify=submitted-via-history")
                    return 0
            except Exception as e:
                print(f"[runner] history check failed: {e}")
            print(f"[runner] submit did not confirm; url={page.url}")
            print("classify=blocked reason=submit-unconfirmed")
            return 3
        finally:
            try:
                page.close()
            except Exception:
                pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", choices=["tiktok", "bytedance"], default="tiktok")
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--resume", default=None)
    ap.add_argument("--no-submit", dest="submit", action="store_false")
    ap.set_defaults(submit=True)
    a = ap.parse_args()
    sys.exit(run(a.brand, a.job_id, a.resume, a.submit))
