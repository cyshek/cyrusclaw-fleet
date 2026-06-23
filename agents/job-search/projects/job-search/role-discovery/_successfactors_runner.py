#!/usr/bin/env python3
"""
_successfactors_runner.py — SAP SuccessFactors guest-apply runner.

Proven recipe: Schaeffler 1284 SUBMITTED on career5.successfactors.eu (2026-05-31).
A.O. Smith 2280 tested on career8.successfactors.com (2026-06-22).

Flow:
  1. Navigate to SF job-save URL (career_ns=job_save&career_job_req_id=<id>)
  2. Sign-in page: click "Create an account" OR sign in if account exists
  3. For new account: fill fbclc_* + tor__f* fields, accept data privacy, submit
  4. After login/account-creation: modal may appear (dismiss), then apply form loads
  5. Fill EEO, screening questions, upload resume
  6. Click #fbqa_apply → success = isRedirectToAppSent=true in URL

Exit codes:
    0 = submitted (or dryrun ok)
    1 = error / unexpected failure
    6 = req closed / not found
    7 = already applied
"""
from __future__ import annotations
import argparse, json, os, re, sys, time, traceback
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# CDP connection
# ---------------------------------------------------------------------------
CDP_ENDPOINT = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")


def _get_page(cdp_endpoint: str = None):
    from playwright.sync_api import sync_playwright
    ep = cdp_endpoint or CDP_ENDPOINT
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(ep)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    return pw, browser, ctx, page


# ---------------------------------------------------------------------------
# Field-fill helpers (React-compatible native setter)
# ---------------------------------------------------------------------------
_JS_FILL = """([sel, val]) => {
    const el = document.querySelector(sel);
    if (!el) return sel + ':MISSING';
    const proto = el.tagName === 'SELECT' ? window.HTMLSelectElement.prototype
        : (el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype
        : window.HTMLInputElement.prototype);
    const d = Object.getOwnPropertyDescriptor(proto, 'value');
    if (d && d.set) d.set.call(el, val); else el.value = val;
    el.dispatchEvent(new Event('input',  {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
    el.dispatchEvent(new Event('blur',   {bubbles:true}));
    return sel + ':ok';
}"""

_JS_CLICK_RADIO = """([name, val]) => {
    for (const r of document.querySelectorAll('[name="' + name + '"]')) {
        if (r.value === String(val)) { r.click(); return name + '=' + val + ':ok'; }
    }
    return name + '=' + val + ':MISSING';
}"""


def _fill(page, selector: str, value: str) -> str:
    return page.evaluate(_JS_FILL, [selector, value])


def _click_radio(page, name: str, value: str) -> str:
    return page.evaluate(_JS_CLICK_RADIO, [name, str(value)])


def _screenshot(page, label: str, debug_dir: Path):
    if not debug_dir:
        return
    debug_dir.mkdir(parents=True, exist_ok=True)
    path = debug_dir / f"sf_{label}.png"
    try:
        page.screenshot(path=str(path))
        print(f"[sf_runner] screenshot: {path}")
    except Exception as e:
        print(f"[sf_runner] screenshot failed {label}: {e}")
    return str(path)


def _log(*args):
    print("[sf_runner]", *args, flush=True)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
_SF_TENANT_RX = re.compile(
    r"https?://(?P<server>career\d+\.successfactors\.(?:com|eu))/career.*[?&]company=(?P<tenant>[^&]+)",
    re.I,
)
_SF_JOB_ID_RX = re.compile(r"[?&](?:jobId|reqId|jobReqId|career_job_req_id)=(\d+)", re.I)
_SF_AOSMITH_RX = re.compile(r"jobs\.aosmith\.com/job/[^/]+/(\d+)")


def parse_sf_url(url: str) -> dict | None:
    """Return {server, tenant, job_id} or None."""
    m = _SF_TENANT_RX.search(url)
    if m:
        job_m = _SF_JOB_ID_RX.search(url)
        return {
            "server": m.group("server"),
            "tenant": m.group("tenant"),
            "job_id": job_m.group(1) if job_m else None,
        }
    ao = _SF_AOSMITH_RX.search(url)
    if ao:
        return {"server": "career8.successfactors.com", "tenant": "aosmith", "job_id": ao.group(1)}
    return None


def sf_apply_url(server: str, tenant: str, job_id: str) -> str:
    """Legacy compat: job listing URL with jobId param."""
    return f"https://{server}/career?company={tenant}&jobId={job_id}&lang=en_US"


def sf_career_url(server: str, tenant: str) -> str:
    return f"https://{server}/career?company={tenant}&lang=en_US"


def sf_job_save_url(server: str, tenant: str, req_id: str) -> str:
    """The URL that triggers the apply flow (sign-in page with job context)."""
    return (
        f"https://{server}/career?company={tenant}"
        f"&career_ns=job_save&career_job_req_id={req_id}"
        f"&navBarLevel=JOB_SEARCH&career_os=job_listing"
        f"&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected"
    )


def sf_signin_url(server: str, tenant: str, req_id: str) -> str:
    """Direct sign-in URL with job context (loginFlowRequired forces sign-in form)."""
    return (
        f"https://{server}/career?company={tenant}"
        f"&loginFlowRequired=true"
        f"&career_ns=job_save&career_job_req_id={req_id}"
    )


def sf_listing_url(server: str, tenant: str, req_id: str) -> str:
    # Use portalcareer (SPA) URL to preserve session after sign-in.
    # career? URLs force re-auth; portalcareer? URLs use cookie-based session.
    return (
        f"https://{server}/portalcareer?company={tenant}"
        f"&career_ns=job_listing&career_job_req_id={req_id}"
    )


CLOSED_PHRASES = [
    "no longer active", "no longer available", "position has been filled",
    "requisition has been closed", "job has expired", "not currently accepting",
    "job listing is no longer",
]
SUCCESS_URL_MARKER = "isRedirectToAppSent=true"
SUCCESS_BODY_PHRASES = [
    "your application has been sent",
    "thank you for applying",
    "application submitted",
    "application has been received",
]
ALREADY_APPLIED_PHRASES = ["already applied", "already submitted", "duplicate application"]


def detect_closed(page) -> bool:
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    return any(k in body for k in CLOSED_PHRASES)


def detect_already_applied(page) -> bool:
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    return any(k in body for k in ALREADY_APPLIED_PHRASES)


def detect_success(page) -> bool:
    url = page.url
    if SUCCESS_URL_MARKER in url:
        return True
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    return any(k in body for k in SUCCESS_BODY_PHRASES)


# ---------------------------------------------------------------------------
# Step 1: Check job active on listing page
# ---------------------------------------------------------------------------
def check_job_active(page, server: str, tenant: str, req_id: str, debug_dir: Path) -> str:
    """Returns 'active', 'closed', or 'unknown'."""
    url = sf_listing_url(server, tenant, req_id)
    _log(f"Checking job active: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    _screenshot(page, "01_job_listing", debug_dir)

    if detect_closed(page):
        _log("Job CLOSED")
        return "closed"

    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    html = page.content().lower()
    hints = ["apply now", "apply for this job", "applybutton", "fbqa_apply"]
    if any(h in body for h in hints) or any(h in html for h in hints):
        return "active"
    if req_id in page.url:
        return "active"
    return "unknown"


# ---------------------------------------------------------------------------
# Step 2: Navigate to sign-in page with job context, then create account or sign in
# ---------------------------------------------------------------------------
def navigate_to_signin(page, server: str, tenant: str, req_id: str, debug_dir: Path) -> str:
    """Navigate to the job-save (apply) URL which lands on sign-in page.
    Returns: 'signin_page', 'already_applied', 'apply_ready', 'error'
    """
    url = sf_job_save_url(server, tenant, req_id)
    _log(f"Navigating to apply URL: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    _screenshot(page, "02_signin_page", debug_dir)

    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    html = page.content()

    if detect_already_applied(page):
        return "already_applied"
    if SUCCESS_URL_MARKER in page.url:
        return "already_applied"
    if "fbqa_apply" in html or "fbclc_userName" in html:
        return "apply_ready"
    if "sign in" in body or "sign-in" in body or "username" in html.lower() or "email address" in body:
        return "signin_page"
    return "signin_page"  # optimistic


def get_create_account_href(page) -> str | None:
    """Find the 'Create an account' link on the sign-in page."""
    return page.evaluate("""() => {
        for (const l of document.querySelectorAll('a')) {
            if (l.href && /login_ns=register/.test(l.href)) return l.href;
        }
        for (const l of document.querySelectorAll('a')) {
            if (l.href && /career.*successfactors/.test(l.href) &&
                /create.*account|new.*user|not.*registered/i.test(l.innerText))
                return l.href;
        }
        return null;
    }""")


# ---------------------------------------------------------------------------
# Step 3: Fill account creation form
# ---------------------------------------------------------------------------
def fill_account_form(page, email: str, password: str, personal: dict, debug_dir: Path):
    """Fill fbclc_* + tor__f* registration fields and accept privacy."""
    _log("Filling account creation form...")
    identity = personal.get("identity", {})
    addr = personal.get("address", {})
    contact = personal.get("contact", {})

    # Basic account fields
    for sel, val in [
        ("input[name='fbclc_userName']",   email),
        ("input[name='fbclc_emailConf']",  email),
        ("input[name='fbclc_pwd']",        password),
        ("input[name='fbclc_pwdConf']",    password),
        ("input[name='fbclc_fName']",      identity.get("first_name", "Cyrus")),
        ("input[name='fbclc_lName']",      identity.get("last_name", "Shekari")),
    ]:
        r = _fill(page, sel, val)
        _log(f"  {sel} -> {r.split(':')[-1]}")

    # Country select → US
    cv = page.evaluate("""() => {
        const s = document.querySelector("select[name='fbclc_country']");
        if (!s) return null;
        for (const o of s.options)
            if (/^united states$/i.test(o.text.trim()) || o.value === 'US') return o.value;
        return null;
    }""")
    if cv:
        _fill(page, "select[name='fbclc_country']", cv)
        _log(f"  fbclc_country → {cv}")

    # Profile visibility = 2 (only recruiters for applied jobs)
    r = _click_radio(page, "fbclc_searPref", "2")
    _log(f"  fbclc_searPref=2 → {r.split(':')[-1]}")

    # Personal tor__f* fields
    tor_fields = [
        ("input[name='tor__fcellPhone']",       contact.get("phone", "").replace("-", "").replace(" ", "")),
        ("input[name='tor__faddress']",          addr.get("street", "")),
        ("input[name='tor__fzip']",              addr.get("zip", "")),
        ("input[name='tor__fcity']",             addr.get("city", "")),
        ("input[name='tor__fcustNoticePeriod']", "2 weeks"),
        ("input[name='tor__fcustSalExpect']",    ""),
    ]
    for sel, val in tor_fields:
        exists = page.evaluate(f"() => !!document.querySelector(\"{sel}\")")
        if exists:
            r = _fill(page, sel, val)
            _log(f"  {sel} -> {r}")

    # State: may be text or select
    state_val = addr.get("state", "WA")
    has_state_sel = page.evaluate("() => !!document.querySelector(\"select[name='tor__fstate']\")")
    if has_state_sel:
        sv = page.evaluate("""() => {
            const s = document.querySelector("select[name='tor__fstate']");
            for (const o of s.options)
                if (o.value === 'WA' || /^washington$/i.test(o.text.trim())) return o.value;
            return null;
        }""")
        if sv:
            _fill(page, "select[name='tor__fstate']", sv)
            _log(f"  tor__fstate (select) → {sv}")
    elif page.evaluate("() => !!document.querySelector(\"input[name='tor__fstate']\")"):
        _fill(page, "input[name='tor__fstate']", state_val)
        _log(f"  tor__fstate (text) → {state_val}")

    _screenshot(page, "03_account_filled", debug_dir)


def accept_data_privacy(page, debug_dir: Path) -> bool:
    """Click #dataPrivacyId → accept modal. Returns True if dpcsId populated."""
    has_link = page.evaluate("() => !!document.querySelector('#dataPrivacyId')")
    if not has_link:
        _log("  #dataPrivacyId not present - skipping")
        return True

    _log("Accepting data privacy...")
    page.evaluate("() => document.querySelector('#dataPrivacyId').click()")
    page.wait_for_timeout(2000)
    _screenshot(page, "04_privacy_modal", debug_dir)

    result = page.evaluate("""() => {
        const candidates = document.querySelectorAll(
            'button, input[type=button], a[role=button], [id^="dlgButton_"]'
        );
        for (const btn of candidates) {
            const t = (btn.innerText || btn.value || btn.textContent || '').trim();
            if (/^(accept|i agree|agree|ok|confirm|done|close)$/i.test(t)) {
                btn.click(); return 'accepted:' + t;
            }
        }
        const d = document.querySelector('[id^="dlgButton_"]');
        if (d) { d.click(); return 'dlgButton:' + d.id; }
        return 'NOT_FOUND';
    }""")
    _log(f"  privacy accept: {result!r}")

    if result == "NOT_FOUND":
        # Scroll modal to show buttons
        page.evaluate("""() => {
            const m = document.querySelector('[role=dialog],.ui-dialog,#dpcsDialogContainer');
            if (m) m.scrollTop = m.scrollHeight;
        }""")
        page.wait_for_timeout(500)
        result2 = page.evaluate("""() => {
            for (const btn of document.querySelectorAll('button, input[type=button]')) {
                const t = (btn.innerText || btn.value || '').trim().toLowerCase();
                if (t.includes('accept') || t.includes('agree') || t.includes('ok')) {
                    btn.click(); return 'retry:' + t;
                }
            }
            return 'STILL_NOT_FOUND';
        }""")
        _log(f"  privacy accept retry: {result2!r}")

    page.wait_for_timeout(1000)
    _screenshot(page, "05_privacy_done", debug_dir)
    dpcs = page.evaluate(
        "() => { const e = document.querySelector('[name=fbclc_dpcsId]'); return e ? e.value : ''; }"
    )
    _log(f"  fbclc_dpcsId: {dpcs!r}")
    return bool(dpcs)


def submit_create_account(page, debug_dir: Path) -> str:
    """Click #fbclc_createAccountButton. Returns 'apply_ready', 'already_applied',
    'account_exists', 'need_signin', or 'error'.
    """
    _log("Submitting create-account form...")
    has_btn = page.evaluate("() => !!document.querySelector('#fbclc_createAccountButton')")
    if not has_btn:
        _log("  #fbclc_createAccountButton NOT FOUND")
        _screenshot(page, "err_no_create_btn", debug_dir)
        return "error"

    page.evaluate("() => document.querySelector('#fbclc_createAccountButton').click()")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(3000)
    _screenshot(page, "06_after_create_account", debug_dir)

    url = page.url
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    html = page.content()
    _log(f"  post-create URL: {url[:100]}")
    _log(f"  post-create body[200]: {body[:200]!r}")

    if detect_already_applied(page):
        return "already_applied"
    if SUCCESS_URL_MARKER in url:
        return "already_applied"
    if "fbqa_apply" in html or "job application" in body or "my applications" in body:
        _log("  Apply form detected")
        return "apply_ready"
    if "already exists" in body or "already registered" in body or "account already" in body:
        _log("  Account already exists")
        return "account_exists"

    banner = page.evaluate("""() => {
        const e = document.querySelector('.errorMessage,.error-banner,#errorMsg,.validationError');
        return e ? e.innerText.trim().substring(0, 200) : null;
    }""")
    if banner:
        _log(f"  Registration error: {banner!r}")
        _screenshot(page, "err_reg_error", debug_dir)
        return "error"

    if "sign in" in body or page.evaluate("() => !!document.querySelector('input[name=username], input[name=Email]')"):
        _log("  Landed on sign-in page after account creation")
        return "need_signin"

    # May be on apply form already (portalcareer URL is the apply form)
    if "portalcareer" in url:
        _log("  On portalcareer (apply form)")
        return "apply_ready"

    return "apply_ready"  # optimistic


def sign_in(page, email: str, password: str, debug_dir: Path,
            signin_url: str | None = None) -> str:
    """Sign in on the SF sign-in page. Returns 'apply_ready', 'already_applied', 'error'.
    If signin_url is provided and we're not on a sign-in form, navigate there first.
    """
    _log("Signing in...")

    # Check if we're actually on a sign-in form; if not, navigate to signin_url
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    on_signin = ("email address" in body[:500] and "password" in body[:500]) or \
                ("sign in" in body[:200] and "keyword" not in body[:200])
    if not on_signin:
        if signin_url:
            _log(f"  not on sign-in form; navigating to {signin_url[:80]}")
            page.goto(signin_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        else:
            _log("  WARNING: not on sign-in form and no signin_url provided")

    _screenshot(page, "07_signin_form", debug_dir)

    # SF sign-in uses 'username' or 'Email' field
    has_user = page.evaluate("() => !!document.querySelector('[name=username]')")
    has_email_txt = page.evaluate("() => !!document.querySelector('input[type=text][name*=mail], input[type=email]')")
    has_email_addr = page.evaluate("() => !!document.querySelector('[name=Email], [id=Email]')")

    if has_user:
        _fill(page, "[name=username]", email)
        _fill(page, "[name=password]", password)
    elif has_email_addr:
        _fill(page, "[name=Email]", email)
        _fill(page, "[name=Password]", password)
    elif has_email_txt:
        # Try the text field
        page.evaluate(f"""() => {{
            const f = document.querySelector('input[type=text][name*=mail], input[type=email]');
            if (f) f.value = '{email}';
            const p = document.querySelector('input[type=password]');
            if (p) p.value = '{password}';
        }}""")
    else:
        # Try filling the visible text/email fields
        page.evaluate(f"""() => {{
            const fields = document.querySelectorAll('input[type=text], input[type=email]');
            if (fields[0]) fields[0].value = '{email}';
            const pw = document.querySelector('input[type=password]');
            if (pw) pw.value = '{password}';
        }}""")

    _screenshot(page, "08_signin_filled", debug_dir)

    # Click Sign In button
    page.evaluate("""() => {
        for (const btn of document.querySelectorAll('button, input[type=submit]')) {
            const t = (btn.innerText || btn.value || '').trim();
            if (/^sign in$/i.test(t)) { btn.click(); return; }
        }
        // Fallback: submit form
        const form = document.querySelector('form[name=careerform], form');
        if (form) form.submit();
    }""")

    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(4000)
    _screenshot(page, "09_after_signin", debug_dir)

    url = page.url
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    html = page.content()
    _log(f"  post-signin URL: {url[:100]}")
    _log(f"  post-signin body[200]: {body[:200]!r}")

    if "invalid" in body or "incorrect" in body or "failed" in body:
        _log("  Sign-in failed!")
        _screenshot(page, "err_signin_failed", debug_dir)
        return "error"

    if detect_already_applied(page):
        return "already_applied"

    if SUCCESS_URL_MARKER in url:
        return "already_applied"

    # After sign-in, SF may land on portal home or directly on apply form
    if "fbqa_apply" in html or "job application" in body or "my applications" in body:
        _log("  Apply form detected after sign-in")
        return "apply_ready"

    if "welcome" in body and ("portalcareer" in url or "career" in url):
        _log("  Signed in (welcome page or portal home)")
        return "apply_ready"  # will navigate to apply form

    return "apply_ready"  # optimistic


def navigate_to_apply_after_signin(page, server: str, tenant: str, req_id: str, debug_dir: Path) -> str:
    """After sign-in, navigate to the job apply form.
    Returns 'apply_ready', 'already_applied', or 'error'.
    """
    # Try portalcareer path first (works when session is already established)
    portal_apply_url = (
        f"https://{server}/portalcareer?company={tenant}"
        f"&career_ns=job_save&career_job_req_id={req_id}"
        f"&navBarLevel=JOB_SEARCH&career_os=job_listing"
        f"&isApplyWithLinkedIn=false&joblist_jobApplyRedirect=applyRedirected"
    )
    _log(f"Navigating to apply form post-signin: {portal_apply_url[:100]}")
    page.goto(portal_apply_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)
    _screenshot(page, "10_apply_form", debug_dir)

    url = page.url
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    html = page.content()
    _log(f"  apply form URL: {url[:100]}")
    _log(f"  apply form body[200]: {body[:200]!r}")

    # If redirected to sign-in again, fall back to the /career path
    if "sign in" in body[:200] and "already have an account" in body[:400]:
        _log("  portalcareer path triggered re-auth; trying /career path")
        apply_url = sf_job_save_url(server, tenant, req_id)
        page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        _screenshot(page, "10b_apply_form_fallback", debug_dir)
        url = page.url
        body = page.evaluate("() => document.body.innerText.toLowerCase()")
        html = page.content()
        _log(f"  fallback apply form URL: {url[:100]}")

    if detect_already_applied(page):
        return "already_applied"
    if SUCCESS_URL_MARKER in url:
        return "already_applied"

    # Dismiss any onboarding modals
    for _ in range(5):
        dismissed = _dismiss_modal(page)
        if not dismissed:
            break
        page.wait_for_timeout(2000)
        _screenshot(page, "11_modal_dismissed", debug_dir)

    return "apply_ready"


def _dismiss_modal(page) -> bool:
    """Dismiss any overlay modal. Returns True if a modal was found."""
    return page.evaluate("""() => {
        const closeLabels = /^(close|skip|dismiss|cancel|x)$/i;
        const nextLabels  = /^(next|ok|got it|continue|start|done)$/i;
        const dialogSels = [
            '[role=dialog]:not([aria-hidden=true]) button',
            '.ui-dialog button',
            '.sf-dialog button',
            '.modal button',
            '.overlay button',
        ];
        for (const sel of dialogSels) {
            const btns = [...document.querySelectorAll(sel)].filter(b => {
                const r = b.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            });
            if (!btns.length) continue;
            // Prefer Close first (don't advance state)
            for (const b of btns) {
                const t = (b.innerText || b.value || '').trim();
                if (closeLabels.test(t)) { b.click(); return 'closed:' + t; }
            }
            for (const b of btns) {
                const t = (b.innerText || b.value || '').trim();
                if (nextLabels.test(t)) { b.click(); return 'next:' + t; }
            }
        }
        return null;
    }""") is not None


# ---------------------------------------------------------------------------
# Step 4: Fill apply form (EEO, screening Qs)
# ---------------------------------------------------------------------------
DECLINE_RE = (
    r"do not wish|decline|choose not|prefer not|not disclose|not to answer"
    r"|not a protected|not a veteran|rather not|no, i am not"
    r"|i choose not|not specified|i do not want"
)
EEO_FIELD_NAMES = [
    "tor__fethnicity", "tor__frace", "tor__fgender",
    "tor__fdisabilityStatus", "tor__fveteranStatus",
    "tor__fgenderIdentity", "tor__fsexualOrientation",
]


def fill_screening_questions(page, debug_dir: Path):
    """Answer fbjq_question_N radios and textareas."""
    _log("Screening questions...")
    questions = page.evaluate(r"""() => {
        const result = [], seen = new Set();
        for (const el of document.querySelectorAll('[name^="fbjq_question_"]')) {
            const m = el.name.match(/fbjq_question_(\d+)/);
            if (!m || seen.has(m[1])) continue;
            seen.add(m[1]);
            let label = '';
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) label = lbl.innerText.trim();
            if (!label) {
                const row = el.closest('tr,.question-row,.formRow');
                if (row) label = (row.innerText || '').trim().substring(0, 200);
            }
            result.push({n: m[1], id: el.id, tag: el.tagName, type: el.type || '', label});
        }
        return result;
    }""")
    _log(f"  {len(questions)} questions found")

    for q in questions:
        n = q["n"]
        lbl = q["label"].lower()
        tag = q["tag"]
        if tag == "INPUT":
            if any(k in lbl for k in ["18", "age", "authorized", "eligible", "legal right",
                                        "legally authorized", "citizenship", "right to work",
                                        "authorized to work", "work in the united states"]):
                ans, why = "0", "YES"
            elif any(k in lbl for k in ["sponsor", "visa", "work permit", "h-1b", "h1b",
                                          "sponsorship", "immigration"]):
                ans, why = "1", "NO (sponsorship)"
            elif any(k in lbl for k in ["previously employed", "previously worked", "former employee",
                                          "worked for this company"]):
                ans, why = "1", "NO (prev)"
            elif any(k in lbl for k in ["convicted", "felony", "criminal"]):
                ans, why = "1", "NO (criminal)"
            else:
                ans, why = "1", "NO (default)"
            r = _click_radio(page, f"fbjq_question_{n}", ans)
            _log(f"  Q{n} ({why}): {r.split(':')[-1]} | {lbl[:60]!r}")
        elif tag == "TEXTAREA":
            r = page.evaluate(_JS_FILL, [f"#{q['id']}", "See attached resume."])
            _log(f"  Q{n} textarea: {r.split(':')[-1]}")


def fill_eeo_fields(page, debug_dir: Path):
    """Decline all EEO sfCascadingPicklist fields."""
    _log("EEO fields (decline all)...")
    decline_re = re.compile(DECLINE_RE, re.IGNORECASE)

    for fname in EEO_FIELD_NAMES:
        exists = page.evaluate(f"() => !!document.querySelector('[name=\"{fname}\"]')")
        if not exists:
            continue
        _log(f"  EEO {fname}...")

        # Find the visible autocomplete trigger input
        autocomplete_id = page.evaluate(f"""() => {{
            const hidden = document.querySelector('[name="{fname}"]');
            if (!hidden) return null;
            // Walk up to container, find autocomplete input
            let c = hidden.closest('td, .sfpicklistContainer, .sf-field-row, .formControl');
            if (!c) c = hidden.parentElement;
            if (!c) return null;
            const inp = c.querySelector('input[id$=":_input"], input[id$="_input"]');
            if (inp) return inp.id;
            // Fallback: find by position in EEO field list
            const all = document.querySelectorAll('input[id$=":_input"]');
            const hiddens = [...document.querySelectorAll('[name^="tor__f"]')];
            const idx = hiddens.indexOf(hidden);
            if (idx >= 0 && idx < all.length) return all[idx].id;
            return null;
        }}""")

        if not autocomplete_id:
            _log(f"    {fname}: autocomplete input not found")
            continue

        # Focus + trigger dropdown
        try:
            page.focus(f"#{autocomplete_id}")
        except Exception:
            pass
        page.evaluate(f"""() => {{
            const el = document.getElementById('{autocomplete_id}');
            if (!el) return;
            el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
            el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
            el.dispatchEvent(new FocusEvent('focus', {bubbles:true}));
        }}""")
        page.wait_for_timeout(600)

        # Pick "decline / do not wish" option from dropdown
        options = page.query_selector_all("[id^='M:item'], .sf-option, [role=option]")
        declined = False
        for opt in options:
            try:
                text = (opt.inner_text() or "").strip()
                if decline_re.search(text):
                    page.evaluate("(el) => el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}))", opt)
                    _log(f"    {fname} → declined: {text[:50]!r}")
                    page.wait_for_timeout(300)
                    declined = True
                    break
            except Exception:
                pass

        if not declined:
            _log(f"    {fname}: no decline option found in {len(options)} options")

    _screenshot(page, "12_eeo_filled", debug_dir)


def _navigate_wizard(page, resume_path: str, personal: dict, debug_dir: Path):
    """Click through SF multi-step wizard steps until #fbqa_apply is visible.
    Each step: fill visible fields, click Next.
    """
    _log("Navigating wizard steps...")
    PERSONAL = personal or {}
    for step_num in range(1, 8):
        # Check if we're already at the submit button
        if page.evaluate("() => !!document.querySelector('#fbqa_apply')"):
            _log(f"  step {step_num}: #fbqa_apply visible — wizard done")
            return

        # Fill visible form fields on this step
        _fill_wizard_step(page, resume_path, PERSONAL, step_num, debug_dir)

        # Dismiss any modals that appeared during fill (clicking Next in modal advances wizard)
        # First check if there's a modal with a Next button and click it
        modal_next = page.evaluate("""
            () => {
                for (const sel of ['[role=dialog] button', '.ui-dialog button', '.modal button', 'button']) {
                    for (const b of document.querySelectorAll(sel)) {
                        const r = b.getBoundingClientRect();
                        if (r.width === 0) continue;
                        const t = (b.innerText || b.value || '').trim();
                        if (/^next$/i.test(t)) { b.click(); return 'next:' + t; }
                    }
                }
                return null;
            }
        """)
        if modal_next:
            _log(f"  step {step_num}: clicked '{modal_next}' in modal")
            page.wait_for_timeout(2000)
        page.wait_for_timeout(500)

        # Check if #fbqa_apply appeared after modal dismissal
        if page.evaluate("() => !!document.querySelector('#fbqa_apply')"):
            _log(f"  step {step_num}: #fbqa_apply visible after modal dismiss")
            return

        # Find and click Next button (may be below viewport fold)
        clicked_next = page.evaluate("""
            () => {
                // Try by id first
                for (const sel of ['#fbqa_next', 'input[value=Next]', 'input[value=next]']) {
                    const el = document.querySelector(sel);
                    if (el) { el.scrollIntoView({block:'center'}); el.click(); return 'next:' + sel; }
                }
                // Try buttons with Next text
                for (const btn of document.querySelectorAll('button, input[type=button], input[type=submit]')) {
                    const t = (btn.innerText || btn.value || '').trim();
                    if (/^next$/i.test(t)) { btn.scrollIntoView({block:'center'}); btn.click(); return 'next:btn:' + t; }
                }
                return null;
            }
        """)
        if not clicked_next:
            _log(f"  step {step_num}: no Next button found — checking for Apply")
            break
        _log(f"  step {step_num}: clicked Next ({clicked_next})")
        page.wait_for_timeout(2500)
        _screenshot(page, f"wizard_step{step_num+1}", debug_dir)

        # Dismiss any modal after Next
        for _ in range(3):
            if not _dismiss_modal(page):
                break
            page.wait_for_timeout(1000)


def _fill_wizard_step(page, resume_path: str, personal: dict, step_num: int, debug_dir: Path):
    """Fill whatever fields are visible on the current wizard step."""
    from pathlib import Path as _Path

    # Step 1 (Getting Started): 'How to proceed' dropdown -> Resume, then upload resume
    proc_sel = page.query_selector("select[name*='proceed'], select[id*='proceed']")
    if proc_sel:
        try:
            proc_sel.select_option("Resume")
        except Exception:
            pass

    # Upload resume if file input is visible (and no resume shown yet)
    file_input = page.query_selector(
        "input[type=file][name*=resume], input[type=file][id*=resume], "
        "input[type=file][name*=Resume], input[type=file][id*=Resume], "
        "input[type=file]"
    )
    if file_input and resume_path and _Path(resume_path).exists():
        existing = page.evaluate(
            """() => {
                const l = document.querySelector('.fileUploadName, [class*=filename], [id*=resumeName]');
                return l ? l.innerText.trim() : '';
            }"""
        )
        if existing:
            _log(f"  step {step_num}: resume already shown ({existing[:40]}) - skipping upload")
        else:
            _log(f"  step {step_num}: uploading resume")
            file_input.set_input_files(resume_path)
            page.wait_for_timeout(1500)
            # Wait for overwrite confirmation modal and dismiss it
            # Try Cancel first (keeps existing profile data; faster than re-parse)
            dismissed = False
            for attempt in range(6):
                modal_txt = page.evaluate("""() => {
                    const d = document.querySelector('.ui-dialog, [role=dialog]');
                    return d ? d.innerText.trim().substring(0, 200) : '';
                }""")
                if not modal_txt:
                    if attempt < 3:
                        page.wait_for_timeout(1000)
                        continue
                    break
                # Modal found - click Cancel to keep existing data
                cancel_clicked = page.evaluate("""() => {
                    for (const el of document.querySelectorAll('a, button')) {
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        if (t === 'cancel' || t === 'no') { el.click(); return 'cancel'; }
                    }
                    return null;
                }""")
                if cancel_clicked:
                    _log(f"  step {step_num}: clicked Cancel on overwrite modal (JS)")
                    dismissed = True
                    page.wait_for_timeout(500)
                    break
                # Cancel not found - try Yes
                yes_clicked = page.evaluate("""() => {
                    for (const el of document.querySelectorAll('button, input[type=button]')) {
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        if (t === 'yes') { el.click(); return 'yes'; }
                    }
                    return null;
                }""")
                if yes_clicked:
                    _log(f"  step {step_num}: clicked Yes on overwrite modal (JS)")
                    dismissed = True
                    page.wait_for_timeout(5000)
                    break
                page.wait_for_timeout(1000)
            if not dismissed:
                _log(f"  step {step_num}: no overwrite modal appeared - proceeding")
            # Wait for any parsing spinner to finish
            for _ in range(15):
                try:
                    is_parsing = page.evaluate("""() => {
                        const m = document.querySelector('.blockUI, [class*=loading], [class*=spinner]');
                        if (m && m.offsetParent !== null) return true;
                        for (const el of document.querySelectorAll('.ui-dialog-title')) {
                            if (el.innerText && el.innerText.indexOf('Uploading') >= 0) return true;
                        }
                        return false;
                    }""")
                    if not is_parsing:
                        break
                except Exception:
                    break
                page.wait_for_timeout(1000)
            page.wait_for_timeout(1000)
            if dismissed and cancel_clicked == 'cancel':
                return  # resume kept; nothing else to do for this step
    # Fill profile fields if visible (step 2 Profile Info)
    for sel, val in [
        ("input[name='tor__fphone']", personal.get("phone", "3468040227")),
        ("input[name='tor__faddress']", personal.get("address", "12420 NE 120th St #1437")),
        ("input[name='tor__fzip']", personal.get("zip", "98034")),
        ("input[name='tor__fcity']", personal.get("city", "Kirkland")),
    ]:
        el = page.query_selector(sel)
        if el:
            current = el.input_value() or ""
            if not current.strip():
                el.fill(val)


def submit_apply(page, debug_dir: Path, dryrun: bool) -> dict:
    """Click #fbqa_apply. Returns {'success': bool, ...}."""
    _screenshot(page, "13_pre_submit", debug_dir)

    if dryrun:
        _log("DRYRUN — skipping submit")
        return {"success": True, "dryrun": True, "url": page.url}

    has_btn = page.evaluate("() => !!document.querySelector('#fbqa_apply')")
    if not has_btn:
        _log("  ERROR: #fbqa_apply not found")
        _screenshot(page, "err_no_apply_btn", debug_dir)
        return {"success": False, "error": "apply_button_missing"}

    _log("Clicking #fbqa_apply...")
    page.evaluate("() => document.querySelector('#fbqa_apply').click()")
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(4000)
    _screenshot(page, "14_post_submit", debug_dir)

    url = page.url
    body = page.evaluate("() => document.body.innerText.lower()")
    _log(f"  post-submit URL: {url[:120]}")

    if detect_already_applied(page):
        return {"success": False, "error": "already_applied", "url": url}

    if detect_success(page):
        return {"success": True, "url": url}

    # Check for validation banner
    banner = page.evaluate("""() => {
        const e = document.querySelector(
            '.errorMessage,.error-banner,#errorMsg,[class*=errorBanner],.validationError'
        );
        return e ? e.innerText.trim().substring(0, 300) : null;
    }""")
    if banner:
        _log(f"  Validation: {banner!r}")
        _screenshot(page, "15_validation", debug_dir)
        # Retry once after any validation issues
        page.evaluate("() => { const b = document.querySelector('#fbqa_apply'); if (b) b.click(); }")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        _screenshot(page, "16_retry_submit", debug_dir)
        if detect_success(page):
            return {"success": True, "url": page.url}

    return {"success": False, "error": "no_success_indicator", "url": url}


# ---------------------------------------------------------------------------
# New SAP CXE (UI5 wizard) apply flow — used for A.O. Smith & similar tenants
# ---------------------------------------------------------------------------
_JS_FILL_BY_LABEL = """
(args) => {
    const [labelText, value] = args;
    // Pierce shadow DOM to find input associated with a label
    function findInput(root, labelPattern) {
        const labels = root.querySelectorAll('label');
        for (const lbl of labels) {
            const txt = (lbl.innerText || lbl.textContent || '').trim();
            if (labelPattern.test(txt)) {
                // direct htmlFor
                if (lbl.htmlFor) {
                    const inp = root.getElementById(lbl.htmlFor);
                    if (inp) return inp;
                }
                // sibling or parent-child
                const parent = lbl.parentElement;
                if (parent) {
                    const inp = parent.querySelector('input:not([type=hidden]),select,textarea');
                    if (inp) return inp;
                }
            }
        }
        return null;
    }
    function setNative(el, val) {
        const proto = el.tagName === 'SELECT' ? window.HTMLSelectElement.prototype
            : (el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype);
        const d = Object.getOwnPropertyDescriptor(proto, 'value');
        if (d && d.set) d.set.call(el, val); else el.value = val;
        el.dispatchEvent(new Event('input',  {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur',   {bubbles:true}));
    }
    const re = new RegExp(labelText.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), 'i');
    // Search main document
    const direct = findInput(document, re);
    if (direct) { setNative(direct, value); return 'filled:doc:' + direct.id; }
    // Search all shadow roots
    for (const el of document.querySelectorAll('*')) {
        if (el.shadowRoot) {
            const found = findInput(el.shadowRoot, re);
            if (found) { setNative(found, value); return 'filled:shadow:' + found.id; }
        }
    }
    return null;
}
"""

_JS_CLICK_UI5_BTN = """
(text) => {
    for (const tagName of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE', 'ui5-button']) {
        for (const el of document.querySelectorAll(tagName)) {
            const t = (el.textContent || el.innerText || '').trim();
            if (t !== text) continue;
            // Skip disabled/transparent buttons (opacity < 0.5 means disabled)
            const style = getComputedStyle(el);
            const opacity = parseFloat(style.opacity);
            if (opacity < 0.5) continue;
            if (style.pointerEvents === 'none') continue;
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;
            el.scrollIntoView({block: 'center'});
            el.click();
            return 'clicked:' + tagName + ':' + t;
        }
    }
    return null;
}
"""

_JS_GET_WIZARD_STEP = """
() => {
    const a = document.getElementById('wizard-step-announcer');
    if (a) return a.textContent || a.innerText || '';
    const panels = document.querySelectorAll('.PanelRenderer_wizardPanelTitle__HN2e8');
    // Current step is often the one that's actually rendered
    return 'unknown';
}
"""

_JS_GET_NAV_BUTTONS = """
() => {
    const r = [];
    for (const t of ['UI5-BUTTON-XWEB-DYNAMIC-CONTENT', 'UI5-BUTTON-XWEB-CANDIDATE-EXPERIENCE']) {
        for (const el of document.querySelectorAll(t)) {
            const txt = (el.textContent || el.innerText || '').trim();
            if (['Next', 'Previous', 'Close', 'Submit Application', 'Submit'].includes(txt)) {
                r.push(txt);
            }
        }
    }
    return [...new Set(r)];
}
"""


def _wait_wizard_ready(page, max_secs: int = 35) -> str:
    """Wait until wizard body has real content (not just skeleton loaders)."""
    for _ in range(max_secs * 2):
        body = page.evaluate("() => document.body.innerText")
        stripped = re.sub(r"[\s\xa0]+", "", body)
        if len(stripped) > 150:
            return body.lower()
        page.wait_for_timeout(500)
    return page.evaluate("() => document.body.innerText").lower()


def _type_into_label(page, label_text, value):
    try:
        loc = page.get_by_label(label_text, exact=True)
        cnt = loc.count()
        if cnt == 0:
            return "NOT_FOUND:" + label_text
        inp = loc.first
        inp.click()
        page.wait_for_timeout(100)
        inp.click(click_count=3)
        page.keyboard.type(value)
        page.wait_for_timeout(150)
        final = inp.input_value()
        return "ok:" + repr(final)
    except Exception as exc:
        return "ERROR:" + str(exc)


_STATE_NAMES = {
    "WA": "Washington", "CA": "California", "NY": "New York", "TX": "Texas",
    "FL": "Florida", "IL": "Illinois", "PA": "Pennsylvania", "OH": "Ohio",
    "GA": "Georgia", "NC": "North Carolina", "MI": "Michigan", "NJ": "New Jersey",
    "VA": "Virginia", "AZ": "Arizona", "MA": "Massachusetts", "TN": "Tennessee",
    "IN": "Indiana", "MO": "Missouri", "MD": "Maryland", "WI": "Wisconsin",
    "CO": "Colorado", "MN": "Minnesota", "SC": "South Carolina", "AL": "Alabama",
    "LA": "Louisiana", "KY": "Kentucky", "OR": "Oregon", "OK": "Oklahoma",
    "CT": "Connecticut", "UT": "Utah", "IA": "Iowa", "NV": "Nevada",
    "AR": "Arkansas", "MS": "Mississippi", "KS": "Kansas", "NM": "New Mexico",
    "NE": "Nebraska", "ID": "Idaho", "HI": "Hawaii", "NH": "New Hampshire",
    "ME": "Maine", "MT": "Montana", "RI": "Rhode Island", "DE": "Delaware",
    "SD": "South Dakota", "ND": "North Dakota", "AK": "Alaska", "VT": "Vermont",
    "WY": "Wyoming", "DC": "District of Columbia",
}


def _fill_profile_step(page, personal, debug_dir):
    addr_obj = personal.get("address", {})
    if isinstance(addr_obj, dict):
        addr = addr_obj.get("street", "12420 NE 120th St #1437")
        city = addr_obj.get("city", "Kirkland")
        state_raw = addr_obj.get("state", "WA")
        postal = addr_obj.get("zip", "98034")
    else:
        addr = str(addr_obj) or "12420 NE 120th St #1437"
        city = personal.get("city", "Kirkland")
        state_raw = personal.get("state", "WA")
        postal = personal.get("postal_code", "98034")
    contact = personal.get("contact", {})
    if isinstance(contact, dict):
        raw_phone = contact.get("phone", "3468040227")
    else:
        raw_phone = personal.get("phone", "3468040227")
    phone = re.sub(r"[^0-9]", "", str(raw_phone))
    state = _STATE_NAMES.get(state_raw.upper(), state_raw) if state_raw else state_raw

    for label_text, value in [
        ("Address Line1", addr),
        ("City", city),
        ("Postal Code", postal),
        ("Mobile Phone", phone),
        ("State/Province", state),
    ]:
        if not value:
            continue
        r = _type_into_label(page, label_text, value)
        _log("  " + label_text + ": " + r)

    # Phone - fill first empty Phone field
    if phone:
        try:
            loc_phone = page.get_by_label("Phone", exact=True)
            cnt_p = loc_phone.count()
            for i in range(min(cnt_p, 3)):
                cur = ""
                try:
                    cur = loc_phone.nth(i).input_value()
                except Exception:
                    pass
                if not cur:
                    r_phone = _type_into_label(page, "Phone", phone)
                    _log("  Phone[" + str(i) + "]: " + r_phone)
                    break
        except Exception as exc:
            _log("  Phone error: " + str(exc))

    _screenshot(page, "cxe_s2_filled", debug_dir)

def _cxe_click_next(page, step_label: str = "Next") -> str:
    """Click the Next/Submit button in the CXE wizard."""
    result = page.evaluate(_JS_CLICK_UI5_BTN, step_label)
    if result:
        _log(f"  clicked UI5: {result}")
    else:
        _log(f"  '{step_label}' UI5 button not found")
    return result or ""


def _run_cxe_form(
    page,
    tenant,
    server,
    req_id,
    email_alias,
    password,
    resume_path,
    personal,
    debug_dir,
    dryrun=False,
):
    """
    Handle new SAP CXE (UI5 wizard) apply form.
    Always uses Start Over to ensure a clean application with all fields filled.
    Returns: 0=ok, 1=error, 6=closed, 7=already_applied
    """
    ctx = page.context
    ctx.clear_cookies(domain=server)
    _log("CXE: cookies cleared")

    url = sf_job_save_url(server, tenant, req_id)
    _log(f"CXE: navigating to {url[:80]}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    _screenshot(page, "cxe_01_signin", debug_dir)

    # ---- Sign in ----
    page.evaluate("""
        ([e, p]) => {
            const setVal = (el, v) => {
                const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (d && d.set) d.set.call(el, v); else el.value = v;
                el.dispatchEvent(new Event('input', {bubbles:true}));
            };
            const ef = document.querySelector('input[name=username],input[type=email],input[name=Email],#username-field,#email-field');
            const pf = document.querySelector('input[type=password],#password-field');
            if (ef) setVal(ef, e);
            if (pf) setVal(pf, p);
        }
    """, [email_alias, password])
    page.wait_for_timeout(500)
    page.evaluate("""
        () => {
            for (const b of document.querySelectorAll('button,input[type=submit]')) {
                if (/^sign in$/i.test((b.innerText || b.value || '').trim())) { b.click(); return; }
            }
            const f = document.querySelector('form');
            if (f) f.submit();
        }
    """)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(5000)
    _screenshot(page, "cxe_02_after_signin", debug_dir)

    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"CXE: after signin body[:100]: {repr(body[:100])}")

    if detect_already_applied(page):
        _log("CXE: already applied detected")
        return 7
    if "job not found" in body or "requisition is no longer" in body:
        _log("CXE: job closed")
        return 6

    # ---- Click Apply ----
    clicked_apply = page.evaluate("""
        () => {
            const btn = document.getElementById('applyButton_top') || document.getElementById('applyButton_bottom');
            if (btn) { btn.click(); return 'clicked:' + btn.id; }
            for (const a of document.querySelectorAll('a,button')) {
                const t = (a.innerText||a.textContent||'').trim().toLowerCase();
                if (t === 'apply') { a.click(); return 'clicked:link'; }
            }
            return null;
        }
    """)
    _log(f"CXE: apply click: {clicked_apply}")
    page.wait_for_timeout(4000)
    _screenshot(page, "cxe_03_after_apply_click", debug_dir)

    # ---- Handle Saved Applications dialog: always Start Over ----
    dialog_result = page.evaluate("""
        () => {
            const sels = ['[role=dialog] button', '.ui-dialog button', '.ui-dialog-buttonset button'];
            for (const sel of sels) {
                for (const btn of document.querySelectorAll(sel)) {
                    const t = (btn.innerText||btn.textContent||'').trim().toLowerCase();
                    if (t === 'start over') { btn.click(); return 'startover'; }
                }
            }
            for (const sel of sels) {
                for (const btn of document.querySelectorAll(sel)) {
                    const t = (btn.innerText||btn.textContent||'').trim().toLowerCase();
                    if (t === 'continue') { btn.click(); return 'continue'; }
                }
            }
            return 'no_dialog';
        }
    """)
    _log(f"CXE: saved app dialog: {dialog_result}")

    if dialog_result == "startover":
        # Start Over may trigger a confirmation dialog
        page.wait_for_timeout(2000)
        confirm = page.evaluate("""
            () => {
                for (const btn of document.querySelectorAll('[role=dialog] button,.ui-dialog button,button')) {
                    const t = (btn.innerText||btn.textContent||'').trim().toLowerCase();
                    if (t === 'start over' || t === 'yes' || t === 'ok' || t === 'confirm') {
                        btn.click(); return 'confirmed:' + t;
                    }
                }
                return null;
            }
        """)
        _log(f"CXE: startover confirm: {confirm}")
        page.wait_for_timeout(8000)
    elif dialog_result in ("continue", "no_dialog"):
        page.wait_for_timeout(5000)

    _screenshot(page, "cxe_04_apply_form", debug_dir)

    # ---- Wait for wizard ----
    for _ in range(70):  # up to 35 seconds
        b = page.evaluate("() => document.body.innerText")
        stripped = re.sub(r"[\s\xa0]+", "", b)
        if len(stripped) > 150:
            break
        page.wait_for_timeout(500)

    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"CXE: wizard body[:200]: {repr(body[:200])}")

    if "sign in" in body or "login" in body:
        _log("CXE: auth failed - back on sign-in")
        return 1

    # ---- Step 1: Getting Started (upload resume) ----
    body_check = page.evaluate("() => document.body.innerText")
    if "getting started" in body_check.lower():
        _log("CXE: Step 1 Getting Started")
        has_upload = bool(re.search(r"uploaded on|file size", body_check, re.I))
        if not has_upload and resume_path and Path(resume_path).exists():
            _log(f"CXE: uploading {resume_path}")
            try:
                fi = page.locator("input[type=file]")
                if fi.count() > 0:
                    fi.first.set_input_files(resume_path)
                    page.wait_for_timeout(4000)
                    _log("CXE: resume uploaded")
            except Exception as exc:
                _log(f"CXE: upload err: {exc}")
        else:
            _log("CXE: resume already present")
        _screenshot(page, "cxe_s1", debug_dir)

        r1 = _cxe_click_next(page, "Next")
        _log(f"CXE: S1 Next: {r1}")
        if not r1:
            _log("CXE: Next disabled on S1 - waiting more")
            page.wait_for_timeout(5000)
            r1 = _cxe_click_next(page, "Next")
            _log(f"CXE: S1 Next retry: {r1}")
        page.wait_for_timeout(5000)

    # ---- Step 2: Profile Information ----
    body_check = page.evaluate("() => document.body.innerText")
    if "profile information" in body_check.lower():
        _log("CXE: Step 2 Profile Information")
        _fill_profile_step(page, personal, debug_dir)
        page.wait_for_timeout(1000)
        _screenshot(page, "cxe_s2_ready", debug_dir)

        if dryrun:
            _log("CXE dryrun: stopping before S2 Next")
            return 0

        r2 = _cxe_click_next(page, "Next")
        _log(f"CXE: S2 Next: {r2}")
        if not r2:
            _log("CXE: Next disabled on S2 - checking validation")
            # Check for validation errors
            v_errs = page.evaluate("""
                () => [...document.querySelectorAll('[aria-invalid=true],[value-state=Error]')]
                    .map(el => (el.closest('label') ? (el.closest('label').innerText||'') : el.id||el.name||'?'))
                    .filter(Boolean)
            """)
            _log(f"CXE: validation errors: {v_errs}")
            page.wait_for_timeout(2000)
            r2 = _cxe_click_next(page, "Next")
            _log(f"CXE: S2 Next retry: {r2}")
        page.wait_for_timeout(5000)

    # ---- Steps 3-7: Click Next through empty/optional steps ----
    _screenshot(page, "cxe_s3_start", debug_dir)
    for step_num in range(3, 8):
        nav_btns = page.evaluate(_JS_GET_NAV_BUTTONS)
        body_now = page.evaluate("() => document.body.innerText.toLowerCase()")
        _log(f"CXE: step~{step_num} nav={nav_btns}")

        if "submit application" in nav_btns or "submit" in nav_btns:
            _log(f"CXE: found Submit on step~{step_num}")
            break

        if "Next" not in nav_btns:
            _log(f"CXE: no enabled Next on step~{step_num}, stopping")
            break

        rN = _cxe_click_next(page, "Next")
        _log(f"CXE: S{step_num} Next: {rN}")
        if not rN:
            _log(f"CXE: Next click failed on step~{step_num}")
            break
        page.wait_for_timeout(4000)
        _screenshot(page, f"cxe_s{step_num}", debug_dir)

    # ---- Final step: Submit ----
    nav_btns = page.evaluate(_JS_GET_NAV_BUTTONS)
    _log(f"CXE: final nav: {nav_btns}")
    _screenshot(page, "cxe_final", debug_dir)

    if dryrun:
        _log("CXE dryrun: at final step, not submitting")
        return 0

    submit_label = "Submit Application" if "Submit Application" in nav_btns else "Submit"
    if submit_label not in nav_btns and "Next" not in nav_btns:
        _log(f"CXE: no submit/next button. nav={nav_btns}")
        return 1

    btn_to_click = submit_label if submit_label in nav_btns else "Next"
    rS = _cxe_click_next(page, btn_to_click)
    _log(f"CXE: submit click: {rS}")
    page.wait_for_timeout(6000)
    _screenshot(page, "cxe_after_submit", debug_dir)

    final_url = page.url
    final_body = page.evaluate("() => document.body.innerText.toLowerCase()")
    _log(f"CXE: post-submit url: {repr(final_url[-80:])}")
    _log(f"CXE: post-submit body: {repr(final_body[:200])}")

    success = any([
        "isredirecttoappsent=true" in final_url.lower(),
        "application submitted" in final_body,
        "successfully submitted" in final_body,
        ("thank you" in final_body and "application" in final_body),
        "application has been received" in final_body,
        "review" in final_body and "submitted" in final_body,
    ])
    if success:
        _log(f"CXE: SUBMITTED. url={final_url}")
        return 0

    # Try confirmation dialog
    conf = page.evaluate("""
        () => {
            for (const btn of document.querySelectorAll('button,[role=button]')) {
                const t = (btn.innerText||'').trim().toLowerCase();
                if (t === 'yes, proceed' || t === 'confirm' || t === 'yes') {
                    btn.click(); return 'clicked:' + t;
                }
            }
            return null;
        }
    """)
    if conf:
        page.wait_for_timeout(5000)
        _screenshot(page, "cxe_after_confirm", debug_dir)
        final_url2 = page.url
        final_body2 = page.evaluate("() => document.body.innerText.toLowerCase()")
        _log(f"CXE: after confirm url: {repr(final_url2[-80:])}")
        _log(f"CXE: after confirm body: {repr(final_body2[:200])}")
        if any([
            "isredirecttoappsent=true" in final_url2.lower(),
            "application submitted" in final_body2,
            "successfully submitted" in final_body2,
            "thank you" in final_body2,
        ]):
            _log("CXE: SUBMITTED after confirm!")
            return 0

    _log(f"CXE: submit not confirmed. url={final_url}")
    return 1

def run(
    url: str = "",
    tenant: str = "",
    server: str = "career8.successfactors.com",
    job_id: str = "",
    role_id: int = 0,
    resume_path: str = "",
    dryrun: bool = False,
    personal: dict | None = None,
    debug_dir: Path | None = None,
    cdp_endpoint: str | None = None,
) -> int:
    """Returns exit code: 0=submitted/dryrun, 1=error, 6=closed, 7=already_applied."""
    if personal is None:
        personal = {}
    if debug_dir is None:
        debug_dir = Path(__file__).parent.parent / ".sf-debug"
    debug_dir = Path(debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)

    req_id = job_id  # SF internal req/job ID
    email_alias = f"cyshekari+{tenant}{role_id}@gmail.com"
    password = "Cyrus2026!Apply"

    _log(f"run: tenant={tenant} server={server} req_id={req_id} email={email_alias} dryrun={dryrun}")

    pw = browser = ctx = page = None
    try:
        pw, browser, ctx, page = _get_page(cdp_endpoint)

        # Use new CXE (UI5 wizard) flow for A.O. Smith and similar
        exit_code = _run_cxe_form(
            page=page,
            tenant=tenant,
            server=server,
            req_id=req_id,
            email_alias=email_alias,
            password=password,
            resume_path=resume_path,
            personal=personal,
            debug_dir=debug_dir,
            dryrun=dryrun,
        )
        return exit_code
    except Exception:
        _log("EXCEPTION:" + traceback.format_exc())
        if page:
            try:
                _screenshot(page, "err_exception", debug_dir)
            except Exception:
                pass
        return 1
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="SuccessFactors guest-apply runner")
    ap.add_argument("--url", help="Full SF apply URL or vendor job URL")
    ap.add_argument("--tenant", help="SF tenant slug (e.g. aosmith)")
    ap.add_argument("--server", default="career8.successfactors.com", help="SF server hostname")
    ap.add_argument("--job-id", "--req-id", dest="job_id", help="SF job/req ID (e.g. 27523)")
    ap.add_argument("--role-id", dest="role_id", type=int, default=0, help="tracker.db role id")
    ap.add_argument("--resume", help="Path to resume PDF")
    ap.add_argument("--dryrun", action="store_true", help="Fill form but do not submit")
    ap.add_argument("--cdp", dest="cdp", default=None, help="CDP endpoint URL")
    ap.add_argument(
        "--personal-info",
        dest="personal_info",
        default=str(Path(__file__).parent.parent / "personal-info.json"),
        help="Path to personal-info.json",
    )
    args = ap.parse_args()

    tenant = args.tenant
    server = args.server
    job_id = args.job_id

    if args.url:
        # Try to extract from URL
        m_sf = re.search(
            r"career_job_req_id=(\d+)|jobReqId=(\d+)|jobId=(\d+)", args.url
        )
        if m_sf:
            job_id = job_id or (m_sf.group(1) or m_sf.group(2) or m_sf.group(3))
        m_tenant = re.search(r"company=([^&]+)", args.url)
        if m_tenant and not tenant:
            tenant = m_tenant.group(1)
        m_server = re.search(r"https?://(career\d+\.successfactors\.(?:com|eu))/", args.url)
        if m_server and server == "career8.successfactors.com":
            server = m_server.group(1)

    if not tenant or not job_id:
        print("ERROR: need --tenant + --job-id, or --url with recognizable SF URL")
        sys.exit(1)

    personal = {}
    pi_path = Path(args.personal_info)
    if pi_path.exists():
        personal = json.loads(pi_path.read_text())

    # Resolve resume path
    resume = args.resume
    if not resume:
        pi_resume = personal.get("files", {}).get("resume_path", "")
        if pi_resume:
            resume = str(Path(args.personal_info).parent / pi_resume)
    if not resume or not Path(resume).exists():
        # Fallback to known location
        base = Path(__file__).parent.parent
        candidates = [
            base / "resume" / "Cyrus_Shekari_Resume.pdf",
            base / "_archive" / "apply_bot" / "assets" / "Cyrus_Shekari_Resume.pdf",
        ]
        for c in candidates:
            if c.exists():
                resume = str(c)
                break

    if not resume or not Path(resume).exists():
        print(f"ERROR: resume not found (tried: {resume})")
        sys.exit(1)

    # Set CDP endpoint if provided
    cdp = args.cdp
    if cdp:
        os.environ["JOBSEARCH_CDP"] = cdp
    global CDP_ENDPOINT
    CDP_ENDPOINT = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")

    debug_dir = Path(__file__).parent.parent / ".sf-debug"

    exit_code = run(
        url=args.url or "",
        tenant=tenant,
        server=server,
        job_id=job_id,
        role_id=args.role_id,
        resume_path=resume,
        dryrun=args.dryrun,
        personal=personal,
        debug_dir=debug_dir,
        cdp_endpoint=cdp,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
