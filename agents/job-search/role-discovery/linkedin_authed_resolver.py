#!/usr/bin/env python3
"""LinkedIn → ATS resolver (authenticated, browser-driven).

Companion to `linkedin_resolver_pipeline.py` (the anonymous, requests-based
v3 pipeline). This worker uses the OpenClaw browser tool to walk each
LinkedIn job page in a real Chromium instance, click the Apply button,
capture the off-site redirect URL (the ATS link), and write it back to
`tracker.db`.

Why this exists
---------------
The anonymous pipeline-port resolver BLOCKED on 121 stranded rows because:
  * LinkedIn's public JD HTML does NOT inline the off-site Apply URL.
  * Even the JS-rendered DOM on the public page only shows a
    `sign-up-modal__outlet` Apply button — clicking it opens a sign-up
    modal, not an off-site redirect.
  * The off-site redirect is ONLY exposed once the visitor has a valid
    `li_at` auth cookie.

CLI mirrors `linkedin_resolver_pipeline.py`:
    --limit N            max rows to attempt (0 = no limit)
    --apply              actually write to tracker.db (default: dry-run)
    --dry-run            force dry-run (default behaviour; explicit override)
    --max-seconds 10800  whole-run wall-clock cap (default 3h)
    --role-id ID         single-row debug mode (skips the selection query)
    --profile NAME       browser profile to use (default: "openclaw";
                         set to "user" once the chrome-mcp existing-session
                         attach is functional)
    --per-row-seconds 90 per-row wall-clock cap
    --db PATH            tracker.db path

Tactic ladder (per row, in order):
  1. **Apply-button redirect capture (authed).**
     Navigate to the LinkedIn URL. Snapshot. Find the "Apply" button.
     If text contains "Easy Apply" → mark as easy-apply-only (LinkedIn
     in-platform only, no off-site URL exists). If text is just "Apply",
     click and capture the URL of the new tab that opens; that's the
     resolved ATS URL.
  2. **JD-body ATS scrape (authed).**
     Even without clicking, the authed JD often inlines off-site links
     ("Apply on company website", recruiter URLs in the description).
     Run a JS regex sweep over the rendered DOM for greenhouse / ashby /
     lever / workday / smartrecruiters / icims / jobvite / workable /
     myworkdayjobs / oraclecloud / successfactors URLs.
  3. **Company-careers-page nav (authed).**
     If the JD page exposes a company URL in the topcard, follow it; if
     it points to the company's careers page, scrape that for an off-site
     ATS link with a fuzzy title match.
  4. **Anonymous-ladder fallback.**
     Delegates to `linkedin_resolver_pipeline.resolve_one()`
     (companies.yaml lookup + LinkedIn HTML fetch + careers-page probe).
     Free, fast, no auth required — catches the rows where the company
     careers page happens to expose the same role.

DB writes (only with --apply):
  * Resolved   → app_url = <ats_url>, source_key = derive_source_key(ats_url),
                 agent_notes = 'LINKEDIN-AUTHED <date>: resolved via <tactic> | original: <linkedin_url>'
  * Easy-apply → flags += 'manual-apply',
                 agent_notes = 'LINKEDIN-AUTHED <date>: EASY-APPLY-ONLY | manual-apply only'
  * Unresolved → agent_notes = 'LINKEDIN-AUTHED <date>: UNRESOLVED | tried: <list> | reasons: <brief>'
  * Backoff    → agent_notes = 'LINKEDIN-AUTHED <date>: BACKOFF-RATE-LIMITED' (no other field change)

Safety:
  * Idempotent — selection query filters out rows that already have a
    'LINKEDIN-AUTHED' note.
  * Creates `tracker.db.bak.<stamp>-linkedin-authed-resolver` before the
    first write in --apply mode.
  * Read-only-navigation worker. Does NOT submit anything anywhere. The
    only browser interaction is a single click of the LinkedIn Apply
    button (and even that only to capture the resulting tab URL — the
    new tab is closed immediately).

Browser-tool driver:
  The browser interactions are wrapped in `BrowserDriver`, a small adapter
  class. In production it's instantiated from `OpenClawBrowserDriver` which
  shells out to the `openclaw browser` CLI. In tests we inject a fake.
  This keeps the rest of the module pure-Python and unit-testable offline.

Status:
  * Code + unit tests written 2026-05-27.
  * LIVE-UNVALIDATED. See ESCALATE.md — the OpenClaw browser does not
    currently carry a `li_at` LinkedIn auth cookie, so the authed tactics
    (1/2/3) cannot be exercised against real LinkedIn pages until auth
    is provisioned. Tactic 4 (anonymous fallback) IS exercisable but is
    expected to keep returning UNRESOLVED for the same 121 rows.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DB = PROJ / "tracker.db"
# Canonical place Cyrus drops a fresh LinkedIn li_at cookie. The resolver
# auto-injects this into the CDP browser context on startup so the value
# actually takes effect (the browser profile cookie jar is AES-GCM encrypted,
# so a flat-file value is otherwise invisible to the pipeline). Drop ONLY the
# raw li_at value (the long string starting `AQED...`) into this file.
# Added 2026-05-31 after a dead/unwired-cookie incident.
LI_AT_FILE = PROJ / ".linkedin-li-at"

sys.path.insert(0, str(HERE))
import linkedin_resolver_pipeline as lp  # noqa: E402

DEFAULT_PROFILE = "openclaw"  # switch to "user" when chrome-mcp attach works
DEFAULT_PER_ROW_SECONDS = 90
DEFAULT_MAX_SECONDS = 10800  # 3h

# Regex used by Tactic 2 (DOM sweep). Wider than the requests-side rx in
# lp because authed pages embed more ATS shapes.
ATS_DOMAINS_DOM_RX = re.compile(
    r"(?:greenhouse\.io|boards\.greenhouse|job-boards\.greenhouse|"
    r"jobs\.lever\.co|jobs\.ashbyhq\.com|myworkdayjobs\.com|"
    r"smartrecruiters\.com|workable\.com|bamboohr\.com|recruitee\.com|"
    r"jobvite\.com|icims\.com|breezy\.hr|teamtailor\.com|"
    r"oraclecloud\.com|successfactors\.com|eightfold\.ai|paylocity\.com|"
    r"dayforcehcm\.com|adp\.com)",
    re.I,
)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

SELECT_TARGETS_SQL = """
    SELECT id, company, role, app_url, est_tc
    FROM roles
    WHERE (status IS NULL OR status='' OR status='blocked')
      AND (applied_by IS NULL OR applied_by='')
      AND app_url LIKE '%linkedin.com%'
      AND (agent_notes IS NULL OR agent_notes NOT LIKE '%LINKEDIN-AUTHED%')
    ORDER BY (est_tc IS NULL) ASC, est_tc DESC, id ASC
"""

SELECT_ONE_SQL = """
    SELECT id, company, role, app_url, est_tc
    FROM roles
    WHERE id = ?
"""


def fetch_targets(con: sqlite3.Connection, limit: int) -> list[tuple]:
    rows = con.execute(SELECT_TARGETS_SQL).fetchall()
    if limit:
        rows = rows[:limit]
    return rows


def fetch_single(con: sqlite3.Connection, role_id: int) -> Optional[tuple]:
    return con.execute(SELECT_ONE_SQL, (role_id,)).fetchone()


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def is_linkedin_jd_url(url: str) -> bool:
    if not url:
        return False
    u = urlparse(url)
    return (u.netloc or "").endswith("linkedin.com") and "/jobs/view" in (u.path or "")


def looks_like_ats_url(url: str) -> bool:
    if not url:
        return False
    return bool(ATS_DOMAINS_DOM_RX.search(url))


def is_linkedin_host(url: str) -> bool:
    """Defensive guard against 'false-resolve-still-linkedin'.

    The anonymous fallback (lp.tactic_yaml_match) can return a URL that
    came from the crawler's roles.json — and for some companies
    (e.g. Rivian, Tesla) the crawler's recorded URL IS the LinkedIn
    discovery URL. If we 'resolve' to that, we'd stamp the row resolved
    while app_url still points at linkedin.com. Always reject.
    """
    if not url:
        return False
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return host.endswith("linkedin.com")


def extract_ats_urls_from_dom_blob(blob: str) -> list[str]:
    """Same regex shape as lp.extract_ats_urls_from_html but over a richer
    rendered-DOM blob."""
    if not blob:
        return []
    urls: set[str] = set()
    for m in re.finditer(r"https?://[^\s\"'<>]+", blob):
        u = m.group(0).rstrip(".,);]\"'<>")
        if ATS_DOMAINS_DOM_RX.search(u):
            urls.add(u)
    return list(urls)


def score_ats_urls_by_company(urls: list[str], company: str) -> Optional[str]:
    """Prefer URLs whose host/path mention the company slug."""
    if not urls:
        return None
    cnorm = lp.norm_company(company)
    scored: list[tuple[int, str]] = []
    for u in urls:
        unorm = re.sub(r"[^a-z0-9]", "", u.lower())
        score = 1 if cnorm and cnorm in unorm else 0
        scored.append((score, u))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


# ---------------------------------------------------------------------------
# Browser driver (pluggable for tests)
# ---------------------------------------------------------------------------

class BrowserResult(dict):
    """Light wrapper around the dict result from the browser tool, for
    type-hint readability."""


class BrowserDriver:
    """Abstract driver. Subclasses implement actual browser interactions."""

    def open_tab(self, url: str, label: str) -> BrowserResult: raise NotImplementedError
    def close_tab(self, target_id: str) -> None: raise NotImplementedError
    def list_tabs(self) -> list[dict]: raise NotImplementedError
    def evaluate(self, target_id: str, fn: str) -> Any: raise NotImplementedError
    def snapshot_text(self, target_id: str, max_chars: int = 4000) -> str: raise NotImplementedError
    def click_ref(self, target_id: str, ref: str) -> bool: raise NotImplementedError


DEFAULT_CDP_URL = "http://127.0.0.1:18800"


class OpenClawBrowserDriver(BrowserDriver):
    """Production driver that talks directly to the OpenClaw Chromium
    instance over the Chrome DevTools Protocol via Playwright's
    `connect_over_cdp`.

    Previous implementation shelled out to `openclaw browser ...` with
    a `--url` flag that doesn't exist; every call failed with
    `browser-open-failed` and the resolver silently dropped to T4 only.
    Bug fix 2026-05-27.
    """

    def __init__(self, profile: str = DEFAULT_PROFILE, cdp_url: str = DEFAULT_CDP_URL):
        self.profile = profile  # informational only; CDP attaches to the running browser
        self.cdp_url = cdp_url
        self._pw = None
        self._browser = None
        self._ctx = None
        self._pages: dict[str, Any] = {}  # targetId -> Page

    def _ensure(self) -> None:
        if self._ctx is not None:
            return
        from playwright.sync_api import sync_playwright  # lazy import
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.connect_over_cdp(self.cdp_url)
        # Use the first existing context (the openclaw default) so cookies
        # (li_at etc.) are reused.
        if self._browser.contexts:
            self._ctx = self._browser.contexts[0]
        else:
            self._ctx = self._browser.new_context()
        # Auto-inject a fresh li_at from the canonical drop file (LI_AT_FILE) so a
        # cookie Cyrus provides actually takes effect. The profile's on-disk jar
        # is AES-GCM encrypted, so a flat-file value is otherwise never used.
        self._inject_li_at()

    def _inject_li_at(self) -> None:
        """Read LI_AT_FILE and inject as the li_at cookie on the live context.
        No-op if the file is missing/empty. Logs a clear validity hint: if the
        value is present we still can't prove liveness here, but wiring it in is
        what makes 'Cyrus drops cookie' -> 'pipeline uses it' automatic."""
        try:
            if not LI_AT_FILE.exists():
                print(f"[authed-resolver] no li_at file at {LI_AT_FILE} — "
                      f"running with whatever cookies the profile already has", file=sys.stderr)
                return
            val = LI_AT_FILE.read_text().strip()
            if not val:
                print(f"[authed-resolver] {LI_AT_FILE} is empty — skipping li_at inject", file=sys.stderr)
                return
            import time as _t
            exp = _t.time() + 330 * 24 * 3600
            self._ctx.add_cookies([
                {"name": "li_at", "value": val, "domain": dom, "path": "/",
                 "secure": True, "httpOnly": True, "sameSite": "None", "expires": exp}
                for dom in (".www.linkedin.com", ".linkedin.com")
            ])
            print(f"[authed-resolver] injected li_at from {LI_AT_FILE} "
                  f"(len={len(val)}) into context", file=sys.stderr)
        except Exception as e:  # never let cookie wiring crash the run
            print(f"[authed-resolver] li_at inject failed (non-fatal): {e}", file=sys.stderr)

    def shutdown(self) -> None:
        try:
            for tid, page in list(self._pages.items()):
                try:
                    page.close()
                except Exception:
                    pass
            self._pages.clear()
        finally:
            try:
                if self._browser is not None:
                    self._browser.close()
            except Exception:
                pass
            try:
                if self._pw is not None:
                    self._pw.stop()
            except Exception:
                pass
            self._browser = None
            self._ctx = None
            self._pw = None

    def open_tab(self, url: str, label: str) -> BrowserResult:
        try:
            self._ensure()
            page = self._ctx.new_page()
            tid = f"pw-{id(page)}"
            self._pages[tid] = page
            # Override UA to a normal Chrome string so LinkedIn doesn't
            # block HeadlessChrome on every request.
            try:
                cdp = self._ctx.new_cdp_session(page)
                cdp.send("Network.setUserAgentOverride", {
                    "userAgent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/148.0.0.0 Safari/537.36"
                    )
                })
            except Exception:
                pass
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                # Keep the page open so callers can still evaluate (or close).
                return BrowserResult({"targetId": tid, "url": url, "label": label,
                                      "nav_error": str(e)[:200]})
            return BrowserResult({"targetId": tid, "url": page.url, "label": label})
        except Exception as e:
            return BrowserResult({"error": f"open-failed:{type(e).__name__}:{e}"[:200]})

    def close_tab(self, target_id: str) -> None:
        page = self._pages.pop(target_id, None)
        if page is None:
            return
        try:
            page.close()
        except Exception:
            pass

    def list_tabs(self) -> list[dict]:
        try:
            self._ensure()
        except Exception:
            return []
        out: list[dict] = []
        # Include our tracked tabs.
        for tid, page in self._pages.items():
            try:
                out.append({"targetId": tid, "url": page.url, "title": page.title()})
            except Exception:
                out.append({"targetId": tid, "url": "", "title": ""})
        # Also include any pages in the context we don't own (newly-opened
        # popup tabs from clicks).
        try:
            owned = set(self._pages.values())
            for p in self._ctx.pages:
                if p in owned:
                    continue
                tid = f"pw-{id(p)}"
                # Track the popup so close_tab works on it.
                self._pages[tid] = p
                try:
                    out.append({"targetId": tid, "url": p.url, "title": p.title()})
                except Exception:
                    out.append({"targetId": tid, "url": "", "title": ""})
        except Exception:
            pass
        return out

    def evaluate(self, target_id: str, fn: str) -> Any:
        page = self._pages.get(target_id)
        if page is None:
            return None
        try:
            # Playwright accepts an arrow-function-string as `expression`.
            return page.evaluate(fn)
        except Exception:
            return None

    def snapshot_text(self, target_id: str, max_chars: int = 4000) -> str:
        page = self._pages.get(target_id)
        if page is None:
            return ""
        try:
            txt = page.evaluate("() => document.body && document.body.innerText || ''")
            if isinstance(txt, str):
                return txt[:max_chars]
            return ""
        except Exception:
            return ""

    def click_ref(self, target_id: str, ref: str) -> bool:
        # Not used by the resolver tactics (we click via JS evaluate). Stub.
        page = self._pages.get(target_id)
        if page is None:
            return False
        try:
            page.click(ref, timeout=5000)
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# JS payloads for tactics 1/2/3
# ---------------------------------------------------------------------------

# Tactic 1 helper — classify the apply button on the JD page.
# Returns: { kind: 'easy-apply' | 'apply' | 'sign-up-wall' | 'none',
#            sample_text: str, sample_classes: str }
JS_CLASSIFY_APPLY_BUTTON = """
() => {
  const btns = Array.from(document.querySelectorAll('button, a'));
  const apply = btns.filter(b => /\\bapply\\b/i.test((b.textContent || '').trim()));
  if (apply.length === 0) return {kind: 'none', sample_text: '', sample_classes: ''};
  // Easy Apply has the highest signal — its text starts with "Easy Apply"
  const ea = apply.find(b => /easy\\s*apply/i.test(b.textContent || ''));
  if (ea) return {kind: 'easy-apply', sample_text: ea.textContent.trim().slice(0,80), sample_classes: ea.className || ''};
  // Sign-up-wall: anonymous public page reveals only modal buttons
  const wall = apply.find(b => /sign-up-modal__outlet|contextual-sign-in-modal/i.test(b.className || '') || /sign-up-modal__outlet/i.test((b.outerHTML||'')));
  if (wall) return {kind: 'sign-up-wall', sample_text: wall.textContent.trim().slice(0,80), sample_classes: wall.className || ''};
  // Otherwise treat as a real authed apply button. Also surface any direct href.
  const a = apply.find(b => b.tagName === 'A' && b.href);
  if (a) return {kind: 'apply', sample_text: a.textContent.trim().slice(0,80), sample_classes: a.className || '', href: a.href};
  return {kind: 'apply', sample_text: apply[0].textContent.trim().slice(0,80), sample_classes: apply[0].className || ''};
}
"""

# Tactic 2 helper — sweep the rendered DOM for off-site ATS URLs.
JS_SCRAPE_ATS_URLS = """
() => {
  const html = document.documentElement.outerHTML;
  const rx = /(https?:\\/\\/[^\\s"'<>]*(?:greenhouse\\.io|boards\\.greenhouse|job-boards\\.greenhouse|jobs\\.lever\\.co|jobs\\.ashbyhq\\.com|myworkdayjobs\\.com|smartrecruiters\\.com|workable\\.com|jobvite\\.com|icims\\.com|breezy\\.hr|teamtailor\\.com|oraclecloud\\.com|successfactors\\.com|eightfold\\.ai|paylocity\\.com|dayforcehcm\\.com|adp\\.com|bamboohr\\.com|recruitee\\.com)[^\\s"'<>]*)/gi;
  const matches = Array.from(new Set((html.match(rx) || [])));
  return matches;
}
"""

# Tactic 3 helper — read the company URL from the topcard.
JS_COMPANY_URL = """
() => {
  const a = document.querySelector('a[data-tracking-control-name*="topcard"][href*="/company/"]') ||
            document.querySelector('a.topcard__org-name-link') ||
            document.querySelector('.topcard__org-name-link');
  return a ? a.href : null;
}
"""


# ---------------------------------------------------------------------------
# Tactics
# ---------------------------------------------------------------------------

def tactic_apply_button(
    driver: BrowserDriver, target_id: str, role: tuple,
) -> tuple[Optional[str], str, str]:
    """Returns (ats_url, kind, info).

    kind ∈ {'resolved', 'easy-apply', 'sign-up-wall', 'none', 'error'}
    """
    rid, company, role_title, app_url, _est_tc = role
    cls = driver.evaluate(target_id, JS_CLASSIFY_APPLY_BUTTON)
    if not isinstance(cls, dict):
        return None, "error", "classify-failed"
    kind = cls.get("kind", "none")
    if kind == "easy-apply":
        return None, "easy-apply", "easy-apply-detected"
    if kind == "sign-up-wall":
        return None, "sign-up-wall", "anonymous-sign-up-wall"
    if kind == "none":
        return None, "none", "no-apply-button"
    # 'apply' — try direct href first.
    href = cls.get("href")
    if href and looks_like_ats_url(href):
        return href, "resolved", "apply-direct-href"
    # Else: click & capture new tab.
    tabs_before = {t.get("targetId") for t in driver.list_tabs()}
    # No ref-passing path is shell-CLI-stable; do a snapshot to surface refs
    # then click the apply text via JS as fallback. We try a JS-driven click
    # first because that always works (no ref staleness).
    clicked = driver.evaluate(target_id, """
        () => {
          const btns = Array.from(document.querySelectorAll('button, a'));
          const apply = btns.find(b => /\\bapply\\b/i.test((b.textContent||'').trim()) &&
                                       !/easy\\s*apply/i.test(b.textContent||'') &&
                                       !/sign-up-modal__outlet|contextual-sign-in-modal/i.test(b.className||''));
          if (!apply) return {clicked: false, reason: 'no-button'};
          apply.click();
          return {clicked: true, tag: apply.tagName, text: (apply.textContent||'').trim().slice(0,80)};
        }
    """)
    if not (isinstance(clicked, dict) and clicked.get("clicked")):
        return None, "error", f"click-failed:{clicked}"
    # Give LinkedIn ~3s to open the new tab.
    time.sleep(3)
    tabs_after = driver.list_tabs()
    new_tabs = [t for t in tabs_after if t.get("targetId") not in tabs_before]
    for t in new_tabs:
        url = t.get("url") or ""
        if looks_like_ats_url(url):
            # Clean up the popup tab immediately.
            try:
                driver.close_tab(t["targetId"])
            except Exception:
                pass
            return url, "resolved", "apply-click-new-tab"
        # Some ATS pages 302 through the LinkedIn redirector first; capture
        # the final URL anyway as it's often a careers page on the company.
    # No new ATS tab — give up tactic 1.
    return None, "error", "no-new-tab-with-ats"


def tactic_dom_scrape(
    driver: BrowserDriver, target_id: str, role: tuple,
) -> tuple[Optional[str], str]:
    rid, company, role_title, app_url, _ = role
    result = driver.evaluate(target_id, JS_SCRAPE_ATS_URLS)
    if not isinstance(result, list):
        return None, "scrape-failed"
    if not result:
        return None, "dom-no-ats"
    picked = score_ats_urls_by_company(result, company)
    if picked:
        return picked, f"dom-sweep(found={len(result)})"
    return None, f"dom-no-company-match(found={len(result)})"


def tactic_company_careers(
    driver: BrowserDriver, target_id: str, role: tuple,
) -> tuple[Optional[str], str]:
    rid, company, role_title, app_url, _ = role
    company_url = driver.evaluate(target_id, JS_COMPANY_URL)
    if not (isinstance(company_url, str) and company_url.startswith("http")):
        return None, "no-company-url"
    # If the company URL is itself an ATS link (rare but cheap to handle),
    # return it.
    if looks_like_ats_url(company_url):
        return company_url, "company-link-is-ats"
    # Otherwise we'd need to open the company page and look for a careers tab.
    # That's expensive and not commonly fruitful when LinkedIn's company URL
    # is a `/company/<slug>` page. Defer to the anonymous fallback (tactic 4)
    # which has a stronger careers-probe ladder.
    return None, "company-page-no-direct-ats"


def tactic_anonymous_fallback(
    role: tuple, yaml_cos: list[dict], roles_idx: list[dict],
) -> tuple[Optional[str], Optional[str], list[str]]:
    rid, company, role_title, app_url, _ = role
    return lp.resolve_one(
        company or "", role_title or "", app_url or "", yaml_cos, roles_idx,
    )


# ---------------------------------------------------------------------------
# Per-row driver
# ---------------------------------------------------------------------------

def resolve_one_row(
    driver: BrowserDriver, role: tuple,
    yaml_cos: list[dict], roles_idx: list[dict],
    per_row_seconds: int = DEFAULT_PER_ROW_SECONDS,
    label_prefix: str = "li-auth",
) -> dict:
    """Return a result dict describing what happened.

    Shape:
      {ok: True, kind: 'resolved'|'easy-apply'|'unresolved'|'backoff'|'error',
       ats_url: str|None, tactic: str|None, reasons: list[str], elapsed: float}
    """
    rid, company, role_title, app_url, est_tc = role
    started = time.time()
    reasons: list[str] = []
    tactics_tried: list[str] = []

    if not is_linkedin_jd_url(app_url or ""):
        return {"ok": True, "kind": "error", "ats_url": None, "tactic": None,
                "reasons": ["not-a-linkedin-jd-url"], "elapsed": 0.0}

    # 1-3 require the browser. If the browser fails to open, skip to tactic 4.
    label = f"{label_prefix}-{rid}"
    opened = driver.open_tab(app_url, label)
    target_id = (opened or {}).get("targetId")
    browser_ok = bool(target_id)
    if not browser_ok:
        reasons.append(f"browser-open-failed:{(opened or {}).get('error','?')[:80]}")

    try:
        if browser_ok:
            # Give LinkedIn 2.5s to JS-render.
            time.sleep(2.5)

            # Tactic 1
            tactics_tried.append("apply-button")
            ats, kind, info = tactic_apply_button(driver, target_id, role)
            if kind == "easy-apply":
                return {"ok": True, "kind": "easy-apply", "ats_url": None,
                        "tactic": "apply-button", "reasons": reasons + [info],
                        "elapsed": time.time() - started}
            if ats and not is_linkedin_host(ats):
                return {"ok": True, "kind": "resolved", "ats_url": ats,
                        "tactic": f"apply-button:{info}",
                        "reasons": reasons + [info],
                        "elapsed": time.time() - started}
            if ats:
                reasons.append(f"t1-rejected-still-linkedin:{info}")
            else:
                reasons.append(f"t1:{info}")

            if time.time() - started > per_row_seconds:
                return {"ok": True, "kind": "unresolved", "ats_url": None, "tactic": None,
                        "reasons": reasons + ["per-row-timeout"],
                        "elapsed": time.time() - started}

            # Tactic 2
            tactics_tried.append("dom-scrape")
            ats, info = tactic_dom_scrape(driver, target_id, role)
            if ats and not is_linkedin_host(ats):
                return {"ok": True, "kind": "resolved", "ats_url": ats,
                        "tactic": f"dom-scrape:{info}",
                        "reasons": reasons + [info],
                        "elapsed": time.time() - started}
            if ats:
                reasons.append(f"t2-rejected-still-linkedin:{info}")
            else:
                reasons.append(f"t2:{info}")

            if time.time() - started > per_row_seconds:
                return {"ok": True, "kind": "unresolved", "ats_url": None, "tactic": None,
                        "reasons": reasons + ["per-row-timeout"],
                        "elapsed": time.time() - started}

            # Tactic 3
            tactics_tried.append("company-careers")
            ats, info = tactic_company_careers(driver, target_id, role)
            if ats and not is_linkedin_host(ats):
                return {"ok": True, "kind": "resolved", "ats_url": ats,
                        "tactic": f"company-careers:{info}",
                        "reasons": reasons + [info],
                        "elapsed": time.time() - started}
            if ats:
                reasons.append(f"t3-rejected-still-linkedin:{info}")
            else:
                reasons.append(f"t3:{info}")

        # Tactic 4 (always — works without the browser)
        tactics_tried.append("anonymous-fallback")
        ats, info, anon_reasons = tactic_anonymous_fallback(role, yaml_cos, roles_idx)
        reasons.extend(f"t4:{r}" for r in anon_reasons)
        if ats:
            # Defensive: anonymous yaml-tactic can return a LinkedIn URL when
            # the crawler's roles.json itself stored a LinkedIn discovery URL.
            # Never claim 'resolved' when the new URL is still on linkedin.com.
            if is_linkedin_host(ats):
                reasons.append(
                    f"t4-rejected-still-linkedin:{info}"
                )
                return {"ok": True, "kind": "unresolved", "ats_url": None,
                        "tactic": None,
                        "reasons": reasons + ["false-resolve-still-linkedin"],
                        "elapsed": time.time() - started,
                        "tactics_tried": tactics_tried}
            return {"ok": True, "kind": "resolved", "ats_url": ats,
                    "tactic": f"anonymous-fallback:{info}",
                    "reasons": reasons, "elapsed": time.time() - started}

        return {"ok": True, "kind": "unresolved", "ats_url": None, "tactic": None,
                "reasons": reasons, "elapsed": time.time() - started,
                "tactics_tried": tactics_tried}

    finally:
        if browser_ok:
            try:
                driver.close_tab(target_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def write_resolved(
    con: sqlite3.Connection, role_id: int, ats_url: str, source_key: str,
    tactic_info: str, linkedin_url: str, stamp: str,
) -> None:
    note = (
        f"LINKEDIN-AUTHED {stamp}: resolved via {tactic_info} | "
        f"original: {linkedin_url or ''}"
    )
    con.execute(
        "UPDATE roles SET app_url=?, source_key=?, agent_notes=? WHERE id=?",
        (ats_url, source_key, note, role_id),
    )


def write_easy_apply(
    con: sqlite3.Connection, role_id: int, stamp: str,
) -> None:
    # Read current flags so we don't drop existing tokens.
    row = con.execute("SELECT flags FROM roles WHERE id=?", (role_id,)).fetchone()
    flags = (row[0] or "") if row else ""
    if "manual-apply" not in flags:
        flags = (flags + "," + "manual-apply").lstrip(",")
    # Cyrus 2026-06-08: route Easy-Apply postings to the Manual Apply sheet
    # (status='manual-apply') with a clear 'LinkedIn Easy-Apply' note so he can
    # apply by hand. Setting status (not just flags) is what actually moves the
    # row onto the Manual Apply sheet.
    note = (
        f"LinkedIn Easy-Apply | apply manually on LinkedIn (no external ATS) | "
        f"LINKEDIN-AUTHED {stamp}: EASY-APPLY-ONLY"
    )
    con.execute(
        "UPDATE roles SET flags=?, status='manual-apply', "
        "agent_notes=? WHERE id=?",
        (flags, note, role_id),
    )


def write_unresolved(
    con: sqlite3.Connection, role_id: int, tactics_tried: list[str],
    reasons: list[str], stamp: str,
) -> None:
    # Cyrus 2026-06-08: an UNRESOLVED LinkedIn row (no external apply button
    # found, i.e. 'no-apply-button') is, in practice, an Easy-Apply-only or
    # agency-repost posting with no external ATS to drive. Route it to the
    # Manual Apply sheet tagged 'LinkedIn Easy-Apply' rather than leaving it in
    # status limbo. (This was the leak that required a manual bulk-tag pass.)
    tried = ",".join(tactics_tried)
    reason_txt = "; ".join(reasons)[:500]
    note = (
        f"LinkedIn Easy-Apply | apply manually on LinkedIn (no external ATS) | "
        f"LINKEDIN-AUTHED {stamp}: UNRESOLVED | tried: {tried} | "
        f"reasons: {reason_txt}"
    )
    con.execute(
        "UPDATE roles SET status='manual-apply', "
        "agent_notes=? WHERE id=?",
        (note, role_id),
    )


def write_backoff(
    con: sqlite3.Connection, role_id: int, stamp: str,
) -> None:
    note = f"LINKEDIN-AUTHED {stamp}: BACKOFF-RATE-LIMITED"
    con.execute(
        "UPDATE roles SET agent_notes=? WHERE id=?",
        (note, role_id),
    )


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_db(db_path: Path) -> Path:
    if not db_path.exists():
        return db_path
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = db_path.with_name(db_path.name + f".bak.{stamp}-linkedin-authed-resolver")
    shutil.copy2(db_path, dst)
    return dst


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _build_default_driver(profile: str) -> BrowserDriver:
    # JOBSEARCH_CDP lets us point the resolver at a RESIDENTIAL-PROXIED Chrome
    # (relay -> RESIDENTIAL_PROXY) instead of the default bare-VM-IP browser on
    # 18800. Required because LinkedIn force-deletes li_at on any authed request
    # from this Azure datacenter IP (2026-06-02 finding); residential egress is
    # the actual unblock. DevTools binds IPv6, so use http://[::1]:<port>.
    cdp = os.environ.get("JOBSEARCH_CDP", "").strip()
    if cdp:
        return OpenClawBrowserDriver(profile=profile, cdp_url=cdp)
    return OpenClawBrowserDriver(profile=profile)


def main(
    argv: Optional[Iterable[str]] = None,
    driver_factory: Optional[Callable[[str], BrowserDriver]] = None,
) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-seconds", type=int, default=DEFAULT_MAX_SECONDS)
    ap.add_argument("--per-row-seconds", type=int, default=DEFAULT_PER_ROW_SECONDS)
    ap.add_argument("--role-id", type=int, default=0)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    write_mode = args.apply and not args.dry_run
    log = (lambda *a, **k: None) if args.quiet else print

    try:
        con = sqlite3.connect(args.db)
    except Exception as e:
        print(f"[linkedin-authed] FATAL: can't open DB {args.db}: {e}", file=sys.stderr)
        return 1

    # Targets
    if args.role_id:
        row = fetch_single(con, args.role_id)
        targets = [row] if row else []
    else:
        targets = fetch_targets(con, args.limit or 0)

    log(f"[linkedin-authed] db={args.db} mode={'APPLY' if write_mode else 'DRY-RUN'} "
        f"profile={args.profile} targets={len(targets)} per_row={args.per_row_seconds}s "
        f"max_run={args.max_seconds}s", flush=True)

    if not targets:
        print(json.dumps({"mode": "apply" if write_mode else "dry-run",
                          "attempted": 0, "resolved": 0, "easy_apply": 0,
                          "unresolved": 0, "errored": 0, "by_ats": {}}, indent=2))
        return 0

    # Backup before any writes
    if write_mode:
        bak = backup_db(Path(args.db))
        log(f"[linkedin-authed] backup: {bak.name}", flush=True)

    # Build the driver (real or injected for tests)
    factory = driver_factory or _build_default_driver
    driver = factory(args.profile)

    yaml_cos = lp.load_companies_yaml()
    roles_idx = lp.load_latest_roles_json()

    stamp = _stamp()
    start = time.time()
    resolved = easy_apply = unresolved = errored = backoff = 0
    by_ats: dict[str, int] = {}
    sample_rows: list[dict] = []

    for i, row in enumerate(targets, 1):
        if time.time() - start > args.max_seconds:
            log(f"[linkedin-authed] run-budget exhausted at row {i-1}/{len(targets)}", flush=True)
            break
        rid, company, role_title, app_url, est_tc = row
        log(f"[linkedin-authed] row {i}/{len(targets)} id={rid} tc={est_tc} {company} :: {role_title[:60]}", flush=True)
        try:
            result = resolve_one_row(
                driver, row, yaml_cos, roles_idx,
                per_row_seconds=args.per_row_seconds,
            )
        except Exception as e:
            result = {"ok": False, "kind": "error", "ats_url": None,
                      "tactic": None, "reasons": [f"exc:{type(e).__name__}:{e}"],
                      "elapsed": 0.0}

        kind = result.get("kind")
        if kind == "resolved":
            ats_url = result["ats_url"]
            sk = lp.derive_source_key(ats_url)
            ats = sk.split(":", 1)[0]
            by_ats[ats] = by_ats.get(ats, 0) + 1
            resolved += 1
            sample_rows.append({"id": rid, "company": company, "role": role_title,
                                "ats": ats, "url": ats_url, "tactic": result.get("tactic")})
            if write_mode:
                write_resolved(con, rid, ats_url, sk, result.get("tactic") or "?", app_url, stamp)
        elif kind == "easy-apply":
            easy_apply += 1
            if write_mode:
                write_easy_apply(con, rid, stamp)
        elif kind == "backoff":
            backoff += 1
            if write_mode:
                write_backoff(con, rid, stamp)
        elif kind == "unresolved":
            unresolved += 1
            if write_mode:
                write_unresolved(
                    con, rid,
                    result.get("tactics_tried") or [],
                    result.get("reasons") or [], stamp,
                )
        else:
            errored += 1
            if write_mode:
                write_unresolved(
                    con, rid,
                    result.get("tactics_tried") or ["error"],
                    result.get("reasons") or ["unknown-error"], stamp,
                )

        log(f"  -> {kind} (elapsed={result.get('elapsed',0):.1f}s)"
            + (f" {result.get('ats_url')}" if kind == "resolved" else ""), flush=True)

        if write_mode and i % 10 == 0:
            con.commit()

    if write_mode:
        con.commit()
    con.close()
    try:
        if hasattr(driver, "shutdown"):
            driver.shutdown()
    except Exception:
        pass

    summary = {
        "mode": "apply" if write_mode else "dry-run",
        "profile": args.profile,
        "attempted": resolved + easy_apply + unresolved + errored + backoff,
        "resolved": resolved,
        "easy_apply": easy_apply,
        "unresolved": unresolved,
        "errored": errored,
        "backoff": backoff,
        "by_ats": by_ats,
        "elapsed_sec": int(time.time() - start),
        "sample_resolved": sample_rows[:5],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
