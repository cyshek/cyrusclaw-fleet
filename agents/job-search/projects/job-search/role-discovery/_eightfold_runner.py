"""
_eightfold_runner.py -- Eightfold ATS full-submit runner (Playwright CDP)

Applies to: Netflix (explore.jobs.netflix.net), and any other Eightfold tenant
with the same /api/application/v2/ API structure.

ARCHITECTURE NOTES (from 2026-06-14 recon):
- Apply URL: /careers/apply?pid=<job_id>  (NOT /careers/job/<id>/apply which 404s)
- ATS is a SPA -- uses browser automation (Playwright CDP) for reliable submit
- reCAPTCHA: Solved automatically by browser's native grecaptcha when Submit is clicked
- Submit API: POST /api/application/v2/submit?domain=netflix.com&hl=en
  * Returns HTTP 201 + JSON {data: {success: true}} on success
  * SPA stays on same URL (no redirect after submit)
- Resume upload: POST /api/application/v2/resume_upload with CSRF token
  * MUST upload per-role TAILORED resume -- never use cached profile resume
  * CSRF token extracted from page state via EF_REDUX_STORE
- Contact fields: Contact_Information_email, Contact_Information_firstname,
  Contact_Information_lastname, Contact_Information_phone, Contact_Information_city
- Country/State: custom combobox selects (ARIA role=combobox + option click)
- Application Questions (all roles share these 3):
  * "Are you currently working for Netflix as a contractor?" -> No
  * "Have you worked for Netflix or any of Netflix's subsidiaries in the past?" -> No
  * "Do you require sponsorship to legally work in the job location?" -> No
- filterDependentQuestionsEnabled: 0 (disabled for Netflix)

EXIT CODES (mirrors _workday_runner.py convention):
  0 = submitted / dry-run review
  2 = auth block / sign-in required
  3 = submit succeeded but no confirmation detected
  4 = can't click submit
  5 = loop cap / ended without confirmation
  6 = req CLOSED / removed (404 on apply page)
  7 = already applied
  9 = fatal form error
"""

import base64
import json
import logging
import os
import re
import sqlite3
import sys
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUBMITTED = 0
EXIT_AUTH_BLOCK = 2
EXIT_NO_CONFIRMATION = 3
EXIT_CANT_SUBMIT = 4
EXIT_LOOP_CAP = 5
EXIT_CLOSED = 6
EXIT_ALREADY_APPLIED = 7
EXIT_FATAL = 9

# Eightfold tenant configs
TENANT_CONFIGS = {
    "netflix.com": {
        "base_url": "https://explore.jobs.netflix.net",
        "domain": "netflix.com",
        "user_mode": "logged_out_candidate",
    },
}

# CDP URL for the browser
CDP_URL = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")

# ---------------------------------------------------------------------------
# JS snippets (module-level constants so tests can assert their shape)
# ---------------------------------------------------------------------------

JS_GET_PAGE_STATE = """
() => {
    const csrf = (() => {
        // Try EF_REDUX_STORE first (most reliable)
        try {
            const store = window.EF_REDUX_STORE || window.__EF_STORE;
            if (store) {
                const state = store.getState();
                const t = state?.global?.csrf || state?.session?.csrf || state?.csrf;
                if (t) return t;
            }
        } catch(e) {}
        // Fallback: <meta name="_csrf">
        const meta = document.querySelector('meta[name="_csrf"]');
        if (meta) return meta.getAttribute('content');
        // Fallback: window.__CSRF or window.__csrf
        return window.__CSRF || window.__csrf || null;
    })();

    // pids: from URL query param ?pid=... or state
    const urlPids = new URLSearchParams(window.location.search).get('pid');
    let pids = urlPids;
    if (!pids) {
        try {
            const store = window.EF_REDUX_STORE || window.__EF_STORE;
            if (store) {
                const state = store.getState();
                pids = state?.apply?.pids || state?.job?.pids || null;
            }
        } catch(e) {}
    }

    const formPresent = !!document.querySelector('#Contact_Information_email, [data-testid="apply-form"], form[id*="apply"]');

    // reCAPTCHA detection
    const recaptchaSitekey = (() => {
        const scripts = Array.from(document.querySelectorAll('script[src*="recaptcha"]'));
        for (const s of scripts) {
            const m = s.src.match(/[?&]render=([^&]+)/);
            if (m) return m[1];
        }
        try {
            const cfg = window.___grecaptcha_cfg;
            if (cfg && cfg.clients) {
                for (const k of Object.keys(cfg.clients)) {
                    const client = cfg.clients[k];
                    for (const ck of Object.keys(client || {})) {
                        const sk = client[ck]?.sitekey;
                        if (sk) return sk;
                    }
                }
            }
        } catch(e) {}
        return null;
    })();

    const recaptchaEnterprise = !!document.querySelector('script[src*="recaptcha/enterprise"]');

    // Extra application questions (comboboxes with Application_Questions_ prefix)
    const extraQs = Array.from(document.querySelectorAll('[role="combobox"]'))
        .filter(c => (c.getAttribute('aria-labelledby') || '').startsWith('Application_Questions_'))
        .map(c => {
            const lb = c.getAttribute('aria-labelledby');
            const el = document.getElementById(lb);
            return { id: lb, label: el ? el.textContent.trim() : lb };
        });

    return {
        csrf,
        pids,
        formPresent,
        recaptchaSitekey,
        recaptchaEnterprise,
        extraQs,
        url: window.location.href,
    };
}
"""

JS_UPLOAD_RESUME = """async (args) => {
    const [csrfToken, pdfBase64, uploadUrl, fileName] = args;
    const binaryStr = atob(pdfBase64);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) { bytes[i] = binaryStr.charCodeAt(i); }
    const blob = new Blob([bytes], { type: 'application/pdf' });
    const fd = new FormData();
    fd.append('resume', blob, fileName || 'resume.pdf');
    try {
        const resp = await fetch(uploadUrl, { method: 'POST', headers: { 'X-CSRF-Token': csrfToken }, body: fd, credentials: 'include' });
        const text = await resp.text();
        let data; try { data = JSON.parse(text); } catch(e) { return { error: 'json_parse_failed', text: text.slice(0, 500), status: resp.status }; }
        return { ok: resp.ok, status: resp.status, data: data };
    } catch(e) { return { error: e.toString() }; }
}"""

JS_NATIVE_RECAPTCHA = """async (sitekey) => {
    // Execute native grecaptcha to get a fresh token — no CapSolver needed
    // Eightfold loads the grecaptcha library; we just call execute() directly
    try {
        if (typeof grecaptcha === 'undefined') return { ok: false, reason: 'grecaptcha_undefined' };
        // grecaptcha.execute returns a promise
        const token = await new Promise((resolve, reject) => {
            if (grecaptcha.enterprise) {
                grecaptcha.enterprise.ready(() => {
                    grecaptcha.enterprise.execute(sitekey, {action: 'submit'}).then(resolve).catch(reject);
                });
            } else {
                grecaptcha.ready(() => {
                    grecaptcha.execute(sitekey, {action: 'submit'}).then(resolve).catch(reject);
                });
            }
        });
        return { ok: true, token: token };
    } catch(e) { return { ok: false, reason: e.toString() }; }
}"""

JS_HOOK_FETCH = """
() => {
    // Hook window.fetch to capture the submit API response.
    // Must be called BEFORE the submit button is clicked.
    // Result stored in sessionStorage under 'ef_submit_result'.
    sessionStorage.removeItem('ef_submit_result');
    sessionStorage.removeItem('ef_all_fetches');
    const allFetches = [];
    const origFetch = window.fetch;
    window.fetch = function(url, opts) {
        const urlStr = String(url);
        const p = origFetch.apply(this, arguments);
        // Log all fetches for debugging
        p.then(function(resp) {
            resp.clone().text().then(function(t) {
                let data;
                try { data = JSON.parse(t); } catch(e) { data = { raw: t.slice(0, 500) }; }
                const entry = {url: urlStr.slice(0, 200), ok: resp.ok, status: resp.status, data: data};
                allFetches.push(entry);
                sessionStorage.setItem('ef_all_fetches', JSON.stringify(allFetches.slice(-10)));
                if (urlStr.includes('/api/application/v2/submit')) {
                    sessionStorage.setItem('ef_submit_result', JSON.stringify({
                        ok: resp.ok, status: resp.status, data: data
                    }));
                }
            });
        }).catch(function(e) {
            const entry = {url: urlStr.slice(0, 200), ok: false, status: 0, error: e.toString()};
            allFetches.push(entry);
            sessionStorage.setItem('ef_all_fetches', JSON.stringify(allFetches.slice(-10)));
            if (urlStr.includes('/api/application/v2/submit')) {
                sessionStorage.setItem('ef_submit_result', JSON.stringify({
                    ok: false, status: 0, error: e.toString()
                }));
            }
        });
        return p;
    };
}
"""

JS_READ_SUBMIT_RESULT = """
() => {
    const raw = sessionStorage.getItem('ef_submit_result');
    if (!raw) return null;
    try { return JSON.parse(raw); } catch(e) { return { raw: raw, error: e.toString() }; }
}
"""

JS_CHECK_CONFIRMATION = """
() => {
    const url = window.location.href;
    const body = document.body ? document.body.innerText : '';
    const thankYou = url.includes('/apply/success') ||
        body.toLowerCase().includes('thank you for') ||
        body.toLowerCase().includes('application has been received') ||
        body.toLowerCase().includes('application received') ||
        !!document.querySelector('[data-testid="thank-you"], .thank-you, [class*="thankYou"], [class*="ThankYou"]');
    const formGone = !document.querySelector('#Contact_Information_email');
    const confirmUrl = url.includes('/apply/success') || url.includes('success');
    const confirmElement = !!document.querySelector('[data-testid="thank-you"], [class*="thankYou"], [class*="ThankYou"]');
    return {
        confirmed: thankYou,
        thank_you: thankYou,
        form_gone: formGone,
        confirm_url: confirmUrl,
        confirm_element: confirmElement,
        snippet: body.slice(0, 200),
        url,
        body_sample: body.slice(0, 200),
    };
}
"""

# ---------------------------------------------------------------------------
# URL / domain helpers
# ---------------------------------------------------------------------------

def _derive_domain(app_url: str) -> str:
    """Derive Eightfold tenant domain from app_url."""
    # Known tenants
    known = [
        ("explore.jobs.netflix.net", "netflix.com"),
        ("careers.starbucks.com", "starbucks.com"),
    ]
    for host_fragment, domain in known:
        if host_fragment in app_url:
            return domain
    # Generic: extract domain from hostname
    m = re.search(r"https?://([^/]+)", app_url)
    if m:
        host = m.group(1)
        # Strip www./explore.jobs. prefixes
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
    return "unknown.com"


def _derive_host(app_url: str) -> str:
    """Derive hostname from app_url."""
    m = re.search(r"https?://([^/]+)", app_url)
    return m.group(1) if m else ""


def _pid_from_url(app_url: str) -> Optional[str]:
    """Extract PID from URL query param ?pid=... or /careers/job/<pid> path."""
    # Try query param first
    m = re.search(r"[?&]pid=(\d+)", app_url)
    if m:
        return m.group(1)
    # Try /careers/job/<pid> path
    m = re.search(r"/careers/job/(\d+)", app_url)
    if m:
        return m.group(1)
    # Try any trailing numeric path segment
    m = re.search(r"/(\d{9,})/?$", app_url)
    if m:
        return m.group(1)
    return None


def _build_apply_url(app_url: str, pid: str, host: str) -> str:
    """Build the /careers/apply?pid=... URL from an app_url."""
    if "/careers/apply" in app_url:
        return app_url
    return f"https://{host}/careers/apply?pid={pid}"


# ---------------------------------------------------------------------------
# Form helpers
# ---------------------------------------------------------------------------

def _handle_extra_questions(page, questions: list, personal_info: dict, role_id: int) -> dict:
    """
    Determine answers for extra application questions.
    Returns dict of {question_id: answer_text}.
    """
    work_auth = personal_info.get("work_authorization", {})
    is_us_citizen = work_auth.get("status", "").lower() in ("us_citizen", "citizen", "green_card")
    needs_sponsor = work_auth.get("sponsorship_required_now", "no").lower() in ("yes", "true")

    answers = {}
    for q in questions:
        qid = q.get("id", "")
        label = q.get("label", "").lower()

        if any(w in label for w in ["authorized", "authoriz", "legally authorized", "work in the us", "eligible to work"]):
            answers[qid] = "Yes"
        elif any(w in label for w in ["sponsor", "sponsorship", "visa"]):
            answers[qid] = "No" if not needs_sponsor else "Yes"
        elif any(w in label for w in ["contractor", "currently working for"]):
            answers[qid] = "No"
        elif any(w in label for w in ["worked for netflix", "previously worked", "worked for", "past", "previously employed"]):
            answers[qid] = "No"
        elif any(w in label for w in ["relocate", "relocation"]):
            answers[qid] = "Yes"
        elif any(w in label for w in ["background check", "drug test", "drug screen"]):
            answers[qid] = "Yes"
        elif any(w in label for w in ["hybrid", "office", "onsite", "on-site", "on site"]):
            answers[qid] = "Yes"
        elif any(w in label for w in ["citizen", "citizenship"]):
            answers[qid] = "Yes" if is_us_citizen else "No"
        else:
            answers[qid] = "No"  # Conservative default

        logger.info(f"[Eightfold] Q: '{label[:60]}' -> '{answers[qid]}'")
    return answers


def _maybe_solve_recaptcha(page, page_state: dict) -> dict:
    """
    Attempt reCAPTCHA solving if sitekey is present.
    Returns dict with keys: enabled, injected, reason.
    """
    sitekey = page_state.get("recaptchaSitekey")
    is_enterprise = page_state.get("recaptchaEnterprise", False)

    if not sitekey:
        return {"enabled": False, "injected": False, "reason": "no_sitekey"}

    capsolver_key = os.environ.get("CAPSOLVER_API_KEY", "")
    if not capsolver_key:
        return {"enabled": True, "injected": False, "reason": "no_capsolver_key — native browser grecaptcha will handle on click"}

    try:
        from capsolver_client import CapSolverClient
        client = CapSolverClient(api_key=capsolver_key)
        if is_enterprise:
            result = client.recaptcha_v3_enterprise(sitekey=sitekey, page_url=page.url, action="job_apply")
        else:
            result = client.recaptcha_v3(sitekey=sitekey, page_url=page.url, action="job_apply")
        token = result  # recaptcha_v3 returns the token string directly
        if token and isinstance(token, str):
            token = result["token"]
            # Inject into textarea (Eightfold expects g-recaptcha-response)
            page.evaluate(f"""
            () => {{
                const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
                if (ta) {{ ta.value = {json.dumps(token)}; ta.dispatchEvent(new Event('change')); }}
                // Also try grecaptcha callback
                try {{
                    const cfg = window.___grecaptcha_cfg;
                    if (cfg && cfg.clients) {{
                        for (const k of Object.keys(cfg.clients)) {{
                            const client = cfg.clients[k];
                            for (const ck of Object.keys(client || {{}})) {{
                                const cb = client[ck]?.callback;
                                if (typeof cb === 'function') {{ cb({json.dumps(token)}); }}
                            }}
                        }}
                    }}
                }} catch(e) {{}}
            }}
            """)
            logger.info("[Eightfold] reCAPTCHA token injected")
            return {"enabled": True, "injected": True, "reason": "solved"}
        else:
            logger.warning(f"[Eightfold] CapSolver returned no token: {result}")
            return {"enabled": True, "injected": False, "reason": "capsolver_no_token"}
    except Exception as ex:
        logger.warning(f"[Eightfold] reCAPTCHA solve failed: {ex}")
        return {"enabled": True, "injected": False, "reason": str(ex)}


# ---------------------------------------------------------------------------
# Main entry point: run_eightfold()
# ---------------------------------------------------------------------------

def run_eightfold(
    role_id: int,
    apply_url: str,
    personal_info: dict,
    resume_pdf_path: str,
    dry_run: bool = False,
) -> dict:
    """
    Submit an Eightfold application using Playwright CDP browser automation.

    MANDATORY: resume_pdf_path must exist and be >0 bytes.
    If missing/empty, returns {status: 'error', error: '...'} immediately —
    never submits with the cached profile resume.

    Returns dict:
        status:       'submitted' | 'dryrun' | 'blocked' | 'error' | 'already_applied' | 'closed'
        enc_id:       Eightfold profile encId (str or None)
        pids:         job pids string
        confirmation: confirmation data dict (on success/dryrun)
        error:        error message (on error/blocked)
        exit_code:    numeric exit code (mirrors EXIT_* constants)
    """
    # --- Guard: tailored resume is MANDATORY ---
    if not resume_pdf_path or not os.path.exists(resume_pdf_path):
        msg = f"resume_pdf_path not found or empty: {resume_pdf_path!r} — refusing to submit without tailored resume"
        logger.error(f"[Eightfold] {msg}")
        return {"status": "error", "error": msg, "exit_code": EXIT_FATAL}

    resume_size = os.path.getsize(resume_pdf_path)
    if resume_size < 1:
        msg = f"resume_pdf_path is empty (0 bytes): {resume_pdf_path!r}"
        logger.error(f"[Eightfold] {msg}")
        return {"status": "error", "error": msg, "exit_code": EXIT_FATAL}

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
    except ImportError:
        from playwright.sync_api import sync_playwright
        PWTimeoutError = Exception

    # Derive host/domain from apply_url
    host = _derive_host(apply_url)
    domain = _derive_domain(apply_url)
    config = TENANT_CONFIGS.get(domain, {"base_url": f"https://{host}", "domain": domain, "user_mode": "logged_out_candidate"})
    base_url = config["base_url"]
    user_mode = config["user_mode"]

    # Extract PID from URL
    pid = _pid_from_url(apply_url)
    if not pid:
        msg = f"Cannot extract pids from apply_url: {apply_url!r}"
        logger.error(f"[Eightfold] {msg}")
        return {"status": "error", "error": f"pids not found in {apply_url}", "exit_code": EXIT_FATAL}

    apply_url_canonical = _build_apply_url(apply_url, pid, host)
    logger.info(f"[Eightfold] role={role_id} pid={pid} url={apply_url_canonical} resume={os.path.basename(resume_pdf_path)}")

    # Extract personal info
    identity = personal_info.get("identity", {})
    contact = personal_info.get("contact", {})
    address = personal_info.get("address", {})

    firstname = identity.get("first_name", "")
    lastname = identity.get("last_name", "")
    email = contact.get("email", "")
    phone = contact.get("phone", "")
    city = address.get("city", "")
    state = address.get("state", "")

    state_map = {
        "WA": "Washington", "CA": "California", "TX": "Texas", "NY": "New York",
        "IL": "Illinois", "FL": "Florida",
    }
    state_full = state_map.get(state, state)

    # Read resume bytes for upload
    with open(resume_pdf_path, "rb") as fh:
        resume_bytes = fh.read()
    resume_b64 = base64.b64encode(resume_bytes).decode("ascii")
    resume_filename = os.path.basename(resume_pdf_path)
    ext = os.path.splitext(resume_filename)[1].lower()
    mime_map = {".pdf": "application/pdf", ".doc": "application/msword",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".txt": "text/plain"}
    mime_type = mime_map.get(ext, "application/pdf")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = browser.new_context()

        page = context.new_page()

        logger.info(f"[Eightfold] Navigating to {apply_url_canonical}")
        try:
            page.goto(apply_url_canonical, wait_until="networkidle", timeout=30000)
        except PWTimeoutError:
            try:
                page.goto(apply_url_canonical, wait_until="domcontentloaded", timeout=30000)
            except Exception as ex:
                page.close()
                return {"status": "error", "error": f"Navigation failed: {ex}", "exit_code": EXIT_FATAL}

        page.wait_for_timeout(3000)

        # Dismiss OneTrust cookie consent banner (intercepts clicks if not dismissed)
        try:
            onetrust_btn = page.locator('#onetrust-accept-btn-handler, button#accept-recommended-btn-handler, button:has-text("Accept All"), button:has-text("Accept all"), button:has-text("I Accept")').first
            if onetrust_btn.count() > 0:
                onetrust_btn.click(timeout=5000)
                logger.info("[Eightfold] OneTrust cookie banner dismissed")
                page.wait_for_timeout(1000)
            else:
                # Try JS dismiss as fallback
                page.evaluate("""() => {
                    try {
                        const sdk = document.getElementById('onetrust-consent-sdk');
                        if (sdk) { sdk.remove(); }
                        const btn = document.getElementById('onetrust-accept-btn-handler');
                        if (btn) { btn.click(); }
                    } catch(e) {}
                }""")
                logger.info("[Eightfold] OneTrust dismissed via JS (or not present)")
        except Exception as _ot_ex:
            logger.info(f"[Eightfold] OneTrust dismiss (non-fatal): {_ot_ex}")

        # Check for redirect away from apply page
        current_url = page.url
        if "careers/apply" not in current_url:
            logger.warning(f"[Eightfold] Apply page redirected to {current_url}")
            content = page.content().lower()
            if "already applied" in content or "you've already applied" in content:
                page.close()
                return {"status": "already_applied", "exit_code": EXIT_ALREADY_APPLIED}
            page.close()
            return {"status": "closed", "exit_code": EXIT_CLOSED}

        # Wait for form
        try:
            page.wait_for_selector("#Contact_Information_email", timeout=15000)
        except PWTimeoutError:
            page.close()
            return {"status": "error", "error": "Form did not load (no email field found)", "exit_code": EXIT_FATAL}

        # Get page state (CSRF, pids, extra questions)
        page_state = page.evaluate(JS_GET_PAGE_STATE)
        csrf_token = page_state.get("csrf") or ""
        page_pids = page_state.get("pids") or pid
        recap_sitekey = page_state.get("recaptchaSitekey")
        recap_enterprise = page_state.get("recaptchaEnterprise", False)
        logger.info(f"[Eightfold] reCAPTCHA: sitekey={'YES' if recap_sitekey else 'NONE'} enterprise={recap_enterprise}")
        if recap_sitekey:
            logger.info(f"[Eightfold] reCAPTCHA sitekey={recap_sitekey[:20]}...")

        if not csrf_token:
            msg = "CSRF token not found in page state"
            logger.error(f"[Eightfold] {msg}")
            page.close()
            return {"status": "error", "error": msg, "exit_code": EXIT_FATAL}

        logger.info(f"[Eightfold] CSRF={csrf_token[:8]}... pids={page_pids}")

        # --- Upload tailored resume BEFORE filling form ---
        logger.info(f"[Eightfold] Uploading tailored resume: {resume_filename} ({resume_size} bytes)")
        upload_url = f"{base_url}/api/application/v2/resume_upload?domain={domain}&user_mode={user_mode}"
        upload_result = page.evaluate(
            JS_UPLOAD_RESUME,
            [csrf_token, resume_b64, upload_url, resume_filename]
        )

        if upload_result.get("error"):
            msg = f"Resume upload JS error: {upload_result['error']}"
            logger.error(f"[Eightfold] {msg}")
            page.close()
            return {"status": "error", "error": msg, "exit_code": EXIT_FATAL}
        if not upload_result.get("ok"):
            status_code = upload_result.get("status", 0)
            err_data = upload_result.get("data", {})
            msg = f"Resume upload failed: HTTP {status_code} — {str(err_data)[:200]}"
            logger.error(f"[Eightfold] {msg}")
            page.close()
            return {"status": "error", "error": msg, "exit_code": EXIT_FATAL}

        # Extract enc_id from upload response
        upload_data = upload_result.get("data", {})
        profile_data = (
            (upload_data.get("data") or {}).get("profile") or {}
        ) or upload_data.get("profile") or {}
        enc_id = profile_data.get("encId", "")
        uploaded_filename = profile_data.get("resumeFilename", resume_filename)
        if not enc_id:
            msg = f"encId missing from upload response: {json.dumps(upload_data)[:300]}"
            logger.error(f"[Eightfold] {msg}")
            page.close()
            return {"status": "error", "error": msg, "exit_code": EXIT_FATAL}
        logger.info(f"[Eightfold] Resume upload SUCCESS: encId={enc_id} filename={uploaded_filename}")

        # Fill contact fields
        logger.info("[Eightfold] Filling contact fields (native value setter + events)")

        def _native_fill(selector: str, value: str) -> bool:
            """Fill a React-controlled input using native value setter + dispatch events."""
            try:
                page.click(selector, timeout=5000)
                page.wait_for_timeout(100)
                page.evaluate(
                    """([sel, val]) => {
                        const el = document.querySelector(sel);
                        if (!el) return false;
                        const nativeSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeSetter.call(el, val);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        el.dispatchEvent(new Event('blur', {bubbles: true}));
                        return true;
                    }""",
                    [selector, value]
                )
                return True
            except Exception as ex:
                logger.warning(f"[Eightfold] _native_fill({selector}) error: {ex}")
                try:
                    page.fill(selector, value)
                except Exception:
                    pass
                return False

        _native_fill("#Contact_Information_email", email)
        page.wait_for_timeout(200)
        _native_fill("#Contact_Information_firstname", firstname)
        page.wait_for_timeout(200)
        _native_fill("#Contact_Information_lastname", lastname)
        page.wait_for_timeout(200)
        _native_fill("#Contact_Information_phone", phone)
        page.wait_for_timeout(200)
        _native_fill("#Contact_Information_city", city)
        page.wait_for_timeout(500)

        # Country/State combobox selection
        def _click_select_option(labelledby_id: str, option_text: str, timeout: int = 10000) -> bool:
            try:
                combo = page.locator(f'[aria-labelledby="{labelledby_id}"]').first
                # Check if already set to the desired value
                current_val = ""
                try:
                    current_val = combo.input_value(timeout=1000) or ""
                except Exception:
                    pass
                if current_val and option_text.lower() in current_val.lower():
                    logger.info(f"[Eightfold] select '{labelledby_id}' already='{current_val}' (skip)")
                    return True
                combo.click(timeout=timeout)
                page.wait_for_timeout(800)
                opt = page.locator('[role="option"]').filter(has_text=option_text).first
                opt.click(timeout=timeout)
                page.wait_for_timeout(600)
                return True
            except Exception as ex:
                logger.warning(f"[Eightfold] select '{labelledby_id}' -> '{option_text}' failed: {ex}")
                # Close any stuck open dropdown via Escape
                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(300)
                except Exception:
                    pass
                return False

        logger.info("[Eightfold] Selecting country United States")
        _click_select_option("Contact_Information_country_label", "United States")
        page.wait_for_timeout(2000)

        try:
            page.wait_for_selector('[aria-labelledby="Contact_Information_state_label"]', timeout=10000)
        except Exception:
            logger.warning("[Eightfold] State field did not appear after country selection")

        logger.info(f"[Eightfold] Selecting state {state_full}")
        _click_select_option("Contact_Information_state_label", state_full)
        page.wait_for_timeout(500)

        # LinkedIn URL
        try:
            linkedin_url = contact.get("linkedin", "https://linkedin.com/in/cyshekari")
            page.fill("#Additional_Documents_candidate_portfolio_url", linkedin_url)
        except Exception:
            pass

        # Self-ID questions (voluntary)
        # 1) Combobox-style self-ID (military, transgender, disability)
        self_id_map = {
            "Self_ID_Questions_US_military_label": "I choose not to disclose",
            "Self_ID_Questions_US_transgender_label": "I choose not to disclose",
            "Self_ID_Questions_US_disability_label": "I choose not to disclose",
            "Self_ID_Questions_US_race_label": "I choose not to disclose",
            "Self_ID_Questions_US_gender_label": "I choose not to disclose",
        }
        logger.info("[Eightfold] Checking for Self-ID questions")
        for sid_label, sid_answer in self_id_map.items():
            sid_combo = page.locator(f'[aria-labelledby="{sid_label}"]')
            if sid_combo.count() > 0:
                logger.info(f"[Eightfold] Answering Self-ID: {sid_label}")
                ok = _click_select_option(sid_label, sid_answer, timeout=6000)
                if not ok:
                    _click_select_option(sid_label, "I choose not to disclose", timeout=4000)

        # 2) Checkbox-group self-ID (gender identity, race/ethnicity, sexual orientation)
        # These are DIV[role=group] containers with checkbox inputs. The reliable
        # commit is Playwright .check() on the actual checkbox INPUT by id
        # (label.click() leaves React state uncommitted -> SPA silently blocks the
        # submit POST with a required-field validation, 2026-06-20 fix).
        # Each option's input id is f"{grp_id}-{value}-{index}"; 'I choose not to
        # disclose' is what we want. We resolve its exact id from the DOM.
        checkbox_selfid_groups = [
            "Self_ID_Questions_US_genderIdentity",
            "Self_ID_Questions_US_raceEthnicity",
            "Self_ID_Questions_US_sexualOrientation",
        ]
        for grp_id in checkbox_selfid_groups:
            grp = page.locator(f'[id="{grp_id}"]')
            if grp.count() == 0:
                logger.debug(f"[Eightfold] Checkbox self-ID group not found: {grp_id}")
                continue
            # Resolve the exact checkbox-input id for 'I choose not to disclose'
            decline_id = page.evaluate(
                """(gid) => {
                    const g = document.getElementById(gid);
                    if (!g) return null;
                    const cbs = Array.from(g.querySelectorAll('input[type=checkbox]'));
                    const m = cbs.find(c => (c.value||'').toLowerCase().includes('not to disclose'))
                              || cbs.find(c => /not to disclose/i.test(c.id));
                    return m ? m.id : null;
                }""",
                grp_id,
            )
            committed = False
            if decline_id:
                try:
                    page.locator(f'input[id="{decline_id}"]').check(timeout=5000)
                    page.wait_for_timeout(250)
                    committed = bool(page.evaluate(
                        "(id)=>{const e=document.getElementById(id); return e? e.checked: false;}",
                        decline_id,
                    ))
                except Exception as _cex:
                    logger.warning(f"[Eightfold] check() failed for {grp_id} ({decline_id}): {_cex}")
            if committed:
                logger.info(f"[Eightfold] Committed 'I choose not to disclose' checkbox for {grp_id} (id={decline_id})")
            else:
                # Fallback: label click (legacy path)
                lbl = grp.locator('label').filter(has_text='I choose not to disclose')
                if lbl.count() > 0:
                    try:
                        lbl.first.click(timeout=4000)
                        logger.warning(f"[Eightfold] .check() did not commit {grp_id}; fell back to label click")
                        page.wait_for_timeout(300)
                    except Exception:
                        pass
                else:
                    first_lbl = grp.locator('label').first
                    if first_lbl.count() > 0:
                        first_lbl.click(timeout=3000)
                        logger.warning(f"[Eightfold] 'I choose not to disclose' not found in {grp_id}, clicked first option")

        # Application questions from page state -- DOM fill only (also captured for API submit below)
        # Add wait after Self-ID to ensure no stuck dropdown from previous interaction
        page.wait_for_timeout(800)
        extra_qs_dom = page_state.get("extraQs") or []
        answers_dom = _handle_extra_questions(page, extra_qs_dom, personal_info, role_id)
        for qid, answer in answers_dom.items():
            _click_select_option(qid, answer, timeout=8000)

        page.wait_for_timeout(1000)

        logger.info(f"[Eightfold] Found {len(extra_qs_dom)} application question comboboxes")

        if dry_run:
            logger.info("[Eightfold] DRY RUN -- form filled + resume uploaded. EXIT dryrun")
            page.close()
            return {
                "status": "dryrun",
                "enc_id": enc_id,
                "pids": str(page_pids),
                "confirmation": {"enc_id": enc_id, "resume_filename": uploaded_filename},
                "exit_code": EXIT_SUBMITTED,
            }

        # --- Button-click submit (proven approach, 2026-06-14) ---
        # The SPA handles stringifiedQuestions format + reCAPTCHA automatically.
        # We hook window.fetch BEFORE clicking to capture the API response.
        # NOTE: Do NOT try API-direct submit — server expects stringifiedQuestions
        # JSON format (not simple fields), only the SPA builds it correctly.
        logger.info("[Eightfold] Hooking fetch to capture submit response")
        submit_response_captured = []
        def _on_response(resp):
            if '/api/application/v2/submit' in resp.url:
                try:
                    body = resp.body()
                    import json as _json
                    try:
                        data = _json.loads(body)
                    except Exception:
                        data = {"raw": body.decode('utf-8', errors='replace')[:500]}
                    submit_response_captured.append({"ok": resp.ok, "status": resp.status, "data": data})
                    logger.info(f"[Eightfold] Playwright response hook captured: ok={resp.ok} status={resp.status}")
                except Exception as _ex:
                    logger.warning(f"[Eightfold] Response hook read error: {_ex}")
        page.on("response", _on_response)
        try:
            page.evaluate(JS_HOOK_FETCH)
        except Exception as ex:
            logger.warning(f"[Eightfold] fetch hook error (non-fatal): {ex}")

        # Test reCAPTCHA execute capability before attempting submit
        if recap_sitekey:
            try:
                recap_test = page.evaluate("""
                    async (sk) => {
                        try {
                            if (typeof grecaptcha === 'undefined') return {ok: false, reason: 'grecaptcha_undefined'};
                            let token = null;
                            if (grecaptcha.enterprise) {
                                token = await new Promise((res, rej) => {
                                    grecaptcha.enterprise.ready(() => {
                                        grecaptcha.enterprise.execute(sk, {action: 'test'}).then(res).catch(rej);
                                    });
                                });
                            } else {
                                token = await new Promise((res, rej) => {
                                    grecaptcha.ready(() => {
                                        grecaptcha.execute(sk, {action: 'test'}).then(res).catch(rej);
                                    });
                                });
                            }
                            return {ok: !!token, token_prefix: token ? token.substring(0,20) : null};
                        } catch(e) { return {ok: false, reason: e.toString()}; }
                    }
                """, recap_sitekey)
                logger.info(f"[Eightfold] reCAPTCHA pre-test: ok={recap_test.get('ok')} token={recap_test.get('token_prefix')} reason={recap_test.get('reason')}")
            except Exception as _rtex:
                logger.warning(f"[Eightfold] reCAPTCHA pre-test error: {_rtex}")

        # Ensure OneTrust banner is fully gone before submit click
        try:
            page.evaluate("""() => {
                try {
                    const sdk = document.getElementById('onetrust-consent-sdk');
                    if (sdk) { sdk.remove(); }
                } catch(e) {}
            }""")
        except Exception:
            pass
        page.wait_for_timeout(300)

        logger.info("[Eightfold] Clicking Submit application button")
        try:
            btn = page.locator("button:has-text('Submit application')").first
            if btn.count() == 0:
                logger.error("[Eightfold] Submit button not found")
                page.close()
                return {"status": "error", "error": "Submit button not found", "exit_code": EXIT_CANT_SUBMIT}
            # Check if button is disabled (form validation not complete)
            is_disabled = btn.get_attribute("disabled") is not None or btn.is_disabled()
            if is_disabled:
                logger.warning("[Eightfold] Submit button is disabled — form may have unfilled required fields")
                # Log current combobox state for diagnosis
                combobox_state = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('[role="combobox"]')).map(function(c) {
                        return {lb: c.getAttribute('aria-labelledby'), v: c.value};
                    });
                }""")
                logger.warning(f"[Eightfold] Combobox state: {combobox_state}")
            btn.click(timeout=10000)
            logger.info("[Eightfold] Button clicked, waiting for SPA response...")
            # Extra diagnostic: check for validation errors after click
            page.wait_for_timeout(2000)
            val_errors = page.evaluate("""() => {
                var errs = Array.from(document.querySelectorAll('[aria-invalid="true"], .error-message, [class*=error]'));
                return errs.map(function(e) { return {tag: e.tagName, id: e.id, text: (e.textContent || '').trim().substring(0,100)}; }).slice(0, 10);
            }""")
            if val_errors:
                logger.warning(f"[Eightfold] Validation errors after click: {val_errors}")
        except Exception as ex:
            logger.error(f"[Eightfold] Submit button click failed: {ex}")
            page.close()
            return {"status": "error", "error": f"Submit click failed: {ex}", "exit_code": EXIT_CANT_SUBMIT}

        # Wait for reCAPTCHA callback + fetch to complete (up to 30s)
        logger.info("[Eightfold] Waiting for submit fetch response (up to 30s)")
        sub = None
        _submit_wait_iters = int(os.environ.get("EF_SUBMIT_WAIT_ITERS", "30"))
        for _i in range(_submit_wait_iters):
            time.sleep(1)
            # Check Playwright-level response hook first (more reliable)
            if submit_response_captured:
                sub = submit_response_captured[0]
                logger.info(f"[Eightfold] Submit response (PW hook) after {_i+1}s: ok={sub.get('ok')} status={sub.get('status')}")
                break
            try:
                result = page.evaluate(JS_READ_SUBMIT_RESULT)
            except Exception:
                result = None
            if result is not None:
                sub = result
                logger.info(f"[Eightfold] Submit response (JS hook) after {_i+1}s: ok={sub.get('ok')} status={sub.get('status')}")
                break

        if sub is None:
            # No API response captured — check if confirmation appeared anyway
            conf = page.evaluate(JS_CHECK_CONFIRMATION)
            if conf.get("confirmed"):
                snippet = conf.get("snippet") or "UI confirmation detected"
                logger.info(f"[Eightfold] *** SUBMITTED (UI confirm, no API capture) *** enc_id={enc_id}")
                page.close()
                return {
                    "status": "submitted",
                    "enc_id": enc_id,
                    "pids": str(page_pids),
                    "confirmation": {"snippet": snippet, "url": conf.get("url", ""), "resume_filename": uploaded_filename},
                    "exit_code": EXIT_SUBMITTED,
                }
            # Log current page URL and form state for diagnosis
            cur_url = page.url
            combobox_final = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('[role="combobox"]')).map(function(c) {
                    return {lb: (c.getAttribute('aria-labelledby') || '').substring(0,50), v: c.value};
                });
            }""")
            all_fetches_raw = page.evaluate("() => sessionStorage.getItem('ef_all_fetches')")
            logger.error(f"[Eightfold] No submit response — URL={cur_url}")
            logger.error(f"[Eightfold] Combos at fail: {combobox_final}")
            logger.error(f"[Eightfold] All fetches after submit: {all_fetches_raw}")
            page.close()
            return {
                "status": "blocked",
                "error": "BLOCKED: eightfold-submit-no-response — reCAPTCHA may be blocking or form invalid",
                "exit_code": EXIT_LOOP_CAP,
            }

        logger.info(f"[Eightfold] Submit API: ok={sub.get('ok')} status={sub.get('status')} data={json.dumps(sub.get('data', {}))[:400]}")

        s_status = sub.get("status", 0)
        s_data = sub.get("data", {})
        s_body_lower = json.dumps(s_data).lower()

        # Already applied
        if s_status == 400 and "already applied" in s_body_lower:
            logger.info(f"[Eightfold] Already applied to this position (HTTP 400)")
            page.close()
            return {
                "status": "already_applied",
                "enc_id": enc_id,
                "pids": str(page_pids),
                "exit_code": EXIT_ALREADY_APPLIED,
            }

        # Success: HTTP 200 or 201
        if sub.get("ok") or s_status in (200, 201):
            conf = page.evaluate(JS_CHECK_CONFIRMATION)
            snippet = conf.get("snippet") or f"HTTP {s_status}"
            logger.info(f"[Eightfold] *** SUBMITTED *** enc_id={enc_id} pids={page_pids}")
            page.close()
            return {
                "status": "submitted",
                "enc_id": enc_id,
                "pids": str(page_pids),
                "confirmation": {"snippet": snippet, "url": conf.get("url", ""), "resume_filename": uploaded_filename},
                "exit_code": EXIT_SUBMITTED,
            }

        # reCAPTCHA scoring block (score too low, can't retry in this session)
        if "captcha" in s_body_lower or "recaptcha" in s_body_lower or "robot" in s_body_lower or s_status == 429:
            logger.warning(f"[Eightfold] reCAPTCHA/bot block: HTTP {s_status}")
            page.close()
            return {
                "status": "blocked",
                "error": f"BLOCKED: eightfold-recaptcha-v3-score-gate HTTP {s_status}",
                "exit_code": EXIT_LOOP_CAP,
            }

        # Server error (500) or other failure
        err_text = str(s_data)[:500]
        logger.error(f"[Eightfold] Submit failed: HTTP {s_status} {err_text}")
        page.close()
        return {
            "status": "error",
            "error": f"Submit API HTTP {s_status}: {err_text}",
            "exit_code": EXIT_NO_CONFIRMATION,
        }


# ---------------------------------------------------------------------------
# Legacy wrappers (preserved for backward compat with inline_submit.py)
# ---------------------------------------------------------------------------

def _get_pid_for_role(role_id: int) -> Optional[str]:
    """Look up the Eightfold PID (job ID) from tracker DB."""
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tracker.db"))
    if not os.path.exists(db_path):
        logger.error(f"tracker.db not found at {db_path}")
        return None
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT app_url FROM roles WHERE id = ?", (role_id,)).fetchone()
        conn.close()
    except Exception as ex:
        logger.error(f"DB error: {ex}")
        return None
    if not row:
        return None
    app_url = row[0] or ""
    return _pid_from_url(app_url)


def submit_eightfold(
    role_id: int,
    resume_path: str,
    personal_info: dict,
    domain: str = "netflix.com",
    dry_run: bool = False,
) -> int:
    """
    Legacy entry point — wraps run_eightfold().
    resume_path is REQUIRED (tailored PDF). Returns exit code int.
    """
    if not resume_path or not os.path.exists(resume_path):
        logger.error(f"[Eightfold] submit_eightfold called without valid resume_path: {resume_path!r}")
        return EXIT_FATAL

    # Look up apply_url from DB
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tracker.db"))
    apply_url = ""
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT app_url FROM roles WHERE id = ?", (role_id,)).fetchone()
            conn.close()
            if row:
                apply_url = row[0] or ""
        except Exception as ex:
            logger.error(f"DB error: {ex}")

    if not apply_url:
        logger.error(f"[Eightfold] No app_url found for role {role_id}")
        return EXIT_FATAL

    result = run_eightfold(
        role_id=role_id,
        apply_url=apply_url,
        personal_info=personal_info,
        resume_pdf_path=resume_path,
        dry_run=dry_run,
    )
    status = result.get("status", "error")
    if status in ("submitted", "dryrun"):
        return EXIT_SUBMITTED
    elif status == "already_applied":
        return EXIT_ALREADY_APPLIED
    elif status == "closed":
        return EXIT_CLOSED
    elif status == "blocked":
        return EXIT_LOOP_CAP
    else:
        return result.get("exit_code", EXIT_FATAL)


def submit_eightfold_playwright(
    role_id: int,
    personal_info: dict,
    domain: str = "netflix.com",
    dry_run: bool = False,
    resume_path: str = "",
) -> int:
    """Legacy Playwright wrapper — delegates to submit_eightfold()."""
    return submit_eightfold(role_id, resume_path, personal_info, domain, dry_run)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(description="Eightfold ATS runner")
    parser.add_argument("--role-id", type=int, required=True, help="Tracker role ID")
    parser.add_argument("--resume", required=True, help="Path to TAILORED resume PDF (MANDATORY)")
    parser.add_argument("--domain", default="netflix.com", help="Eightfold tenant domain")
    parser.add_argument("--dry-run", action="store_true", help="Fill form but don't submit")
    parser.add_argument("--personal-info", default=None, help="Path to personal-info.json")
    args = parser.parse_args()

    # Load personal info
    if args.personal_info:
        info_path = args.personal_info
    else:
        info_path = os.path.join(os.path.dirname(__file__), "..", "personal-info.json")
    info_path = os.path.normpath(info_path)

    if not os.path.exists(info_path):
        print(f"ERROR: personal-info.json not found at {info_path}", file=sys.stderr)
        sys.exit(EXIT_FATAL)

    with open(info_path) as f:
        personal_info = json.load(f)

    # Look up apply_url from DB
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tracker.db"))
    apply_url = ""
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT app_url FROM roles WHERE id = ?", (args.role_id,)).fetchone()
            conn.close()
            if row:
                apply_url = row[0] or ""
        except Exception as ex:
            print(f"ERROR: DB lookup failed: {ex}", file=sys.stderr)
            sys.exit(EXIT_FATAL)

    if not apply_url:
        print(f"ERROR: No app_url found for role {args.role_id}", file=sys.stderr)
        sys.exit(EXIT_FATAL)

    logger.info(f"Starting Eightfold runner for role {args.role_id} (dry_run={args.dry_run})")
    logger.info(f"Tailored resume: {args.resume}")

    result = run_eightfold(
        role_id=args.role_id,
        apply_url=apply_url,
        personal_info=personal_info,
        resume_pdf_path=args.resume,
        dry_run=args.dry_run,
    )

    status = result.get("status", "error")
    logger.info(f"Result: status={status} enc_id={result.get('enc_id')} exit_code={result.get('exit_code', EXIT_FATAL)}")

    if status in ("submitted", "dryrun"):
        print(f"SUCCESS: {status} enc_id={result.get('enc_id')} pids={result.get('pids')}")
        sys.exit(EXIT_SUBMITTED)
    elif status == "already_applied":
        print("Already applied to this role")
        sys.exit(EXIT_ALREADY_APPLIED)
    elif status == "closed":
        print("Role is closed")
        sys.exit(EXIT_CLOSED)
    elif status == "blocked":
        print(f"BLOCKED: {result.get('error', 'captcha/other block')}")
        sys.exit(EXIT_LOOP_CAP)
    else:
        print(f"ERROR: {result.get('error', 'unknown error')}", file=sys.stderr)
        sys.exit(result.get("exit_code", EXIT_FATAL))
