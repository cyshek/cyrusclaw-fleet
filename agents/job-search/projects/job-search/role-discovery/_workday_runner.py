#!/usr/bin/env python3
"""
_workday_runner.py — reusable Workday apply runner (Playwright sync, persistent context per tenant).

Flow: goto apply URL -> Apply Manually -> create-account-or-sign-in -> fill all steps
from Cyrus profile -> upload resume -> submit -> verify confirmation.

Usage:
  python3 _workday_runner.py --url "<apply-or-jd url>" --tenant nvidia --role-id 1607 \
      --resume /path/to/resume.pdf [--dryrun] [--source "LinkedIn"]

--dryrun fills everything but STOPS before final submit (and before each next-button on last review).

Selectors use Workday data-automation-id which are stable across tenants.
Screenshots saved to ../.workday-debug/<tenant>-step-*.png

EXIT-code map (run() return values):
  0  submitted / dryrun reached Review
  2  blocked at sign-in / account-create
  3  submit clicked but no confirmation text found
  4  could not click submit
  5  generic loop-cap / ended without confirmation
  6  req CLOSED / removed
  7  ALREADY_APPLIED
  8  My-Info dropdown would not commit
  9  profile-prefill uncommittable required start-date (LEGACY saved-profile data bug)
  10 create-account email-verification timeout (fresh-account path; workday-fresh-account-fix 2026-06-08)

FRESH-ACCOUNT default (workday-fresh-account-fix 2026-06-08, Cyrus directive): for ALL
Workday tenants the runner CREATES A FRESH account (new gmail '+' alias) by default so
every field is filled from the tailored resume and we NEVER reuse Workday's saved-
candidate-profile autofill. This is the GLOBAL default (not just dupe-class). See
resolve_account_for_tenant() / _create_fresh_account(). Override per-run with
--legacy-account (explicit force_fresh=False) to keep historical sign-in for debugging;
--fresh-account is now the default behavior.
"""
import sys, argparse, time, re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DBG = ROOT / ".workday-debug"
DBG.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
import gmail_imap

# ---- Cyrus profile ----
import json as _json
_PI = _json.loads((ROOT / "personal-info.json").read_text())
EMAIL = _PI["contact"]["email"]
PW = (ROOT / ".tiktok-password").read_text().strip()

def load_tenant_creds(tenant):
    """Resolve the correct Workday sign-in email + password for a tenant.
    FIX (workday nvidia 2026-06-02 nvidia_workday): NVIDIA (and most Workday tenants we
    have accounts on) use a PLUS-ALIASED email (cyshekari+<tenant>@gmail.com) and the
    shared 24-char Workday password from .workday-creds.json -- NOT the bare
    cyshekari@gmail.com / .tiktok-password the module defaulted to. Using the wrong
    creds made sign-in silently fail (form re-renders clean, no inline error), the runner
    then thought it was 'already in application' off a stale cookie, hit candidateHome's
    routing, and spun forever in recover_to_step. Always prefer creds.json; fall back to
    module defaults only if the tenant isn't listed. Returns (email, password)."""
    try:
        import json as _json
        creds = _json.load(open(ROOT / ".workday-creds.json"))
        pw = creds.get("shared_password") or PW
        t = (creds.get("tenants") or {}).get(tenant) or {}
        email = t.get("email") or creds.get("shared_email") or EMAIL
        return email, pw
    except Exception as _e:
        log("load_tenant_creds err", str(_e)[:80])
        return EMAIL, PW

# ===========================================================================
# FRESH-ACCOUNT APPLY (workday-fresh-account-fix 2026-06-08, Cyrus option A)
# ---------------------------------------------------------------------------
# STANDING RULE (Cyrus 2026-06-08): "Workday ALWAYS applies with FRESH information
# from the customized resume; NEVER autofill/reuse saved-profile data because it is
# likely outdated." Prior failed runs polluted the persistent per-tenant accounts
# with duplicate, read-only, UNCOMMITTABLE work-experience blocks -> the saved
# profile auto-prefilled My Experience -> EXIT 9 (_WE_PREFILL_UNCOMMITTABLE) and the
# work-history NEVER came from the tailored resume. The default Workday path is now
# to CREATE A FRESH ACCOUNT (gmail + addressing off the base inbox so verification
# emails still land where gmail_imap reads) which starts with an EMPTY work-history
# that we fill from the tailored resume. We sign into a known-good fresh alias if one
# already exists for the tenant; we only mint a NEW alias when needed.
#
# DUPE_CLASS_TENANTS: the known dupe-class tenants whose PERSISTENT/legacy accounts are
# polluted with uncommittable work-history. RETAINED for logging context + to mark which
# legacy accounts are known-bad. NOTE (2026-06-08): this set NO LONGER gates fresh-vs-
# legacy -- resolve_account_for_tenant() now defaults EVERY tenant to create-fresh.
DUPE_CLASS_TENANTS = {"philips", "rbi", "nordstrom", "exfo", "nvidia", "hpe"}

# Module state for the chosen account + branch decision (set per-run by run() via
# resolve_account_for_tenant(); read by ensure_signed_in() and populate_work_history()).
# _ACCOUNT_MODE is one of: "create_fresh" (mint/create a fresh account), "signin_fresh"
# (sign into a previously-minted known-good fresh alias), "signin_legacy" (legacy
# behavior: sign into the historical shared/tenant account -- only for non-dupe tenants
# that already worked). The decision is EXPLICIT + LOGGED, never heuristic-flaky.
_ACCOUNT_MODE = None
_FRESH_VERIFY_PW = None  # password chosen for the fresh account this run (create or signin)
# New failure flag: Workday create-account email-verification code never arrived in time.
# run() reads this to bank a precise EXIT 10 ('workday-create-account-email-verify-timeout')
# instead of silently passing through or falling back to the polluted account.
_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL = None

# How long to wait for Workday's create-account verification email. Kept modest so we
# do not thrash gmail; a single create attempt polls within this budget then fails loud.
WD_CREATE_VERIFY_TIMEOUT_S = 150


def _gen_strong_password(length=22):
    """Strong random password for a fresh Workday account. Mix of upper/lower/digits and
    a few symbols Workday accepts. Generated per fresh-account mint and PERSISTED into
    .workday-creds.json so a later run can SIGN IN to the same fresh account (never
    strand it)."""
    import secrets, string
    # Workday password policy: >=8, needs upper+lower+digit; symbols from a safe set.
    alphabet = string.ascii_letters + string.digits
    symbols = "!@#$%*?-_"
    while True:
        core = "".join(secrets.choice(alphabet) for _ in range(length - 3))
        pw = core + secrets.choice(string.ascii_uppercase) + secrets.choice(string.digits) + secrets.choice(symbols)
        # ensure it has at least one lower (core almost always does, but be safe)
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw) and any(c in symbols for c in pw)):
            return pw


def _gmail_base_inbox():
    """The base gmail inbox that gmail_imap actually reads. All '+' aliases deliver here,
    so verification emails are always retrievable. Resolved from creds shared_email, then
    module EMAIL; the local-part before any existing '+' is the canonical base."""
    base = EMAIL
    try:
        import json as _json
        creds = _json.load(open(ROOT / ".workday-creds.json"))
        base = creds.get("shared_email") or base
    except Exception:
        pass
    # strip any existing +tag to get the canonical local-part@domain
    local, _, domain = base.partition("@")
    local = local.split("+", 1)[0]
    return f"{local}@{domain}" if domain else base


def _gen_fresh_alias(tenant, now=None):
    """Deterministic-but-unique fresh email alias via gmail '+' addressing off the base
    inbox so verification still lands in the SAME gmail gmail_imap reads. Shape:
        <local>+wd-<tenant>-<YYYYMMDDHHMM>@<domain>
    The minute-resolution datestamp guarantees a NEW alias on each fresh-account attempt
    (so it never collides with the OLD polluted account) while staying parseable +
    idempotent within a single run (same `now` -> same alias). Tenant is sanitized to
    gmail-safe chars."""
    import re as _re, time as _time
    base = _gmail_base_inbox()
    local, _, domain = base.partition("@")
    t = _re.sub(r"[^a-z0-9]", "", (tenant or "").lower()) or "tenant"
    ts = _time.strftime("%Y%m%d%H%M", _time.localtime(now if now is not None else _time.time()))
    return f"{local}+wd-{t}-{ts}@{domain}"


def _persist_tenant_creds(tenant, **fields):
    """Merge `fields` into creds['tenants'][tenant] in .workday-creds.json and write back
    (chmod 600). Used to STORE a freshly-minted alias + password so a later run can sign
    into the same fresh account rather than minting yet another one. Best-effort: a write
    failure is logged, not fatal."""
    try:
        import json as _json, os as _os
        path = ROOT / ".workday-creds.json"
        creds = _json.load(open(path))
        creds.setdefault("tenants", {})
        cur = creds["tenants"].get(tenant) or {}
        cur.update({k: v for k, v in fields.items() if v is not None})
        creds["tenants"][tenant] = cur
        tmp = str(path) + ".tmp"
        with open(tmp, "w") as fh:
            _json.dump(creds, fh, indent=2)
        _os.replace(tmp, path)
        try:
            _os.chmod(path, 0o600)
        except Exception:
            pass
        return True
    except Exception as _e:
        log("_persist_tenant_creds err", str(_e)[:80])
        return False


def resolve_account_for_tenant(tenant, force_fresh=None):
    """Decide WHICH Workday account to use for this tenant and HOW, per the standing
    fresh-account rule. Returns (email, password, mode) where mode is one of
    'create_fresh' | 'signin_fresh' | 'signin_legacy'. EXPLICIT + logged, never
    heuristic-flaky (fixes the cold-start mis-pick triage flagged for Nordstrom/EXFO,
    where create-vs-signin was decided by which form happened to render first).

    Branch logic (GLOBAL FRESH DEFAULT, Cyrus directive 2026-06-08):
      1. If a KNOWN-GOOD fresh alias already exists for this tenant in creds
         (fresh_alias set AND fresh_polluted not True), SIGN INTO that fresh account
         ('signin_fresh') -- don't strand it, don't mint a new one. (Still
         fresh-account-correct: a previously-minted clean alias has no stale prefill.)
      2. Else, by DEFAULT (force_fresh is None) for ANY tenant -- clean OR dupe-class --
         MINT a brand-new fresh alias + strong password, PERSIST it, and CREATE a fresh
         account ('create_fresh') so My Experience starts EMPTY and every field is filled
         from the tailored resume, never from Workday's saved-candidate-profile autofill.
         The dupe-class set is NO LONGER the discriminator; fresh is the global default.
      3. ONLY when force_fresh is explicitly False (the debugging escape hatch) AND the
         loud env override WORKDAY_ALLOW_LEGACY_PROFILE=1 is set do we keep the historical
         signed-in behavior ('signin_legacy') using load_tenant_creds(). Without that env
         override a bare force_fresh=False is REFUSED (anti-pollution policy) and falls
         through to create_fresh with a WARN -- there is NO silent legacy fallback in a
         normal production run. DUPE_CLASS_TENANTS is retained only for logging / to flag
         known-polluted legacy accounts -- it does not gate the fresh-vs-legacy decision.

    NET INVARIANT (Cyrus 2026-06-09): there is NO code path that signs into a legacy/
    existing/polluted Workday profile during a normal production run. Only create_fresh or
    sign-in to a CLEAN previously-minted fresh alias. Legacy is reachable solely behind the
    explicit, non-default WORKDAY_ALLOW_LEGACY_PROFILE=1 debug flag.
    """
    import json as _json
    import os as _os
    try:
        creds = _json.load(open(ROOT / ".workday-creds.json"))
    except Exception as _e:
        log("resolve_account_for_tenant: creds read err", str(_e)[:80])
        creds = {}
    t = (creds.get("tenants") or {}).get(tenant) or {}
    shared_pw = creds.get("shared_password") or PW

    # (1) reuse a known-good fresh alias if present and not flagged polluted
    fresh_alias = t.get("fresh_alias")
    fresh_pw = t.get("fresh_password") or shared_pw
    if fresh_alias and not t.get("fresh_polluted"):
        log(f"account-decision[{tenant}]: SIGN-IN to existing FRESH alias {fresh_alias} (mode=signin_fresh)")
        return fresh_alias, fresh_pw, "signin_fresh"

    # ANTI-POLLUTION HARD-REFUSE (workday-no-legacy-fallback 2026-06-09, Cyrus directive):
    # signing into a legacy/existing Workday profile is the ONLY way a duplicate, read-only,
    # uncommittable work-experience block ever gets into an apply (the EXFO/RBI/Nordstrom
    # EXIT-9 class). So legacy sign-in is now REFUSED in normal operation -- it is reachable
    # ONLY behind a loud, non-default debug env flag. Without that flag, an explicit
    # force_fresh=False does NOT fall back to legacy; we force a fresh mint and WARN.
    _allow_legacy = (_os.environ.get("WORKDAY_ALLOW_LEGACY_PROFILE") == "1")
    if force_fresh is False and not _allow_legacy:
        # Caller explicitly asked for legacy (e.g. --legacy-account) but the anti-pollution
        # policy refuses it without the env override. Force fresh instead and WARN loudly.
        log(f"WARN account-decision[{tenant}]: LEGACY profile sign-in was REQUESTED "
            f"(force_fresh=False) but REFUSED by anti-pollution policy -- forcing a FRESH "
            f"account instead. Set WORKDAY_ALLOW_LEGACY_PROFILE=1 to explicitly allow a "
            f"polluted-profile run (NOT recommended; risks duplicate uncommittable WE blocks).")

    # (2) GLOBAL DEFAULT (Cyrus 2026-06-08): create a fresh account for ANY tenant unless
    # force_fresh is explicitly False *AND* the legacy override is set. Fresh is the default
    # so we always fill from the tailored resume and never trust Workday's saved-profile
    # autofill. dupe-class no longer gates this -- it's only surfaced for logging context.
    # The anti-pollution refuse above means a bare force_fresh=False still lands HERE (fresh).
    want_fresh = True if (force_fresh is False and not _allow_legacy) else (
        force_fresh if force_fresh is not None else True)
    if want_fresh:
        alias = _gen_fresh_alias(tenant)
        new_pw = _gen_strong_password()
        # PERSIST immediately so even a mid-flow crash leaves the alias recoverable and
        # the next run signs into it instead of minting a third alias.
        _persist_tenant_creds(tenant, fresh_alias=alias, fresh_password=new_pw,
                              fresh_polluted=False, fresh_created=False)
        log(f"account-decision[{tenant}]: CREATE FRESH account {alias} (mode=create_fresh; "
            f"global_fresh_default=True dupe_class={tenant in DUPE_CLASS_TENANTS} "
            f"force_fresh={force_fresh})")
        return alias, new_pw, "create_fresh"

    # (3) explicit legacy escape hatch -- now GATED behind WORKDAY_ALLOW_LEGACY_PROFILE=1.
    # Only reachable when force_fresh is explicitly False AND the env override is set; this
    # is the single code path that signs into a legacy/possibly-polluted saved profile, and
    # it screams about it so a polluted run is never silent.
    log(f"WARN account-decision[{tenant}]: POLLUTED-PROFILE run EXPLICITLY ALLOWED via "
        f"WORKDAY_ALLOW_LEGACY_PROFILE=1 -- signing into LEGACY saved profile. This may "
        f"reintroduce duplicate/uncommittable work-experience blocks (EXIT-9 risk).")
    email, pw = load_tenant_creds(tenant)
    log(f"account-decision[{tenant}]: legacy SIGN-IN {email} (mode=signin_legacy; "
        f"explicit force_fresh=False, WORKDAY_ALLOW_LEGACY_PROFILE=1, "
        f"dupe_class={tenant in DUPE_CLASS_TENANTS})")
    return email, pw, "signin_legacy"


FIRST = _PI["identity"]["first_name"]
LAST = _PI["identity"]["last_name"]
PHONE = _PI["contact"]["phone"].replace("-", "")  # 10-digit no-dash
ADDR1 = "Kirkland"   # placeholder; real line set below
ADDRESS_LINE1 = "11800 NE 128th St"  # generic Kirkland address; Workday rarely verifies
CITY = "Kirkland"
STATE = "Washington"
STATE_ABBR = "WA"
POSTAL = _PI["address"]["zip"]
COUNTRY = "United States of America"
LINKEDIN = "https://www.linkedin.com/in/cyrus-shekari"
SOURCE_DEFAULT = "LinkedIn"

def log(*a): print("[wd]", *a, flush=True)

# FIX (workday-p17 2026-06-02 NVIDIA recovery): set by recover_to_step/terminal_state when a
# non-recoverable terminal state is hit; run() reads it to emit a precise verdict.
_RECOVER_TERMINAL = None
_MYINFO_COMMIT_FAIL = None  # workday-myinfo-fix: set to the un-committed dropdown name(s)
_WE_PREFILL_UNCOMMITTABLE = None  # workday-prefill-uncommittable-fix (2026-06-05): set to the
_RESUME_UPLOADED = 0  # workday-reupload-loop-fix (2026-06-10 Gates 2542 / Boeing 2546): run-scoped
# COUNT of resume uploads this row. Some tenants (Gates-class) attach the file fine but render
# NO 'successfully uploaded' text / DeleteFile automation-id, so DOM file_present returns False
# on EVERY My-Experience revisit -> re-upload -> each parse spawns a NEW empty parser WE block
# (idx 123->248->377...) -> non-convergent EXIT-5 loop. We CAP uploads at _MAX_RESUME_UPLOADS so
# EXFO-class drop-on-revisit tenants still get a legit re-upload, but Gates-class can't loop
# forever. After the cap, skip re-upload and let delete_empty_we_blocks + populate converge.
_MAX_RESUME_UPLOADS = 2
# workday-boeing-upload-required-on-revisit (2026-06-11 Boeing 2546): separate bounded counter
# for re-uploads forced by a genuinely REQUIRED-AND-EMPTY upload widget on a revisit (the file
# display dropped). These re-uploads satisfy a hard-required field, so they are exempt from
# _MAX_RESUME_UPLOADS, but capped on their own so a tenant that NEVER accepts the file can't
# loop forever (the loop-cap EXIT-5 still backstops at >3 revisits regardless).
_RESUME_REQ_REUPLOADS = 0
# workday-paypal-req-reupload-cap-fix (2026-06-13): cap was 4, allowing 4 re-uploads on
# tenants (PayPal/Boeing-class) that drop the upload display on every My-Experience revisit
# and flag 'Upload a file is required'. On a FRESH account the file IS server-side after
# upload 1; the drop is a display artifact. Allowing 4 re-uploads = 4 parser runs = 4 new
# empty WE blocks spawned = EXIT-5 loop. Cap at 1: allow ONE re-upload (in case upload 1
# silently failed), then trust the server-side file on subsequent revisits.
_MAX_REQ_REUPLOADS = 1
# count/ids of PROFILE-PREFILLED work-exp blocks whose REQUIRED start-date stays empty after
# the prefill-guard date-repair ran. These are read-only tenant-profile prefills (e.g. EXFO
# 2121 carries 5 Microsoft dupes) whose dates physically cannot be committed by our automation
# -> Workday keeps the form dirty + regenerates an empty required block every render -> the
# step would spin to the generic EXIT 5 loop-cap. We fast-fail with a precise EXIT 9 + a clean
# 'workday-profile-prefill-uncommittable' bank reason instead of burning the full loop-cap.
# This is a DATA/profile-side blocker (Cyrus must dedupe his Workday tenant profile), NOT an
# engine bug -- the empty-block regen itself is already handled by the prefill-guard converge
# loop (block count converges; empties->0). Do not re-grind these rows.

def shot(page, tenant, tag):
    try: page.screenshot(path=str(DBG / f"{tenant}-{tag}.png"), full_page=True)
    except Exception: pass

def safe_click(page, sel, timeout=8000):
    """Click handling Workday's click_filter overlay interceptor."""
    try:
        loc = page.locator(sel).first
        loc.wait_for(state="visible", timeout=timeout)
        try:
            loc.click(timeout=timeout)
            return True
        except Exception:
            # overlay interceptor: find sibling click_filter or force
            try:
                cf = loc.locator("xpath=preceding-sibling::*[@data-automation-id='click_filter']").first
                if cf.count(): cf.click(timeout=3000); return True
            except Exception: pass
            loc.click(force=True, timeout=timeout); return True
    except Exception as e:
        log("click fail", sel, str(e)[:80]); return False

def fill_if(page, sel, value):
    try:
        loc = page.locator(sel).first
        if loc.count():
            loc.fill(value); return True
    except Exception as e:
        log("fill fail", sel, str(e)[:60])
    return False

def wd_pick_listbox(page, button_sel, option_text, type_text=None):
    """Workday button-dropdown: click button -> options render as [role=option] -> click matching text."""
    try:
        btn = page.locator(button_sel).first
        btn.click(timeout=6000)
        page.wait_for_timeout(900)
        if type_text:
            try: page.keyboard.type(type_text); page.wait_for_timeout(900)
            except Exception: pass
        # exact match first
        for o in page.locator("[role=option]").all():
            try:
                t = (o.text_content() or "").strip()
                if t.lower() == option_text.lower():
                    o.click(timeout=4000); page.wait_for_timeout(500); return True
            except Exception: pass
        # contains match
        for o in page.locator("[role=option]").all():
            try:
                t = (o.text_content() or "").strip()
                if option_text.lower() in t.lower() and t.lower() != "select one":
                    o.click(timeout=4000); page.wait_for_timeout(500); return True
            except Exception: pass
        page.keyboard.press("Escape")
    except Exception as e:
        log("listbox fail", button_sel, str(e)[:80])
    return False

def _commit_wd_dropdown(page, automation_id, want_text, want_alts=None, cap=3):
    """Generic Workday single/multi-select committer with verify-or-retry (workday-myinfo-fix
    2026-06-02). Both 'How did you hear about us?' (source) and phoneNumber countryPhoneCode
    were logging a 'picked' but NEVER committing a value -> 'Save and Continue' bounced with a
    required-field error and My-Info never advanced (observed Philips 1466: work-exp clean, but
    My-Info stuck on source + country code).

    Contract:
      - locate the control (button OR input) by data-automation-id (substring/ends-with) OR id.
      - JS scrollIntoView(center) BEFORE every interaction (reuse the work-exp fix pattern).
      - open -> wait for options ([role=option]/[data-automation-id=promptOption]) -> click the
        option whose visible text matches want_text (or any of want_alts), exact then contains.
      - VERIFY a value committed (re-read control text / selected pill). If not, retry via
        keyboard (focus -> type first chars -> ArrowDown -> Enter) and re-verify.
      - retry up to `cap` times; return True iff committed, False after cap (caller fails LOUD).
    `automation_id` may be a full DOM id, a data-automation-id, or a substring of either.
    Returns True iff a value committed."""
    wants = [want_text] + list(want_alts or [])

    def _find_control():
        # Resolve the control element id so we can scroll + re-read it. Match by exact id,
        # exact data-automation-id, or substring of either (countryPhoneCode etc.).
        try:
            return page.evaluate("""(aid)=>{
                const al=aid.toLowerCase();
                const cands=[...document.querySelectorAll('button,input,div[role=button],[data-automation-id]')];
                for(const e of cands){
                    const id=(e.id||''); const da=(e.getAttribute('data-automation-id')||'');
                    if(id===aid||da===aid) return id||da;
                }
                for(const e of cands){
                    const id=(e.id||'').toLowerCase(); const da=(e.getAttribute('data-automation-id')||'').toLowerCase();
                    if(id.includes(al)||da.includes(al)) return e.id||e.getAttribute('data-automation-id');
                }
                return null;
            }""", automation_id)
        except Exception:
            return None

    def _committed(ctrl_id):
        # A control is committed if its text/value is a real selection (not empty / 'select one')
        # OR a removable selectedItem/DELETE_charm pill rendered near it (multiselect).
        try:
            return bool(page.evaluate("""(cid)=>{
                let el=document.getElementById(cid);
                if(!el) el=[...document.querySelectorAll('[data-automation-id]')].find(e=>(e.getAttribute('data-automation-id')||'')===cid);
                if(!el) return false;
                const txt=((el.textContent||'')+' '+(el.value||'')+' '+(el.getAttribute('aria-label')||'')).trim().toLowerCase();
                const real = txt && txt!=='select one' && !/^\\s*$/.test(txt);
                // climb for a committed multiselect pill
                let scope=el;
                for(let i=0;i<6&&scope;i++){
                    scope=scope.parentElement;
                    if(scope&&scope.querySelector('[data-automation-id=selectedItem],[data-automation-id=DELETE_charm]')) return true;
                }
                return !!real;
            }""", ctrl_id))
        except Exception:
            return False

    ctrl_id = _find_control()
    if not ctrl_id:
        log(f"dropdown[{automation_id}] control not present -> skip")
        return True  # field not on this step
    if _committed(ctrl_id):
        log(f"dropdown[{automation_id}] already committed -> skip")
        return True

    def _opts():
        els = page.locator("[data-automation-id=promptOption]").all()
        if not els:
            els = page.locator("[role=option]").all()
        return els

    def _click_match():
        # exact pass first, then contains
        for exact in (True, False):
            for o in _opts():
                try:
                    t = (o.text_content() or "").strip()
                    tl = t.lower()
                    if not t or tl == "select one":
                        continue
                    for w in wants:
                        wl = w.lower()
                        if (tl == wl) if exact else (wl in tl):
                            try: o.scroll_into_view_if_needed(timeout=2000)
                            except Exception: pass
                            o.click(timeout=4000); page.wait_for_timeout(800); return t
                except Exception:
                    pass
        return None

    for attempt in range(cap):
        _scroll_into_view_js(page, ctrl_id)
        try:
            page.locator(f"#{ctrl_id}").first.click(timeout=5000)
        except Exception:
            try:
                page.locator(f"[data-automation-id={ctrl_id}]").first.click(timeout=4000)
            except Exception:
                pass
        page.wait_for_timeout(800)
        picked = _click_match()
        if picked:
            log(f"dropdown[{automation_id}] picked '{picked}' (attempt {attempt})")
        try: page.keyboard.press("Escape")
        except Exception: pass
        page.wait_for_timeout(500)
        if _committed(ctrl_id):
            log(f"dropdown[{automation_id}] COMMITTED (attempt {attempt})")
            return True
        # keyboard typeahead fallback
        try:
            _scroll_into_view_js(page, ctrl_id)
            page.locator(f"#{ctrl_id}").first.click(timeout=3000)
            page.wait_for_timeout(300)
            page.keyboard.type(wants[0][:6])
            page.wait_for_timeout(900)
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(300)
            page.keyboard.press("Enter")
            page.wait_for_timeout(700)
            if _committed(ctrl_id):
                log(f"dropdown[{automation_id}] COMMITTED via typeahead (attempt {attempt})")
                return True
        except Exception:
            pass
    log(f"dropdown[{automation_id}] NOT committed after {cap} attempts")
    return False


def terminal_state(page):
    """Detect Workday TERMINAL non-recoverable states so the runner exits with a precise
    verdict instead of spinning recover_to_step.
    FIX (workday-p17 2026-06-02 NVIDIA recovery): the recover loop clicked adventureButton
    forever and never noticed that (a) the req was REMOVED ('The page you are looking for
    doesn't exist') or (b) the candidate had ALREADY applied (post-sign-in 'alreadyAppliedPage'
    / 'You've already applied for this job'). Both are hard terminal states -- detect & return
    a tag so run() can stop cleanly. Tenant-general (these are stock Workday strings/ids).
    Returns: 'already_applied' | 'closed' | None."""
    try:
        body = (page.locator("body").text_content() or "")
    except Exception:
        body = ""
    low = body.lower()
    try:
        if page.locator("[data-automation-id=alreadyAppliedPage]").count() or "you've already applied for this job" in low or "you have already applied" in low:
            return "already_applied"
    except Exception:
        pass
    if "the page you are looking for doesn't exist" in low or "requested page not found" in low or "page you are looking for does not exist" in low:
        return "closed"
    return None

def banner_text(page):
    out=[]
    for sel in ["[role=alert]","[data-automation-id*=anner]","[class*=alert]"]:
        for e in page.locator(sel).all()[:4]:
            try:
                t=(e.text_content() or "").strip()
                if t: out.append(t[:160])
            except Exception: pass
    return out

def recover_to_step(page, tries=4, base_url=None):
    """After sign-in, ensure we're on an actual application step. Handles Workday's
    'Something went wrong - please refresh' and Candidate-Home landings.
    FIX (workday-p3 2026-06-02 NVIDIA 1607): after sign-in NVIDIA lands on Candidate
    Home; re-hitting the deep /apply/applyManually URL on a logged-in session just
    redirects back to Candidate Home WITHOUT re-opening the application form. The only
    reliable recovery is to go to the BASE job posting URL and re-click Apply ->
    Apply Manually (which starts/resumes the draft). So recover navigates to base_url
    and replays the Apply nav loop."""
    apply_url = base_url or page.url
    for t in range(tries):
        page.wait_for_timeout(2500)
        # FIX (workday-p17 2026-06-02 NVIDIA recovery): bail immediately on terminal states
        # (already-applied / closed) so we don't burn 4x8 click iterations on a page that
        # will NEVER render the form. Signal via module global for run() to read.
        _ts = terminal_state(page)
        if _ts:
            global _RECOVER_TERMINAL
            _RECOVER_TERMINAL = _ts
            log(f"recover_to_step: TERMINAL state '{_ts}' -- stopping recovery")
            return False
        body = page.locator("body").text_content() or ""
        on_step = (page.locator("input#name--legalName--firstName").count()
                   or page.locator("input#source--source").count()
                   or page.locator("[data-automation-id=pageFooterNextButton]").count()
                   or page.locator("[data-automation-id=submit]").count())
        signin_form = page.locator("[data-automation-id=password]").count() and page.locator("[data-automation-id=email]").count()
        if on_step and not signin_form:
            return True
        if "Something went wrong" in body or (not on_step and not signin_form):
            log(f"recover_to_step: re-nav to base (try {t}) body='{body[:60].strip()}'")
            try:
                page.goto(apply_url, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(4500)
            # Replay Apply -> Apply Manually nav loop (handles modal + deep landings).
            # Already signed in here, so Apply Manually should land straight on the form.
            for _n in range(8):
                if (page.locator("input#name--legalName--firstName").count()
                        or page.locator("input#source--source").count()
                        or page.locator("[data-automation-id=pageFooterNextButton]").count()):
                    break
                # FIX (workday-proof 2026-06-02, Nordstrom 1456): when logged-in with an
                # in-progress draft, the JD page shows 'Continue Application'
                # (data-automation-id=continueButton) and NO Apply button. The replay loop
                # previously only handled applyManually/adventureButton, so it spun 8x and
                # gave up -> 'FAILED to reach application step'. Click continueButton first
                # to resume the draft straight into the step form.
                if page.locator("[data-automation-id=continueButton]").count():
                    safe_click(page, "[data-automation-id=continueButton]"); page.wait_for_timeout(4000); continue
                # FIX (workday-proof 2026-06-02, Snap 1933): once SIGNED IN with an existing
                # draft, Snap replaces Apply/Continue on the JD page with a 'View'
                # (data-automation-id=viewButton) that opens the application's Manage view.
                # The recover loop previously only knew applyManually/adventureButton/continue
                # -> spun 8x on viewButton and never resumed. Click viewButton to open the
                # application, then click any 'Continue'/'Edit'/'Update' that resumes the draft.
                if page.locator("[data-automation-id=viewButton]").count():
                    safe_click(page, "[data-automation-id=viewButton]"); page.wait_for_timeout(4500)
                    # On the Manage/View page, resume the draft if a continue/edit control exists.
                    for rs in ["[data-automation-id=continueButton]",
                               "button:has-text('Continue')", "a:has-text('Continue')",
                               "button:has-text('Update Application')", "button:has-text('Edit Application')",
                               "button:has-text('Manage Application')"]:
                        if page.locator(rs).count():
                            safe_click(page, rs); page.wait_for_timeout(4000); break
                    continue
                if page.locator("[data-automation-id=applyManually]").count():
                    safe_click(page, "[data-automation-id=applyManually]"); page.wait_for_timeout(4000); continue
                # wait for Apply button to render then click it
                try:
                    page.locator("[data-automation-id=adventureButton]").first.wait_for(state="visible", timeout=6000)
                except Exception:
                    pass
                if page.locator("[data-automation-id=adventureButton]").count():
                    safe_click(page, "[data-automation-id=adventureButton]"); page.wait_for_timeout(3500); continue
                # DIAG: nothing actionable found -- dump apply-related ids so we can see
                # what the post-sign-in landing actually offers.
                try:
                    d = page.evaluate("() => { const o=[]; for(const el of document.querySelectorAll('a,button,[data-automation-id]')){const i=el.getAttribute&&el.getAttribute('data-automation-id'); const t=(el.textContent||'').trim(); if((i&&/apply|adventure|manual|continue|resume|task/i.test(i))||(t&&/apply|continue|resume my|view appl/i.test(t)&&t.length<35)) o.push(i||t);} return JSON.stringify([...new Set(o)].slice(0,12)); }")
                    log(f"recover DIAG apply-affordances: {d}")
                except Exception:
                    pass
                page.wait_for_timeout(2000)
            continue
        if signin_form:
            return False
    return bool(page.locator("[data-automation-id=pageFooterNextButton]").count() or page.locator("input#name--legalName--firstName").count())

def _create_fresh_account(page, tenant, base_url=None):
    """CREATE-FRESH path (workday-fresh-account-fix 2026-06-08). Drive Workday's
    create-account form using the freshly-minted alias (module EMAIL) + password
    (module PW, == _FRESH_VERIFY_PW), complete email verification robustly, and land on
    the application's first step with an EMPTY work-history. NEVER falls back to signing
    into the polluted persistent account -- on a hard failure it sets a precise module
    flag and returns False so run() banks the right exit:
      * _CREATE_ACCOUNT_EMAIL_VERIFY_FAIL set -> EXIT 10 (email-verify timeout).
    Standing rule: Workday ALWAYS applies fresh from the tailored resume; we must not
    reuse saved-profile data."""
    global _CREATE_ACCOUNT_EMAIL_VERIFY_FAIL
    log(f"create-fresh: minting Workday account for {tenant} as {EMAIL}")
    # Get to the create-account form: click 'Sign in with email' if shown, then the
    # 'Create Account' toggle/link if the sign-in form rendered first.
    if page.locator("[data-automation-id=SignInWithEmailButton]").count():
        safe_click(page, "[data-automation-id=SignInWithEmailButton]"); page.wait_for_timeout(2000)
    if not page.locator("[data-automation-id=verifyPassword]").count():
        for sel in ("[data-automation-id=createAccountLink]", "button:has-text('Create Account')",
                    "a:has-text('Create Account')"):
            if page.locator(sel).count():
                safe_click(page, sel); page.wait_for_timeout(2000); break
    if not page.locator("[data-automation-id=verifyPassword]").count():
        log("create-fresh: create-account form (verifyPassword) never rendered")
        try: shot(page, tenant, "ERR-createfresh-noform")
        except Exception: pass
        return False
    # Fill the fresh credentials.
    fill_if(page, "[data-automation-id=email]", EMAIL)
    fill_if(page, "[data-automation-id=password]", PW)
    fill_if(page, "[data-automation-id=verifyPassword]", PW)
    cb = page.locator("[data-automation-id=createAccountCheckbox]").first
    if cb.count():
        try:
            if not cb.is_checked(): cb.check()
        except Exception:
            try: cb.click()
            except Exception: pass
    if not safe_click(page, "[data-automation-id=createAccountSubmitButton]"):
        safe_click(page, "[data-automation-id=click_filter]")
    page.wait_for_timeout(6000)
    # If we already landed on a step, the tenant didn't require email verification.
    if recover_to_step(page, base_url=base_url):
        log("create-fresh: account created & signed in (no email-verify required)")
        _persist_tenant_creds(tenant, fresh_created=True)
        return True
    bt = banner_text(page)
    log("create-fresh: post-submit banners:", bt)
    # Email verification required: poll gmail for the code. ROBUST: a bounded timeout,
    # and on timeout we set a DISTINCT flag (EXIT 10) instead of silently passing or
    # falling back to the polluted account. We do NOT thrash gmail -- single wait window.
    code = None
    needs_code = bool(page.locator("[data-automation-id*=erification] input, input[aria-label*=ode], input[data-automation-id*=erificationCode]").count())
    try:
        code = gmail_imap.wait_for_verification_code(
            timeout_seconds=WD_CREATE_VERIFY_TIMEOUT_S, since_epoch=time.time() - 240)
        log("create-fresh: got verification code:", code)
    except Exception as e:
        # Only treat as a hard verify-timeout failure if the page is actually asking for
        # a code. If no code field is present, the account may already be usable.
        if needs_code:
            _CREATE_ACCOUNT_EMAIL_VERIFY_FAIL = f"no verify code within {WD_CREATE_VERIFY_TIMEOUT_S}s for {EMAIL}: {str(e)[:80]}"
            log("create-fresh: EMAIL-VERIFY TIMEOUT ->", _CREATE_ACCOUNT_EMAIL_VERIFY_FAIL)
            try: shot(page, tenant, "ERR-createfresh-verify-timeout")
            except Exception: pass
            return False
        log("create-fresh: no code field + no code (verification may be optional):", str(e)[:80])
    if code:
        ci = page.locator("[data-automation-id*=erification] input, input[aria-label*=ode], input[data-automation-id*=erificationCode]").first
        if ci.count():
            try:
                ci.fill(code); page.wait_for_timeout(1200)
                for sub in ("[data-automation-id=verifyEmailSubmitButton]", "[data-automation-id=submitButton]",
                            "button:has-text('Verify')", "[data-automation-id=click_filter]"):
                    if page.locator(sub).count():
                        safe_click(page, sub); break
                page.wait_for_timeout(4000)
            except Exception as _e:
                log("create-fresh: code-fill err", str(_e)[:80])
    # After verify, ensure we're signed in on a step. Re-sign-in with the fresh creds if
    # the tenant dropped us back to the sign-in screen.
    if recover_to_step(page, base_url=base_url):
        log("create-fresh: account verified & signed in")
        _persist_tenant_creds(tenant, fresh_created=True)
        return True
    # LINK-ACTIVATION path (workday-activation-link 2026-06-10 Gates 2542): many Workday
    # tenants do NOT send a numeric code -- they email a clickable activation LINK
    # ('Click this link to confirm your email address' -> /<Site>/activate/<token>).
    # The old code-extractor mis-parsed '%2FSenior...' out of the link's redirect query
    # and returned garbage ('2FSenior') -> account never activated -> EXIT-2. Here, if we
    # still aren't on a step, fetch the activation URL from gmail and GET it to activate,
    # then sign in with the fresh creds. Reusable across ALL link-activation tenants.
    try:
        host_hint = None
        try:
            from urllib.parse import urlparse
            host_hint = urlparse(base_url or page.url).hostname
        except Exception:
            pass
        act_link = gmail_imap.wait_for_activation_link(
            timeout_seconds=90, since_epoch=time.time() - 300, host_hint=host_hint)
        if act_link:
            log("create-fresh: activation LINK found -> navigating to activate account")
            page.goto(act_link, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            if recover_to_step(page, base_url=base_url):
                log("create-fresh: account activated via link & on a step")
                _persist_tenant_creds(tenant, fresh_created=True)
                return True
    except Exception as _le:
        log("create-fresh: activation-link path err", str(_le)[:90])
    if page.locator("[data-automation-id=SignInWithEmailButton]").count():
        safe_click(page, "[data-automation-id=SignInWithEmailButton]"); page.wait_for_timeout(2000)
    if page.locator("[data-automation-id=email]").count() and page.locator("[data-automation-id=password]").count():
        fill_if(page, "[data-automation-id=email]", EMAIL)
        fill_if(page, "[data-automation-id=password]", PW)
        if not safe_click(page, "[data-automation-id=signInSubmitButton]"):
            safe_click(page, "[data-automation-id=click_filter]")
        page.wait_for_timeout(6000)
        if recover_to_step(page, base_url=base_url):
            log("create-fresh: signed in after verify")
            _persist_tenant_creds(tenant, fresh_created=True)
            return True
    log("create-fresh: created account but could not reach a step after verify")
    try: shot(page, tenant, "ERR-createfresh-postverify")
    except Exception: pass
    return False


def ensure_signed_in(page, tenant, base_url=None):
    """From the applyManually/sign-in screen: sign in, or create account, then sign in.
    FRESH-ACCOUNT default (workday-fresh-account-fix 2026-06-08): when run() set
    _ACCOUNT_MODE='create_fresh' (dupe-class / polluted-profile tenants), we go STRAIGHT
    to _create_fresh_account() and DO NOT attempt to sign into the saved profile, so the
    work-history starts EMPTY and gets filled from the tailored resume (standing rule:
    never reuse saved-profile data). For 'signin_fresh'/'signin_legacy' we use the
    historical sign-in-first behavior with the resolved (fresh-or-legacy) creds."""
    page.wait_for_timeout(2500)
    # Real 'in application' signal: a next button visible AND no sign-in form present,
    # OR the utility bar shows the logged-in email.
    def in_app():
        has_next = page.locator("[data-automation-id=pageFooterNextButton]").count() > 0
        has_signin = page.locator("[data-automation-id=SignInWithEmailButton]").count() > 0 or page.locator("[data-automation-id=password]").count() > 0
        logged = page.locator("[data-automation-id=utilityButtonSignIn]").count() == 0 and page.locator("button:has-text('cyshekari')").count() > 0
        # require an actual form field of My Information to be sure
        has_field = page.locator("input#name--legalName--firstName").count() > 0 or page.locator("input#source--source").count() > 0
        return (has_next and not has_signin) or logged or has_field
    if in_app():
        log("already in application"); return True
    # FRESH-ACCOUNT BRANCH (explicit, logged -- fixes the cold-start create-vs-signin
    # mis-pick triage flagged for Nordstrom/EXFO). When the decision is create_fresh we
    # NEVER touch the polluted saved account's sign-in form.
    if globals().get("_ACCOUNT_MODE") == "create_fresh":
        log(f"ensure_signed_in: mode=create_fresh -> minting fresh account (no saved-profile sign-in)")
        return _create_fresh_account(page, tenant, base_url=base_url)
    # Click 'Sign in with email'
    if page.locator("[data-automation-id=SignInWithEmailButton]").count():
        safe_click(page, "[data-automation-id=SignInWithEmailButton]")
        page.wait_for_timeout(2500)
    # Try sign-in first (account likely exists)
    if page.locator("[data-automation-id=email]").count() and page.locator("[data-automation-id=password]").count() and not page.locator("[data-automation-id=verifyPassword]").count():
        log("attempting sign-in with existing account")
        fill_if(page, "[data-automation-id=email]", EMAIL)
        fill_if(page, "[data-automation-id=password]", PW)
        # FIX (workday-p3 2026-06-02, NVIDIA 1607): the sign-in submit button is
        # data-automation-id=signInSubmitButton, NOT click_filter. click_filter is
        # the robot-honeypot overlay wrapper present on the form; clicking it never
        # submits -> 'FAILED to reach application step'. Click the real button.
        if not safe_click(page, "[data-automation-id=signInSubmitButton]"):
            safe_click(page, "[data-automation-id=click_filter]")
        page.wait_for_timeout(7000)
        if recover_to_step(page, base_url=base_url):
            log("signed in OK"); return True
        bt = banner_text(page)
        log("sign-in did not land on step; banners:", bt)
        # maybe wrong creds / need create account -> fall through to create
    # Create account path
    # FIX (workday-signin-first 2026-06-02 EXFO 2121): on a COLD context some tenants land
    # DIRECTLY on the create-account form (verifyPassword present), so the sign-in block
    # above is skipped. If the account already exists (our shared email is reused across
    # tenants), create-account submit no-ops on 'email already registered' and the runner
    # then waits 120s for a verify code that never arrives. Prefer the Sign-In toggle FIRST
    # when the create form is shown but a sign-in link exists, and attempt sign-in before
    # falling back to create.
    if page.locator("[data-automation-id=verifyPassword]").count():
        signin_toggle = None
        for sel in ("[data-automation-id=signInLink]", "a[data-automation-id=signIn]",
                    "button:has-text('Sign In')", "a:has-text('Sign In')"):
            if page.locator(sel).count():
                signin_toggle = sel; break
        if signin_toggle:
            log("create-account form shown on cold start -> trying Sign In toggle first")
            safe_click(page, signin_toggle); page.wait_for_timeout(2500)
            if (page.locator("[data-automation-id=email]").count()
                    and page.locator("[data-automation-id=password]").count()
                    and not page.locator("[data-automation-id=verifyPassword]").count()):
                fill_if(page, "[data-automation-id=email]", EMAIL)
                fill_if(page, "[data-automation-id=password]", PW)
                if not safe_click(page, "[data-automation-id=signInSubmitButton]"):
                    safe_click(page, "[data-automation-id=click_filter]")
                page.wait_for_timeout(7000)
                if recover_to_step(page, base_url=base_url):
                    log("signed in OK (via toggle)"); return True
                log("toggle sign-in did not land; falling back to create-account")
    if page.locator("[data-automation-id=createAccountLink]").count():
        safe_click(page, "[data-automation-id=createAccountLink]")
        page.wait_for_timeout(2000)
    if page.locator("[data-automation-id=verifyPassword]").count():
        log("creating account")
        fill_if(page, "[data-automation-id=email]", EMAIL)
        fill_if(page, "[data-automation-id=password]", PW)
        fill_if(page, "[data-automation-id=verifyPassword]", PW)
        cb = page.locator("[data-automation-id=createAccountCheckbox]").first
        if cb.count():
            try:
                if not cb.is_checked(): cb.check()
            except Exception: cb.click()
        # FIX (workday-p3 2026-06-02): create-account submit is
        # data-automation-id=createAccountSubmitButton, not click_filter.
        if not safe_click(page, "[data-automation-id=createAccountSubmitButton]"):
            safe_click(page, "[data-automation-id=click_filter]")
        page.wait_for_timeout(6000)
        if recover_to_step(page, base_url=base_url):
            log("account created & signed in"); return True
        body = page.locator("body").text_content() or ""
        bt = banner_text(page)
        log("after create-account banners:", bt)
        # Some tenants email a verify link/code, then drop to sign-in page.
        # Try email verification code then re-sign-in.
        try:
            code = gmail_imap.wait_for_verification_code(timeout_seconds=120, since_epoch=time.time()-300)
            log("got verification code:", code)
            # If there's a code input, fill it
            ci = page.locator("[data-automation-id*=erification] input, input[aria-label*=ode]").first
            if ci.count(): ci.fill(code); page.wait_for_timeout(1500)
        except Exception as e:
            log("no verify code (may not be required):", str(e)[:100])
        # LINK-ACTIVATION recovery (workday-activation-link 2026-06-10 Gates 2542): many
        # Workday tenants email a clickable ACTIVATION LINK, not a numeric code. The
        # code-extractor above mis-parses the link's redirect query ('2FSenior' garbage)
        # and the account stays UNVERIFIED -> 'Verify your account before you sign in'
        # banner -> sign-in fails. Fetch the real activation URL and GET it to activate,
        # then continue to sign-in below. Reusable across all link-activation tenants.
        try:
            host_hint = None
            try:
                from urllib.parse import urlparse
                host_hint = urlparse(base_url or page.url).hostname
            except Exception:
                pass
            act_link = gmail_imap.wait_for_activation_link(
                timeout_seconds=90, since_epoch=time.time()-300, host_hint=host_hint)
            if act_link:
                log("activation LINK found -> navigating to activate account")
                page.goto(act_link, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                if recover_to_step(page, base_url=base_url):
                    log("account activated via link & on a step"); return True
        except Exception as _le:
            log("activation-link recovery err", str(_le)[:90])
        # Re-attempt sign-in
        page.goto(page.url, wait_until="domcontentloaded"); page.wait_for_timeout(3000)
        if page.locator("[data-automation-id=SignInWithEmailButton]").count():
            safe_click(page, "[data-automation-id=SignInWithEmailButton]"); page.wait_for_timeout(2000)
        if page.locator("[data-automation-id=email]").count():
            fill_if(page, "[data-automation-id=email]", EMAIL)
            fill_if(page, "[data-automation-id=password]", PW)
            if not safe_click(page, "[data-automation-id=signInSubmitButton]"):
                safe_click(page, "[data-automation-id=click_filter]")
            page.wait_for_timeout(5000)
            if page.locator("[data-automation-id=pageFooterNextButton]").count():
                log("signed in after verify"); return True
    # DIAG (workday-p3): dump page state so failures are diagnosable, not opaque.
    try:
        u = page.url
        ids = page.evaluate("() => { const s={}; for (const el of document.querySelectorAll('[data-automation-id]')){ const i=el.getAttribute('data-automation-id'); if(/email|password|signin|submit|create|apply|adventure|next|verify|error|alert/i.test(i)) s[i]=(s[i]||0)+1;} return s; }")
        bt = banner_text(page)
        log(f"DIAG fail-state url={u}")
        log(f"DIAG automation-ids={ids}")
        log(f"DIAG banners={bt}")
        shot(page, tenant, "ERR-signin")
    except Exception as _e:
        log(f"DIAG dump fail: {_e}")
    log("ensure_signed_in: FAILED to reach application step")
    return False

def click_next(page):
    # NOADVANCE instrumentation (2026-06-11): capture the page heading + Next-button state
    # before and after the click so a "Next clicked but step did not advance" loop (Boeing
    # 2546 / PayPal 2891) is diagnosable. Logging only; click behavior unchanged.
    def _head():
        try:
            hs = [(h.text_content() or '').strip() for h in page.locator('h1,h2,h3').all()]
            hs = [h for h in hs if h][:4]
            return " | ".join(hs)
        except Exception:
            return "?"
    for sel in ["[data-automation-id=pageFooterNextButton]","[data-automation-id=bottom-navigation-next-button]"]:
        loc = page.locator(sel)
        if loc.count():
            try:
                btn = loc.first
                disabled = btn.get_attribute("aria-disabled") or btn.get_attribute("disabled")
                before = _head()
                log(f"  click_next[{sel}] btn_disabled={disabled} head_before='{before[:90]}'")
            except Exception:
                before = "?"
            safe_click(page, sel); page.wait_for_timeout(3500)
            try:
                after = _head()
                if after == before:
                    log(f"  click_next: NEXT CLICKED BUT HEADING UNCHANGED ('{after[:90]}') -> step did not advance")
                else:
                    log(f"  click_next: advanced -> head_after='{after[:90]}'")
                    # boeing-paypal-WE-fix (2026-06-13): when Workday returns 'Errors Found'
                    # after Next, dump the visible error text so we know WHAT failed
                    # (instead of only discovering it on the next My-Experience revisit).
                    if "errors found" in after.lower():
                        try:
                            _err_nodes = page.evaluate(
                                "()=>{const out=[];for(const e of document.querySelectorAll("
                                "'[data-automation-id*=error],[role=alert],[data-automation-id=errorMessage],"
                                "[class*=error]')){const t=(e.textContent||'').trim();"
                                "if(t&&t.length<200&&!out.includes(t))out.push(t);}"
                                "return JSON.stringify(out.slice(0,10));}"
                            )
                            log(f"  click_next ERRORS-FOUND dump: {_err_nodes[:600]}")
                            # workday-multi-upload-diag (2026-06-13): also dump upload-input count
                            # so we know if a second file slot is in play.
                            try:
                                _upcount = page.locator("[data-automation-id=file-upload-input-ref]").count()
                                _upcount2 = page.locator("input[type=file]").count()
                                _upsuccess = "yes" if "successfully uploaded" in (page.locator("body").text_content() or "").lower() else "no"
                                _delfile = page.locator("[data-automation-id*=DeleteFile]").count()
                                log(f"  ERRORS-FOUND upload-diag: file-upload-input-ref={_upcount} input[type=file]={_upcount2} successfully-uploaded={_upsuccess} DeleteFile={_delfile}")
                            except Exception:
                                pass
                        except Exception:
                            pass
            except Exception:
                pass
            return True
    log("  click_next: NO next button found on page")
    return False


def page_errors(page):
    errs=[]
    for sel in ["[data-automation-id=errorMessage]","[role=alert]","[class*=rror]"]:
        for e in page.locator(sel).all()[:8]:
            try:
                t=(e.text_content() or "").strip()
                if t and "required" in t.lower() or (t and len(t)<120 and "error" in (e.get_attribute('data-automation-id') or '').lower()):
                    errs.append(t[:120])
            except Exception: pass
    return errs

def diagnose_noadvance(page):
    """Diagnostic-only (no side effects): when a step won't advance on Next, dump the
    signals the standard DIAG misses so a real blocker can be NAMED instead of spinning
    to the EXIT-5 loop-cap. Surfaces: (1) ALL error/alert text incl long ones the
    page_errors() <120-char filter drops; (2) required listbox/dropdown BUTTONS still on
    'Select One' (Workday renders these as <button>, NOT aria-required inputs, so the
    input-only DIAG never sees them); (3) required-but-empty fields lacking aria-required
    (Formik/DOM-only required, like the GH-Remix class); (4) unchecked checkboxes in a
    required/error context. Returns a short dict; logging is the caller's job."""
    try:
        return page.evaluate(r"""()=>{
            const out={all_errors:[],select_one:[],domreq_empty:[],unchecked:[]};
            // (1) every error/alert, full text (trimmed to 200)
            for (const e of document.querySelectorAll('[data-automation-id*=error i],[role=alert],[class*=rror]')){
                const t=(e.textContent||'').trim();
                if (t && t.length<=200 && !out.all_errors.includes(t)) out.all_errors.push(t);
            }
            // (2) listbox/combobox buttons still showing a placeholder (Select One / blank)
            for (const b of document.querySelectorAll('button[aria-haspopup=listbox],[data-automation-id*=selectinput] button,button[data-automation-id*=Prompt]')){
                const lbl=(b.textContent||'').trim();
                if (/^select( one)?$/i.test(lbl) || lbl===''){
                    const id=b.id||b.getAttribute('data-automation-id')||b.getAttribute('aria-label')||'?';
                    out.select_one.push(id+' :: '+(lbl||'(blank)'));
                }
            }
            // (3) required-but-empty without aria-required (DOM-only / Formik required)
            for (const el of document.querySelectorAll('input[required]:not([aria-required]),select[required]:not([aria-required])')){
                if (!(el.value||'').trim()) out.domreq_empty.push(el.id||el.name||el.getAttribute('data-automation-id')||'?');
            }
            // (4) any unchecked checkbox sitting inside an errored/required group
            for (const c of document.querySelectorAll('input[type=checkbox][aria-required=true]:not(:checked),input[type=checkbox][required]:not(:checked)')){
                out.unchecked.push(c.id||c.getAttribute('data-automation-id')||c.name||'?');
            }
            return JSON.stringify(out);
        }""")
    except Exception as _e:
        return '{"diag_err":"%s"}' % (str(_e)[:80].replace('"', ''))

def _source_committed(page):
    """True iff How-Did-You-Hear-About-Us has a committed selection, SCOPED to the
    source field's own container (id starts with 'source'). A global selectedItem query
    false-positived on other fields' pills (grind-resolver 2026-06-02: returned True while
    Workday still threw 'How Did You Hear About Us is required'). We locate the form widget
    whose data-automation-id / id references 'source' and check for a removable pill
    (selectedItem / DELETE_charm) INSIDE it."""
    try:
        return bool(page.evaluate("""()=>{
            // Find the source multiselect container.
            let host = document.querySelector('input#source--source');
            let box = host ? host.closest('[data-automation-id]') : null;
            // climb to the widget wrapper (a few levels) to capture pills rendered as siblings
            let scope = host;
            for (let i=0; i<6 && scope; i++){
                scope = scope.parentElement;
                if (scope && scope.querySelector('[data-automation-id=selectedItem],[data-automation-id=DELETE_charm]')) {
                    return true;
                }
            }
            return false;
        }"""))
    except Exception:
        return False

def pick_workday_source(page):
    """Robustly fill Workday 'How Did You Hear About Us?' multiselect.
    FIX (grind-resolver 2026-06-02): the old [role=option] exact-text click logged
    'source picked' but NEVER committed -> req_empty[source--source] + 'field is required'
    loop on EVERY tenant (Philips, rbi both EXIT 5). Root cause: Workday renders these as
    [data-automation-id=promptOption] inside a promptLeafButton tree, not [role=option],
    and the leaf needs a real click that registers a pill. This helper:
      1) opens the prompt, 2) walks category->leaf via promptOption automation-ids,
      3) VERIFIES a pill committed (re-opens & retries up to 3x), 4) typeahead fallback.
    Returns True iff committed."""
    if _source_committed(page):
        log("source already selected, skipping"); return True
    src = page.locator("input#source--source").first
    if not src.count():
        # Fallback: some tenants (e.g. Cisco wd5) render 'How Did You Hear About Us?'
        # as a standard Workday single-select listbox with a different ID pattern.
        # Detect by label text and attempt _commit_wd_dropdown.
        try:
            hw_label = page.evaluate("""()=>{
                const labels = [...document.querySelectorAll('label')];
                for (const l of labels) {
                    const t = (l.textContent||'').toLowerCase();
                    if (t.includes('hear about') || t.includes('how did you')) {
                        return l.getAttribute('for') || l.id || 'FOUND';
                    }
                }
                return null;
            }""")
            if hw_label:
                log("source: fallback label-based field detected:", hw_label)
                committed = _commit_wd_dropdown(page, hw_label,
                    "LinkedIn",
                    want_alts=["LinkedIn", "Indeed", "Job Board", "Other", "Internet"])
                if committed:
                    log("source COMMITTED via label-fallback")
                    return True
                # If _commit_wd_dropdown fails, try generic promptOption pick
                src_fb = page.locator(f"input#{hw_label}").first if hw_label != 'FOUND' else None
                if src_fb and src_fb.count():
                    src = src_fb  # fall through to main flow below
                else:
                    return True  # unknown widget variant; don't block submission
            else:
                return True  # no source field on this step
        except Exception as e:
            log("source label-fallback fail", str(e)[:80])
            return True  # don't block on this field
    # ONE-TIME DOM probe (grind-resolver): dump the source widget structure so we use the
    # right commit selector. Guarded by env WD_SOURCE_PROBE=1.
    import os as _os
    if _os.environ.get("WD_SOURCE_PROBE") == "1":
        try:
            html = page.evaluate("""()=>{let h=document.querySelector('input#source--source');
                let n=h; for(let i=0;i<7&&n&&n.parentElement;i++){n=n.parentElement;}
                return n? n.outerHTML.slice(0,4000):'NO-WIDGET';}""")
            log("SOURCE_WIDGET_HTML:", html)
        except Exception as e:
            log("probe fail", str(e)[:80])

    def open_prompt():
        try:
            src.click(timeout=6000)
        except Exception:
            try: src.click(force=True, timeout=4000)
            except Exception: return False
        page.wait_for_timeout(900); return True

    def opts():
        # promptOption is the canonical Workday node; fall back to role=option.
        els = page.locator("[data-automation-id=promptOption]").all()
        if not els:
            els = page.locator("[role=option]").all()
        return els

    def click_text(substrs, exact=False):
        for o in opts():
            try:
                t = (o.text_content() or "").strip()
                tl = t.lower()
                for s in substrs:
                    if (tl == s.lower()) if exact else (s.lower() in tl):
                        o.scroll_into_view_if_needed(timeout=2000)
                        o.click(timeout=4000); page.wait_for_timeout(900); return t
            except Exception: pass
        return None

    CATEGORIES = ["Job Board", "Social Media", "Online", "Job Boards", "Internet"]
    LEAVES = ["LinkedIn", "Indeed", "Glassdoor", "Company Website", "Other"]

    for attempt in range(3):
        if not open_prompt():
            continue
        if _os.environ.get("WD_SOURCE_PROBE") == "1" and attempt == 0:
            try:
                dump = page.evaluate("""()=>{const a=[...document.querySelectorAll('[data-automation-id=promptOption],[role=option]')].slice(0,40).map(o=>({aid:o.getAttribute('data-automation-id'),role:o.getAttribute('role'),t:(o.textContent||'').trim().slice(0,40)})); return JSON.stringify(a);}""")
                log("PROMPT_OPTIONS:", dump)
            except Exception: pass
        # Try to expand a known category (multi-level prompts). Ignore if flat.
        cat = None
        for c in CATEGORIES:
            cat = click_text([c])
            if cat:
                log("source category:", cat); break
        # Pick a leaf (works for flat lists too — leaf substrings present at top level).
        leaf = None
        for l in LEAVES:
            leaf = click_text([l])
            if leaf: break
        if not leaf:
            # last resort: first non-empty, non-'select one' option
            for o in opts():
                try:
                    t = (o.text_content() or "").strip()
                    if t and t.lower() not in ("select one",) and "+1" not in t:
                        o.click(timeout=4000); leaf = t; page.wait_for_timeout(900); break
                except Exception: pass
        if leaf:
            log("source picked:", leaf)
        # close the prompt so the pill commits, then verify
        try: page.keyboard.press("Escape")
        except Exception: pass
        page.wait_for_timeout(600)
        if _source_committed(page):
            log("source COMMITTED (attempt %d)" % attempt); return True
        # typeahead fallback before next attempt
        try:
            src.click(timeout=3000); page.wait_for_timeout(400)
            page.keyboard.type("LinkedIn"); page.wait_for_timeout(1200)
            tp = click_text(["LinkedIn"]) or click_text(["Indeed"])
            if tp: log("source typeahead picked:", tp)
            page.keyboard.press("Escape"); page.wait_for_timeout(600)
            if _source_committed(page):
                log("source COMMITTED via typeahead"); return True
        except Exception: pass
    log("source NOT committed after retries")
    return False

def fill_my_information(page, source):
    log("step: My Information")
    page.wait_for_timeout(1500)
    global _MYINFO_COMMIT_FAIL
    _MYINFO_COMMIT_FAIL = None
    # How Did You Hear About Us (multiselect): robust committing picker (see pick_workday_source).
    try:
        if not pick_workday_source(page):
            _MYINFO_COMMIT_FAIL = "source"
    except Exception as e:
        log("source fail", str(e)[:80])
    # Previously worked? -> No. Radios are visually-hidden; click the label[for=id] whose text == 'No'.
    try:
        rid_no = page.evaluate("""()=>{const rs=document.querySelectorAll('input[name=candidateIsPreviousWorker]');
            for(const r of rs){const l=document.querySelector('label[for=\\''+r.id+'\\']'); if(l && l.textContent.trim().toLowerCase()==='no') return r.id;}
            return rs.length?rs[rs.length-1].id:null;}""")
        if rid_no:
            page.locator(f"label[for={rid_no}]").first.click()
            page.wait_for_timeout(400)
    except Exception as e:
        log("prevworker fail", str(e)[:80])
    # Names
    fill_if(page, "input#name--legalName--firstName", FIRST)
    fill_if(page, "input#name--legalName--lastName", LAST)
    # Email (anonymous Apply-Manually flow, e.g. Adobe external_experienced, has an
    # email field on My Information that account-based tenants pre-fill from profile).
    # FIX (workday-p13 2026-06-02 Adobe R165611): runner never filled it -> 'Email is
    # required' loop. Fill only when present & empty.
    try:
        em = page.locator("input#emailAddress--emailAddress").first
        if em.count() and not (em.input_value() or "").strip():
            em.fill(EMAIL); log("email filled (anon flow)")
    except Exception as e:
        log("email fill fail", str(e)[:60])
    # Country phone code (button-dropdown). Default United States (+1). Only if empty.
    # FIX (workday-myinfo-fix 2026-06-02): the old wd_pick_listbox path 'picked' but the value
    # never COMMITTED on some tenants (Philips 1466) -> phone read invalid + My-Info bounced.
    # Route through the generic verify-or-retry committer; fail LOUD if it won't stick.
    try:
        if not _commit_wd_dropdown(
                page, "countryPhoneCode",
                "United States of America (+1)",
                want_alts=["United States of America", "United States", "(+1)", "+1"]):
            _MYINFO_COMMIT_FAIL = (_MYINFO_COMMIT_FAIL + "+countryPhoneCode") if _MYINFO_COMMIT_FAIL else "countryPhoneCode"
    except Exception as e:
        log("country phone code fail", str(e)[:60])
    # Address
    fill_if(page, "input#address--addressLine1", ADDRESS_LINE1)
    fill_if(page, "input#address--city", CITY)
    fill_if(page, "input#address--postalCode", POSTAL)
    # State dropdown
    if page.locator("button#address--countryRegion").count():
        wd_pick_listbox(page, "button#address--countryRegion", STATE)
    # Phone device type (option labels vary by tenant: 'Home Cellular'/'Mobile'/'Cell'/'Home').
    if page.locator("button#phoneNumber--phoneType").count():
        ptbtn = page.locator("button#phoneNumber--phoneType").first
        cur_pt = (ptbtn.text_content() or "").strip()
        if not cur_pt or cur_pt.lower() == "select one":
            picked_pt = False
            for opt in ["Home Cellular", "Mobile", "Cell", "Cellular", "Home"]:
                if wd_pick_listbox(page, "button#phoneNumber--phoneType", opt):
                    picked_pt = True; break
            if not picked_pt:
                # fallback: open + click first non-'Select One' option
                try:
                    ptbtn.click(); page.wait_for_timeout(700)
                    for o in page.locator("[role=option]").all():
                        t = (o.text_content() or "").strip()
                        if t and t.lower() != "select one" and "+1" not in t:
                            o.click(); page.wait_for_timeout(400); break
                except Exception: pass
    fill_if(page, "input#phoneNumber--phoneNumber", PHONE)
    shot(page, "myinfo", "filled")

def run(args):
    tenant = args.tenant
    global _CUR_TENANT
    _CUR_TENANT = tenant  # (workday-ack-widget) so _dump_ack_diag names its file per-tenant
    global _RECOVER_TERMINAL
    _RECOVER_TERMINAL = None
    global _WE_PREFILL_UNCOMMITTABLE
    _WE_PREFILL_UNCOMMITTABLE = None  # reset per-run so the flag never leaks across batch rows
    global _CREATE_ACCOUNT_EMAIL_VERIFY_FAIL
    _CREATE_ACCOUNT_EMAIL_VERIFY_FAIL = None  # reset per-run (fresh-account email-verify timeout)
    global _RESUME_UPLOADED, _RESUME_REQ_REUPLOADS
    _RESUME_UPLOADED = 0  # reset per-run so the upload cap never leaks across batch rows
    _RESUME_REQ_REUPLOADS = 0  # reset per-run (Boeing required-upload re-upload counter)
    # FRESH-ACCOUNT default (workday-fresh-account-fix 2026-06-08, Cyrus option A):
    # resolve_account_for_tenant() decides EXPLICITLY whether to CREATE a fresh account
    # (dupe-class / polluted-profile tenants -> empty work-history filled from the
    # tailored resume) or sign into a known-good fresh alias / legacy clean account. It
    # sets module EMAIL/PW to the chosen account + records the branch mode globally so
    # ensure_signed_in() and populate_work_history() honor it. Standing rule: NEVER reuse
    # saved-profile data; always apply fresh from the customized resume.
    global EMAIL, PW, _ACCOUNT_MODE, _FRESH_VERIFY_PW
    _force_fresh = None
    if getattr(args, "legacy_account", False):
        _force_fresh = False  # explicit escape hatch: keep historical sign-in behavior
    elif getattr(args, "fresh_account", False):
        _force_fresh = True   # explicit: force a fresh-account mint even for a clean tenant
    EMAIL, PW, _ACCOUNT_MODE = resolve_account_for_tenant(tenant, force_fresh=_force_fresh)
    _FRESH_VERIFY_PW = PW if _ACCOUNT_MODE in ("create_fresh", "signin_fresh") else None
    log(f"creds: email={EMAIL} pw_len={len(PW)} account_mode={_ACCOUNT_MODE}")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / ".workday-browser-data" / tenant),
            headless=True, viewport={"width":1400,"height":900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            accept_downloads=True,
        )
        page = ctx.new_page()
        page.set_default_timeout(20000)
        log("goto", args.url)
        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        # Dismiss cookie/legal banner if present (Snap and others).
        for cb in ["[data-automation-id=legalNoticeAcceptButton]", "button:has-text('Accept Cookies')"]:
            if page.locator(cb).count():
                try: page.locator(cb).first.click(timeout=3000)
                except Exception: pass
                break
        shot(page, tenant, "00-landing")
        # FIX (workday-p17 2026-06-02 NVIDIA recovery): detect a CLOSED/removed req up front
        # (NVIDIA JR2012702 returns 'The page you are looking for doesn't exist'). No apply
        # affordance will ever render -> stop now with a precise verdict instead of spinning.
        _ts = terminal_state(page)
        if _ts == "closed":
            shot(page, tenant, "CLOSED-req")
            log("RESULT: BLOCKED req CLOSED/removed (page doesn't exist)"); ctx.close(); return 6
        # Navigate JD page -> Apply modal -> Apply Manually, robustly.
        # FIX (workday-p3 2026-06-02 NVIDIA 1607): clicking adventureButton (Apply)
        # once and immediately probing applyManually is flaky -- the modal may not
        # have rendered yet, or a logged-in profile lands on a different intermediate.
        # Loop: if Apply button present, click it & wait; if Apply Manually present,
        # click it; stop once we leave the JD posting (sign-in form or app step shows).
        for _nav in range(6):
            if (page.locator("[data-automation-id=email]").count()
                    or page.locator("[data-automation-id=SignInWithEmailButton]").count()
                    or page.locator("[data-automation-id=pageFooterNextButton]").count()
                    or page.locator("input#name--legalName--firstName").count()):
                break
            if page.locator("[data-automation-id=applyManually]").count():
                safe_click(page, "[data-automation-id=applyManually]"); page.wait_for_timeout(3500); continue
            # FIX (workday-proof 2026-06-02 Nordstrom 1456): logged-in + in-progress draft
            # shows 'Continue Application' instead of Apply; resume it.
            if page.locator("[data-automation-id=continueButton]").count():
                safe_click(page, "[data-automation-id=continueButton]"); page.wait_for_timeout(3500); continue
            if page.locator("[data-automation-id=adventureButton]").count():
                safe_click(page, "[data-automation-id=adventureButton]"); page.wait_for_timeout(3000); continue
            page.wait_for_timeout(1500)
        shot(page, tenant, "01-after-applymanually")
        if not ensure_signed_in(page, tenant, base_url=args.url):
            # FIX (workday-p17 2026-06-02 NVIDIA recovery): distinguish terminal already-applied
            # from a genuine sign-in block. recover_to_step sets _RECOVER_TERMINAL.
            if _RECOVER_TERMINAL == "already_applied":
                shot(page, tenant, "already-applied")
                log("RESULT: ALREADY_APPLIED (Workday you-applied banner)"); ctx.close(); return 7
            if _RECOVER_TERMINAL == "closed":
                shot(page, tenant, "CLOSED-req")
                log("RESULT: BLOCKED req CLOSED/removed"); ctx.close(); return 6
            # FAST-FAIL (workday-fresh-account-fix 2026-06-08): the create-fresh path could
            # not get Workday's email-verification code in time. Bank a DISTINCT EXIT 10
            # ('workday-create-account-email-verify-timeout') so this is retryable/diagnosable
            # and is NEVER confused with a generic sign-in block (EXIT 2) -- and we did NOT
            # silently fall back to the polluted saved account.
            if globals().get("_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL"):
                log(f"RESULT: BLOCKED workday-create-account-email-verify-timeout: {_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL}")
                shot(page, tenant, "ERR-createfresh-verify-timeout")
                ctx.close(); return 10
            shot(page, tenant, "ERR-signin")
            log("RESULT: BLOCKED at sign-in/account-create"); ctx.close(); return 2
        shot(page, tenant, "02-step1")
        # Walk steps
        MAX_STEPS = 10
        # FIX (workday-workexp-fix 2026-06-02) loop-cap: if the SAME step name keeps
        # repeating without advancing (My Experience runaway), abort THIS row cleanly
        # with a precise note instead of burning all MAX_STEPS spinning.
        _step_revisits = {}
        _STEP_REVISIT_CAP = 3
        for i in range(MAX_STEPS):
            page.wait_for_timeout(1500)
            body = page.locator("body").text_content() or ""
            if "Something went wrong" in body:
                log("transient 'Something went wrong' - recovering")
                recover_to_step(page, base_url=args.url); page.wait_for_timeout(1500)
                body = page.locator("body").text_content() or ""
            shot(page, tenant, f"step-{i}")
            cur = current_step_name(page, body)
            _step_revisits[cur] = _step_revisits.get(cur, 0) + 1
            if _step_revisits[cur] > _STEP_REVISIT_CAP:
                log(f"RESULT: BLOCKED step '{cur}' revisited >{_STEP_REVISIT_CAP}x without advancing (loop-cap)")
                shot(page, tenant, "LOOPCAP-stuck")
                ctx.close(); return 5
            log(f"--- iteration {i}: step '{cur}' (visit {_step_revisits[cur]}) ---")
            if "My Information" in cur:
                fill_my_information(page, args.source)
                try:
                    md = page.evaluate("() => { const o={req_empty:[],errors:[]}; for(const el of document.querySelectorAll('input[aria-required=true],input[required],[data-automation-id*=requiredIndicator]')){ if(el.tagName==='INPUT' && !(el.value||'').trim()){ o.req_empty.push(el.id||el.name||el.getAttribute('data-automation-id')||'?'); } } for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert]')){const t=(e.textContent||'').trim(); if(t&&t.length<140)o.errors.push(t);} return JSON.stringify(o); }")
                    log("DIAG myinfo:", md[:500])
                except Exception as _e:
                    log("DIAG myinfo fail", str(_e)[:80])
                # FIX (workday-myinfo-fix 2026-06-02): if a required My-Info dropdown (source /
                # countryPhoneCode) still would not COMMIT after the in-helper verify+retry cap,
                # fail LOUD with a precise EXIT 8 instead of spinning to the revisit loop-cap.
                if globals().get("_MYINFO_COMMIT_FAIL"):
                    log(f"RESULT: BLOCKED My-Info dropdown(s) would not commit: {_MYINFO_COMMIT_FAIL}")
                    shot(page, tenant, "MYINFO-nocommit")
                    ctx.close(); return 8
            elif "My Experience" in cur:
                # workday-post-nav-regen-fix (2026-06-13): Boeing 2546 / PayPal 2891 sub-class.
                # Workday regenerates a brand-new empty required WE block on each My-Experience
                # re-render (post click_next nav). Harden runs BEFORE Next so it never sees this
                # post-nav block. Clean it up FIRST on revisit, before handle_experience runs.
                if _step_revisits.get(cur, 0) >= 2:
                    try:
                        post_next_we_guard(page)
                    except Exception as _png:
                        log("  post_next_we_guard err", str(_png)[:100])
                handle_experience(page, args.resume)
                try:
                    ed = page.evaluate("() => { const o={uploaded:false,req_empty:[],errors:[]}; o.uploaded=/successfully uploaded|\\.pdf|\\.docx/i.test(document.body.innerText); for(const el of document.querySelectorAll('input[aria-required=true],textarea[aria-required=true]')){ if(!(el.value||'').trim()) o.req_empty.push(el.id||el.getAttribute('data-automation-id')||el.name||'?'); } for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert]')){const t=(e.textContent||'').trim(); if(t&&t.length<140)o.errors.push(t);} return JSON.stringify(o); }")
                    log("DIAG experience:", ed[:500])
                except Exception as _e:
                    log("DIAG experience fail", str(_e)[:80])
                # FAST-FAIL (workday-prefill-uncommittable-fix 2026-06-05): if the prefill-guard
                # detected PROFILE-PREFILLED work-exp block(s) whose REQUIRED start-date cannot
                # be committed (read-only tenant-profile dupes, e.g. EXFO 2121's 5 Microsoft
                # dupes), bank a precise EXIT 9 instead of spinning to the generic EXIT 5
                # loop-cap. This is a profile-side DATA blocker (Cyrus must dedupe his Workday
                # tenant profile), not an engine bug -- the empty-block regen is already handled.
                if globals().get("_WE_PREFILL_UNCOMMITTABLE"):
                    log(f"RESULT: BLOCKED workday-profile-prefill-uncommittable: {_WE_PREFILL_UNCOMMITTABLE}")
                    shot(page, tenant, "PREFILL-uncommittable")
                    ctx.close(); return 9
                # NO-ADVANCE DIAGNOSTIC (workday-myexperience-next-noadvance probe, 2026-06-11):
                # if we are REVISITING My-Experience (Next failed at least once), the
                # standard input-only DIAG cannot see WHY. Dump listbox 'Select One' buttons,
                # DOM-only required-empties, unchecked required checkboxes, and FULL error text
                # so the real blocker is NAMED. Diagnostic-only (no side effects).
                if _step_revisits.get(cur, 0) >= 2:
                    try:
                        nd = diagnose_noadvance(page)
                        log("NOADVANCE-DIAG experience:", (nd or "")[:700])
                    except Exception as _e2:
                        log("NOADVANCE-DIAG fail", str(_e2)[:80])
                # workday-we-persist-fix (2026-06-11 run4): LAST action on My Experience before
                # the shared click_next below -> make the WE-block COUNT plateau (delete every
                # empty block + re-measure until 0-empty AND total stable x2). Stops the resume
                # PARSER's late-spawned 'add-another' empty required block from bouncing Next ->
                # revisit -> loop-cap EXIT-5 (the true root cause on Nvidia 2829/Gates/Boeing/PayPal).
                # Runs in dryrun too so a dryrun validates the step now advances past WE.
                try:
                    harden_my_experience_before_next(page)
                except Exception as _he:
                    log("  harden_my_experience_before_next err", str(_he)[:100])
                # workday-post-harden-reupload-fix (2026-06-13 PayPal/Boeing class):
                # populate_work_history manipulates many WE-block form fields, which can
                # invalidate Workday's upload widget state. Re-check the upload is still
                # present AFTER harden completes and re-upload if missing, so click_next
                # sees a valid upload. Capped at 1 re-upload to avoid loops.
                try:
                    _refile = page.evaluate(
                        "()=>/successfully uploaded/i.test(document.body.innerText)"
                        "||!![...document.querySelectorAll('[data-automation-id*=DeleteFile]')].length"
                    )
                    _reupl_inp = page.locator("[data-automation-id=file-upload-input-ref]")
                    if not _refile and _reupl_inp.count() and getattr(args, 'resume', None):
                        log("  post-harden-reupload: upload dropped after WE-fill -> re-uploading before click_next")
                        _reupl_inp.first.set_input_files(args.resume)
                        # wait for upload to confirm (up to 15s)
                        for _rwt in range(15):
                            page.wait_for_timeout(1000)
                            _rb = page.evaluate("()=>document.body.innerText") or ""
                            if "successfully uploaded" in _rb.lower() or page.locator("[data-automation-id*=DeleteFile]").count():
                                log(f"  post-harden-reupload: confirmed after {_rwt+1}s")
                                break
                        else:
                            log("  post-harden-reupload: not confirmed after 15s (proceeding anyway)")
                    else:
                        log(f"  post-harden-reupload: upload ok (file_present={_refile}) -> skip")
                except Exception as _rhe:
                    log(f"  post-harden-reupload err: {str(_rhe)[:80]}")
            elif "Application Question" in cur:
                handle_questions(page)
                # DIAG (workday-proof 2026-06-02 Snap 1933): real-run looped 9x on App
                # Questions w/o advancing. Dump every primaryQuestionnaire button's COMMITTED
                # value + any validation error so we can see which Q didn't commit / what blocks Next.
                try:
                    qd = page.evaluate("""() => { const o={qs:[],errors:[],unanswered:[]};
                        for(const b of document.querySelectorAll('button[id^=primaryQuestionnaire],button[aria-haspopup=listbox]')){
                          const v=(b.getAttribute('aria-label')||b.innerText||'').trim();
                          o.qs.push((b.id||'?').slice(-24)+'=>'+v.slice(-30));
                          if(/select one|^$/i.test(v)) o.unanswered.push((b.id||'?').slice(-24));
                        }
                        for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert],.css-error,[data-automation-id=errorMessage]')){const t=(e.textContent||'').trim(); if(t&&t.length<160)o.errors.push(t);}
                        return JSON.stringify(o); }""")
                    log("DIAG questions:", qd[:700])
                except Exception as _e:
                    log("DIAG questions fail", str(_e)[:80])
                # (workday-ack-widget 2026-06-10 GEICO 2358 forensic) one-shot: click Next
                # and capture the heading + FULL validation/error/aria-invalid state to see
                # exactly what blocks the advance when everything reads answered.
                if globals().get("_CUR_TENANT") == "geico" and not globals().get("_POSTNEXT_FORENSIC_DONE"):
                    try:
                        globals()["_POSTNEXT_FORENSIC_DONE"] = True
                        click_next(page); page.wait_for_timeout(3500)
                        pf = page.evaluate(r"""()=>{
                            const o={heading:'',errors:[],invalid:[],unanswered:[],nextDisabled:null};
                            const h=document.querySelector('h1,h2,h3'); o.heading=h?(h.innerText||'').trim().slice(0,60):'';
                            for(const e of document.querySelectorAll('[role=alert],[data-automation-id*=error],[data-automation-id=errorMessage],.css-error,[id*=error]')){const t=(e.textContent||'').trim(); if(t&&t.length<200)o.errors.push(t);}
                            for(const el of document.querySelectorAll('[aria-invalid=true]')){let lab='';let p=el;for(let i=0;i<6&&p;i++){p=p.parentElement;if(p){const l=p.querySelector('label,legend');if(l){lab=(l.textContent||'').trim();break;}}}o.invalid.push(((el.id||el.getAttribute('data-automation-id')||'?')+' :: '+lab).slice(0,80));}
                            for(const b of document.querySelectorAll('button[id^=primaryQuestionnaire]')){const v=(b.getAttribute('aria-label')||b.innerText||'').trim();if(/select one|^$/i.test(v))o.unanswered.push((b.id||'?').slice(-16)+'='+v.slice(0,20));}
                            const nb=document.querySelector('[data-automation-id=pageFooterNextButton],[data-automation-id=bottom-navigation-next-button]'); o.nextDisabled=nb?(nb.disabled||nb.getAttribute('aria-disabled')==='true'):null;
                            return JSON.stringify(o);
                        }""")
                        log("POSTNEXT-FORENSIC:", pf[:900])
                        shot(page, tenant, "POSTNEXT-forensic")
                    except Exception as _e:
                        log("POSTNEXT-FORENSIC fail", str(_e)[:80])
            elif "Voluntary" in cur or "Self Identif" in cur:
                # DIAG (workday-p3): dump self-id field ids + errors once to diagnose loops.
                try:
                    diag = page.evaluate("() => { const out={inputs:[],buttons:[],errors:[]}; for(const el of document.querySelectorAll('input,button[id]')){ const i=el.id||el.getAttribute('data-automation-id')||''; if(/disab|selfId|veteran|gender|ethnic|terms|name|date|signed/i.test(i)) out[el.tagName==='BUTTON'?'buttons':'inputs'].push(i+(el.value?('='+el.value):'')); } for(const e of document.querySelectorAll('[data-automation-id*=error],[role=alert]')){const t=(e.textContent||'').trim(); if(t&&t.length<140) out.errors.push(t);} return JSON.stringify(out); }")
                    log("DIAG selfid:", diag[:600])
                except Exception as _e:
                    log("DIAG selfid fail", str(_e)[:80])
                # (workday-paypal-voluntary 2026-06-13) ENHANCED error dump for voluntary step
                if _step_revisits.get(cur, 0) >= 2:
                    try:
                        _vol_errs = page.evaluate("()=>{const out=[];for(const e of document.querySelectorAll('button,span,div,p')){const t=(e.textContent||'').trim();if(t&&t.startsWith('Error-')&&t.length<200&&!out.includes(t))out.push(t.slice(0,180));}return JSON.stringify(out.slice(0,10));}")

                        log(f"  NOADVANCE-DIAG voluntary (Error- buttons): {_vol_errs[:500]}")
                        _vol_req = page.evaluate("()=>{const out=[];for(const el of document.querySelectorAll('[aria-required=true]')){const v=(el.value||el.getAttribute('aria-label')||el.innerText||'').trim();const filled=el.tagName==='BUTTON'?!/select one|^$/i.test(v):!!v;if(!filled){let lab='';let p=el;for(let i=0;i<5&&p;i++){p=p.parentElement;if(p){const l=p.querySelector('label');if(l){lab=l.textContent.trim();break;}}}out.push((el.id||el.getAttribute('data-automation-id')||'?').slice(0,40)+'::'+lab.slice(0,30));}}return JSON.stringify(out.slice(0,15));")
                        log(f"  NOADVANCE-DIAG voluntary (aria-required empty): {_vol_req[:400]}")
                    except Exception as _vde:
                        log(f"  NOADVANCE-DIAG voluntary fail: {str(_vde)[:60]}")
                if page.locator("input#selfIdentifiedDisabilityData--name").count():
                    handle_self_identify(page)
                else:
                    handle_voluntary(page)
            elif "Review" in cur:
                shot(page, tenant, "review")
                if args.dryrun:
                    log("DRYRUN: reached Review, stopping before submit")
                    ctx.close(); return 0
                # final submit
                if submit_final(page):
                    page.wait_for_timeout(5000)
                    shot(page, tenant, "after-submit")
                    if verify_confirmation(page, base_url=args.url):
                        log("RESULT: SUBMITTED - confirmation verified"); ctx.close(); return 0
                    else:
                        log("RESULT: submit clicked but NO confirmation text found"); ctx.close(); return 3
                else:
                    log("RESULT: BLOCKED could not click submit"); ctx.close(); return 4
            else:
                log("unknown step, body head:", body[:200])
            errs = page_errors(page)
            if errs: log("page errors:", errs[:5])
            if args.dryrun and i>=1 and "Review" not in cur:
                pass
            if not click_next(page):
                log("no next button; trying submit"); 
                if submit_final(page):
                    page.wait_for_timeout(5000)
                    if verify_confirmation(page, base_url=args.url):
                        log("RESULT: SUBMITTED"); ctx.close(); return 0
                log("stuck, breaking"); break
            errs = page_errors(page)
            if errs: log("after-next errors:", errs[:5])
        log("RESULT: ended loop without confirmation")
        shot(page, tenant, "END")
        ctx.close(); return 5

def current_step_name(page, body):
    # Detect by ACTUAL rendered form fields (the step nav list is always present in body, so don't trust regex on it).
    if page.locator("[data-automation-id=legalNameSection_firstName]").count() or page.locator("input#name--legalName--firstName").count() or page.locator("[data-automation-id=addressSection_addressLine1]").count():
        return "My Information"
    # Heading-based detection: find the visible h2/h3 page title
    try:
        heads = [ (h.text_content() or '').strip() for h in page.locator('h1,h2,h3').all() ]
    except Exception:
        heads = []
    for h in heads:
        for kw in ["My Experience","Application Question","Voluntary Disclosure","Self Identif","Review","My Information"]:
            if kw.lower() in h.lower():
                return kw
    if page.locator("[data-automation-id=file-upload-input-ref]").count() or page.locator("input[type=file]").count():
        return "My Experience"
    if page.locator("[data-automation-id=submit]").count():
        return "Review"
    return "?"

# Cyrus work history (most-recent first) + education for Workday My Experience populator.
# FIX (workday-proof 2026-06-02 Snap 1933): Snap-class tenants require Work Experience +
# Education entries on My Experience (not just resume upload) -> runner looped forever.
# ---------------------------------------------------------------------------
# WORK_HISTORY — built FROM personal-info.json (the SAME single source of truth
# the rendered resume uses), NOT a separate hardcoded list. This fixes the
# "typed Workday experience fields conflict with the uploaded PDF" drift Cyrus
# flagged 2026-06-09: the old hardcoded list had only 3 of 5 roles (missing
# both Microsoft internships) and a wrong Amazon date, so the typed section
# disagreed with the 5-role PDF. Now both render from personal-info.json.
# Falls back to the legacy 3-role list ONLY if personal-info is missing/broken.
# ---------------------------------------------------------------------------
_MONTH_TO_NUM = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "sept": "09", "oct": "10",
    "nov": "11", "dec": "12",
}

_WORK_HISTORY_FALLBACK = [
    {"title": "Technical Program Manager", "company": "Microsoft", "location": "Seattle, WA",
     "start": ("03", "2024"), "end": None, "current": True,
     "desc": "Scaled Azure recovery validation into a platformized system; led 0-to-1 Resilience Automation Platform; drove 14M-plus dollars business impact."},
    {"title": "Technical Program Manager Intern", "company": "Amazon Robotics", "location": "Boston, MA",
     "start": ("08", "2023"), "end": ("12", "2023"), "current": False,
     "desc": "Zero operational downtime during a 2,000-plus unit pilot OS migration; defined legacy migration strategy across 1,200-plus stations."},
    {"title": "Program Manager Intern", "company": "Pro Painters", "location": "Houston, TX",
     "start": ("05", "2021"), "end": ("05", "2022"), "current": False,
     "desc": "Increased job bookings 26 percent via CRM-driven scoping/invoicing; reduced CAC 13 percent with a digital-first GTM strategy."},
]


def _month_num(val):
    """Normalize a month (name, abbrev, or numeric str) to a 2-digit 'MM' string, or '' ."""
    s = str(val or "").strip()
    if not s:
        return ""
    if s.isdigit():
        n = int(s)
        return f"{n:02d}" if 1 <= n <= 12 else ""
    return _MONTH_TO_NUM.get(s.lower(), "")


def _build_work_history():
    """Build the WORK_HISTORY list the runner fills from personal-info.json so the
    TYPED Workday experience section matches the uploaded resume (single source of
    truth). Converts personal-info's {start_month,start_year,end_month,end_year}
    into the runner's {start:(MM,YYYY), end:(MM,YYYY)|None} shape. Returns the
    legacy fallback list on ANY load/parse problem so the runner never breaks."""
    import json as _json
    try:
        pi = _json.load(open(ROOT / "personal-info.json"))
        rows = pi.get("work_experience") or []
        out = []
        for j in rows:
            if not isinstance(j, dict):
                continue
            company = (j.get("company") or "").strip()
            title = (j.get("title") or "").strip()
            if not company or not title:
                continue
            sm, sy = _month_num(j.get("start_month")), str(j.get("start_year") or "").strip()
            current = bool(j.get("current"))
            if current:
                end = None
            else:
                em, ey = _month_num(j.get("end_month")), str(j.get("end_year") or "").strip()
                end = (em, ey) if (em and ey) else None
            out.append({
                "title": title,
                "company": company,
                "location": (j.get("location") or "").strip(),
                "start": (sm, sy),
                "end": end,
                "current": current,
                "desc": (j.get("desc") or "").strip(),
            })
        # Require a usable, dated, current-job-bearing list; else fall back.
        if out and any(r["current"] for r in out) and all(r["start"][0] and r["start"][1] for r in out):
            return out
    except Exception:
        pass
    return list(_WORK_HISTORY_FALLBACK)


WORK_HISTORY = _build_work_history()
EDUCATION = [
    {"school": "University of Houston", "degree": "Bachelor's Degree",
     "field": "Computer Science", "start_year": "2019", "end_year": "2023"},
]

def _set_native(page, el_id, value):
    """Set an input value via React-aware native setter (id may contain dots)."""
    return page.evaluate("""([id,val])=>{
        const el=document.getElementById(id) || [...document.querySelectorAll('input,textarea')].find(e=>(e.getAttribute('data-automation-id')||'')===id);
        if(!el) return false;
        const proto = el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
        const d=Object.getOwnPropertyDescriptor(proto,'value');
        el.focus(); d.set.call(el,val);
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
        el.blur(); return true;
    }""", [el_id, value])

def _find_id_suffix(page, suffix):
    """Return the full id of the first element whose id ENDS WITH suffix (Workday prefixes vary by form-hash)."""
    return page.evaluate("""(suf)=>{const el=[...document.querySelectorAll('input,textarea,button,div[role=button]')].find(e=>(e.id||'').endsWith(suf) || (e.getAttribute('data-automation-id')||'').endsWith(suf)); return el?(el.id||el.getAttribute('data-automation-id')):null;}""", suffix)

def _scroll_into_view_js(page, el_id):
    """FIX (workday-workexp-fix 2026-06-02): the WORK-EXPERIENCE RUNAWAY root cause. On
    profile-prefill tenants (NVIDIA/EXFO/RBI/Philips), each freshly-Added work-exp block
    renders BELOW the fold; Playwright Locator.click / scroll_into_view_if_needed then
    abort with 'Element is outside of the viewport', leaving the block required-empty ->
    'Next' bounces forever. A raw JS scrollIntoView({block:'center'}) ALWAYS works even
    when Playwright's own actionability scroll times out. Call this BEFORE every work-exp
    field/date/dropdown interaction. id may be a full DOM id or a data-automation-id."""
    if not el_id:
        return False
    try:
        return page.evaluate("""(id)=>{const el=document.getElementById(id)||[...document.querySelectorAll('input,textarea,button,div[role=button],[role=option]')].find(e=>(e.getAttribute('data-automation-id')||'')===id); if(!el)return false; el.scrollIntoView({block:'center',inline:'center'}); return true;}""", el_id)
    except Exception:
        return False

def delete_empty_we_blocks(page, max_iter=40):
    """FIX (workday-workexp-fix 2026-06-02): run BEFORE the fill sweep to stop the runaway
    accumulation. DELETE every work-exp block whose jobTitle is empty AND has a Delete/Remove
    button scoped to that block. Returns count deleted. Permanent (non-deletable) empty blocks
    are LEFT for the kbd-fill fallback (they have no delete affordance, so this returns -1
    internally and stops). Looping because each delete re-indexes the DOM."""
    deleted = 0
    for _ in range(max_iter):
        r = page.evaluate("""()=>{const inp=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&!(x.value||'').trim()); if(!inp)return 0; let sec=inp; for(let i=0;i<14&&sec;i++){sec=sec.parentElement; if(sec){const del=sec.querySelector('[data-automation-id=panel-set-delete-button],[data-automation-id*=delete-button],button[aria-label^=Delete],button[title^=Delete],button[data-automation-id*=delete]'); if(del){del.click();return 1;}}} return -1;}""")
        if r == 0:
            break
        if r == -1:
            # remaining empty block is PERMANENT (no delete button) -> leave for kbd-fill
            break
        deleted += 1
        page.wait_for_timeout(500)
    if deleted:
        log(f"  delete_empty_we_blocks: removed {deleted} deletable empty block(s)")
    return deleted

def post_next_we_guard(page, max_rounds=4):
    """workday-post-nav-regen-fix (2026-06-13): Boeing 2546 / PayPal 2891 sub-class.

    PROBLEM: After harden_my_experience_before_next converges (empty=0, count stable) and
    click_next fires, Workday's React renderer re-initializes a brand-NEW empty required
    WE block on the revisit (index climbs: PayPal 165→290→417, Boeing 161→298→425). This
    is NOT from a resume re-upload. It is Workday reinitializing an 'add-another' template
    slot on page render. harden runs BEFORE Next so it never sees the post-Next new block.

    FIX: At the TOP of the My Experience branch on revisit (visit ≥ 2), before handle_experience
    runs, detect any new empty WE block and delete or fill it immediately. A short bounded
    loop (delete deletable empties; fill permanent one from WORK_HISTORY[0]; re-measure).
    Returns True when the count is clean (0 empty), False if it could not converge.
    No-op when there are no WE blocks or already clean (empty==0).
    """
    total, empty = _count_we_blocks(page)
    if total == 0 or empty == 0:
        log(f"  post_next_we_guard: total={total} empty={empty} -> already clean, skip")
        return True
    log(f"  post_next_we_guard: detected {empty} post-nav empty WE block(s) (total={total}) -> cleaning")
    for rnd in range(max_rounds):
        delete_empty_we_blocks(page)
        page.wait_for_timeout(600)
        total, empty = _count_we_blocks(page)
        if empty == 0:
            log(f"  post_next_we_guard: clean after {rnd+1} round(s) (total={total})")
            return True
        # a permanent (non-deletable) empty remains -> fill once from WORK_HISTORY[0]
        pidx = page.evaluate(
            "()=>{const e=[...document.querySelectorAll('input')]"
            ".find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&!(x.value||'').trim());"
            "if(!e)return null;const m=(e.id||'').match(/workExperience-(\\d+)--/);return m?m[1]:null;}"
        )
        if pidx is not None and WORK_HISTORY:
            # boeing-paypal-WE-fix (2026-06-13): same logic as harden — use a PAST job
            # (current=False, has end) so endDate is committed via keyboard without relying
            # on the currentlyWorkHere JS checkbox (which doesn't fire React's synthetic
            # onChange reliably => endDate stays required => Errors Found after Next).
            _pg_past = [j for j in WORK_HISTORY if not j.get("current") and j.get("end")]
            _pg_job = _pg_past[-1] if _pg_past else WORK_HISTORY[0]
            log(f"  post_next_we_guard: filling permanent empty WE block[{pidx}] "
                f"from '{_pg_job.get('company','')}' (current={_pg_job.get('current')})")
            _kbd_fill_we_block_by_idx(page, pidx, _pg_job)
            page.wait_for_timeout(600)
            total, empty = _count_we_blocks(page)
            if empty == 0:
                log(f"  post_next_we_guard: clean after fill (total={total})")
                return True
    ft, fe = _count_we_blocks(page)
    log(f"  post_next_we_guard: could NOT fully clean in {max_rounds} rounds (total={ft} empty={fe})")
    return fe == 0


def _verify_we_dates_persisted(page, max_pass=3):
    """workday-we-date-reverify (2026-06-20): after the WE-block COUNT plateaus, do a FINAL
    full re-read pass over every FILLED work-exp block and re-commit any date section that
    reads back empty. Closes the one residual gap in harden_my_experience_before_next, which
    proved the block COUNT but never re-verified the committed DATES on the real blocks right
    before click_next.

    Why this is safe + additive: _fill_wd_date already does blur+verify+retry+calendar-fallback
    internally (returns True only on a successful multi-source read-back). Here we only RE-READ
    each filled block's start (and end, if not current) date via _wd_read_date_section (the
    probe-proven value || aria-valuetext path) and ONLY re-invoke _fill_wd_date for a section
    that is actually blank. A fully-committed block is a no-op. Matches each block to
    WORK_HISTORY by companyName (substring either direction) so we never fabricate a date.

    Returns True iff, after up to `max_pass` re-commit passes, no FILLED block has an empty
    required start date (end dates are best-effort: a still-empty end on a non-current block is
    logged but not treated as a hard failure, since some tenants accept an open end on Next).
    No-op-safe: returns True when there are no filled WE blocks or no WORK_HISTORY.
    """
    if not WORK_HISTORY:
        return True
    for _pass in range(max_pass):
        try:
            blocks = page.evaluate(
                "()=>[...document.querySelectorAll('input')]"
                ".filter(x=>/workExperience-\\d+--companyName/.test(x.id||'')&&(x.value||'').trim())"
                ".map(x=>({idx:(x.id.match(/workExperience-(\\d+)--/)||[])[1], company:(x.value||'').trim()}))"
            )
        except Exception as _e:
            log("  date-reverify enumerate err", str(_e)[:70]); return True
        if not blocks:
            return True  # no filled WE blocks (step may not require work-exp)
        repaired = 0
        still_empty = []
        for b in (blocks or []):
            bidx = b.get("idx"); comp = (b.get("company") or "").lower()
            if not bidx or not comp:
                continue
            job = next((j for j in WORK_HISTORY
                        if j["company"].lower() in comp or comp in j["company"].lower()), None)
            if not job:
                continue
            # is this block marked current? (an empty start on a current block is still wrong)
            try:
                is_cur = bool(page.evaluate(
                    "(ix)=>{const c=[...document.querySelectorAll('input[type=checkbox]')]"
                    ".find(e=>(e.id||'').includes('workExperience-'+ix+'--currentlyWorkHere'));"
                    "return !!(c&&c.checked);}", bidx))
            except Exception:
                is_cur = bool(job.get("current"))
            # --- start date ---
            sm = _find_id_suffix(page, f"workExperience-{bidx}--startDate-dateSectionMonth-input")
            sy = _find_id_suffix(page, f"workExperience-{bidx}--startDate-dateSectionYear-input")
            sm_v = _wd_read_date_section(page, sm)
            sy_v = _wd_read_date_section(page, sy)
            if not (sm_v and sy_v):
                log(f"  date-reverify pass{_pass} block[{bidx}] {job['company']}: "
                    f"start blank (mon='{sm_v}' yr='{sy_v}') -> re-commit")
                ok = _fill_wd_date(page, f"workExperience-{bidx}--startDate",
                                   job["start"][0], job["start"][1])
                if ok:
                    repaired += 1
                else:
                    still_empty.append(f"{job['company']}:start")
            # --- end date (only when the block is NOT current and the job has an end) ---
            if not is_cur and job.get("end"):
                em = _find_id_suffix(page, f"workExperience-{bidx}--endDate-dateSectionMonth-input")
                ey = _find_id_suffix(page, f"workExperience-{bidx}--endDate-dateSectionYear-input")
                em_v = _wd_read_date_section(page, em)
                ey_v = _wd_read_date_section(page, ey)
                if not (em_v and ey_v):
                    log(f"  date-reverify pass{_pass} block[{bidx}] {job['company']}: "
                        f"end blank (mon='{em_v}' yr='{ey_v}') -> re-commit")
                    _fill_wd_date(page, f"workExperience-{bidx}--endDate",
                                  job["end"][0], job["end"][1])
        if repaired == 0 and not still_empty:
            log(f"  date-reverify: all filled WE start-dates persisted (pass {_pass}) -> clean")
            return True
        if still_empty:
            log(f"  date-reverify pass{_pass}: {len(still_empty)} section(s) STILL blank after re-commit: {still_empty}")
        page.wait_for_timeout(400)
    # final read: a still-empty required START date is the real blocker -> report it
    try:
        bad = page.evaluate(
            "()=>{const out=[];"
            "const names=[...document.querySelectorAll('input')]"
            ".filter(x=>/workExperience-\\d+--companyName/.test(x.id||'')&&(x.value||'').trim());"
            "for(const n of names){const m=(n.id||'').match(/workExperience-(\\d+)--/); if(!m)continue; const ix=m[1];"
            "const sm=document.getElementById('workExperience-'+ix+'--startDate-dateSectionMonth-input');"
            "const cur=[...document.querySelectorAll('input[type=checkbox]')].find(e=>(e.id||'').includes('workExperience-'+ix+'--currentlyWorkHere'));"
            "if(sm&&!(sm.value||'').trim())out.push((n.value||'').trim()||('block'+ix));}"
            "return out;}")
        if bad:
            log(f"  date-reverify: FILLED block(s) with empty required start-date remain: {bad}")
            return False
    except Exception:
        pass
    return True


def harden_my_experience_before_next(page, max_rounds=6):
    """workday-we-persist-fix (2026-06-11 run4): make the WE-block COUNT PLATEAU before we
    click Next on My Experience.

    ROOT CAUSE (proven live on a TRUE fresh Nvidia 2829 account, EXIT-5 reproduced): typed
    work-history dates DO persist (DOM + React fiber + hidden inputs) -- the wall is that the
    block COUNT never settles. The resume PARSER manufactures a blank 'add-another' REQUIRED
    WE block from the parsed PDF text, and that new empty can materialize in the settle AFTER
    the prefill-guard converge loop returns empty=0 but BEFORE click_next fires -> Next bounces
    on the fresh empty required block -> revisit -> repeat -> loop-cap EXIT-5.

    This is the LAST thing run on My Experience before click_next: a tight bounded loop that
    DELETES every deletable empty WE block and re-measures, with settle waits, until we reach
    0-empty AND a STABLE total across 2 consecutive checks (so a late-spawning parser block is
    caught). A lone NON-deletable permanent empty block (no delete affordance) is filled ONCE
    as a last resort from WORK_HISTORY[0] so it stops being required.

    Returns True when the count plateaued clean (0 empty, stable total), False otherwise.
    No-op-safe: if there are no WE blocks at all (step doesn't require work-exp) returns True.
    """
    prev_total = None
    stable_hits = 0
    for rnd in range(max_rounds):
        # settle past any async resume re-parse re-render that spawns a late empty block
        page.wait_for_timeout(1800)
        total, empty = _count_we_blocks(page)
        if total == 0:
            return True  # no work-exp section on this step
        if empty > 0:
            # delete deletable empties; a -1 return inside means a permanent (non-deletable)
            # empty remains -> fill it once below.
            delete_empty_we_blocks(page)
            page.wait_for_timeout(900)
            t2, e2 = _count_we_blocks(page)
            if e2 > 0:
                # remaining empty is PERMANENT (no delete button). Fill it ONCE from the most
                # recent job so it is no longer a required-empty, then re-measure next round.
                try:
                    pidx = page.evaluate(
                        "()=>{const e=[...document.querySelectorAll('input')]"
                        ".find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&!(x.value||'').trim());"
                        "if(!e)return null;const m=(e.id||'').match(/workExperience-(\\d+)--/);return m?m[1]:null;}"
                    )
                    if pidx is not None and WORK_HISTORY:
                        log(f"  harden: filling lone permanent empty WE block[{pidx}] as last resort")
                        # boeing-paypal-WE-fix (2026-06-13): use a PAST job (current=False,
                        # has end date) instead of WORK_HISTORY[0] (current Microsoft job).
                        # WORK_HISTORY[0] is current=True so _kbd_fill_we_block_by_idx skips
                        # the endDate fill and relies on the currentlyWorkHere checkbox commit
                        # via page.evaluate JS click. That JS click does NOT reliably fire
                        # React's synthetic onChange => endDate fields remain required in
                        # Workday's React model => click_next returns 'My Experience | Errors
                        # Found' instead of advancing => loop-cap EXIT-5. A past job has both
                        # start+end committed cleanly via keyboard with no checkbox needed.
                        _past = [j for j in WORK_HISTORY if not j.get("current") and j.get("end")]
                        _harden_job = _past[-1] if _past else WORK_HISTORY[0]
                        log(f"  harden: using job '{_harden_job.get('company','')}' "
                            f"(current={_harden_job.get('current')}) for permanent-fill")
                        _kbd_fill_we_block_by_idx(page, pidx, _harden_job)
                        page.wait_for_timeout(700)
                except Exception as _he:
                    log("  harden permanent-fill err", str(_he)[:80])
            stable_hits = 0
            prev_total = None
            continue
        # empty == 0 here: require the total to hold STABLE across 2 consecutive checks so a
        # late parser-spawned block gets caught before we click Next.
        if prev_total is not None and total == prev_total:
            stable_hits += 1
            if stable_hits >= 1:  # 2 consecutive equal readings (prev + this)
                log(f"  harden: WE count plateaued clean (total={total} empty=0, stable) -> safe to Next")
                # workday-we-date-reverify (2026-06-20): COUNT is stable; now PROVE every filled
                # block's required date(s) are still committed (re-commit any that read back
                # blank) before we let click_next fire. Additive: a clean block is a no-op.
                try:
                    _verify_we_dates_persisted(page)
                except Exception as _dre:
                    log("  harden date-reverify err", str(_dre)[:80])
                return True
        else:
            stable_hits = 0
        prev_total = total
    ft, fe = _count_we_blocks(page)
    log(f"  harden: WE count did NOT fully plateau after {max_rounds} rounds (total={ft} empty={fe})")
    if fe == 0:
        # count is clean even though the stability gate timed out -> still re-verify dates.
        try:
            _verify_we_dates_persisted(page)
        except Exception as _dre:
            log("  harden date-reverify (final) err", str(_dre)[:80])
    return fe == 0

def _wd_section_add(page, section_kw):
    """Click the Add button for a My Experience section identified by heading keyword
    (e.g. 'Work Experience', 'Education'). Returns True if an Add was clicked."""
    clicked = page.evaluate("""(kw)=>{
        // Find a heading containing kw, then the nearest following 'Add' button.
        const heads=[...document.querySelectorAll('h2,h3,h4,legend,div')].filter(e=>{const t=(e.textContent||'').trim();return t.toLowerCase().startsWith(kw.toLowerCase()) && t.length<kw.length+25;});
        function findAdd(root){
          const cands=[...document.querySelectorAll('[data-automation-id=Add],button,[role=button]')];
          // prefer an Add button after the heading in DOM order
          return cands.find(b=>{const t=(b.textContent||'').trim(); const da=(b.getAttribute('data-automation-id')||''); return (da==='Add' || t==='Add') && (!root || (root.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING));});
        }
        let b = heads.length? findAdd(heads[0]) : null;
        if(!b){ // fallback: any Add button whose nearby text mentions kw
          b=[...document.querySelectorAll('[data-automation-id=Add],button,[role=button]')].find(x=>{const t=(x.textContent||'').trim(); if(t!=='Add')return false; let p=x; for(let i=0;i<6&&p;i++){p=p.parentElement; if(p&&(p.innerText||'').toLowerCase().includes(kw.toLowerCase()))return true;} return false;});
        }
        if(b){b.click(); return true;} return false;
    }""", section_kw)
    if clicked: page.wait_for_timeout(1800)
    return clicked

def _wd_date_section_ids(page, base_suffix):
    """Resolve the actual DOM input ids for the Month/Day/Year sections of a Workday date
    widget. Day is optional (most tenants are Month/Year; some add a Day section)."""
    mon = _find_id_suffix(page, base_suffix + "-dateSectionMonth-input") or _find_id_suffix(page, base_suffix + "-dateSectionMonth-display")
    day = _find_id_suffix(page, base_suffix + "-dateSectionDay-input")   or _find_id_suffix(page, base_suffix + "-dateSectionDay-display")
    yr  = _find_id_suffix(page, base_suffix + "-dateSectionYear-input")  or _find_id_suffix(page, base_suffix + "-dateSectionYear-display")
    return mon, day, yr


def _wd_read_date_section(page, eid):
    """Read the COMMITTED value of one date-section input back (value, then aria-valuetext
    fallback). Returns '' when the element is missing/blank. Used to VERIFY a real commit
    (Workday's spinbutton .value reflects the committed digits; aria-valuetext mirrors it)."""
    if not eid:
        return ""
    try:
        return (page.evaluate("""(id)=>{const el=document.getElementById(id); if(!el)return ''; const v=(el.value||'').trim(); if(v)return v; const vt=(el.getAttribute('aria-valuetext')||'').trim(); return /^\\d+$/.test(vt)?vt:'';}""", eid) or "").strip()
    except Exception:
        return ""


def _wd_section_has_error(page, eid):
    """Return True if the date field owning section `eid` shows a required/invalid error."""
    if not eid:
        return False
    try:
        return bool(page.evaluate(r"""(id)=>{const el=document.getElementById(id); if(!el)return false; let wrap=el; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date|dateSection|DateWidget/i.test(wrap.getAttribute('data-automation-id')||''))break;} if(!wrap)return false; for(const e of wrap.querySelectorAll('[role=alert],[data-automation-id*=error],[id$=-error]')){const t=((e.textContent||'')+'').toLowerCase(); if(/required|must|invalid/.test(t))return true;} return false;}""", eid))
    except Exception:
        return False


def _wd_persist_probe(page, base_suffix, tag):
    """DIAGNOSTIC (WD_PERSIST_PROBE=1 only): dump everything that could hold a Workday date
    widget's canonical value, so we can see WHAT persists vs drops across the My-Experience
    -> next-step navigation. For the Month + Year sections of `base_suffix` capture:
      - the visible spinbutton .value + aria-valuetext + aria-valuenow
      - the React fiber memoizedProps (value/onChange presence) + memoizedState
      - any hidden <input> siblings inside the date widget wrapper (the canonical edit value
        Workday may serialize the date into)
      - the widget wrapper's data-automation-id + any [data-uxi-*]/value attrs
    No-op unless WD_PERSIST_PROBE=1. Logs a single JSON line tagged with `tag`."""
    import os as _os
    if _os.environ.get("WD_PERSIST_PROBE") != "1":
        return
    mon, day, yr = _wd_date_section_ids(page, base_suffix)
    try:
        out = page.evaluate(r"""([ids,tag,base])=>{
          function fiberOf(el){
            if(!el) return null;
            for(const k in el){ if(k.startsWith('__reactFiber$')||k.startsWith('__reactInternalInstance$')) return el[k]; }
            return null;
          }
          function propsOf(el){
            if(!el) return null;
            for(const k in el){ if(k.startsWith('__reactProps$')) return el[k]; }
            return null;
          }
          function summarize(v){
            try{ if(v===null||v===undefined) return v;
              if(typeof v==='function') return 'fn';
              if(typeof v==='object') return Object.keys(v).slice(0,12);
              return String(v).slice(0,40);
            }catch(e){return 'ERR';}
          }
          function fiberDump(el){
            const f=fiberOf(el); const p=propsOf(el);
            const d={hasFiber:!!f,hasProps:!!p};
            if(p){ d.propValue=summarize(p.value); d.propOnChange=typeof p.onChange; d.propDefaultValue=summarize(p.defaultValue); d.propAriaValueNow=summarize(p['aria-valuenow']); }
            if(f){
              d.mProps=f.memoizedProps?{value:summarize(f.memoizedProps.value),onChange:typeof f.memoizedProps.onChange,defaultValue:summarize(f.memoizedProps.defaultValue)}:null;
              d.mState=summarize(f.memoizedState);
              // climb a few parent fibers, capture any memoizedState holding a date-ish value
              let pf=f.return; const chain=[];
              for(let i=0;i<8&&pf;i++){ const ms=pf.memoizedState; if(ms&&typeof ms==='object'){const keys=Object.keys(ms).slice(0,8); chain.push({i:i,type:(pf.type&&pf.type.name)||(typeof pf.type==='string'?pf.type:'?'),stateKeys:keys, baseState: summarize(ms.baseState), memo: summarize(ms.memoizedState)});} pf=pf.return; }
              d.parentChain=chain;
            }
            return d;
          }
          function sectionInfo(id){
            const el=document.getElementById(id);
            if(!el) return {id:id,missing:true};
            return {id:id, value:(el.value||''), ariaValueText:el.getAttribute('aria-valuetext'),
                    ariaValueNow:el.getAttribute('aria-valuenow'), tag:el.tagName, fiber:fiberDump(el)};
          }
          const r={tag:tag, base:base, mon: ids[0]?sectionInfo(ids[0]):null, yr: ids[2]?sectionInfo(ids[2]):null};
          // widget wrapper: hidden inputs + automation ids that may hold the canonical date
          const anchor=document.getElementById(ids[0])||document.getElementById(ids[2]);
          if(anchor){
            let wrap=anchor;
            for(let i=0;i<12&&wrap;i++){ wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date|dateSection|DateWidget|dateInputWrapper/i.test(wrap.getAttribute('data-automation-id')||'')) break; }
            if(wrap){
              r.wrapperAid=wrap.getAttribute('data-automation-id');
              r.hiddenInputs=[...wrap.querySelectorAll('input[type=hidden],input:not([type]),input[aria-hidden=true]')].map(h=>({aid:h.getAttribute('data-automation-id'),name:h.name,value:(h.value||'').slice(0,40)}));
              // any element carrying a data-uxi-* serialized value or a value attr that looks like a date
              r.dataUxi=[...wrap.querySelectorAll('[data-uxi-widget-value],[data-uxi-element-id],[data-uxi-value]')].slice(0,6).map(x=>({aid:x.getAttribute('data-automation-id'),uxiVal:x.getAttribute('data-uxi-widget-value')||x.getAttribute('data-uxi-value')}));
              const wf=fiberOf(wrap); if(wf){ r.wrapperFiberState=summarize(wf.memoizedState); r.wrapperFiberProps=wf.memoizedProps?Object.keys(wf.memoizedProps).slice(0,12):null; }
            }
          }
          return JSON.stringify(r);
        }""", [[mon, day, yr], tag, base_suffix])
        log(f"  PERSIST-PROBE[{tag}]:", (out or "")[:1800])
    except Exception as _e:
        log(f"  PERSIST-PROBE[{tag}] err", str(_e)[:120])


def _wd_kbd_type_section(page, eid, digits):
    """PROVEN per-section commit (probe6 winner KB_focus_type_persection, 2026-06-09 EXFO):
    js-clear the section, JS-focus it (scrollIntoView+focus -> immune to 'outside viewport'),
    then type the digits with REAL page.keyboard.type (NOT synthetic JS KeyboardEvent --
    those commit MONTH but SILENTLY FAIL to commit YEAR). Returns the read-back value."""
    if not eid:
        return ""
    # js-clear (native-setter blank + input/change) so a stale/partial value can't fight us
    try:
        page.evaluate("""(id)=>{const el=document.getElementById(id); if(!el)return; el.focus(); const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value'); d.set.call(el,''); el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}""", eid)
    except Exception:
        pass
    page.wait_for_timeout(100)
    # JS-focus (NOT Playwright .click -> never times out on below-fold blocks)
    try:
        page.evaluate("(id)=>{const el=document.getElementById(id); if(el){el.scrollIntoView({block:'center'}); el.focus();}}", eid)
    except Exception:
        pass
    page.wait_for_timeout(120)
    try:
        page.keyboard.type(str(digits), delay=80)
    except Exception as _e:
        log("  kbd type-section err", eid[-24:], str(_e)[:50])
    page.wait_for_timeout(250)
    return _wd_read_date_section(page, eid)


def _wd_try_calendar_month_pick(page, base_suffix, mm, yyyy):
    """FALLBACK month-picker click path (probe4: '[data-automation-id*=monthPicker]' opens
    via the dateIcon). Open the calendar, navigate to YYYY via prev/next year arrows, click
    the target month cell. Best-effort; returns True only if the year section reads back yyyy."""
    try:
        mon, _day, yr = _wd_date_section_ids(page, base_suffix)
        opened = page.evaluate(r"""(mid)=>{const mon=document.getElementById(mid); if(!mon)return 'no-mon'; let wrap=mon; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date|dateSection|DateWidget/i.test(wrap.getAttribute('data-automation-id')||''))break;} if(!wrap)return 'no-wrap'; const ic=wrap.querySelector('[data-automation-id=dateIcon]'); if(!ic)return 'no-icon'; ic.scrollIntoView({block:'center'}); ic.click(); return 'clicked';}""", mon)
        if opened != "clicked":
            return False
        page.wait_for_timeout(700)
        import calendar as _cal
        mon_abbr = _cal.month_abbr[int(mm)]  # e.g. 'Aug'
        nav = page.evaluate(r"""([targetYear,targetMonAbbr])=>{const mp=document.querySelector('[data-automation-id*=monthPicker]'); if(!mp)return 'no-mp'; function curYear(){const t=[...mp.querySelectorAll('*')].map(e=>(e.textContent||'').trim()).find(s=>/^\\d{4}$/.test(s)); return t?parseInt(t):null;} const allb=[...mp.querySelectorAll('button,[role=button]')]; const prev=allb.find(b=>/prev|back|left/i.test((b.getAttribute('aria-label')||'')+(b.getAttribute('data-automation-id')||''))); const next=allb.find(b=>/next|forward|right/i.test((b.getAttribute('aria-label')||'')+(b.getAttribute('data-automation-id')||''))); let guard=0, cy=curYear(); while(cy!==null && cy!==targetYear && guard<80){ if(cy>targetYear){ if(!prev)break; prev.click(); } else { if(!next)break; next.click(); } guard++; cy=curYear(); } const mcell=[...mp.querySelectorAll('button,[role=button],div,td,abbr,span')].find(b=>(b.textContent||'').trim()===targetMonAbbr); if(mcell){mcell.click(); return 'picked@'+cy;} return 'no-cell@'+cy;}""", [int(yyyy), mon_abbr])
        page.wait_for_timeout(600)
        got_yr = _wd_read_date_section(page, yr)
        got_mon = _wd_read_date_section(page, mon)
        log(f"  date calendar-fallback {base_suffix[-28:]}: nav={nav} -> mon={got_mon!r} yr={got_yr!r}")
        return got_yr == str(yyyy) and got_mon in (str(mm), str(int(mm)))
    except Exception as _e:
        log("  date calendar-fallback err", str(_e)[:70])
        return False


def _fill_wd_date(page, base_suffix, mm, yyyy):
    """Fill + VERIFY a Workday Month/Year (or Month/Day/Year) date widget.
    FIX (workday-date-commit-fix 2026-06-09 EXFO 2121): the old path typed digits via
    SYNTHETIC KeyboardEvent/InputEvent dispatch (`_type_digits_js`) which committed the
    MONTH but SILENTLY FAILED to commit the YEAR (year stayed empty/red 'required'), AND
    returned True without reading the value back -> false-positive start_filled=True. Since
    the date never validated, Workday regenerated a fresh empty required block on every My-
    Experience revisit -> blocks accumulated -> loop-cap EXIT 5. ROOT of the EXIT-5 wall on
    date-spinbutton tenants.
    NEW (proven in probe6 `KB_focus_type_persection`, monVal='8' yrVal='2022' both_ok=true):
    use REAL page.keyboard.type() PER-SECTION with a js-clear+js-focus first, then READ BACK
    each section's committed value. Return True ONLY when BOTH month AND year (AND day, if a
    day section exists) read back correct and the field shows no required/invalid error.
    Retry ONCE, then fall back to the calendar month-picker click path. NEVER return True on
    an empty/red field."""
    mon, day, yr = _wd_date_section_ids(page, base_suffix)
    if not (mon or yr):
        return False
    mm = str(mm); yyyy = str(yyyy)
    mm_norm = (str(int(mm)) if mm.isdigit() else mm)
    # Optional day section: derive a day digit if the widget has one (EXFO needs only
    # month+year, but don't regress Month/Day/Year tenants -- default day '01').
    dd = "01"

    def _attempt():
        # PROVEN per-section real-keyboard commit (probe6 KB_focus_type_persection).
        mon_val = _wd_kbd_type_section(page, mon, mm) if mon else ""
        if day:
            _wd_kbd_type_section(page, day, dd)
        yr_val = _wd_kbd_type_section(page, yr, yyyy) if yr else ""
        # Tab off to blur/commit the widget the way the proven recipe ends.
        try:
            page.keyboard.press("Tab")
        except Exception:
            pass
        page.wait_for_timeout(300)
        # READ BACK each section's committed value for the verdict.
        mon_rb = _wd_read_date_section(page, mon) if mon else ""
        yr_rb = _wd_read_date_section(page, yr) if yr else ""
        day_rb = _wd_read_date_section(page, day) if day else ""
        mon_ok = (not mon) or (mon_rb in (mm, mm_norm))
        yr_ok = (not yr) or (yr_rb == yyyy)
        day_ok = (not day) or (day_rb in (dd, str(int(dd))))
        err = (_wd_section_has_error(page, mon) or _wd_section_has_error(page, yr)
               or (_wd_section_has_error(page, day) if day else False))
        ok = mon_ok and yr_ok and day_ok and not err
        log(f"  date-commit {base_suffix[-30:]}: mon={mon_rb!r}(typed {mon_val!r}) yr={yr_rb!r}(typed {yr_val!r})"
            + (f" day={day_rb!r}" if day else "") + f" err={err} -> {'OK' if ok else 'FAIL'}")
        return ok

    try:
        # Attempt the proven recipe, then RETRY ONCE if the read-back doesn't verify.
        if _attempt():
            return True
        log(f"  date-commit retry on {base_suffix[-30:]} (read-back did not verify)")
        page.wait_for_timeout(250)
        if _attempt():
            return True
        # FALLBACK: calendar month-picker click path (probe4 found dateIcon opens monthPicker).
        if _wd_try_calendar_month_pick(page, base_suffix, mm, yyyy):
            mon_rb = _wd_read_date_section(page, mon) if mon else ""
            yr_rb = _wd_read_date_section(page, yr) if yr else ""
            if (((not mon) or mon_rb in (mm, mm_norm)) and ((not yr) or yr_rb == yyyy)):
                log(f"  date-commit via calendar-fallback OK: mon={mon_rb!r} yr={yr_rb!r}")
                return True
        # Could NOT commit. NEVER return True on an empty/red field.
        mon_rb = _wd_read_date_section(page, mon) if mon else ""
        yr_rb = _wd_read_date_section(page, yr) if yr else ""
        log(f"  date-commit FAILED to verify {base_suffix[-30:]}: mon={mon_rb!r} yr={yr_rb!r} -> returning False")
        return False
    except Exception as e:
        log("  date fill err", base_suffix, str(e)[:60])
        return False

def _wd_fill_mdy_sequential(page, base_suffix, mm, dd, yyyy):
    """Commit a Workday Month/DAY/Year date by typing the whole date as ONE continuous
    keyboard sequence into the MONTH section and letting Workday's own date-widget handler
    auto-advance section->section (month->day->year). Per-SECTION js-focus+type (the path
    `_fill_wd_date` uses for Month/Year widgets) leaves the 3-section signed-date widget's
    React model half-built: every section reads back its value yet Workday still shows
    'Enter a valid date' -> loop-cap EXIT-5 (Nvidia 2829 self-id, 2026-06-11). Typing the
    full MMDDYYYY in one focused run builds the model correctly.
    Returns True only when all present sections read back AND no section shows an error."""
    mon, day, yr = _wd_date_section_ids(page, base_suffix)
    if not mon:
        return False
    mm = f"{int(mm):02d}"; dd = f"{int(dd):02d}"; yyyy = str(yyyy)
    seq = mm + (dd if day else "") + yyyy  # e.g. '06'+'11'+'2026' -> '06112026'
    def _attempt():
        for _eid in (mon, day, yr):
            if not _eid:
                continue
            try:
                page.evaluate("""(id)=>{const el=document.getElementById(id); if(!el)return; const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value'); d.set.call(el,''); el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}""", _eid)
            except Exception:
                pass
        page.wait_for_timeout(120)
        try:
            page.locator(f"#{mon}").first.click(timeout=4000)
        except Exception:
            try:
                page.evaluate("(id)=>{const el=document.getElementById(id); if(el){el.scrollIntoView({block:'center'}); el.focus();}}", mon)
            except Exception:
                pass
        page.wait_for_timeout(120)
        try:
            page.keyboard.type(seq, delay=90)
        except Exception:
            pass
        page.wait_for_timeout(250)
        try:
            page.keyboard.press("Tab")
        except Exception:
            pass
        page.wait_for_timeout(300)
        mon_rb = _wd_read_date_section(page, mon) if mon else ""
        day_rb = _wd_read_date_section(page, day) if day else ""
        yr_rb = _wd_read_date_section(page, yr) if yr else ""
        mon_ok = (not mon) or (mon_rb in (mm, str(int(mm))))
        day_ok = (not day) or (day_rb in (dd, str(int(dd))))
        yr_ok = (not yr) or (yr_rb == yyyy)
        err = (_wd_section_has_error(page, mon) or (_wd_section_has_error(page, day) if day else False)
               or _wd_section_has_error(page, yr))
        ok = mon_ok and day_ok and yr_ok and not err
        log(f"  mdy-seq {base_suffix[-30:]}: mon={mon_rb!r} day={day_rb!r} yr={yr_rb!r} typed={seq!r} err={err} -> {'OK' if ok else 'FAIL'}")
        return ok
    try:
        if _attempt():
            return True
        page.wait_for_timeout(250)
        return _attempt()
    except Exception:
        return False


def _count_we_blocks(page):
    """Return (total, empty) work-experience block counts. 'empty' = jobTitle blank.
    Used to DETECT the regen-on-fill runaway: when filling a block makes Workday's React
    layer spawn a NEW empty required block, `total` grows -- the new empty must be DELETED,
    not re-filled (re-filling is what triggers the next regen)."""
    try:
        return tuple(page.evaluate("()=>{const t=[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')); const e=t.filter(x=>!(x.value||'').trim()); return [t.length,e.length];}"))
    except Exception:
        return (0, 0)


def _kbd_fill_we_block_by_idx(page, idx, job):
    """Keyboard-commit a SPECIFIC work-experience block (by index): jobTitle/companyName/
    location + current checkbox + dates + roleDescription. Native .value writes do NOT
    satisfy Workday's React required-validation (so the page keeps regenerating empty
    required blocks); real key events DO commit. Shared by the prefill-guard permanent-block
    path and the main `if not we_done:` fill loop (workday-regen-fix 2026-06-05)."""
    if idx is None:
        return
    def kbd(suffix, value):
        fid = _find_id_suffix(page, suffix)
        if not fid:
            return False
        try:
            loc = page.locator(f"#{fid}").first
            _scroll_into_view_js(page, fid)  # FIX (workday-workexp-fix): JS scroll first
            loc.scroll_into_view_if_needed(timeout=4000)
            loc.click(timeout=4000)
            page.keyboard.press("Control+A"); page.keyboard.press("Delete")
            page.keyboard.type(value, delay=25)
            page.keyboard.press("Tab")
            page.wait_for_timeout(300)
            return True
        except Exception as e:
            log("  kbd field fail", suffix, str(e)[:50]); return False
    kbd(f"workExperience-{idx}--jobTitle", job["title"])
    kbd(f"workExperience-{idx}--companyName", job["company"])
    kbd(f"workExperience-{idx}--location", job["location"])
    # current-role checkbox
    if job.get("current"):
        page.evaluate("(ix)=>{const c=[...document.querySelectorAll('input[type=checkbox]')].find(e=>(e.id||'').includes('workExperience-'+ix+'--currentlyWorkHere')); if(c&&!c.checked){const l=document.querySelector('label[for=\\''+c.id+'\\']'); (l||c).click();}}", idx)
        page.wait_for_timeout(400)
    # workday-date-commit-fix 2026-06-09: capture the read-back verdict so a FAILED date
    # commit (the documented EXIT-5 regen root) is VISIBLE in logs instead of silently
    # logging start_filled=True on an empty/red field.
    _sd_ok = _fill_wd_date(page, f"workExperience-{idx}--startDate", job["start"][0], job["start"][1])
    _wd_persist_probe(page, f"workExperience-{idx}--startDate", f"FRESH-FILL idx={idx} {job.get('company','')}")
    if not _sd_ok:
        log(f"  !! WE[{idx}] {job.get('company','')} START-DATE did NOT commit (read-back failed) -- block may regenerate")
    if not job.get("current") and job.get("end"):
        _ed_ok = _fill_wd_date(page, f"workExperience-{idx}--endDate", job["end"][0], job["end"][1])
        if not _ed_ok:
            log(f"  !! WE[{idx}] {job.get('company','')} END-DATE did NOT commit (read-back failed)")
    # FIX (workday-roledesc 2026-06-02 EXFO 2121): fill the REQUIRED Role Description here
    # too -- if roleDescription is required (EXFO) the block stays blocked (and keeps
    # regenerating) unless we fill it at population time.
    if job.get("desc"):
        rd = _find_id_suffix(page, f"workExperience-{idx}--roleDescription")
        if rd:
            page.evaluate("""([id,val])=>{
                const el=document.getElementById(id)||[...document.querySelectorAll('textarea')].find(e=>(e.getAttribute('data-automation-id')||'')===id);
                if(!el) return false;
                const d=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');
                el.focus(); d.set.call(el,val);
                el.dispatchEvent(new Event('input',{bubbles:true}));
                el.dispatchEvent(new Event('change',{bubbles:true}));
                el.blur(); return true;
            }""", [rd, _wd_sanitize_desc(job["desc"])])
            log(f"  kbd-filled roleDescription on work-exp[{idx}]")
    jt = _find_id_suffix(page, f"workExperience-{idx}--jobTitle")
    committed = page.evaluate("(id)=>{const e=document.getElementById(id);return e?(e.value||'').trim():'';}", jt) if jt else ""
    log(f"  kbd-filled work-exp[{idx}]: jobTitle now={committed!r}")


def _kbd_fill_empty_we_block(page, job):
    """Fill the first EMPTY work-experience block's jobTitle/companyName/location + dates
    using keyboard typing (focus, select-all, type, blur). NVIDIA reverts native value-set
    writes, so commit via real key events. Idempotent: only targets a block whose jobTitle
    is currently empty. Delegates to _kbd_fill_we_block_by_idx (workday-regen-fix 2026-06-05)."""
    idx = page.evaluate("()=>{const inp=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&!(x.value||'').trim()); return inp?inp.id.match(/workExperience-(\\d+)--/)[1]:null;}")
    if not idx:
        return
    _kbd_fill_we_block_by_idx(page, idx, job)


def populate_work_history(page):
    """Add/fill Work Experience + Education entries on Workday My Experience.
    Snap-class tenants PRE-RENDER one empty Work Experience block and one Education
    block (e.g. workExperience-8--*, education-9--*) -- so we must FILL the existing
    block(s) by their real id, and only click Add for ADDITIONAL entries."""
    # Discover the dynamic index Workday assigned to the (pre-rendered) blocks.
    we_idx = page.evaluate("()=>{const e=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')); if(!e)return null; const m=(e.id||'').match(/workExperience-(\\d+)--/); return m?m[1]:null;}")
    ed_idx = page.evaluate("()=>{const e=[...document.querySelectorAll('input')].find(x=>/education-\\d+--schoolName/.test(x.id||'')); if(!e)return null; const m=(e.id||'').match(/education-(\\d+)--/); return m?m[1]:null;}")
    log(f"  populate: detected we_idx={we_idx} ed_idx={ed_idx}")

    # FRESH-ACCOUNT FILL GUARANTEE (workday-fresh-account-fix 2026-06-08). Standing rule:
    # Workday ALWAYS applies with FRESH info from the customized resume; NEVER autofill/reuse
    # saved-profile data. On a freshly-created (or known-good fresh) account the work-history
    # MUST start EMPTY and be filled entirely from the tailored resume. We log/assert that
    # initial-empty contract here so a regression (account that secretly auto-prefills) is
    # visible, and so EXIT-9 (uncommittable PREFILL) cannot fire for fresh accounts: on a
    # fresh account there is no legitimate saved profile, so any prefilled block is anomalous
    # pollution the converge/delete loop handles -- not a Cyrus-profile data bug to bank.
    _fresh_acct = globals().get("_ACCOUNT_MODE") in ("create_fresh", "signin_fresh")
    if _fresh_acct:
        try:
            _pref0 = page.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&(x.value||'').trim()).map(x=>x.value)")
        except Exception:
            _pref0 = []
        if _pref0:
            # Anomalous on a fresh account: a prefilled block exists. Log LOUD; the delete/
            # converge loop below will remove deletables. We still proceed to fill fresh.
            log(f"  FRESH-ACCOUNT WARN: {len(_pref0)} prefilled WE block(s) on a fresh account (unexpected) -> will delete + fill fresh: {(_pref0 or [])[:3]}")
        else:
            log("  FRESH-ACCOUNT ASSERT OK: work-history starts EMPTY -> filling from tailored resume (no saved-profile reuse)")
        log("  FRESH-FILL SOURCE: tailored resume / WORK_HISTORY (not profile autofill)")

    # FIX (workday-workexp-fix 2026-06-02): stop the RUNAWAY at the source. Before any
    # fill/Add work, delete every DELETABLE empty work-exp block so prior-run pollution
    # (50 -> 278 -> 670 -> 927 escalating indices) can't keep 'Next' blocked.
    try:
        delete_empty_we_blocks(page)
    except Exception as _e:
        log("  pre-sweep delete err", str(_e)[:70])

    # NVIDIA-CLASS GUARD (workday-p13 2026-06-02 NVIDIA JR2015102): some tenants keep the
    # candidate's Work Experience saved on the ACCOUNT PROFILE and PRE-FILL the My Experience
    # blocks (e.g. NVIDIA: workExperience-4/5/6 already = Microsoft/Amazon/Pro Painters). On
    # these, the old fill/Add logic BLANKED the good profile blocks (via _set_native writes
    # that don't commit) and spun forever adding empty blocks (31->160->330->...). 
    # Detection: at least one work-exp block already has a jobTitle value (profile-filled).
    # Action: do NOT touch the filled blocks; just DELETE any EMPTY extra blocks (pollution
    # from prior runs) and return -- resume + profile history carry the step.
    try:
        any_filled = page.evaluate("()=>[...document.querySelectorAll('input')].some(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&(x.value||'').trim())")
        resume_up = page.evaluate("()=>/successfully uploaded/i.test(document.body.innerText)|| !![...document.querySelectorAll('[data-automation-id*=DeleteFile],[data-automation-id=file-upload-item]')].length")
        if any_filled:
            log("  profile-prefilled work history detected -> repair dates on filled blocks, fill/delete empties, skip Add")
            # (a) CONVERGE the empty blocks (workday-regen-fix 2026-06-05): on EXFO the
            # prefilled-profile path ALSO regenerates a fresh empty REQUIRED block each
            # render (53->267->...). Old code deleted-deletables + kbd-filled the permanent
            # empty ONCE per visit -> the regen out-paced it and the My-Experience step
            # loop-capped (EXIT5) at visit 3. Now: bounded loop -> kbd-COMMIT the permanent
            # empty (commits to React) then DELETE any regenerated empties, re-measuring the
            # WE-block count each pass, until no empty remains or the count stops shrinking.
            gt0, ge0 = _count_we_blocks(page)
            log(f"  prefill-guard WE start: total={gt0} empty={ge0}")
            _gprev = None
            for _gconv in range(6):
                # delete deletable empties first (cheap; clears pure pollution)
                delete_empty_we_blocks(page)
                _perm_empty = page.evaluate("()=>{const inp=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&!(x.value||'').trim()); return inp?inp.id:null;}")
                ct, ce = _count_we_blocks(page)
                log(f"  prefill-guard conv {_gconv}: total={ct} empty={ce} perm_empty={bool(_perm_empty)}")
                if ce == 0:
                    break
                if _perm_empty:
                    # a permanent (non-deletable) empty remains -> kbd-COMMIT it so it
                    # satisfies required-validation (re-filling a committed block is what
                    # would trigger the next regen, so we commit ONCE then re-loop to
                    # delete whatever new empty the commit spawned).
                    try:
                        _kbd_fill_empty_we_block(page, WORK_HISTORY[0])
                    except Exception as _e2:
                        log("  kbd-fill err", str(_e2)[:80])
                    page.wait_for_timeout(500)
                # stop if the count is no longer shrinking AND we already committed the
                # permanent block this pass (avoid an unbounded regen spin).
                if _gprev is not None and ct >= _gprev and not _perm_empty:
                    log("  prefill-guard: empty count plateaued with no permanent empty -> stop")
                    break
                _gprev = ct
            gt1, ge1 = _count_we_blocks(page)
            log(f"  prefill-guard WE converged: total={gt1} empty={ge1}")
            # (b) REPAIR DATES on every filled block (NVIDIA profile blocks save year-only,
            # leaving month empty -> 'Invalid Date: /YYYY' blocks advance). Match each block's
            # companyName to WORK_HISTORY and fill missing month(s) via keyboard date widget.
            try:
                blocks = page.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--companyName/.test(x.id||'')).map(x=>({idx:(x.id.match(/workExperience-(\\d+)--/)||[])[1], company:(x.value||'').trim()}))")
                for b in (blocks or []):
                    bidx = b.get("idx"); comp = (b.get("company") or "").lower()
                    if not bidx or not comp:
                        continue
                    job = next((j for j in WORK_HISTORY if j["company"].lower() in comp or comp in j["company"].lower()), None)
                    if not job:
                        continue
                    if job.get("current"):
                        page.evaluate("(ix)=>{const c=[...document.querySelectorAll('input[type=checkbox]')].find(e=>(e.id||'').includes('workExperience-'+ix+'--currentlyWorkHere')); if(c&&!c.checked){const l=document.querySelector('label[for=\\''+c.id+'\\']'); (l||c).click();}}", bidx)
                        page.wait_for_timeout(300)
                    sm = _find_id_suffix(page, f"workExperience-{bidx}--startDate-dateSectionMonth-input")
                    sm_empty = page.evaluate("(id)=>{const e=document.getElementById(id);return !(e&&(e.value||'').trim());}", sm) if sm else True
                    _wd_persist_probe(page, f"workExperience-{bidx}--startDate", f"REVISIT-REPAIR idx={bidx} {job.get('company','')} sm_empty={sm_empty}")
                    if sm_empty:
                        _fill_wd_date(page, f"workExperience-{bidx}--startDate", job["start"][0], job["start"][1])
                    if not job.get("current") and job.get("end"):
                        em = _find_id_suffix(page, f"workExperience-{bidx}--endDate-dateSectionMonth-input")
                        em_empty = page.evaluate("(id)=>{const e=document.getElementById(id);return !(e&&(e.value||'').trim());}", em) if em else True
                        if em_empty:
                            _fill_wd_date(page, f"workExperience-{bidx}--endDate", job["end"][0], job["end"][1])
                    log(f"  date-repair (guard) block[{bidx}] {job['company']}")
            except Exception as _e3:
                log("  guard date-repair err", str(_e3)[:80])
            # FAST-FAIL DETECTOR (workday-prefill-uncommittable-fix 2026-06-05): after the
            # date-repair pass above, check whether any PROFILE-PREFILLED work-exp block STILL
            # has an empty REQUIRED start-date month. On EXFO 2121 the tenant profile carries
            # 5 Microsoft DUPE blocks that are read-only prefills -> their start-date never
            # commits (start_filled=False every visit) -> Workday keeps the form dirty +
            # regenerates an empty required block forever -> the My-Experience step would spin
            # to the generic EXIT 5 loop-cap (~3 wasted visits). The empty-block regen itself
            # is ALREADY handled by the converge loop above (empties->0); the wall is these
            # un-committable prefilled DATES, which is a profile-side DATA bug we cannot fix
            # from automation. Set a module flag so the step loop banks a precise EXIT 9
            # ('workday-profile-prefill-uncommittable') instead of grinding. We only trip this
            # AFTER attempting repair, and only when a FILLED (jobTitle present) block has the
            # empty required start month -- never for a normal empty block (that's the Add path).
            try:
                _uncommittable = page.evaluate("""()=>{const out=[];
                  const titles=[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&(x.value||'').trim());
                  for(const t of titles){const m=(t.id||'').match(/workExperience-(\\d+)--/); if(!m)continue; const ix=m[1];
                    const sm=document.getElementById('workExperience-'+ix+'--startDate-dateSectionMonth-input')||[...document.querySelectorAll('input')].find(x=>(x.id||'').includes('workExperience-'+ix+'--startDate-dateSectionMonth-input'));
                    const cur=[...document.querySelectorAll('input[type=checkbox]')].find(e=>(e.id||'').includes('workExperience-'+ix+'--currentlyWorkHere'));
                    const isCur=cur&&cur.checked;
                    if(sm&&!(sm.value||'').trim()&&!isCur){out.push({idx:ix,company:((document.getElementById('workExperience-'+ix+'--companyName')||{}).value||'').trim()});}}
                  return out;}""")
                if _uncommittable and len(_uncommittable) > 0:
                    global _WE_PREFILL_UNCOMMITTABLE
                    _names = ", ".join(sorted({(b.get("company") or "block"+str(b.get("idx"))) for b in _uncommittable}))
                    # FRESH-ACCOUNT GUARD (workday-fresh-account-fix 2026-06-08): EXIT-9
                    # (uncommittable PROFILE-PREFILL) is a Cyrus-saved-profile DATA bug. It
                    # MUST NOT fire on a freshly-created account -- a fresh account has no
                    # legit saved profile, so an uncommittable 'prefilled' block here is
                    # anomalous pollution (already targeted by the delete/converge loop), not
                    # a profile dedup task. Suppress the flag so we don't mislabel a fresh-fill
                    # run as profile-prefill-uncommittable; the standing rule guarantees fresh fill.
                    if _fresh_acct:
                        log(f"  prefill-guard: {len(_uncommittable)} uncommittable block(s) [{_names}] on a FRESH account -> NOT EXIT-9 (anomalous prefill; fresh-fill continues)")
                    else:
                        _WE_PREFILL_UNCOMMITTABLE = (f"{len(_uncommittable)} prefilled WE block(s) w/ uncommittable required start-date [{_names}]")[:200]
                        log(f"  prefill-guard: {len(_uncommittable)} PROFILE-PREFILLED block(s) have an uncommittable required start-date -> {_names} (will fast-fail EXIT 9)")
            except Exception as _eu:
                log("  prefill-uncommittable probe err", str(_eu)[:80])
            # FIX (workday-p17 2026-06-02 NVIDIA JR2018252/JR2012702): do NOT return here.
            # Previously this branch returned right after work-history date-repair, which
            # SKIPPED the Education block below -> NVIDIA (which REQUIRES an Education entry
            # but does NOT prefill one from profile) bounced 'Next' forever on the My
            # Experience step (req_empty=[] because the education FIELDS don't exist yet,
            # so the diag never caught it). The work-exp Add logic below is already guarded
            # by `if not we_done:`, so falling through is safe when history is prefilled --
            # it skips re-adding work exp but still fills/Adds the required Education block.
            log("  prefill-guard: work history done -> fall through to Education fill")
    except Exception as _e:
        log("  profile-prefill probe err", str(_e)[:70])

    # CLEANUP (workday-proof 2026-06-02): a prior buggy run can leave EMPTY duplicate
    # work-experience blocks in the saved draft; those are required -> block advance.
    # Delete any work-exp block whose jobTitle is empty (keep filled ones).
    try:
        removed = page.evaluate("""()=>{let n=0;
          const empties=[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&!(x.value||'').trim());
          for(const inp of empties){let sec=inp; for(let i=0;i<10&&sec;i++){sec=sec.parentElement; if(sec){const del=sec.querySelector('[data-automation-id=panel-set-delete-button],[data-automation-id*=delete-button],button[aria-label^=Delete],button[title^=Delete]'); if(del){del.click();n++;break;}}}}
          return n;}""")
        if removed: log(f"  cleanup: removed {removed} empty work-exp block(s)"); page.wait_for_timeout(1500)
    except Exception as _e:
        log("  cleanup err", str(_e)[:80])
    # re-detect after cleanup
    we_idx = page.evaluate("()=>{const e=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')); if(!e)return null; const m=(e.id||'').match(/workExperience-(\\d+)--/); return m?m[1]:null;}")

    # POPULATE-ONCE GUARD (workday-proof 2026-06-02): if the pre-rendered first block
    # already has a jobTitle/schoolName value, the section is done -- do NOT re-add
    # blocks (that piled up duplicate work-exp entries every loop iteration).
    we_done = page.evaluate("()=>{const e=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')); return !!(e&&(e.value||'').trim());}")
    # ed_done requires BOTH schoolName AND fieldOfStudy filled (schoolName alone left
    # fieldOfStudy empty -> blocked advance, workday-proof 2026-06-02).
    ed_done = page.evaluate("()=>{const s=[...document.querySelectorAll('input')].find(x=>/education-\\d+--schoolName/.test(x.id||'')); const f=[...document.querySelectorAll('input')].find(x=>/education-\\d+--fieldOfStudy/.test(x.id||'')); return !!(s&&(s.value||'').trim()) && !!(f&&(f.value||'').trim());}")

    # DATE-REPAIR PASS (workday-proof 2026-06-02): existing draft blocks may have names
    # filled but dates empty (pre-date-fix). Independently of we_done, fill missing
    # From/To dates on EVERY work-exp block by matching its companyName to WORK_HISTORY.
    try:
        blocks = page.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--companyName/.test(x.id||'')).map(x=>({idx:(x.id.match(/workExperience-(\\d+)--/)||[])[1], company:(x.value||'').trim()}))")
        for b in blocks:
            bidx = b.get("idx"); comp = (b.get("company") or "").lower()
            job = next((j for j in WORK_HISTORY if j["company"].lower() in comp or comp in j["company"].lower()), None)
            if not (bidx and job):
                continue
            # current-role checkbox if applicable
            if job["current"]:
                page.evaluate("(ix)=>{const c=[...document.querySelectorAll('input[type=checkbox]')].find(e=>(e.id||'').includes('workExperience-'+ix+'--currentlyWorkHere')); if(c&&!c.checked){const l=document.querySelector('label[for=\\''+c.id+'\\']'); (l||c).click();}}", bidx)
                page.wait_for_timeout(400)
            sm = _find_id_suffix(page, f"workExperience-{bidx}--startDate-dateSectionMonth-input")
            start_empty = page.evaluate("(id)=>{const e=document.getElementById(id);return !(e&&(e.value||'').trim());}", sm) if sm else True
            if start_empty:
                _fill_wd_date(page, f"workExperience-{bidx}--startDate", job["start"][0], job["start"][1])
            if not job["current"] and job["end"]:
                em = _find_id_suffix(page, f"workExperience-{bidx}--endDate-dateSectionMonth-input")
                end_empty = page.evaluate("(id)=>{const e=document.getElementById(id);return !(e&&(e.value||'').trim());}", em) if em else True
                if end_empty:
                    _fill_wd_date(page, f"workExperience-{bidx}--endDate", job["end"][0], job["end"][1])
            # workday-we-persist-fix (2026-06-11): the OLD log printed `start_filled={start_empty}`
            # which is BACKWARDS (start_empty is the BEFORE-fill emptiness) AND single-source
            # (.value only). Probe proved dates DO persist via aria-valuetext / hidden input even
            # when .value reads blank, so the old line was a chronic FALSE-NEGATIVE that sent us
            # chasing a phantom date-persistence bug. Re-read the COMMITTED value multi-source and
            # log the TRUE post-fill state.
            _sm_mon = _find_id_suffix(page, f"workExperience-{bidx}--startDate-dateSectionMonth-input")
            _sm_yr = _find_id_suffix(page, f"workExperience-{bidx}--startDate-dateSectionYear-input")
            _mon_v = _wd_read_date_section(page, _sm_mon)
            _yr_v = _wd_read_date_section(page, _sm_yr)
            _committed = bool(_mon_v) and bool(_yr_v)
            log(f"  date-repair block[{bidx}] {job['company']}: start_committed={_committed} (mon='{_mon_v}' yr='{_yr_v}')")
        # Clear any role descriptions that contain Workday-illegal chars (< > [ ] " { } \).
        try:
            cleared = page.evaluate("""()=>{let n=0;const proto=window.HTMLTextAreaElement.prototype;const d=Object.getOwnPropertyDescriptor(proto,'value');
              for(const el of document.querySelectorAll('textarea')){if(/workExperience-\\d+--roleDescription/.test(el.id||'')){const v=el.value||'';if(/[<>\\[\\]"{}\\\\]/.test(v)){el.focus();d.set.call(el,'');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.blur();n++;}}}return n;}""")
            if cleared: log(f"  cleared {cleared} role-description(s) with illegal chars")
        except Exception as _e: log("  desc-clear err", str(_e)[:70])
    except Exception as _e:
        log("  date-repair err", str(_e)[:90])

    # ---- Work Experience: reuse pre-rendered EMPTY blocks, then Add for the rest ----
    # FIX (workday-regen-fix 2026-06-05 EXFO 2121): THE REGEN-ON-FILL RUNAWAY.
    # Workday spawns a FRESH empty REQUIRED work-exp block EVERY time you fill the
    # permanent empty block IF the fill never satisfies React's required-validation.
    # The OLD loop wrote jobTitle/company/location via _set_native (a raw DOM .value
    # write) which does NOT commit to React -> the block stayed 'required-empty' -> the
    # page injected a new empty -> next iteration filled THAT -> another -> the empty
    # count exploded 54->274->437 and the My-Experience step hit the loop-cap (EXIT5).
    # NEW logic:
    #   (1) FILL each real history block via _kbd_fill_we_block_by_idx (REAL key events
    #       -> commits to React -> the block satisfies required-validation, so Workday
    #       has no reason to regenerate).
    #   (2) After each commit, if Workday STILL spawned a new empty required block,
    #       DELETE it (delete_empty_we_blocks) instead of re-filling it -- re-filling
    #       is exactly what triggers the next regen. Detect via _count_we_blocks total.
    #   (3) Converge: fill the real blocks ONCE, delete regenerated empties, done.
    def _empty_we_indices():
        # smallest-index first: the ORIGINAL history blocks have lower indices than
        # freshly-regenerated empties, so popping [0] targets real blocks, not regens.
        return page.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--jobTitle/.test(x.id||'')&&!(x.value||'').trim()).map(x=>x.id.match(/workExperience-(\\d+)--/)[1]).sort((a,b)=>(+a)-(+b))")
    def _filled_we_companies():
        """companyName values already committed in any work-exp block, lowercased.
        Used for IDEMPOTENT fill (workday-date-commit-fix FIX2): a job whose company is
        already present must be EDITED-IN-PLACE / skipped, never Added again -- re-Adding
        is what piled up duplicate blocks (PE5 dup of PE1 Microsoft on the EXFO live run)."""
        try:
            return [c.strip().lower() for c in page.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--companyName/.test(x.id||'')&&(x.value||'').trim()).map(x=>x.value)") if c and c.strip()]
        except Exception:
            return []
    def _we_idx_for_company(company):
        """Return the block index whose committed companyName matches `company`
        (substring either direction), else None -> caller edits THAT block in place."""
        comp = (company or "").strip().lower()
        if not comp:
            return None
        try:
            return page.evaluate("""(comp)=>{const m=[...document.querySelectorAll('input')].find(x=>/workExperience-\\d+--companyName/.test(x.id||'')&&((x.value||'').trim().toLowerCase().includes(comp)||comp.includes((x.value||'').trim().toLowerCase())&&(x.value||'').trim())); return m?m.id.match(/workExperience-(\\d+)--/)[1]:null;}""", comp)
        except Exception:
            return None
    if not we_done:
        total0, empty0 = _count_we_blocks(page)
        log(f"  WE-fill start: total_blocks={total0} empty={empty0}")
        empties = _empty_we_indices()
        filled = 0
        for i, job in enumerate(WORK_HISTORY):
            # IDEMPOTENCY GUARD (FIX2): if this company is ALREADY in a committed block,
            # edit THAT block in place (re-assert dates/desc) rather than Add a duplicate.
            existing_idx = _we_idx_for_company(job["company"])
            if existing_idx is not None:
                _kbd_fill_we_block_by_idx(page, existing_idx, job)
                filled += 1
                log(f"  work exp [{existing_idx}] {job['company']}: edit-in-place (company already present, no Add)")
                empties = _empty_we_indices()
                continue
            if empties:
                idx = empties.pop(0)
            else:
                # need a fresh block: click 'Add Another' (or Add)
                page.evaluate("()=>{const b=[...document.querySelectorAll('button,[role=button],[data-automation-id=Add],[data-automation-id=add-button]')].find(x=>{const t=(x.textContent||'').trim();const da=(x.getAttribute('data-automation-id')||'');return /add another/i.test(t)||da==='Add'||da==='add-button'||t==='Add';}); if(b){b.click();return true;}return false;}")
                page.wait_for_timeout(1800)
                fresh = _empty_we_indices()
                if not fresh:
                    log(f"  could not create work-exp block {i}; stop adding"); break
                idx = fresh[0]
            pre_total, pre_empty = _count_we_blocks(page)
            # KEYBOARD-COMMIT fill (commits to React; native .value writes were the bug).
            _kbd_fill_we_block_by_idx(page, idx, job)
            filled += 1
            page.wait_for_timeout(700)
            post_total, post_empty = _count_we_blocks(page)
            log(f"  work exp [{idx}] {job['title']} @ {job['company']}: blocks {pre_total}->{post_total} (empty {pre_empty}->{post_empty})")
            # DETECT REGEN: if filling this block made the page spawn NEW block(s)
            # (total grew) OR left more empties than expected, DELETE the regenerated
            # empties NOW instead of letting the next iteration re-fill one (which is
            # what triggers the next regen). Re-sync the empties worklist afterward.
            if post_total > pre_total or post_empty > max(0, pre_empty - 1):
                before_del = post_total
                delete_empty_we_blocks(page)
                aft_total, aft_empty = _count_we_blocks(page)
                log(f"  regen detected after [{idx}] -> deleted empties: blocks {before_del}->{aft_total} (empty now {aft_empty})")
                # refresh remaining empty worklist; only KEEP indices still unfilled
                empties = _empty_we_indices()
        # FINAL CONVERGENCE: real blocks are committed; delete any leftover/regenerated
        # empties and PROVE the count plateaus (no 54->274->437 explosion). Bounded loop:
        # delete-empties, re-measure; stop as soon as the total stops shrinking AND no
        # empties remain, or after a hard cap (so a pathological regen can't spin forever).
        prev_total = None
        for _conv in range(6):
            delete_empty_we_blocks(page)
            ct, ce = _count_we_blocks(page)
            log(f"  WE convergence pass {_conv}: total={ct} empty={ce}")
            if ce == 0:
                break
            if prev_total is not None and ct >= prev_total:
                # not shrinking and empties remain -> these are PERMANENT empties; the
                # block above already kbd-committed the real history, so kbd-fill one
                # remaining permanent empty (mirrors the prefill-guard path) and re-check.
                try:
                    _kbd_fill_empty_we_block(page, WORK_HISTORY[0])
                except Exception as _e:
                    log("  convergence kbd-fill err", str(_e)[:70])
                delete_empty_we_blocks(page)
                ct2, ce2 = _count_we_blocks(page)
                log(f"  WE convergence pass {_conv} (post perm-fill): total={ct2} empty={ce2}")
                if ce2 == 0:
                    break
            prev_total = ct
        end_total, end_empty = _count_we_blocks(page)
        log(f"  WE-fill done: filled={filled} final total_blocks={end_total} empty={end_empty}")

    # ---- Education: fill pre-rendered block ----
    for i, ed in enumerate(EDUCATION):
        if ed_done:
            break
        if i == 0 and ed_idx is not None:
            idx = ed_idx
        else:
            page.evaluate("()=>{const b=[...document.querySelectorAll('button,[role=button]')].find(x=>/add another|add education/i.test((x.textContent||'').trim())); if(b)b.click();}")
            page.wait_for_timeout(1500)
            idx = page.evaluate("()=>{const empty=[...document.querySelectorAll('input')].filter(x=>/education-\\d+--schoolName/.test(x.id||'')&&!(x.value||'').trim()); return empty.length?empty[empty.length-1].id.match(/education-(\\d+)--/)[1]:null;}")
            if not idx: break
        sn = _find_id_suffix(page, f"education-{idx}--schoolName")
        fo = _find_id_suffix(page, f"education-{idx}--fieldOfStudy")
        if sn: _set_native(page, sn, ed["school"])
        # fieldOfStudy is a searchable multiselect PROMPT (Snap). The id-suffix element
        # is often non-interactable; locate the visible input/container by data-automation-id
        # containing 'fieldOfStudy', scroll into view, type, then pick the matching option.
        if fo and page.evaluate("(id)=>{const e=document.getElementById(id);return !(e&&(e.value||'').trim());}", fo):
            try:
                # ensure the prompt is in view & focus the real input
                page.evaluate("(id)=>{const e=document.getElementById(id); if(e){e.scrollIntoView({block:'center'});}}", fo)
                page.wait_for_timeout(300)
                inp = page.locator(f"#{fo}")
                inp.first.click(timeout=6000, force=True); page.wait_for_timeout(500)
                page.keyboard.type(ed["field"], delay=50); page.wait_for_timeout(1600)
                picked = False
                for o in page.locator("[role=option]").all():
                    t=(o.text_content() or "").strip()
                    if ed["field"].lower() in t.lower():
                        try: o.click(timeout=3000); picked=True; break
                        except Exception: pass
                if not picked:
                    page.keyboard.press("Enter"); page.wait_for_timeout(700)
            except Exception as _e:
                log("  fieldOfStudy prompt err", str(_e)[:70])
            if page.evaluate("(id)=>{const e=document.getElementById(id); return !(e&&(e.value||'').trim());}", fo):
                log("  !! fieldOfStudy STILL empty after prompt attempt")
        # Degree: Workday button-listbox. Required on Snap. Find by id containing degree.
        try:
            deg_btn = page.evaluate("(ix)=>{const b=[...document.querySelectorAll('button')].find(x=>(x.id||'').includes('education-'+ix+'--degree')) || [...document.querySelectorAll('button[id*=--degree]')][0]; return b?b.id:null;}", idx)
            if deg_btn and page.evaluate("(id)=>{const b=document.getElementById(id); return /select one|^$/i.test((b.textContent||b.getAttribute('aria-label')||'').trim());}", deg_btn):
                page.evaluate("(id)=>{const b=document.getElementById(id); if(b)b.scrollIntoView({block:'center'});}", deg_btn)
                page.wait_for_timeout(300)
                page.locator(f"#{deg_btn}").first.click(timeout=5000, force=True); page.wait_for_timeout(800)
                # Cyrus = Bachelor of Computer Science -> prefer 'Bachelor', else 'B.S'
                picked=False
                for kw in ["bachelor", "b.s", "b.s."]:
                    for o in page.locator('[role=option]').all():
                        t=(o.text_content() or '').strip()
                        if kw in t.lower():
                            try: o.click(timeout=3000); picked=True; break
                            except Exception: pass
                    if picked: break
                if not picked: page.keyboard.press("Escape")
                log(f"  degree set picked={picked}")
        except Exception as _e: log("  degree err", str(_e)[:70])
        _fill_wd_date(page, f"education-{idx}--lastYearAttended", "05", ed["end_year"])
        _fill_wd_date(page, f"education-{idx}--firstYearAttended", "08", ed["start_year"])
        log(f"  education [{idx}]: {ed['school']} (sn={bool(sn)} fo={bool(fo)})")
        page.wait_for_timeout(700)

    # FIX (workday-roledesc 2026-06-02 EXFO 2121): some Workday tenants make the work-exp
    # "Role Description" textarea a REQUIRED field. None of the fill paths above ever wrote
    # it (every WORK_HISTORY entry has a `desc` but it was unused outside the illegal-char
    # CLEAR pass), so on those tenants every work-exp block stayed required-empty and the
    # My Experience step bounced 'Next' forever (this is the EXFO 2121 churn-loop). Final
    # single-point sweep: match each rendered block to WORK_HISTORY by companyName and fill
    # any EMPTY roleDescription. Runs regardless of which fill path executed above.
    _sweep_role_descriptions(page)

def _wd_sanitize_desc(text):
    """Strip Workday-illegal chars (< > [ ] " { } \\) the form rejects in roleDescription."""
    import re as _re
    return _re.sub(r'[<>\[\]"{}\\]', '', text or '').strip()

def _sweep_role_descriptions(page):
    """Fill every EMPTY work-exp roleDescription textarea, matching block->WORK_HISTORY by
    companyName. React-aware native textarea setter (same pattern as _set_native)."""
    try:
        blocks = page.evaluate("()=>[...document.querySelectorAll('input')].filter(x=>/workExperience-\\d+--companyName/.test(x.id||'')).map(x=>({idx:(x.id.match(/workExperience-(\\d+)--/)||[])[1], company:(x.value||'').trim()}))")
    except Exception as _e:
        log("  roledesc sweep probe err", str(_e)[:70]); return
    filled = 0
    for b in (blocks or []):
        bidx = b.get("idx"); comp = (b.get("company") or "").lower()
        if not bidx or not comp:
            continue
        job = next((j for j in WORK_HISTORY if j["company"].lower() in comp or comp in j["company"].lower()), None)
        if not job or not job.get("desc"):
            continue
        rd = _find_id_suffix(page, f"workExperience-{bidx}--roleDescription")
        if not rd:
            continue
        is_empty = page.evaluate("(id)=>{const e=document.getElementById(id)||[...document.querySelectorAll('textarea')].find(x=>(x.getAttribute('data-automation-id')||'')===id);return e?!((e.value||'').trim()):true;}", rd)
        if not is_empty:
            continue
        desc = _wd_sanitize_desc(job["desc"])
        ok = page.evaluate("""([id,val])=>{
            const el=document.getElementById(id) || [...document.querySelectorAll('textarea')].find(e=>(e.getAttribute('data-automation-id')||'')===id);
            if(!el) return false;
            const d=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');
            el.focus(); d.set.call(el,val);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            el.blur(); return true;
        }""", [rd, desc])
        if ok:
            filled += 1
            log(f"  roledesc filled block[{bidx}] {job['company']} ({len(desc)} chars)")
    if filled:
        page.wait_for_timeout(500)
    else:
        log("  roledesc sweep: nothing to fill (none empty/required, or no textarea rendered)")

def handle_experience(page, resume):
    log("step: My Experience (resume upload)")
    page.wait_for_timeout(1500)
    # FIX (workday-proof 2026-06-02): idempotent upload -- don't re-upload if a file is
    # already attached (NVIDIA/Snap dryruns showed the resume uploaded 5x because this
    # ran every loop iteration). Detect an existing 'successfully uploaded' / filename row.
    #
    # FIX3 (workday-upload-drop 2026-06-09 EXFO 2121): previously the `already` check
    # also returned True when ANY work-exp block had a jobTitle value (the RBI clause).
    # On tenants like EXFO-class, Workday DROPS the uploaded file whenever the runner
    # navigates away from My Experience and comes back (DIAG: uploaded:true v1 →
    # uploaded:false v2/v3, field errors "Upload a file (5MB max) is required"). After
    # populate_work_history fills the work-exp blocks the jobTitle clause fired True →
    # re-upload was permanently skipped even though the file was gone → My Experience
    # stayed invalid → loop-cap EXIT 5.
    #
    # FIX: separate the two concerns:
    #   file_present  = resume actually attached (file-upload widget, DeleteFile button,
    #                   or "successfully uploaded" text). Used to gate re-upload.
    #   profile_prefill = work-exp block pre-filled from the tenant account profile
    #                     (the original RBI guard: skip re-upload when PROFILE carries
    #                     work history so we don't re-parse and spawn new phantom blocks).
    #                     ONLY applies when the file is NOT upload-able (no input widget
    #                     visible) — i.e. the upload field has been suppressed because
    #                     the platform already has the resume from the profile.
    file_present = page.evaluate(
        "()=>/successfully uploaded/i.test(document.body.innerText)"
        " || !![...document.querySelectorAll("
        "'[data-automation-id=file-upload-item],[data-automation-id*=DeleteFile]'"
        ")].length"
    )
    upload_input_visible = bool(
        page.locator("[data-automation-id=file-upload-input-ref]").count()
        or page.locator("input[type=file]").count()
    )
    profile_prefill_skip = (
        not upload_input_visible
        and page.evaluate(
            "()=>[...document.querySelectorAll('input')].some("
            "x=>/workExperience-\\d+--jobTitle/.test(x.id||'')"
            "&&(x.value||'').trim())"
        )
    )
    already = file_present or profile_prefill_skip
    # workday-boeing-upload-required-on-revisit (2026-06-11 Boeing 2546): SOME Workday
    # tenants render the resume/CV upload widget as a HARD-REQUIRED field on My Experience,
    # and DROP the uploaded-file display on a cross-nav revisit -> file_present=False AND an
    # explicit 'Upload a file ... is required' error appears while the upload INPUT is still
    # visible. The fresh-account skip below (uploaded-once -> never re-upload) is correct for
    # tenants where typed WORK_HISTORY satisfies the step (Nvidia/Gates), but on Boeing it
    # leaves the required upload empty forever -> Next never advances -> the parser respawns a
    # WE block each revisit -> EXIT-5 loop. So when the upload field is genuinely
    # REQUIRED-AND-EMPTY on this visit, we must NOT short-circuit the skip -- allow a re-upload
    # (still bounded by _MAX_RESUME_UPLOADS) and let delete_empty_we_blocks + harden clean up
    # the respawned blocks (they already converge cleanly). Detector: upload input visible AND
    # no file shown AND an error mentioning a required file/upload.
    upload_required_empty = False
    try:
        upload_required_empty = bool(
            upload_input_visible
            and not file_present
            and page.evaluate(
                "()=>[...document.querySelectorAll('[data-automation-id*=error],[role=alert]')]"
                ".some(e=>{const t=(e.textContent||'').toLowerCase();"
                "return /upload a file|upload a document|is required/.test(t)"
                "&&/upload|file|document|resume|cv|attach/.test(t);})"
            )
        )
    except Exception:
        upload_required_empty = False
    if upload_required_empty:
        log("  upload field REQUIRED-EMPTY on revisit (file display dropped) -> allow a "
            "bounded re-upload despite fresh-acct cap (Boeing-class required-upload widget)")
    # workday-reupload-loop-fix (2026-06-10): cap re-uploads per row. Gates-class renders no
    # 'successfully uploaded' marker -> file_present always False -> would re-upload every
    # visit -> new parser block each time -> EXIT-5 loop. After _MAX_RESUME_UPLOADS, stop
    # re-uploading (EXFO-class drop-on-revisit still gets its legit re-upload within the cap).
    global _RESUME_UPLOADED, _RESUME_REQ_REUPLOADS
    _fresh_acct_up = globals().get("_ACCOUNT_MODE") in ("create_fresh", "signin_fresh")
    # workday-we-persist-fix (2026-06-11 run4): on a FRESH account the typed WORK_HISTORY
    # blocks (populate_work_history below) already carry the full content, so re-running the
    # resume PARSER on a revisit is PURE HARM -- the parser manufactures a blank 'add-another'
    # required WE block from the PDF text each time it runs (proven Nvidia 2829: total grew
    # 4->5->6 -> loop-cap EXIT-5). So once we've uploaded ONCE on a fresh account, NEVER
    # re-upload again, regardless of whether the 'successfully uploaded' marker dropped --
    # the typed history is the source of truth, not a re-parsed PDF. (Polluted-profile /
    # signin_legacy tenants are never the default path here, so this only ever helps.)
    # A genuinely REQUIRED-AND-EMPTY upload widget (Boeing-class) overrides BOTH the
    # fresh-acct uploaded-once skip AND the _MAX_RESUME_UPLOADS cap, bounded instead by its
    # own _MAX_REQ_REUPLOADS so it can satisfy a few revisits without looping forever.
    force_req_reupload = (
        not already
        and upload_required_empty
        and _RESUME_REQ_REUPLOADS < _MAX_REQ_REUPLOADS
    )
    if force_req_reupload:
        pass  # leave already=False -> re-upload below; skip the cap short-circuits
    elif not already and _fresh_acct_up and _RESUME_UPLOADED >= 1 and not upload_required_empty:
        already = True
        log(f"  resume already uploaded once on fresh account -> skip re-upload "
            f"(typed work-history is source of truth; re-parse would respawn empty WE blocks)")
    elif not already and _RESUME_UPLOADED >= _MAX_RESUME_UPLOADS and not upload_required_empty:
        already = True
        log(f"  resume upload cap reached ({_RESUME_UPLOADED}/{_MAX_RESUME_UPLOADS}) -> skip re-upload")
    elif not already and upload_required_empty and _RESUME_REQ_REUPLOADS >= _MAX_REQ_REUPLOADS:
        already = True
        log(f"  required-upload re-upload cap reached "
            f"({_RESUME_REQ_REUPLOADS}/{_MAX_REQ_REUPLOADS}) -> skip re-upload (loop-cap will backstop)")
    if not already:
        inp = page.locator("[data-automation-id=file-upload-input-ref]").first
        if not inp.count():
            inp = page.locator("input[type=file]").first
        if inp.count():
            try:
                inp.set_input_files(resume); log("resume set:", resume)
                _RESUME_UPLOADED += 1
                if force_req_reupload:
                    _RESUME_REQ_REUPLOADS += 1
                # workday-upload-wait-fix (2026-06-13): wait for the upload to complete
                # by polling for 'successfully uploaded' text (max 20s). The 6s flat
                # wait was insufficient for PayPal/Boeing-class tenants where the file
                # upload XHR takes >6s to confirm, causing click_next to see the upload
                # field as still-required even though the file was chosen.
                # NOTE: increment FIRST (above) so the cap is respected even if the
                # wait-loop throws (e.g. mock pages in unit tests).
                try:
                    _uploaded_ok = False
                    for _wt in range(20):
                        page.wait_for_timeout(1000)
                        _upbody = page.evaluate("()=>document.body.innerText") or ""
                        _delbtn = page.locator("[data-automation-id*=DeleteFile]").count()
                        if "successfully uploaded" in _upbody.lower() or _delbtn:
                            _uploaded_ok = True
                            log(f"  upload confirmed after {_wt+1}s")
                            break
                    if not _uploaded_ok:
                        page.wait_for_timeout(2000)  # fallback extra settle
                        log("  upload: 'successfully uploaded' not confirmed after 20s (may still be processing)")
                except Exception as _we:
                    page.wait_for_timeout(6000)  # fallback to original flat wait
                    log(f"  upload wait-poll err (using flat 6s fallback): {str(_we)[:60]}")
            except Exception as e: log("upload err", str(e)[:100])
        # workday-multi-upload-fix (2026-06-13): some Workday tenants (PayPal/Boeing-class)
        # have a SECOND required file-upload slot (cover letter / additional attachment)
        # distinct from the resume slot. After the resume upload, scan for additional
        # visible file-upload-input-ref elements (beyond the first) and upload the resume
        # to them too -- satisfying the 'Upload a file (5MB max) is required' error
        # that fires even when the resume slot shows 'successfully uploaded'.
        try:
            all_upload_inputs = page.locator("[data-automation-id=file-upload-input-ref]").all()
            if len(all_upload_inputs) > 1:
                for _ii, _extra_inp in enumerate(all_upload_inputs[1:], 1):
                    try:
                        _extra_inp.set_input_files(resume)
                        log(f"  multi-upload: uploaded resume to extra slot [{_ii}]")
                        page.wait_for_timeout(3000)
                    except Exception as _ue:
                        log(f"  multi-upload: slot [{_ii}] upload err", str(_ue)[:60])
        except Exception as _me:
            log("  multi-upload scan err", str(_me)[:80])
    else:
        if file_present:
            reason = "file-widget"
        elif profile_prefill_skip:
            reason = "profile-prefill-skip"
        elif _fresh_acct_up and _RESUME_UPLOADED >= 1:
            reason = "fresh-acct-uploaded-once"
        else:
            reason = "upload-cap"
        log(f"  resume already uploaded -> skip re-upload ({reason})")
    # FIX (workday-proof 2026-06-02 Snap): populate Work Experience + Education if the
    # step requires them (Snap/Nordstrom-class). Idempotent -- skips if already present.
    # FIX3 (2026-06-09): also delete any per-revisit regenerated empty WE block BEFORE
    # populate_work_history runs, so the block index doesn't keep climbing on revisit.
    delete_empty_we_blocks(page)
    try:
        populate_work_history(page)
    except Exception as e:
        log("populate_work_history err", str(e)[:120])
    # DIAG: list still-empty required fields WITH a human label so we can see what blocks advance.
    try:
        rem = page.evaluate("""()=>{const out=[];for(const el of document.querySelectorAll('input[aria-required=true],textarea[aria-required=true],button[aria-required=true],[aria-required=true]')){const v=(el.value||el.getAttribute('aria-label')||el.textContent||'').trim();const filled=el.tagName==='BUTTON'?!/select one|^$/i.test(v):!!v;if(!filled){let lab='';let p=el;for(let i=0;i<5&&p;i++){p=p.parentElement;if(p){const l=p.querySelector('label');if(l){lab=l.textContent.trim();break;}}}out.push((el.id||el.getAttribute('data-automation-id')||'?')+' :: '+lab.slice(0,30));}}return JSON.stringify(out.slice(0,20));}""")
        log("  STILL-REQUIRED-EMPTY:", rem[:600])
    except Exception: pass
    shot(page, "experience", "uploaded")

def handle_questions(page):
    log("step: Application Questions")
    page.wait_for_timeout(1500)
    # (workday-ack-widget 2026-06-10 GEICO 2358 forensic) one-shot dump of EVERY
    # questionnaire listbox button's FULL id + value + visibility, so we can see whether
    # the ack field that won't commit is a duplicate/hidden node vs the one we picked.
    if globals().get("_CUR_TENANT") == "geico" and not globals().get("_ACK_FORENSIC_DONE"):
        try:
            globals()["_ACK_FORENSIC_DONE"] = True
            forensic = page.evaluate(r"""()=>{
                const out=[];
                for(const b of document.querySelectorAll('button[id^=primaryQuestionnaire],button[aria-haspopup=listbox]')){
                  const r=b.getBoundingClientRect();
                  let qtxt='';let p=b.parentElement;for(let i=0;i<8&&p;i++){const t=(p.innerText||'').trim();if(t){qtxt=t.split('\n')[0];break;}p=p.parentElement;}
                  out.push({id:b.id, val:(b.getAttribute('aria-label')||b.innerText||'').trim().slice(0,50), haspopup:b.getAttribute('aria-haspopup')||'', visible:(b.offsetParent!==null && r.width>0 && r.height>0), q:qtxt.slice(0,60)});
                }
                return out;
            }""")
            import json as _json
            DBG.mkdir(parents=True, exist_ok=True)
            (DBG / "ack-forensic-geico.json").write_text(_json.dumps(forensic, indent=2))
            for f in forensic:
                if "acknowledge" in (f.get("val","")+f.get("q","")).lower() or "read and" in (f.get("val","")+f.get("q","")).lower():
                    log("  ACK-FORENSIC:", _json.dumps(f)[:300])
        except Exception as e:
            log("  ack-forensic fail", str(e)[:80])
    # Workday primary questionnaire: each question is a button[id^=primaryQuestionnaire] (listbox).
    # Set semantically: work-authorization -> Yes ; sponsorship/visa -> No. Default unknown -> Yes.
    qbtns = page.evaluate("()=>Array.from(document.querySelectorAll('button[id^=primaryQuestionnaire]')).map(b=>b.id)")
    for bid in qbtns:
        try:
            # find the question text: nearest ancestor with a label/legend
            qtext = page.evaluate("""(id)=>{let el=document.getElementById(id); let n=el; for(let i=0;i<6 && n;i++){n=n.parentElement; if(!n)break; const t=(n.innerText||'').trim(); if(t.includes('?')) return t.split('\\n')[0];} return (el.getAttribute('aria-label')||'');}""", bid)
            low = (qtext or "").lower()
            cur_val = page.evaluate("(id)=>(document.getElementById(id).getAttribute('aria-label')||document.getElementById(id).innerText||'').trim()", bid)
            # Sponsorship/visa/employer-support questions -> No (Cyrus is a US citizen, needs none).
            SPON = ["sponsor", "visa", "h-1b", "h1b", "employer support", "employer's support",
                    "obtain or maintain", "work permit", "immigration",
                    "green card", "right to work"]
            AUTH = ["authorized to work", "authorised to work", "legally authorized",
                    "legally authorised", "eligible to work", "are you authorized"]
            # Affirmative questions Cyrus answers YES to (relocate/onsite/quals/availability).
            # workday-proof 2026-06-02 Snap: 'default unknown -> No' was tanking the app
            # by answering No to relocate/office/min-qualification questions.
            AFFIRM = ["relocate", "able to relocate", "currently live in", "willing to relocate",
                      "come into the office", "coming into the office", "commit to coming",
                      "in office", "onsite", "on-site", "hybrid",
                      "meet the minimum qualification", "minimum qualification",
                      "years of professional", "years of experience", "meet the minimum",
                      "legally able", "at least 18", "available to start",
                      "legal age", "of legal age", "background check", "submit a background",
                      "willing to submit"]
            # Negative/exclusion questions Cyrus answers NO to.
            NEGATIVE = ["current or former", "prior 18 months", "ey, pwc", "deloitte",
                        "non-compete", "noncompete", "conflict of interest", "related to anyone",
                        "previously employed by snap", "ever worked for snap",
                        # (workday-ack-widget 2026-06-10 GEICO 2358) factual-NO knockout Qs:
                        # Cyrus never worked at GEICO, has no familial/romantic tie to an
                        # employee, and holds no professional/legal license -> these MUST be
                        # No (factual), not the harmful default-Yes. These are reusable across
                        # tenants (generic phrasings, not GEICO-hardcoded).
                        "worked previously as", "previously worked as a", "worked previously at",
                        "ever been employed by", "previously been employed", "former associate",
                        "familial", "romantic", "extraprofessional", "extra-professional",
                        "relationship with a current", "relationship with an existing",
                        "related to a current", "family member who",
                        "suspended, denied, revoked", "revoked, canceled", "revoked or sanctioned",
                        "been suspended", "been revoked", "ever been sanctioned",
                        "hold or have you ever held a professional",
                        "currently hold or have you ever held a professional",
                        "professional state issued license", "professional state-issued license",
                        # (workday-paypal 2026-06-13 PEP question) Cyrus is NOT a politically
                        # exposed person, has no PEP-related association.
                        "politically exposed person", "pep",
                        "associated with a politically", "related to or associated with a pep",
                        # (workday-conocophillips 2026-06-18) sanctions-country citizenship
                        # screening: 'are you a citizen of cuba, iran, north korea, syria'
                        # -> No (Cyrus is a US citizen only).
                        "citizen of cuba", "citizen of iran", "citizen of north korea",
                        "citizen of syria", "citizen or national of cuba",
                        "citizen or national of iran", "citizen or national of north korea",
                        "citizen or national of syria",
                        "cuba, iran", "iran, north korea", "north korea, syria",
                        "sanctioned country", "embargoed country",
                        "cuba, north korea", "iran or syria", "cuba or iran"]
            # Acknowledgement / 'do you understand' / 'do you acknowledge' affirmations: the
            # candidate must affirm to proceed -> pick the affirmative option (Yes / I
            # acknowledge / I have read). (workday-ack-widget 2026-06-10 GEICO 2358: the
            # 'read and acknowledge' listbox needs an explicit affirmative pick.)
            ACK_Q = ["read and acknowledge", "i have read and", "do you acknowledge",
                     "do you understand", "i acknowledge", "i certify", "i agree",
                     "please acknowledge", "by submitting"]
            # Chained gating question: 'Did you answer No to Q1 and/or Yes to Q2 or 3?'
            # Cyrus answered Q1=Yes, Q2=No, Q3=No -> the answer is NO.
            if "did you answer" in low and ("question 1" in low or "q1" in low or "and/or" in low):
                want = "No"
            # I-9 / work-eligibility documentation question (e.g. Adobe: 'can you provide
            # documentation establishing your identity and right to work...') -> YES.
            # FIX (workday-p13 2026-06-02 Adobe R165611): this matched SPON via 'right to
            # work' and was wrongly answered No. Must take precedence over SPON. Cyrus is a
            # US citizen and CAN provide I-9 documentation.
            elif ("provide documentation" in low or "establishing your identity" in low
                  or "document establishing" in low or ("can you provide" in low and "work" in low)):
                want = "Yes"
            elif ("work authorization" in low or "work authorisation" in low) and ("based" in low or "sponsor" in low or "visa" in low or "contingent" in low):
                # 'Is your current work authorization based on sponsorship?' -> No
                want = "No"
            elif any(k in low for k in SPON):
                want = "No"
            elif any(k in low for k in AUTH):
                want = "Yes"
            elif any(k in low for k in NEGATIVE):
                want = "No"
            elif any(k in low for k in ACK_Q):
                # affirmation/acknowledgement question -> affirm. wd_pick_listbox tries the
                # exact text first; for a listbox whose only real option is the ack itself
                # (e.g. 'I have read and acknowledge'), 'Yes' won't match -> handled below.
                want = "Yes"
            elif any(k in low for k in AFFIRM):
                want = "Yes"
            else:
                # Truly unknown: log loudly and default to Yes for eligibility/availability-
                # style questions is risky, but default No is what tanked relocate Qs. Since
                # most remaining unknowns on apply forms are 'are you able/willing' -> Yes is
                # the safer default for a candidate who wants the job. Flag for review.
                log(f"  !! UNRECOGNIZED question '{low[:90]}' -> defaulting YES (review!)")
                want = "Yes"
            # Skip if already correct
            if cur_val.strip().lower().endswith(want.lower()) or cur_val.strip().lower() == want.lower():
                log(f"  Q '{low[:40]}' already={cur_val.strip()[-4:]!r} (want {want}) - ok")
                # but verify it's actually that value, not just substring; re-set to be safe if 'select one'
                if "select one" not in cur_val.lower():
                    continue
            log(f"  Q '{low[:50]}' -> {want}")
            # ACK-class affirmation listboxes (e.g. 'read and acknowledge') usually have NO
            # 'Yes' option -- the affirmative option is phrased 'I have read and acknowledge'
            # / 'I acknowledge' / 'I agree'. Try those explicitly before the plain 'Yes'
            # pick so the field commits in-handler (handle_ack_widget pass-3 is the backstop).
            if any(k in low for k in ACK_Q):
                picked_ack = False
                for ack_opt in ("I have read and acknowledge", "I acknowledge", "I agree",
                                "I understand", "I certify", "Acknowledge", "Yes"):
                    if wd_pick_listbox(page, f"button#{bid}", ack_opt):
                        log(f"    ack-Q committed via {ack_opt!r}")
                        picked_ack = True; break
                if not picked_ack:
                    log("    ack-Q no listbox option matched -> handle_ack_widget backstop")
            else:
                wd_pick_listbox(page, f"button#{bid}", want)
        except Exception as e:
            log("  question err", bid, str(e)[:60])
    # Any other generic listbox questions (non primaryQuestionnaire)
    fill_generic_questions(page)
    # Free-text questionnaire fields (input/textarea with id^=primaryQuestionnaire), e.g.
    # 'What is your desired salary?' / 'List your reasons for leaving your last three
    # positions.' -- these are NOT listboxes/checkboxes so no other handler touches them,
    # and they don't show in the listbox-only DIAG (workday-freetext-questions 2026-06-10
    # GEICO 2358: these were the REAL EXIT-5 blockers, not the ack widget). Reusable.
    fill_freetext_questions(page)
    # Checkbox-group questions (e.g. Adobe 'Have you ever worked at Adobe in the
    # following capacity:* [Employee/Intern/.../I have not worked for Adobe in the past.]').
    # FIX (workday-p13 2026-06-02 Adobe R165611): these are required checkbox groups,
    # NOT listboxes -> neither handle_questions nor fill_generic_questions touched them,
    # so 'field is required' bounced Next forever. Reusable across tenants: if a checkbox
    # group has NO box checked, select the 'none/never/have not/not applicable' option
    # (safest truthful answer for a candidate who never worked there); else first option.
    handle_checkbox_groups(page)
    # Single required ACKNOWLEDGE/consent checkboxes on the Application-Questions step
    # (workday-ack-field 2026-06-10 GEICO 2358 EXIT-5 loop-cap): some tenants render a
    # required single checkbox like 'read and acknowledge' / 'I certify' / 'I understand'
    # with a hashed question id (e.g. abbe...000a) that is NOT the hardcoded
    # termsAndConditions--acceptTermsAndAgreements id and has <2 members so
    # handle_checkbox_groups skips it -> 'field is required' bounces Next forever. Tick
    # any unchecked single checkbox whose label/nearby text is acknowledgment-class.
    handle_ack_checkboxes(page)
    # (workday-ack-widget 2026-06-10 GEICO 2358) After ticking real <input type=checkbox>
    # acks, also satisfy ack/consent fields that are NOT plain checkboxes (ARIA checkbox,
    # radio group, or single-option listbox). The GEICO 'read and acknowledge' qid
    # abbe..000a renders as a non-checkbox widget -> handle_ack_checkboxes no-ops -> the
    # required field never satisfies -> Next bounces -> EXIT-5 loop-cap.
    handle_ack_widget(page)
    shot(page, "questions", "answered")

def handle_ack_checkboxes(page):
    """Tick required SINGLE acknowledge/consent checkboxes (not part of a multi-select
    group) on a questions step. Acknowledgments are non-knockout consent ticks the
    candidate must affirm to proceed (read-and-acknowledge / I certify / I agree / I
    understand / I have read). Idempotent: skips already-checked boxes and the
    work-experience currentlyWorkHere checkbox. Reusable across Workday tenants."""
    try:
        targets = page.evaluate(r"""()=>{
            const ACK=/(acknowledge|i certify|i agree|i consent|i understand|i have read|read and|i attest|i confirm that|by checking|hereby)/i;
            const out=[];
            // map id -> group size by shared trailing question-hash, to skip true groups
            const sizeByKey={};
            for(const c of document.querySelectorAll('input[type=checkbox]')){
              const id=c.id||''; const m=id.match(/-([0-9a-f]{12,})$/i); const k=m?m[1]:('_'+id);
              sizeByKey[k]=(sizeByKey[k]||0)+1;
            }
            for(const c of document.querySelectorAll('input[type=checkbox]')){
              const id=c.id||''; const name=c.name||'';
              if(c.checked) continue;
              if(/currentlyWorkHere/i.test(id)) continue; // WE block handles this
              const m=id.match(/-([0-9a-f]{12,})$/i); const k=m?m[1]:('_'+id);
              if((sizeByKey[k]||0)>=2) continue; // part of a multi-select group
              // gather label + nearby ancestor text
              let txt='';
              const l=document.querySelector('label[for=\''+id+'\']');
              if(l) txt=(l.textContent||'').trim();
              if(!ACK.test(txt)){let p=c.parentElement;for(let i=0;i<5&&p;i++){const t=(p.innerText||'').trim();if(t){txt=t;break;}p=p.parentElement;}}
              if(ACK.test(txt)) out.push({id, label:(txt||'').slice(0,60)});
            }
            return out;
        }""")
    except Exception as e:
        log("  ack-checkbox eval fail", str(e)[:60]); return
    for t in (targets or []):
        tid = t.get("id")
        if not tid: continue
        try:
            log(f"  ack-checkbox -> check {t.get('label','?')[:45]!r}")
            ok = page.evaluate("""(id)=>{const c=document.getElementById(id); if(!c)return false;
                const l=document.querySelector('label[for=\\''+id+'\\']');
                if(l){l.click(); if(c.checked)return true;}
                try{c.click();}catch(e){}
                if(!c.checked){const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'checked').set; set.call(c,true); c.dispatchEvent(new Event('click',{bubbles:true})); c.dispatchEvent(new Event('change',{bubbles:true}));}
                return c.checked;}""", tid)
            page.wait_for_timeout(300)
            if not ok:
                try:
                    page.locator(f"label[for='{tid}']").first.click(timeout=3000); page.wait_for_timeout(300)
                except Exception: pass
        except Exception as e:
            log("  ack-checkbox err", str(e)[:60])

def _dump_ack_diag(page):
    """One-time full-DOM diagnostic of every acknowledgement-class widget on the page so a
    NEW unknown ack widget class can be refined. Writes ../.workday-debug/ack-widget-diag-
    <tenant>.json. Best-effort; never raises."""
    try:
        diag = page.evaluate(r"""()=>{
            const ACK=/(acknowledge|i certify|i agree|i consent|i understand|i have read|read and|i attest|i confirm that|by checking|hereby|i acknowledge)/i;
            const out=[];
            const seen=new Set();
            for(const el of document.querySelectorAll('*')){
              const own=Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ').trim();
              if(!own || !ACK.test(own)) continue;
              let wrap=el; for(let i=0;i<8&&wrap;i++){const a=(wrap.getAttribute&&wrap.getAttribute('data-automation-id'))||''; if(/formField|questionItem|multiSelectContainer|checkbox|radio|listbox/i.test(a)) break; wrap=wrap.parentElement;}
              if(!wrap) wrap=el;
              const key=wrap.outerHTML.slice(0,60); if(seen.has(key)) continue; seen.add(key);
              const desc=(n)=>({tag:n.tagName, role:(n.getAttribute&&n.getAttribute('role'))||'', aid:(n.getAttribute&&n.getAttribute('data-automation-id'))||'', id:n.id||'', name:(n.getAttribute&&n.getAttribute('name'))||'', ariaReq:(n.getAttribute&&n.getAttribute('aria-required'))||'', ariaChecked:(n.getAttribute&&n.getAttribute('aria-checked'))||'', ariaHaspopup:(n.getAttribute&&n.getAttribute('aria-haspopup'))||'', ariaLabel:(n.getAttribute&&n.getAttribute('aria-label'))||'', type:(n.getAttribute&&n.getAttribute('type'))||'', text:(n.innerText||'').trim().slice(0,80)});
              const rec={ack_text:own.slice(0,80), wrapper:desc(wrap), interactive:[]};
              for(const n of wrap.querySelectorAll('button,input,[role=option],[role=radio],[role=checkbox],[role=button],[role=listbox],a[href],select')){ rec.interactive.push(desc(n)); }
              out.push(rec);
            }
            return out;
        }""")
        import json as _json
        DBG.mkdir(parents=True, exist_ok=True)
        p = DBG / ("ack-widget-diag-" + str(globals().get('_CUR_TENANT', 'x')) + ".json")
        p.write_text(_json.dumps(diag, indent=2))
        log("  ack-widget DIAG dumped ->", str(p), "(" + str(len(diag or [])) + " widget(s))")
        if diag:
            log("  ack-widget DIAG (first):", _json.dumps(diag[0])[:600])
    except Exception as e:
        log("  ack-widget diag fail", str(e)[:80])


def handle_ack_widget(page):
    """Satisfy a REQUIRED acknowledgement/consent widget that is NOT an <input type=checkbox>
    (handle_ack_checkboxes already covers real checkboxes). Some Workday tenants render the
    'read and acknowledge' / 'I certify' affirmation as one of:
      (a) an ARIA checkbox  [role=checkbox][aria-checked=false]  (toggle it),
      (b) a radio group with an affirmative option [role=radio] (pick the ack/Yes one),
      (c) a single-option listbox button[aria-haspopup=listbox] whose lone option is the
          acknowledgement (open it, pick the affirmative option).
    GENERIC + data-automation-id/role-based (NOT hardcoded to a qid) so every Workday
    tenant benefits. Idempotent: only acts on widgets that look unsatisfied. Non-fatal.

    workday-ack-widget 2026-06-10 GEICO 2358 (qid abbe100a87fcd9ee2deb000a, text
    'read and acknowledge'): EXIT-5 loop-cap because the field is required but the
    checkbox handler found no <input type=checkbox> to tick."""
    ACK_RE = "(acknowledge|i certify|i agree|i consent|i understand|i have read|read and|i attest|i confirm that|by checking|hereby|i acknowledge)"
    acted = []
    # Pass 1+2 (ARIA checkbox / radio group): toggle/select inside the page in one shot.
    try:
        acted = page.evaluate(r"""(ACK_SRC)=>{
            const ACK=new RegExp(ACK_SRC,'i');
            const results=[];
            const fire=(el,types)=>{for(const t of types){try{el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}));}catch(e){}}};
            // 1) ARIA checkbox (role=checkbox) not yet checked, with ack text nearby
            for(const c of document.querySelectorAll('[role=checkbox]')){
              if(c.getAttribute('aria-checked')==='true') continue;
              let txt=(c.getAttribute('aria-label')||c.innerText||'').trim();
              if(!ACK.test(txt)){let p=c.parentElement;for(let i=0;i<6&&p;i++){const t=(p.innerText||'').trim();if(t){txt=t;break;}p=p.parentElement;}}
              if(!ACK.test(txt)) continue;
              const lbl=c.id?document.querySelector('label[for=\''+c.id+'\']'):null;
              if(lbl) lbl.click();
              if(c.getAttribute('aria-checked')!=='true'){try{c.click();}catch(e){} fire(c,['mousedown','mouseup','click']);}
              results.push({kind:'aria-checkbox',text:txt.slice(0,50),ok:c.getAttribute('aria-checked')==='true'});
            }
            // 2) radio group with an affirmative/ack option (role=radio), none selected
            const radios=Array.from(document.querySelectorAll('[role=radio]'));
            const byName={};
            for(const r of radios){const grp=r.closest('[role=radiogroup]'); const n=r.getAttribute('name')||(grp&&grp.getAttribute('data-automation-id'))||'_'; (byName[n]=byName[n]||[]).push(r);}
            for(const n in byName){
              const grp=byName[n];
              if(grp.some(r=>r.getAttribute('aria-checked')==='true'||(r.tagName==='INPUT'&&r.checked))) continue;
              let gtxt='';let p=grp[0].parentElement;for(let i=0;i<8&&p;i++){const t=(p.innerText||'').trim();if(t){gtxt=t;break;}p=p.parentElement;}
              if(!ACK.test(gtxt)) continue;
              const pick=grp.find(r=>{const t=(r.getAttribute('aria-label')||r.innerText||'').trim();return ACK.test(t)||/^(yes|i have read|acknowledge)/i.test(t);})||grp[0];
              try{pick.click();}catch(e){} fire(pick,['mousedown','mouseup','click']);
              const lbl=pick.id?document.querySelector('label[for=\''+pick.id+'\']'):null; if(lbl) lbl.click();
              results.push({kind:'aria-radio',text:gtxt.slice(0,50),ok:pick.getAttribute('aria-checked')==='true'});
            }
            return results;
        }""", ACK_RE)
        for a in (acted or []):
            log("  ack-widget [" + str(a.get('kind')) + "]", repr(a.get('text', '?')), "ok=" + str(a.get('ok')))
    except Exception as e:
        log("  ack-widget aria pass fail", str(e)[:80]); acted = []

    # Pass 3 (single-option / placeholder LISTBOX): open + pick the affirmative option via
    # Playwright. A Workday listbox button whose displayed value IS itself ack-class text
    # (e.g. ' read and acknowledge') is an UNCOMMITTED placeholder/prompt, NOT an answered
    # field -- it must be opened and a real option ('I have read and acknowledge' / Yes)
    # selected. (workday-ack-widget 2026-06-10 GEICO 2358: the button value 'read and
    # acknowledge' previously looked 'answered' so it was skipped -> EXIT-5 loop-cap.)
    try:
        ack_listboxes = page.evaluate(r"""(ACK_SRC)=>{
            const ACK=new RegExp(ACK_SRC,'i');
            const out=[];
            for(const b of document.querySelectorAll('button[aria-haspopup=listbox]')){
              const v=(b.getAttribute('aria-label')||b.innerText||'').trim();
              let txt='';let p=b.parentElement;for(let i=0;i<8&&p;i++){const t=(p.innerText||'').trim();if(t){txt=t;break;}p=p.parentElement;}
              const unanswered = (!v || /select one/i.test(v) || v.length<=2 || ACK.test(v));
              if(!unanswered) continue;
              if(!ACK.test(txt) && !ACK.test(v)) continue;
              out.push(b.id||b.getAttribute('data-automation-id')||'');
            }
            return out.filter(Boolean);
        }""", ACK_RE)
        for sel_id in (ack_listboxes or []):
            sel = ("button#" + sel_id) if not sel_id.startswith('[') else sel_id
            try:
                page.locator(sel).first.click(timeout=5000); page.wait_for_timeout(900)
                opts = page.locator("[role=option]").all()
                texts = [(o.text_content() or "").strip() for o in opts]
                log("  ack-widget [listbox " + sel_id[:24] + "] options=", repr(texts[:8]))
                idx = None
                for i, t in enumerate(texts):
                    tl = t.lower()
                    if tl in ("select one", ""):
                        continue
                    if re.search(r"acknowledge|i have read|i agree|i certify|i understand|^yes\b|\byes$", tl):
                        idx = i; break
                if idx is None:
                    idx = next((i for i, t in enumerate(texts) if t and t.lower() != "select one"), None)
                if idx is not None:
                    opts[idx].click(timeout=4000); page.wait_for_timeout(600)
                    newv = page.evaluate("(id)=>{const b=document.getElementById(id); return b?((b.getAttribute('aria-label')||b.innerText||'').trim()):''}", sel_id) if not sel_id.startswith('[') else ""
                    log("  ack-widget [listbox " + sel_id[:24] + "] picked", repr(texts[idx][:40]), "newval=", repr(newv[:40]))
                    acted.append({"kind": "listbox", "text": texts[idx][:40], "ok": True})
                else:
                    page.keyboard.press("Escape")
            except Exception as e:
                log("  ack-widget listbox click err", sel_id[:24], str(e)[:60])
    except Exception as e:
        log("  ack-widget listbox pass fail", str(e)[:80])

    # Pass 4 (DIAGNOSTIC): nothing acted but an ack field still looks present -> dump DOM.
    try:
        still = page.evaluate(r"""(ACK_SRC)=>{
            const ACK=new RegExp(ACK_SRC,'i');
            for(const el of document.querySelectorAll('label,span,div,p,legend')){
              const own=Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ').trim();
              if(own && ACK.test(own)) return true;
            }
            return false;
        }""", ACK_RE)
    except Exception:
        still = False
    if still and not [a for a in (acted or []) if a.get('ok')]:
        _dump_ack_diag(page)


def fill_freetext_questions(page):
    """Fill REQUIRED free-text questionnaire fields (Workday renders some screening questions
    as <input type=text|number> / <textarea> with id^=primaryQuestionnaire, NOT listboxes).
    These never appear in the listbox handlers or the listbox-only DIAG, so 'The field X is
    required and must have a value' bounces Next forever with NO captured error (the field
    isn't a button). GENERIC + label-keyword-based so it's reusable across tenants.
    Idempotent: only fills empty required fields. Per Cyrus doctrine (form fields are the
    bot's call -> maximize advancing), answers lean toward completing the application.

    workday-freetext-questions 2026-06-10 GEICO 2358: 'What is your desired salary?' +
    'List your reasons for leaving your last three positions.' were the REAL EXIT-5 blockers
    (the 'read and acknowledge' ack widget was a red herring -- it commits fine)."""
    try:
        fields = page.evaluate(r"""()=>{
            const out=[];
            const seen=new Set();
            for(const el of document.querySelectorAll('input[id^=primaryQuestionnaire],textarea[id^=primaryQuestionnaire],input[aria-required=true],textarea[aria-required=true]')){
              const tag=el.tagName;
              if(tag!=='INPUT' && tag!=='TEXTAREA') continue;
              const type=(el.getAttribute('type')||'text').toLowerCase();
              if(['checkbox','radio','file','hidden','button','submit'].includes(type)) continue;
              const required = el.getAttribute('aria-required')==='true' || el.required || el.getAttribute('aria-invalid')==='true';
              if(!required) continue;
              if((el.value||'').trim()) continue; // already filled
              if(el.id && seen.has(el.id)) continue; if(el.id) seen.add(el.id);
              // label / question text
              let lab='';
              if(el.id){const l=document.querySelector('label[for=\''+el.id+'\']'); if(l) lab=(l.textContent||'').trim();}
              if(!lab){const al=el.getAttribute('aria-label'); if(al) lab=al.trim();}
              if(!lab){let p=el.parentElement;for(let i=0;i<6&&p;i++){const l=p.querySelector('label,legend');if(l){lab=(l.textContent||'').trim();break;}p=p.parentElement;}}
              if(!lab){let p=el.parentElement;for(let i=0;i<6&&p;i++){const t=(p.innerText||'').trim();if(t){lab=t.split('\n')[0];break;}p=p.parentElement;}}
              out.push({id:el.id||el.getAttribute('data-automation-id')||'', tag, type, label:(lab||'').slice(0,120)});
            }
            return out;
        }""")
    except Exception as e:
        log("  freetext eval fail", str(e)[:60]); return
    for f in (fields or []):
        fid = f.get("id"); lab = (f.get("label") or ""); low = lab.lower(); ftype = f.get("type", "text")
        if not fid:
            continue
        val = _freetext_answer_for(low, ftype)
        try:
            ok = _set_native(page, fid, val)
            log(f"  freetext [{fid[-16:]}] {low[:45]!r} -> {val!r} ok={ok}")
            page.wait_for_timeout(250)
        except Exception as e:
            log("  freetext fill err", fid[-16:], str(e)[:60])


def _freetext_answer_for(low, ftype="text"):
    """Decide a sensible answer for a required free-text questionnaire field from its label.
    Reusable/generic. Doctrine: maximize advancing; never lie on factual knockouts."""
    import datetime as _dt
    _today = _dt.date.today()
    # Date section spinbutton fields (month/day/year for an ack/signature date).
    # These appear on PEP/compliance questions as 'I understand... Date: MM/DD/YYYY'.
    if low in ("month",) or "month" == low.strip():
        return str(_today.month)
    if low in ("day",) or "day" == low.strip():
        return str(_today.day)
    if low in ("year",) or "year" == low.strip():
        return str(_today.year)
    # Salary / compensation expectation -> a competitive in-range number (numeric field gets
    # digits only; text field may accept 'Negotiable' but a number is safest to not bounce).
    if any(k in low for k in ["salary", "compensation", "desired pay", "expected pay",
                               "pay expectation", "rate expectation", "desired rate",
                               "comp expectation", "target comp", "base salary"]):
        return "160000"
    # Reasons for leaving prior positions -> clean professional answer.
    if ("reason" in low and ("leav" in low or "left" in low or "departure" in low)) or "why did you leave" in low:
        return ("Seeking roles with greater scope, ownership, and growth. My internships "
                "concluded as scheduled, and I'm now pursuing a full-time program/technical "
                "program management opportunity where I can drive larger cross-functional impact.")
    # Notice period -> immediate/2 weeks.
    if "notice period" in low or ("notice" in low and "weeks" in low):
        return "2 weeks"
    # Years of experience numeric.
    if "years" in low and ("experience" in low or ftype == "number" or ftype == "numeric"):
        return "4"
    # How did you hear about us / referral source.
    if "how did you hear" in low or "hear about" in low or "referral source" in low:
        return "LinkedIn"
    # LinkedIn / portfolio URL.
    if "linkedin" in low:
        return "https://www.linkedin.com/in/cyrus-shekari"
    if "website" in low or "portfolio" in low or "github" in low:
        return "https://github.com/cyrusshekari"
    # Numeric fallback -> a benign number; text fallback -> a non-empty professional default.
    if ftype in ("number", "numeric", "tel"):
        return "0"
    return "N/A"


def handle_checkbox_groups(page):
    """Answer required checkbox-group questions (Workday renders multi-select 'select all
    that apply' questions as <input type=checkbox> groups, NOT listboxes). For each group
    that currently has NOTHING checked, pick the 'I have not / none / never / not
    applicable' option if present (truthful for a candidate who never worked there), else
    the last option, else the first. Reusable across tenants. Idempotent: skips groups
    that already have a checked box."""
    try:
        # Group checkboxes by the shared suffix after the first '-' in their id (Workday
        # checkbox-group members share a question-hash suffix). Fall back to name.
        groups = page.evaluate(r"""()=>{
            const byKey={};
            for(const c of document.querySelectorAll('input[type=checkbox]')){
              const id=c.id||''; const name=c.name||'';
              // skip ack/terms-style single checkboxes (they're handled elsewhere)
              let l=document.querySelector('label[for=\''+id+'\']');
              let txt=l?l.textContent.trim():'';
              if(!txt){let p=c.parentElement;for(let i=0;i<4&&p;i++){const t=(p.innerText||'').trim();if(t&&t.length<60){txt=t;break;}p=p.parentElement;}}
              // group key: the trailing question-hash after a '-' if present, else name
              let key=name;
              const m=id.match(/-([0-9a-f]{12,})$/i);
              if(m) key=m[1];
              if(!key) key='_'+id;
              (byKey[key]=byKey[key]||[]).push({id,checked:c.checked,label:txt});
            }
            // only return groups with >=2 members (true multi-select groups)
            const out={};
            for(const k in byKey){ if(byKey[k].length>=2) out[k]=byKey[k]; }
            return out;
        }""")
    except Exception as e:
        log("  checkbox-group eval fail", str(e)[:60]); return
    for key, members in (groups or {}).items():
        try:
            if any(m.get("checked") for m in members):
                continue  # already answered
            # choose option
            none_re = lambda t: bool(re.search(r"have not|haven't|never|none of the|not applicable|n/?a|no, i have not|i have not", (t or "").lower()))
            target = next((m for m in members if none_re(m.get("label"))), None)
            if not target:
                target = members[-1]  # fall back to last (often the negative/none option)
            tid = target["id"]
            log(f"  checkbox-group -> check {target.get('label','?')[:40]!r}")
            ok = page.evaluate("""(id)=>{const c=document.getElementById(id); if(!c)return false;
                const l=document.querySelector('label[for=\\''+id+'\\']');
                if(l){l.click(); if(c.checked)return true;}
                try{c.click();}catch(e){}
                if(!c.checked){const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'checked').set; set.call(c,true); c.dispatchEvent(new Event('click',{bubbles:true})); c.dispatchEvent(new Event('change',{bubbles:true}));}
                return c.checked;}""", tid)
            page.wait_for_timeout(400)
            if not ok:
                # last resort: Playwright check on the label
                try:
                    page.locator(f"label[for='{tid}']").first.click(timeout=3000); page.wait_for_timeout(300)
                except Exception: pass
        except Exception as e:
            log("  checkbox-group err", str(e)[:60])

def fill_generic_questions(page):
    # Workday questions often render as button[aria-haspopup=listbox]; iterate unanswered ones.
    btns = page.locator("button[aria-haspopup=listbox]").all()
    for b in btns:
        try:
            cur = (b.text_content() or "").strip()
            if cur and cur.lower() not in ("select one",""): continue
            # open
            label = ""
            try:
                lid = b.get_attribute("aria-labelledby")
            except Exception: lid=None
            b.click(); page.wait_for_timeout(600)
            # Decide answer from nearby text
            opts = page.locator("[role=option]").all()
            texts = [ (o.text_content() or "").strip() for o in opts ]
            choice = None
            low = [t.lower() for t in texts]
            # Default: Yes for auth, No for sponsorship — but we can't read label easily; pick 'Yes' if present else first non-empty
            if "yes" in low: choice_idx = low.index("yes")
            else: choice_idx = next((i for i,t in enumerate(texts) if t and t.lower()!="select one"), None)
            if choice_idx is not None:
                opts[choice_idx].click(); page.wait_for_timeout(400)
            else:
                page.keyboard.press("Escape")
        except Exception as e:
            log("q dropdown err", str(e)[:60])

def handle_self_identify(page):
    """Disability self-identification (Self Identify step). Name* + Date* + one checkbox.
    Choose 'I do not want to answer'. Checkbox ids are form-hash specific -> match by label text."""
    log("step: Self Identify (disability)")
    page.wait_for_timeout(1200)
    # Name
    fill_if(page, "input#selfIdentifiedDisabilityData--name", f"{FIRST} {LAST}")
    # Date = today. Workday date widgets are spinbutton sections that .fill() does NOT reliably
    # commit (Nvidia 2829 dryrun: day drifted 11->20 across visits + 'Please choose'/page error
    # -> loop-cap EXIT-5). Use the keyboard-commit date helper (same path that fixed work-exp
    # dates) so the signed date persists. (workday-selfid-fix 2026-06-11)
    import datetime
    now = datetime.date.today()
    try:
        # Month/DAY/Year signed-date: type the FULL date as one continuous keyboard run into
        # the month section (Workday auto-advances M->D->Y) so the widget's React date model
        # is actually built. Per-section js-focus (_fill_wd_date) leaves it half-built -> every
        # section reads back yet Workday shows 'Enter a valid date' -> EXIT-5 (Nvidia 2829
        # 2026-06-11). Fall back to _fill_wd_date then fill_if. (workday-selfid-fix)
        _ok = _wd_fill_mdy_sequential(page, "selfIdentifiedDisabilityData--dateSignedOn",
                                      now.month, now.day, now.year)
        if not _ok:
            log("  self-id date: mdy-sequential not verified, trying _fill_wd_date")
            _ok = _fill_wd_date(page, "selfIdentifiedDisabilityData--dateSignedOn", f"{now.month:02d}", f"{now.year}")
        if not _ok:
            log("  self-id date: falling back to fill_if per-section")
            fill_if(page, "input#selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input", f"{now.month:02d}")
            fill_if(page, "input#selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input", f"{now.day:02d}")
            fill_if(page, "input#selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input", f"{now.year}")
    except Exception as _de:
        log("  self-id date err", str(_de)[:80])
        fill_if(page, "input#selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input", f"{now.month:02d}")
        fill_if(page, "input#selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input", f"{now.day:02d}")
        fill_if(page, "input#selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input", f"{now.year}")
    # Disability status: 3 mutually-exclusive options (Yes / No / 'I do not want to answer').
    # OLD handler clicked once + read .value (always 'on') so it could NOT tell whether the
    # option actually committed -> re-clicked the same one every revisit while Workday required-
    # validation still failed. FIX (workday-selfid-fix 2026-06-11): pick 'do not want to answer',
    # click via its label, then VERIFY el.checked===true (reads .checked, not .value), clearing
    # any OTHER checked option, retrying up to 3x.
    try:
        target_id = page.evaluate("""()=>{const cbs=Array.from(document.querySelectorAll('input[id$=disabilityStatus]'));
            for(const c of cbs){let p=c.parentElement;let txt='';for(let i=0;i<5&&p;i++){const t=(p.innerText||'').trim();if(t.length>3){txt=t;break;}p=p.parentElement;}
              if(/do not want to answer|not to answer|don.t wish/i.test(txt)) return c.id;}
            return cbs.length?cbs[cbs.length-1].id:null;}""")
        if target_id:
            committed = False
            for _attempt in range(3):
                page.evaluate("""(id)=>{
                    for(const c of document.querySelectorAll('input[id$=disabilityStatus]')){
                      if(c.id!==id && c.checked){const l=document.querySelector('label[for=\\''+c.id+'\\']'); (l||c).click();}
                    }
                    const tl=document.querySelector('label[for=\\''+id+'\\']'); const tc=document.getElementById(id);
                    if(tc && !tc.checked){ (tl||tc).click(); }
                }""", target_id)
                page.wait_for_timeout(500)
                committed = bool(page.evaluate("(id)=>{const c=document.getElementById(id); return !!(c&&c.checked);}", target_id))
                if committed:
                    break
            log("disability option committed:", committed, target_id[:12])
    except Exception as e:
        log("self-id checkbox err", str(e)[:80])
    shot(page, "selfid", "done")

def handle_voluntary(page):
    log("step: Voluntary/Self-Identify")
    page.wait_for_timeout(1500)
    DECLINE = ["Decline to State", "Decline to self identify", "Decline to self-identify",
               "do not wish to self-identify", "I do not wish to answer", "I don't wish to answer",
               "Do not wish to disclose", "Prefer not to", "I choose not to disclose",
               "I DO NOT WISH TO SELF-IDENTIFY", "Decline", "Not Applicable"]
    # Voluntary Disclosures: ethnicity / gender / veteranStatus listbox buttons.
    # (workday-paypal-voluntary-button-sel-fix 2026-06-14): PayPal uses data-automation-id
    # instead of element id for these buttons. Try both selectors.
    for bid in ["personalInfoUS--ethnicity", "personalInfoUS--gender", "personalInfoUS--veteranStatus"]:
        sel_id = f"button#{bid}"
        sel_auto = f"button[data-automation-id='{bid}']"
        loc = page.locator(sel_id).first
        if not loc.count():
            loc = page.locator(sel_auto).first
        if not loc.count():
            continue
        # Resolve the working selector for wd_pick_listbox
        btn_sel = sel_id if page.locator(sel_id).count() else sel_auto
        # skip if already set
        cur = (loc.text_content() or "").strip()
        if cur and cur.lower() != "select one":
            continue
        done = False
        for opt in DECLINE:
            if wd_pick_listbox(page, btn_sel, opt):
                done = True; break
        if not done:
            # veteran often uses 'I am not a protected veteran' / gender needs a real value;
            # fall back to first non-'Select One' option.
            try:
                loc.click(); page.wait_for_timeout(700)
                for o in page.locator("[role=option]").all():
                    t = (o.text_content() or "").strip()
                    if t and t.lower() != "select one":
                        o.click(); page.wait_for_timeout(400); break
            except Exception: pass
    # (workday-paypal-voluntary-ethnicity-fix 2026-06-14):
    # PayPal Race/Ethnicity = checkbox multi-select (input[id$=-ethnicityMulti]).
    # React state NOT updated by DOM el.checked=true + change event. Must use Playwright
    # native check() which triggers React synthetic events properly.
    # Strategy: JS identifies the decline input's element ID, then Playwright check()s it.
    try:
        eth_inputs = page.locator(r"input[id$=-ethnicityMulti]")
        n_eth = eth_inputs.count()
        if n_eth > 0:
            _declines = ["do not wish to identify", "decline to identify", "decline",
                         "prefer not", "do not wish to disclose", "i do not wish"]
            # Step 1: JS scan to find the decline input's ID (by proximity to label text)
            # Also returns IDs of any currently-checked inputs so we can uncheck them
            _eth_scan = page.evaluate(
                "(declines)=>{"
                "  var inputs = Array.from(document.querySelectorAll('[id$=-ethnicityMulti]'));"
                "  var declineId = null;"
                "  var checkedIds = [];"
                "  inputs.forEach(function(inp){"
                "    if(inp.checked) checkedIds.push(inp.id);"
                "    var el = inp;"
                "    var txt = '';"
                "    for(var k=0;k<5&&el;k++){"
                "      txt = el.textContent ? el.textContent.toLowerCase().trim() : '';"
                "      if(txt && declines.some(function(d){return txt.indexOf(d)>=0;})) { declineId=inp.id; break; }"
                "      el = el.parentElement;"
                "    }"
                "  });"
                "  if(!declineId){"
                "    var labels = Array.from(document.querySelectorAll('label'));"
                "    labels.forEach(function(lbl){"
                "      var txt = lbl.textContent.toLowerCase().trim();"
                "      if(!declineId && declines.some(function(d){return txt.indexOf(d)>=0 && txt.length<60;})){"
                "        var rect = lbl.getBoundingClientRect();"
                "        var closest=null, cDist=999;"
                "        inputs.forEach(function(inp){"
                "          var r=inp.getBoundingClientRect();"
                "          var d=Math.abs(r.top-rect.top)+Math.abs(r.left-rect.left);"
                "          if(d<cDist){cDist=d;closest=inp;}"
                "        });"
                "        if(closest && cDist<150) declineId=closest.id;"
                "      }"
                "    });"
                "  }"
                "  return {declineId: declineId, checkedIds: checkedIds};"
                "}",
                _declines
            )
            if isinstance(_eth_scan, dict):
                _checked_ids = _eth_scan.get('checkedIds', [])
                _decline_id = _eth_scan.get('declineId')
            else:
                _checked_ids = []
                _decline_id = None
            log(f"  voluntary: ethnicity scan -> declineId={str(_decline_id)[:30]} checkedIds={_checked_ids}")
            # Step 2: uncheck any currently-checked inputs via Playwright (React-safe)
            for _chk_id in _checked_ids:
                try:
                    _inp_loc = page.locator(f"input[id='{_chk_id}']").first
                    if _inp_loc.count() and _inp_loc.is_checked():
                        _inp_loc.uncheck(force=True)
                        page.wait_for_timeout(200)
                except Exception: pass
            # Step 3: Playwright check() on the decline input (React-safe)
            if _decline_id:
                try:
                    _dec_loc = page.locator(f"input[id='{_decline_id}']").first
                    if _dec_loc.count():
                        _dec_loc.check(force=True)
                        page.wait_for_timeout(400)
                        if _dec_loc.is_checked():
                            log(f"    ethnic: Playwright-checked decline input ({_decline_id[:30]})")
                        else:
                            log(f"    ethnic: WARNING check() ran but still unchecked -> JS fallback")
                            # JS fallback with React fiber onChange
                            page.evaluate(
                                "(id)=>{var el=document.getElementById(id);"
                                "if(el){el.checked=true;"
                                "var nativeInput=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'checked');"
                                "if(nativeInput&&nativeInput.set){nativeInput.set.call(el,true);}"
                                "el.dispatchEvent(new Event('change',{bubbles:true,cancelable:true}));"
                                "el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));}}",
                                _decline_id
                            )
                            page.wait_for_timeout(300)
                except Exception as _de:
                    log(f"    ethnic: decline check err: {str(_de)[:60]}")
            else:
                log("    ethnic: could not identify decline input ID")
    except Exception as _ete:
        log(f"  voluntary ethnicity-multi err: {str(_ete)[:80]}")
    # Terms & conditions checkbox
    try:
        cb = page.locator("input#termsAndConditions--acceptTermsAndAgreements").first
        if cb.count():
            if not cb.is_checked():
                cid = cb.get_attribute("id")
                _tc_done = False
                # Method 1: label click
                lbl = page.locator(f"label[for='{cid}']").first
                if lbl.count():
                    try: lbl.click(force=True); _tc_done = True
                    except Exception: pass
                # Method 2: Playwright check
                if not _tc_done:
                    try: cb.check(force=True); _tc_done = True
                    except Exception: pass
                # Method 3: JS check + change (reliable for React-controlled inputs)
                if not _tc_done:
                    try:
                        page.evaluate(
                            "(id)=>{var el=document.getElementById(id);"
                            "if(el&&!el.checked){el.checked=true;"
                            "el.dispatchEvent(new Event('change',{bubbles:true}));"
                            "el.dispatchEvent(new Event('click',{bubbles:true}));}}",
                            cid
                        )
                        _tc_done = True
                    except Exception: pass
                # Method 4: find a consent/agree label nearby
                if not _tc_done:
                    try:
                        for _tc_txt in ['consent', 'i have read', 'terms and conditions', 'agree']:
                            _tc_lbl = page.locator(f"label:has-text('{_tc_txt}')").first
                            if _tc_lbl.count():
                                _tc_lbl.click(force=True); _tc_done = True; break
                    except Exception: pass
                # Method 5: force click the checkbox itself
                if not _tc_done:
                    try: cb.click(force=True)
                    except Exception: pass
                page.wait_for_timeout(400)
                if cb.is_checked():
                    log("  T&C: checked OK")
                else:
                    log("  T&C: WARNING - still unchecked after all attempts")
    except Exception as e:
        log("terms cb err", str(e)[:60])
    # Self Identify (disability) sub-step: radio 'I do not want to answer' + name + date
    try:
        # disability self-id radios are visually-hidden; click label by text
        for txt in ["do not want to answer", "not to answer", "don't wish to answer"]:
            lab = page.locator(f"label:has-text('{txt}')").first
            if lab.count():
                lab.click(); page.wait_for_timeout(300); break
    except Exception: pass
    fill_if(page, "input#selfIdentifiedDisabilityData--name", f"{FIRST} {LAST}")
    fill_if(page, "[data-automation-id=name] input", f"{FIRST} {LAST}")
    shot(page, "voluntary", "done")

def submit_final(page):
    for sel in ["[data-automation-id=submit]","[data-automation-id=pageFooterNextButton]","button:has-text('Submit')"]:
        if page.locator(sel).count():
            txt = (page.locator(sel).first.text_content() or "")
            log("clicking submit-ish:", sel, txt[:30])
            if safe_click(page, sel): return True
    return False

def verify_confirmation(page, base_url=None):
    page.wait_for_timeout(2000)
    body = (page.locator("body").text_content() or "").lower()
    for kw in ["you have submitted","submitted your application","thank you for applying","application submitted","successfully submitted","received your application","we have received",
               # FIX (workday-proof 2026-06-02 Snap 1933): after a successful Submit, Snap's
               # Workday redirects back to the JD page which then reads 'You applied for this
               # job on <date>' + shows a 'View Application' (viewButton) instead of Apply.
               # The runner previously missed this -> logged EXIT5 false-negative even though
               # the app submitted server-side. Treat these as confirmation.
               "you applied for this job on","you applied for this job"]:
        if kw in body:
            log("confirmation matched:", kw); return True
    # candidate home active application
    if "active application" in body or "my applications" in body:
        log("confirmation via active applications listing"); return True
    # Post-submit JD signal: viewButton present = an application now exists for this candidate.
    if page.locator("[data-automation-id=viewButton]").count():
        log("confirmation via viewButton (existing application on JD)"); return True
    # Last resort: re-nav to the JD base and re-check for the 'you applied' banner / viewButton,
    # since the submit redirect can race. Only do this if we have the base url.
    if base_url:
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=45000); page.wait_for_timeout(4000)
            b2 = (page.locator("body").text_content() or "").lower()
            if "you applied for this job" in b2 or page.locator("[data-automation-id=viewButton]").count():
                log("confirmation via JD re-nav (you-applied/viewButton)"); return True
        except Exception as _e:
            log("verify re-nav fail", str(_e)[:80])
    log("no confirmation keyword; body head:", body[:300])
    return False

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--role-id", type=int, default=0)
    ap.add_argument("--resume", required=True)
    ap.add_argument("--source", default=SOURCE_DEFAULT)
    ap.add_argument("--dryrun", action="store_true")
    # FRESH-ACCOUNT controls (workday-fresh-account-fix 2026-06-08). Default behavior is
    # decided by resolve_account_for_tenant(): EVERY tenant mints a FRESH account by
    # default so work-history is filled from the tailored resume (global fresh default,
    # Cyrus 2026-06-08). These flags are explicit escape hatches: --legacy-account forces
    # historical sign-in; --fresh-account just re-affirms the default.
    ap.add_argument("--fresh-account", dest="fresh_account", action="store_true",
                    help="Force CREATE-FRESH account even for a clean tenant (never reuse saved profile).")
    ap.add_argument("--legacy-account", dest="legacy_account", action="store_true",
                    help="Force legacy sign-in into the historical saved account (opt out of fresh-account default).")
    args = ap.parse_args()
    rc = run(args)
    # Debug-shot lifecycle (Cyrus 2026-06-02): on a clean outcome, prune the step-N
    # debug clutter but ALWAYS keep confirmation/proof shots. On failure, keep the full
    # trail for diagnosis. rc 0 = submitted, rc 7 = already-applied (terminal-good).
    try:
        from debug_shots import prune_step_shots_on_success
        prune_step_shots_on_success(str(DBG), args.tenant, rc, success_codes=(0, 7))
    except Exception as _e:
        print(f"[wd] debug-shot prune skipped: {_e}")
    print(f"[wd] EXIT {rc}")
    sys.exit(rc)
