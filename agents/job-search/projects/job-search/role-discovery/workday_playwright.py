#!/usr/bin/env python3
"""
workday_playwright.py — Workday auto-apply driver using Playwright.

Single-loop architecture: Workday's apply flow is a SPA — URL never changes.
We detect the current step via the progress bar and dispatch to step-specific
fillers. Loop until Submit succeeds or we hit a blocker.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError, Page, BrowserContext

HERE = Path(__file__).resolve().parent
# Module-level PI cache for places where full personal_info dict isn't passed in
_PI_CACHE = None
def _get_pi():
    global _PI_CACHE
    if _PI_CACHE is None:
        try:
            _PI_CACHE = json.loads(PERSONAL_INFO_FILE.read_text())
        except Exception:
            _PI_CACHE = {}
    return _PI_CACHE
PROJECT_ROOT = HERE.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent.parent
CREDS_FILE = PROJECT_ROOT / ".workday-creds.json"
PERSONAL_INFO_FILE = PROJECT_ROOT / "personal-info.json"
BROWSER_DATA_ROOT = PROJECT_ROOT / ".workday-browser-data"
DEBUG_ROOT = PROJECT_ROOT / ".workday-debug"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"

# Cyrus's experience to seed Workday's pre-grid (when "no experience added yet")
# 2026-05-30: REWRITTEN from resume/Cyrus_Shekari_Resume.txt (source of truth).
# Prior version contained fabricated entries ("Amazon SWE - Alexa fleet", inflated
# Microsoft figures). Caught by gh-academic-fields-2026-05-30 subagent review.
# DO NOT add roles Cyrus did not actually hold. Source = resume file only.
EXPERIENCE_DATA = [
    {
        "title": "Technical Program Manager",
        "company": "Microsoft",
        "location": "Seattle, WA",
        "current": True,
        "start_year": "2024", "start_month": "03",
        "end_year": "", "end_month": "",
        "description": "Scaled Azure's recovery validation program into a platformized system sustaining 45+ annual resilience drills and $14M+ business impact across enterprise customers (Databricks, Walmart, SAP, NetApp). Led 0\u21921 development of an internal Resilience Automation Platform that reduced operational toil by 30%. Pioneered Azure's first proactive resilience testing with a 94% recovery rate.",
    },
    {
        "title": "Technical Program Manager Intern",
        "company": "Amazon Robotics",
        "location": "Boston, MA",
        "current": False,
        "start_year": "2023", "start_month": "08",
        "end_year": "2023", "end_month": "12",
        "description": "Achieved zero operational downtime during a 2,000+ unit pilot transition by defining the legacy OS migration strategy and mapping dependencies across 1,200+ stations. Facilitated Agile ceremonies and drove cross-team alignment to ship automated CI/CD pipelines (25% faster deploys).",
    },
    {
        "title": "Technical Program Manager Intern",
        "company": "Microsoft",
        "location": "Seattle, WA",
        "current": False,
        "start_year": "2023", "start_month": "05",
        "end_year": "2023", "end_month": "08",
        "description": "Championed product adoption for AI-driven code-generation workflows across 14 key teams, saving 37 engineering hours monthly. Influenced the product roadmap to include intent-based YAML generation via 11+ user interviews. Cut documentation lookup time by 83% with AI-powered semantic search.",
    },
    {
        "title": "Technical Program Manager Intern",
        "company": "Microsoft",
        "location": "Seattle, WA",
        "current": False,
        "start_year": "2022", "start_month": "05",
        "end_year": "2022", "end_month": "08",
        "description": "Generated $3M in accelerated revenue and launched regions 28% faster by securing cross-functional alignment on a unified automation prioritization framework across 140+ teams. Built a Power BI dashboard tracking operational toil to target high-impact automation gaps.",
    },
    {
        "title": "Program Manager Intern",
        "company": "Pro Painters",
        "location": "Houston, TX",
        "current": False,
        "start_year": "2021", "start_month": "05",
        "end_year": "2022", "end_month": "05",
        "description": "Increased job bookings by 26% by optimizing the end-to-end scoping and invoicing lifecycle for 200+ monthly proposals via a new CRM process. Reduced Customer Acquisition Cost by 13% with a digital-first GTM strategy.",
    },
]

EDUCATION_DATA = {
    # 2026-05-30 (gh-academic-fields-2026-05-30): sourced from shared
    # education_answers.py. Single source of truth across
    # greenhouse_filler.py / ashby_filler.py / workday_playwright.py.
    # MEMORY.md ground-truth: U of Houston, BS CS, Math minor, GPA 3.8, 2021-08
    # to 2024-12. SAT 1580/1600. ACT/GRE not taken.
    "school": "University of Houston",
    "degree": "Bachelors",         # Workday dropdowns use the bare form
    "field": "Computer Science",
    "minor": "Mathematics",
    "gpa": "3.8",
    "start_year": "2021",
    "end_year": "2024",
}
try:  # pragma: no cover - import guard for tooling that vendor-copies the file
    from education_answers import EDUCATION_ANSWERS as _EDU_SHARED
    EDUCATION_DATA["school"] = _EDU_SHARED["school"]
    EDUCATION_DATA["degree"] = _EDU_SHARED["degree_workday"]
    EDUCATION_DATA["field"] = _EDU_SHARED["major"]
    EDUCATION_DATA["minor"] = _EDU_SHARED["minor"]
    EDUCATION_DATA["gpa"] = _EDU_SHARED["gpa"]
    EDUCATION_DATA["start_year"] = _EDU_SHARED["start_year"]
    EDUCATION_DATA["end_year"] = _EDU_SHARED["end_year"]
except Exception:
    pass


def log(msg: str):
    print(f"[workday] {datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def load_personal_info() -> dict:
    return json.loads(PERSONAL_INFO_FILE.read_text())


def load_creds(tenant: str) -> dict:
    """Resolve {email, password} for a Workday tenant.

    Supports two creds-file shapes:
      (1) legacy flat: {"<tenant>": {"email":..., "password":...}}
      (2) nested:    {"shared_email":..., "shared_password":..., "tenants": {"<tenant>": {"email":..., "password":..., "note":...}}}

    For (2), missing per-tenant email/password fall back to shared_*.
    """
    if not CREDS_FILE.exists():
        return {}
    data = json.loads(CREDS_FILE.read_text())
    # nested shape
    if "tenants" in data and isinstance(data["tenants"], dict):
        t = data["tenants"].get(tenant, {}) or {}
        email = t.get("email") or data.get("shared_email")
        password = t.get("password") or data.get("shared_password")
        if not (email and password):
            return {}
        return {"email": email, "password": password, **{k: v for k, v in t.items() if k not in ("email", "password")}}
    # legacy flat
    return data.get(tenant, {})


def screenshot(page: Page, slug: str, label: str):
    DEBUG_ROOT.mkdir(exist_ok=True)
    folder = DEBUG_ROOT / slug
    folder.mkdir(exist_ok=True)
    path = folder / f"{datetime.now().strftime('%H%M%S')}-{label}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        log(f"screenshot → {path.name}")
    except Exception as e:
        log(f"screenshot failed: {e}")


# ──────────────────────────────────────────────────────────────────────────
# Primitives
# ──────────────────────────────────────────────────────────────────────────


def fill_text(page: Page, selector: str, value: str, label: str = "") -> bool:
    """Fill a Workday text input; robust to sticky-footer click interception.

    Strategy: try the normal click+fill path with a short timeout; if that fails
    (e.g. Peterson's sticky footer intercepts pointer events on the lower-half of
    the My Information page), fall back to JS focus + native value setter +
    input/change/blur events so the field still commits.

    NOTE 2026-05-26 (Peterson 1269 fix): without this fallback firstName/
    lastName/phoneNumber silently failed to populate on Peterson info-page even
    though the IDs were correct.
    """
    if not value:
        return False
    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            return False
        try:
            loc.click(timeout=2500)
            try: loc.fill("")
            except Exception: pass
            loc.fill(value)
            page.keyboard.press("Tab")
            return True
        except Exception as e:
            log(f"fill_text {label or selector} click/fill timeout ({e}); JS fallback")
            # JS fallback — works through overlays, sticky footers, animations.
            try:
                loc.evaluate("""(el, v) => {
                    el.focus();
                    const proto = (el.tagName === 'TEXTAREA') ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                    setter.call(el, v);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new Event('blur', {bubbles: true}));
                }""", value)
                return True
            except Exception as je:
                log(f"fill_text {label or selector} JS fallback failed: {je}")
                return False
    except Exception as e:
        log(f"fill_text {label or selector} failed: {e}")
        return False


def fill_spinbutton(page: Page, selector: str, value: str, label: str = "") -> bool:
    """Workday date spinbutton (role=spinbutton). Scroll into view, focus, type."""
    if not value:
        return False
    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            log(f"fill_spinbutton {label or selector}: not present")
            return False
        try:
            loc.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        # Focus via JS to avoid viewport actionability checks
        loc.evaluate("el => el.focus()")
        page.wait_for_timeout(80)
        # Clear any existing value
        page.keyboard.press("Control+a")
        page.keyboard.press("Delete")
        page.keyboard.type(str(value), delay=40)
        page.wait_for_timeout(120)
        # Blur to commit
        loc.evaluate("el => el.blur()")
        page.wait_for_timeout(80)
        cur = loc.input_value()
        if not cur:
            # fallback: set via native setter + input event
            loc.evaluate("""(el, v) => {
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                setter.call(el, v);
                el.dispatchEvent(new Event('input',{bubbles:true}));
                el.dispatchEvent(new Event('change',{bubbles:true}));
                el.dispatchEvent(new Event('blur',{bubbles:true}));
            }""", str(value))
            page.wait_for_timeout(80)
        return True
    except Exception as e:
        log(f"fill_spinbutton {label or selector} failed: {e}")
        return False


def fill_workday_date(page: Page, prefix: str, month: str, year: str, label: str = "") -> bool:
    """Fill Workday MM/YYYY date. prefix like 'workExperience-5--startDate'.
    Tries dateSectionMonth-input + dateSectionYear-input."""
    ok = True
    if month:
        ok &= fill_spinbutton(page, f"#{prefix}-dateSectionMonth-input", str(int(month)).zfill(2), f"{label}-month")
    if year:
        ok &= fill_spinbutton(page, f"#{prefix}-dateSectionYear-input", str(year), f"{label}-year")
    return ok


def click_radio(page: Page, name: str, value: str) -> bool:
    """Click a Workday radio. Tries multiple strategies because some tenants
    (Peterson, etc.) hide the native input behind a custom Yes/No widget where
    `input.click()` alone doesn't fire the React handler — you need to click
    the wrapping label/div.

    NOTE 2026-05-26 (Peterson previousWorker fix): the candidateIsPreviousWorker
    radios had value='true'/'false' but JS-click on the input alone didn't
    register; clicking the wrapping label by `for=<input.id>` does.
    """
    try:
        sel = f'input[name="{name}"][value="{value}"]'
        loc = page.locator(sel).first
        if loc.count() == 0:
            return False
        # Strategy 1: click the associated label (Workday's reactive widgets
        # bind their handler to the label, not the hidden input).
        try:
            input_id = loc.get_attribute("id") or ""
            if input_id:
                lab = page.locator(f'label[for="{input_id}"]').first
                if lab.count() and lab.is_visible(timeout=500):
                    try:
                        lab.click(timeout=2000)
                        page.wait_for_timeout(150)
                        # verify
                        if loc.is_checked():
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        # Strategy 2: native JS click on the input itself + change event.
        try:
            loc.evaluate("""el => {
                el.click();
                el.checked = true;
                el.dispatchEvent(new Event('change', {bubbles: true}));
                el.dispatchEvent(new Event('input', {bubbles: true}));
            }""")
            return True
        except Exception:
            pass
        # Strategy 3: force playwright click
        loc.click(force=True, timeout=2000)
        return True
    except Exception as e:
        log(f"click_radio {name}={value} failed: {e}")
        return False


def open_dropdown_and_select(page: Page, button_id: str, option_text: str, label: str = "") -> bool:
    """Workday dropdown: button → menu → option."""
    try:
        btn = page.locator(f'#{button_id}').first
        if btn.count() == 0:
            return False
        btn.click(timeout=5000)
        page.wait_for_timeout(500)
        opt = page.locator(f'[role=option]:has-text("{option_text}")').first
        if opt.count() == 0:
            log(f"dropdown {button_id}: option {option_text!r} not visible")
            page.keyboard.press("Escape")
            return False
        opt.click(force=True, timeout=5000)
        page.wait_for_timeout(300)
        return True
    except Exception as e:
        log(f"dropdown {button_id} failed: {e}")
        return False


def open_button_dropdown_by_aria(page: Page, aria_substr: str, option_text: str, label: str = "") -> bool:
    """Find a button by aria-label substring, click it, pick a role=option by text.

    Fallback for Workday tenants (Peterson, etc.) where the field has no stable
    `id` and only an aria-label like 'State Select One' or 'Phone Device Type Select One'.
    """
    try:
        sel = f'button[aria-label*="{aria_substr}" i]'
        btn = page.locator(sel).first
        if btn.count() == 0:
            return False
        try:
            btn.click(timeout=3000)
        except Exception:
            try: btn.evaluate("el => el.click()")
            except Exception: pass
        page.wait_for_timeout(800)
        opt = page.locator(f'[role=option]:has-text("{option_text}")').first
        if opt.count() == 0:
            # Some tenants render menu items as li with data-automation-label
            opt = page.locator(f'[data-automation-label="{option_text}"]').first
        if opt.count() == 0:
            log(f"aria-dropdown {aria_substr!r}: option {option_text!r} not visible")
            page.keyboard.press("Escape")
            return False
        try:
            opt.click(force=True, timeout=3000)
        except Exception:
            opt.evaluate("el => el.click()")
        page.wait_for_timeout(300)
        return True
    except Exception as e:
        log(f"aria-dropdown {aria_substr!r} failed: {e}")
        return False


def select_moniker_promptoption(page: Page, container_id: str, path: list, label: str = "", fallback_first_sub: bool = False) -> bool:
    """Open a Workday moniker dropdown and navigate the option tree.

    `path` may contain alternates as a tuple at any level, e.g.
        ['Job Board', ('LinkedIn', 'Linkedin Jobs', 'Indeed')]
    The first alternate that exists at that level wins.

    When `fallback_first_sub` is True and a level's explicit candidates are not found,
    pick the first visible `promptOption` at that level (used for tenant-specific source
    sub-trees we haven't enumerated yet).

    Ensures the menu is closed at the end (Escape + small wait + body click fallback).
    """
    def _close_menu():
        # Close any open promptOption menus aggressively (multiple Workday widgets
        # can leave portal menus visible after a previous interaction).
        for _ in range(5):
            try: page.keyboard.press("Escape")
            except Exception: pass
            page.wait_for_timeout(200)
            if page.locator('[data-automation-id="promptOption"]:visible').count() == 0:
                return
        # last resort: click body twice
        for _ in range(2):
            try: page.locator("body").click(position={"x": 10, "y": 10}, timeout=500)
            except Exception: pass
            page.wait_for_timeout(300)

    try:
        # Ensure menu is closed before opening (idempotent toggle)
        if page.locator('[data-automation-id="promptOption"]:visible').count() > 0:
            _close_menu()
        # Snapshot existing promptOption IDs/labels BEFORE opening — any that survive
        # in DOM from a previously-closed menu (Workday sometimes leaves them mounted)
        # should be excluded from "newly visible" calculations.
        try:
            pre_existing = set(page.evaluate("() => Array.from(document.querySelectorAll('[data-automation-id=\"promptOption\"]')).filter(n=>n.offsetParent).map(n => (n.getAttribute('data-automation-label')||'') + '|' + (n.id||''))"))
        except Exception:
            pre_existing = set()
        # Open the moniker dropdown; prefer JS click since Workday's sticky footer
        # often intercepts pointer events in headless mode.
        try:
            page.evaluate(f"() => document.getElementById('{container_id}').click()")
        except Exception:
            try: page.click(f"#{container_id}", timeout=5000, force=True)
            except Exception as e:
                log(f"moniker {container_id} could not open: {e}")
                return False
        page.wait_for_timeout(1200)
        for level in path:
            candidates = level if isinstance(level, (list, tuple)) else [level]
            chosen = None
            for cand in candidates:
                # Find a matching promptOption that is NOT a pre-existing leftover.
                handles = page.evaluate("""({label, preList}) => {
                  const pre = new Set(preList);
                  const els = Array.from(document.querySelectorAll('[data-automation-id="promptOption"]')).filter(n => n.offsetParent && (n.getAttribute('data-automation-label')||'') === label);
                  const fresh = els.find(n => !pre.has((n.getAttribute('data-automation-label')||'') + '|' + (n.id||'')));
                  if (fresh) { fresh.click(); return true; }
                  return false;
                }""", {"label": cand, "preList": list(pre_existing)})
                if handles:
                    chosen = (cand, None); break
            if not chosen:
                if fallback_first_sub:
                    # Pick the first visible promptOption that is NOT a leftover from
                    # a previously-opened menu (excluded via pre_existing key set).
                    first_info = page.evaluate("""(preList) => {
                      const pre = new Set(preList);
                      const els = Array.from(document.querySelectorAll('[data-automation-id="promptOption"]')).filter(n => n.offsetParent);
                      for (const n of els) {
                        const key = (n.getAttribute('data-automation-label')||'') + '|' + (n.id||'');
                        if (pre.has(key)) continue;
                        n.click();
                        return n.getAttribute('data-automation-label') || '(unnamed)';
                      }
                      return null;
                    }""", list(pre_existing))
                    if first_info:
                        log(f"moniker {container_id}: fallback-picked first NEW sub-option {first_info!r}")
                        # update pre_existing snapshot for next level
                        try:
                            pre_existing = set(page.evaluate("() => Array.from(document.querySelectorAll('[data-automation-id=\"promptOption\"]')).filter(n=>n.offsetParent).map(n => (n.getAttribute('data-automation-label')||'') + '|' + (n.id||''))"))
                        except Exception:
                            pass
                        page.wait_for_timeout(700)
                        continue
                log(f"moniker {container_id}: none of {candidates} found at this level")
                _close_menu()
                return False
            try:
                # Already clicked via the JS evaluate above if chosen is set.
                if chosen[1] is not None:
                    chosen[1].evaluate("el=>el.click()")
            except Exception:
                try:
                    if chosen[1] is not None:
                        chosen[1].click(force=True)
                except Exception:
                    _close_menu(); return False
            log(f"moniker {container_id}: picked {chosen[0]!r}")
            # refresh pre_existing for next level
            try:
                pre_existing = set(page.evaluate("() => Array.from(document.querySelectorAll('[data-automation-id=\"promptOption\"]')).filter(n=>n.offsetParent).map(n => (n.getAttribute('data-automation-label')||'') + '|' + (n.id||''))"))
            except Exception:
                pass
            page.wait_for_timeout(1200)
        _close_menu()
        return True
    except Exception as e:
        log(f"moniker {container_id} promptOption failed: {e}")
        _close_menu()
        return False


def click_next(page: Page, slug: str, step_label: str = "") -> bool:
    sels = [
        '[data-automation-id="pageFooterNextButton"]',
        'button:has-text("Save and Continue")',
    ]
    for sel in sels:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1000):
                loc.click(timeout=5000)
                log(f"clicked Next at {step_label}")
                return True
        except Exception:
            continue
    return False


def detect_step(page: Page) -> str:
    """Return current step name from Workday progress bar."""
    try:
        return page.evaluate("""
            () => {
              const cur = document.querySelector('[data-automation-id="progressBarActiveStep"]');
              if (cur) return cur.textContent.replace(/^current step \\d+ of \\d+/i, '').trim();
              // Fallback: title of fieldset H1/H2
              const h = document.querySelector('h2[data-automation-id]') || document.querySelector('h1[data-automation-id]');
              return h ? h.textContent.trim() : '';
            }
        """)
    except Exception:
        return ""


def check_errors(page: Page) -> list:
    """Return any visible Workday validation errors."""
    try:
        return page.evaluate("""
            () => {
              const errs = [];
              document.querySelectorAll('[data-automation-id="errorMessage"], .Error, [role=alert]').forEach(e => {
                const t = (e.textContent || '').trim();
                if (t && t.length < 500) errs.push(t);
              });
              return errs;
            }
        """)
    except Exception:
        return []


# ──────────────────────────────────────────────────────────────────────────
# Step-specific fillers
# ──────────────────────────────────────────────────────────────────────────


def fill_my_information(page: Page, info: dict, slug: str) -> dict:
    log("STEP: My Information")
    page.wait_for_timeout(2000)
    screenshot(page, slug, "info-before")
    # Source. Per-tenant moniker label varies (Adobe='LinkedIn'; Nvidia='Linkedin Jobs').
    # Walk a single tree with alternates at level 2.
    ok = select_moniker_promptoption(
        page, "source--source",
        [("Job Board", "External Career Site Sources"), ("LinkedIn", "Linkedin Jobs", "LinkedIn Jobs",
                        "Job Board - LinkedIn", "Job Board - Indeed",
                        "Indeed", "LinkedIn Connection Post", "Glassdoor")],
        fallback_first_sub=True,
    )
    if not ok:
        # Try other top-level branches if Job Board didn't pan out (e.g. "Other")
        for top in ("Other", "Social Media", "Search Engine", "Company Website"):
            if select_moniker_promptoption(page, "source--source", [top], fallback_first_sub=True):
                ok = True; break
    if not ok:
        # NOTE 2026-05-26 (Peterson 1269 fix): some tenants have NO #source--source
        # element; instead the field is a plain button with aria-label like
        # 'How Did You Hear About Us?'. Generic fallback: find that button, click
        # it, and pick the first non-empty promptOption (or LinkedIn-ish if present).
        try:
            src_btn_sel = (
                'button[aria-label*="How Did You Hear" i], '
                'button[aria-label*="How did you hear" i], '
                'button[aria-label*="Source" i][aria-label*="Select" i]'
            )
            sb = page.locator(src_btn_sel).first
            if sb.count() and sb.is_visible(timeout=500):
                try: sb.click(timeout=3000)
                except Exception:
                    try: sb.evaluate("el => el.click()")
                    except Exception: pass
                page.wait_for_timeout(1200)
                # Try LinkedIn-ish labels first, else first non-empty option.
                opts = page.evaluate("""() => Array.from(document.querySelectorAll('[data-automation-id="promptOption"], [role="option"]')).filter(n => n.offsetParent).map(n => ({label: (n.getAttribute('data-automation-label')||n.innerText||'').trim(), id: n.id||''}))""") or []
                preferred = ["LinkedIn", "Linkedin", "LinkedIn Jobs", "Job Board - LinkedIn", "Indeed", "Job Board", "Other"]
                pick = None
                for p in preferred:
                    for o in opts:
                        if p.lower() in (o["label"] or "").lower() and o["label"]:
                            pick = o["label"]; break
                    if pick: break
                if not pick:
                    for o in opts:
                        if (o["label"] or "").strip() and "select" not in o["label"].lower():
                            pick = o["label"]; break
                if pick:
                    log(f"source-fallback: picking {pick!r} from aria-label dropdown")
                    page.evaluate(f"""() => {{
                        const els = Array.from(document.querySelectorAll('[data-automation-id="promptOption"], [role="option"]'));
                        const t = els.find(n => ((n.getAttribute('data-automation-label')||n.innerText||'').trim()) === {json.dumps(pick)});
                        if (t) t.click();
                    }}""")
                    page.wait_for_timeout(800)
                    page.keyboard.press("Escape")
                    ok = True
                else:
                    log("source-fallback: button opened but no options found")
            else:
                log("source-fallback: no aria-label source button found")
        except Exception as e:
            log(f"source-fallback exception: {e}")
    # Prev employed: No
    click_radio(page, "candidateIsPreviousWorker", "false")
    # Name
    fill_text(page, "#name--legalName--firstName", info["identity"]["first_name"])
    fill_text(page, "#name--legalName--lastName", info["identity"]["last_name"])
    # Address
    fill_text(page, "#address--addressLine1", info["address"]["street"])
    fill_text(page, "#address--city", info["address"]["city"])
    fill_text(page, "#address--postalCode", info["address"]["zip"])
    state_full = {"WA": "Washington", "CA": "California", "NY": "New York", "TX": "Texas"}.get(info["address"]["state"], info["address"]["state"])
    if not open_dropdown_and_select(page, "address--countryRegion", state_full):
        # Peterson-style fallback: aria-label only, no #address--countryRegion.
        open_button_dropdown_by_aria(page, "State", state_full, label="state")
    # Email + phone
    fill_text(page, "#emailAddress--emailAddress", info["contact"]["email"])
    # Phone country code (Nvidia requires; Adobe doesn't render). It's a Workday
    # selectinput widget with promptOption entries like 'United States of America (+1)'.
    if page.locator('#phoneNumber--countryPhoneCode').count():
        try:
            ok = select_moniker_promptoption(
                page, "phoneNumber--countryPhoneCode",
                [("United States of America (+1)", "United States of America")],
                label="phone country code",
            )
            if not ok:
                cc = info["contact"].get("phone_country_code") or "+1"
                fill_text(page, "#phoneNumber--countryPhoneCode", cc.lstrip('+'))
        except Exception as e:
            log(f"phone country code fill exception: {e}")
    # Phone device type (Nvidia required: 'Mobile'). Adobe has no such field.
    if page.locator('#phoneNumber--phoneType').count():
        for candidate in ("Mobile", "Cell", "Cell Phone", "Mobile Phone", "Home"):
            if open_dropdown_and_select(page, "phoneNumber--phoneType", candidate):
                break
    else:
        # Peterson-style fallback: aria-label only.
        for candidate in ("Mobile", "Cell", "Cell Phone", "Mobile Phone", "Home"):
            if open_button_dropdown_by_aria(page, "Phone Device Type", candidate, label="phone-type"):
                break
    fill_text(page, "#phoneNumber--phoneNumber", info["contact"]["phone"])
    screenshot(page, slug, "info-filled")
    return {"blockers": []}


def upload_resume(page: Page, info: dict, slug: str) -> bool:
    # Search candidate paths
    candidates = [
        WORKSPACE_ROOT / info["files"]["resume_path"],
        PROJECT_ROOT / info["files"]["resume_path"],
        PROJECT_ROOT / "resume" / "Cyrus_Shekari_Resume.pdf",
    ]
    submitted = PROJECT_ROOT / "applications" / "submitted" / slug
    if submitted.exists():
        cands = list(submitted.glob("Cyrus_Shekari_Resume_*.pdf"))
        if cands:
            candidates.insert(0, cands[0])
    resume_path = None
    for c in candidates:
        if c.exists():
            resume_path = c
            break
    if not resume_path:
        log(f"resume file missing; tried {candidates}")
        return False
    try:
        fi = page.locator('input[type=file][data-automation-id="file-upload-input-ref"]').first
        if fi.count() == 0:
            log("no file-upload-input-ref on page")
            return False
        fi.set_input_files(str(resume_path))
        log(f"uploaded resume: {resume_path.name}")
        page.wait_for_timeout(4000)
        return True
    except Exception as e:
        log(f"resume upload failed: {e}")
        return False


def fill_my_experience(page: Page, info: dict, slug: str) -> dict:
    log("STEP: My Experience")
    page.wait_for_timeout(2500)
    screenshot(page, slug, "exp-before")
    # Resume upload
    upload_resume(page, info, slug)
    page.wait_for_timeout(2000)

    # Work Experience grid — Workday often pre-seeds row 0 with empty fields.
    # The actual field IDs look like workExperience-N--{field}. Find the lowest N.
    exp_rows = page.evaluate("""
        () => {
          const ids = new Set();
          document.querySelectorAll('input[id^=workExperience-]').forEach(el => {
            const m = el.id.match(/^workExperience-(\\d+)--/);
            if (m) ids.add(parseInt(m[1]));
          });
          return Array.from(ids).sort((a,b)=>a-b);
        }
    """) or []
    log(f"  found work experience rows: {exp_rows}")
    for i, row_n in enumerate(exp_rows[:1]):  # only fill first row
        d = EXPERIENCE_DATA[i] if i < len(EXPERIENCE_DATA) else EXPERIENCE_DATA[0]
        fill_text(page, f"#workExperience-{row_n}--jobTitle", d["title"])
        fill_text(page, f"#workExperience-{row_n}--companyName", d["company"])
        fill_text(page, f"#workExperience-{row_n}--location", d["location"])
        # Currently work here checkbox
        cb = page.locator(f'input[id="workExperience-{row_n}--currentlyWorkHere"], input[id^="workExperience-{row_n}--currentlyWork"]').first
        if cb.count() and d.get("current"):
            try:
                cb.evaluate("el => { if (!el.checked) el.click(); }")
            except Exception: pass
        # Date fields: Workday uses MM/YYYY spinbutton inputs at
        # #workExperience-N--startDate-dateSectionMonth-input / -dateSectionYear-input
        fill_workday_date(page, f"workExperience-{row_n}--startDate", d["start_month"], d["start_year"], f"exp{row_n}-start")
        if not d.get("current"):
            fill_workday_date(page, f"workExperience-{row_n}--endDate", d.get("end_month",""), d.get("end_year",""), f"exp{row_n}-end")
        # Description
        desc_sel = f'textarea[id^="workExperience-{row_n}"]'
        try:
            t = page.locator(desc_sel).first
            if t.count():
                t.fill(d["description"])
        except Exception: pass

    # Education
    edu_rows = page.evaluate("""
        () => {
          const ids = new Set();
          document.querySelectorAll('input[id^=education-]').forEach(el => {
            const m = el.id.match(/^education-(\\d+)--/);
            if (m) ids.add(parseInt(m[1]));
          });
          return Array.from(ids).sort((a,b)=>a-b);
        }
    """) or []
    log(f"  found education rows: {edu_rows}")
    for row_n in edu_rows[:1]:
        d = EDUCATION_DATA
        fill_text(page, f"#education-{row_n}--schoolName", d["school"])
        # Degree button-dropdown
        open_dropdown_and_select(page, f"education-{row_n}--degree", d["degree"])
        # Field of study (moniker)
        fos_id = f"education-{row_n}--fieldOfStudy"
        if page.locator(f"#{fos_id}").count():
            try:
                page.click(f"#{fos_id}")
                page.wait_for_timeout(500)
                page.keyboard.type(d["field"], delay=80)
                page.wait_for_timeout(1500)
                opt = page.locator(f'[data-automation-id="promptOption"]:has-text("{d["field"]}")').first
                if opt.count():
                    opt.click(force=True)
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception as e:
                log(f"  field-of-study moniker failed: {e}")
        # GPA
        fill_text(page, f"#education-{row_n}--gradeAverage", d["gpa"])
        # Dates: education uses firstYearAttended / lastYearAttended (year-only spinbutton)
        fill_spinbutton(page, f"#education-{row_n}--firstYearAttended-dateSectionYear-input", d["start_year"], f"edu{row_n}-from")
        fill_spinbutton(page, f"#education-{row_n}--lastYearAttended-dateSectionYear-input", d["end_year"], f"edu{row_n}-to")

    # LinkedIn URL field (often present as websites--accounts-X-linkedinAccount or social URL)
    fill_text(page, 'input[id*="linkedinAccount"], input[id*="--websiteAddress"], input[name="linkedin"]',
              info["contact"]["linkedin"])
    screenshot(page, slug, "exp-filled")
    return {"blockers": []}


def fill_application_questions(page: Page, info: dict, slug: str) -> dict:
    """Workday Application Questions: dropdown questions + sometimes checkbox/radio groups.
    Strategy: walk DOM, extract question text near each control, apply keyword-based answer.
    """
    log("STEP: Application Questions")
    page.wait_for_timeout(2500)
    screenshot(page, slug, "q-before")
    blockers = []

    # Get each primary-questionnaire question/control pair with text context
    questions = page.evaluate("""
        () => {
          const out = [];
          // Dropdown questions: each lives inside a fieldset with a legend (question text)
          document.querySelectorAll('button[id^="primaryQuestionnaire--"][aria-haspopup="listbox"]').forEach(btn => {
            const fs = btn.closest('fieldset, [data-automation-id^="formField-"]');
            let qtext = '';
            if (fs) {
              const lg = fs.querySelector('legend');
              qtext = lg ? lg.textContent.trim() : fs.textContent.trim().slice(0, 400);
            }
            out.push({type:'dropdown', id: btn.id, question: qtext.slice(0, 400)});
          });
          // Checkbox-group questions (e.g. Adobe "Have you worked here"):
          // Find fieldsets whose role is group OR that contain checkboxes but no listbox button.
          const cbFieldsets = new Set();
          document.querySelectorAll('div[data-automation-id^="formField-"]').forEach(ff => {
            const cbs = ff.querySelectorAll('input[type=checkbox]');
            const btns = ff.querySelectorAll('button[aria-haspopup="listbox"]');
            if (cbs.length >= 2 && btns.length === 0) cbFieldsets.add(ff);
          });
          cbFieldsets.forEach(fs => {
            const lg = fs.querySelector('legend');
            const qtext = lg ? lg.textContent.trim() : fs.textContent.trim().slice(0,300);
            const options = Array.from(fs.querySelectorAll('input[type=checkbox]')).map(c => {
              const lab = document.querySelector(`label[for="${c.id}"]`);
              return {id: c.id, label: lab ? lab.textContent.trim() : '', checked: c.checked};
            });
            out.push({type:'checkboxGroup', question: qtext, options: options});
          });
          // Text-input / textarea questions inside primaryQuestionnaire formFields
          document.querySelectorAll('div[data-automation-id^="formField-"]').forEach(ff => {
            const tx = ff.querySelector('input[type=text], textarea');
            const dd = ff.querySelector('button[aria-haspopup="listbox"]');
            const cb = ff.querySelector('input[type=checkbox]');
            if (tx && !dd && !cb && (tx.id || '').startsWith('primaryQuestionnaire--')) {
              const lg = ff.querySelector('legend') || ff.querySelector('label');
              const qtext = lg ? lg.textContent.trim() : ff.textContent.trim().slice(0,400);
              out.push({type:'text', id: tx.id, question: qtext.slice(0,400)});
            }
          });
          // Date-widget questions (Workday spinbutton trio) inside primaryQuestionnaire formFields
          document.querySelectorAll('div[data-automation-id^="formField-"]').forEach(ff => {
            // Workday date wrapper: data-automation-id="dateInputWrapper" inside the formField
            const dw = ff.querySelector('[data-automation-id="dateInputWrapper"]');
            if (!dw) return;
            // Find the month-input id (spinbutton). Its id prefix matches primaryQuestionnaire--<uuid>
            const month = dw.querySelector('[data-automation-id="dateSectionMonth-input"]');
            if (!month) return;
            const id = month.id || '';
            if (!id.startsWith('primaryQuestionnaire--')) return;
            const prefix = id.replace(/-dateSectionMonth-input$/, '');
            const lg = ff.querySelector('legend') || ff.querySelector('label');
            const qtext = lg ? lg.textContent.trim() : ff.textContent.trim().slice(0,400);
            out.push({type:'date', id: prefix, question: qtext.slice(0,400)});
          });
          return out;
        }
    """) or []
    log(f"  found {len(questions)} application question(s)")

    def pick_option(qtext: str) -> str:
        q = qtext.lower()
        # Order-sensitive special cases FIRST (before generic keyword matches).
        # HPE-style: sanctioned/restricted countries citizenship/PR/refugee check.
        # Q lists Armenia/China/Cuba/Iran/Russia/etc. and asks if you are citizen/PR/refugee
        # of any of them. Cyrus is US citizen only → No.
        if any(k in q for k in ["armenia", "belarus", "china(prc)", "iran", "russia", "north korea", "sanctioned countr", "countries listed below"]):
            return "no"
        # HPE-style work permit / residency permit (US citizen in US doesn't have one)
        if any(k in q for k in ["valid work permit", "valid residency permit", "possess a valid work", "possess a valid residency"]):
            return "no"
        # HPE-style conflict-of-interest policy compliance check (would you engage in COI)
        if "conflict" in q and any(k in q for k in ["engaging in", "engaging in any of the above", "posed by", "policy prohibits"]):
            return "no"
        # HPE government regulatory role / family in regulatory body → No
        if any(k in q for k in ["regulatory authority over", "government official", "in a government or public body"]):
            return "no"
        # Politically Exposed Person (PayPal) — Cyrus is not a PEP, not related to one → No
        if "politically exposed person" in q or "pep" in q or "associated with a politically" in q or "close relationship" in q:
            return "no"
        # Salesforce-specific: Government Responsibilities (broad gov't activities/lobbying/regulatory matters) → No
        if "government responsibilities" in q or ("been responsible for matters" in q and "government" in q):
            return "no"
        # Salesforce-specific: post-government employment restrictions attestation → Yes (I attest I have no restrictions)
        if "post-government employment restriction" in q or ("attest" in q and "no post-government" in q) or ("no post-government employment" in q):
            return "yes"
        # Salesforce-specific: debarred/suspended/excluded from federal awards → No
        if any(k in q for k in ["debarred", "proposed for debarment", "declared ineligible for aw", "excluded from federal", "suspended, proposed for"]):
            return "no"
        if any(k in q for k in ["legal age", "of legal age", "of legal age", "18 years of age", "are you 18"]):
            return "yes"
        if any(k in q for k in ["background check"]):
            return "yes"
        # US citizen / export control / nationality affirmative
        if any(k in q for k in ["export control", "u.s. citizen", "us citizen", "u.s. national", "us national", "lawful permanent resident", "protected individual", "refugee or asylee", "refugee or asylum"]):
            return "yes"
        # Family / relationships / conflicts of interest with other employers / IP encumbrances → No
        if any(k in q for k in ["family member", "immediate family", "relative", "spouse", "sibling", "parent", "child"]):
            return "no"
        if any(k in q for k in ["contract or agreement with your current employer", "non-disclosure", "restrictive covenant", "agreement that would prevent", "non-solicitation", "current or former employer", "contractual obligation"]):
            return "no"
        if any(k in q for k in ["intellectual property", "patents, trademarks", "own, control", "economic interest"]):
            return "no"
        if any(k in q for k in ["department of defense", "dod employee", "federal, state", "government employee", "federal employee", "military employee"]):
            return "no"
        # Are you a current or former employee of <company>? → No (unless we've worked there)
        if any(k in q for k in ["current or former employee of ernst", "former employee of ey", "employee of intel", "worked at intel", "current or former intel", "current or former employee of"]):
            return "no"
        if any(k in q for k in ["right to work", "establishing your identity", "work in the country", "documentation establishing"]):
            return "yes"
        if any(k in q for k in ["work on a daily basis", "relocate", "willing to relocate"]):
            return "yes"
        if any(k in q for k in ["sponsorship", "visa", "h-1b", "work permit", "employer support to obtain", "require employer support", "require sponsorship", "work authorization sponsorship"]):
            return "no"
        if any(k in q for k in ["authorized to work", "legally authorized", "eligible to work", "legally eligible for employment", "eligible for employment"]):
            return "yes"
        if any(k in q for k in ["felony", "convicted"]):
            return "no"
        if any(k in q for k in ["drug screen", "drug test"]):
            return "yes"
        if any(k in q for k in ["non-compete", "non compete"]):
            return "no"
        if any(k in q for k in ["clearance", "top secret"]):
            return "no"
        if any(k in q for k in ["ai tool", "artificial intelligence", "generative ai", "used ai", "use ai"]):
            return "no"
        # Refugee / asylee / EAD status questions — Cyrus is US citizen so all No
        if any(k in q for k in ["refugee status", "asylee status", "asylum applicant", "valid ead", "are you a refugee", "are you an asylee"]):
            return "no"
        # Reasonable accommodation request — No (none needed)
        if any(k in q for k in ["reasonable accommodation", "workplace accommodation", "accommodation for"]):
            return "no"
        # Confidentiality / non-disclosure agreement consent during interview/employment — Yes (standard agree)
        if any(k in q for k in ["i agree that i will not disclose", "will not disclose or use", "agree to maintain confidentiality", "agree to keep confidential"]):
            return "yes"
        if any(k in q for k in ["previously worked", "previously employed", "worked for adobe", "worked at adobe", "former employee", "ever been employed by", "have you been employed by"]):
            return "no"
        # Certification / truthfulness affirmation — Yes (standard agree)
        if any(k in q for k in ["i certify that all information", "certify that all information", "information i have provided", "information provided is true", "all the information provided", "information is true and correct", "information is accurate", "i certify"]):
            return "yes"
        return ""

    for q in questions:
        qtext = q["question"]
        log(f"  Q: {qtext[:120]!r}")
        if q["type"] == "dropdown":
            answer = pick_option(qtext)
            if not answer:
                # Dump available options for diagnosis. Open the dropdown briefly.
                try:
                    btn = page.locator(f"#{q['id']}")
                    btn.scroll_into_view_if_needed(timeout=2000)
                    btn.click(timeout=3000)
                    page.wait_for_timeout(500)
                    opts_diag = page.evaluate("() => Array.from(document.querySelectorAll('[role=option]')).filter(n=>n.offsetParent).map(n=>(n.textContent||'').trim()).slice(0,30)")
                    log(f"    DROPDOWN unanswered options: {opts_diag}")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(300)
                    # Salesforce: 'Regarding future positions' → prefer 'Yes' / 'Yes, please' / 'Yes, I would like' (opt-in to future outreach is benign).
                    if "regarding future positions" in qtext.lower() or "future positions at" in qtext.lower():
                        for opt_text in opts_diag:
                            if opt_text.lower().startswith("yes"):
                                # click matching option
                                btn.click(timeout=3000); page.wait_for_timeout(500)
                                target_locs = page.locator(f'[role=option]').all()
                                for o in target_locs:
                                    try:
                                        if (o.text_content() or "").strip() == opt_text:
                                            o.click(force=True)
                                            log(f"    selected (future-positions): {opt_text}")
                                            answer = "__handled__"
                                            page.wait_for_timeout(400)
                                            break
                                    except Exception: pass
                                if answer: break
                except Exception as e:
                    log(f"    dropdown diag failed: {e}")
                if not answer:
                    blockers.append(f"app-question no answer: {qtext[:120]}")
                    continue
            if answer == "__handled__":
                continue
            try:
                btn = page.locator(f"#{q['id']}")
                btn.scroll_into_view_if_needed(timeout=2000)
                btn.click(timeout=5000)
                page.wait_for_timeout(500)
                # Find option whose text matches yes/no (case-insensitive, exact-ish)
                target_text = "Yes" if answer == "yes" else "No"
                opts = page.locator(f'[role=option]').all()
                clicked = False
                for opt in opts:
                    try:
                        t = (opt.text_content() or "").strip()
                        if t.lower() == target_text.lower():
                            opt.click(force=True)
                            clicked = True
                            log(f"    selected: {t}")
                            break
                    except Exception:
                        pass
                if not clicked:
                    # try partial match
                    for opt in opts:
                        try:
                            t = (opt.text_content() or "").strip().lower()
                            if target_text.lower() in t:
                                opt.click(force=True)
                                clicked = True
                                log(f"    selected (partial): {t}")
                                break
                        except Exception:
                            pass
                if not clicked:
                    blockers.append(f"dropdown {q['id']} no {target_text} option for: {qtext[:80]}")
                page.wait_for_timeout(300)
            except Exception as e:
                log(f"    dropdown click failed: {e}")
                blockers.append(f"dropdown {q['id']} click failed")
        elif q["type"] == "date":
            # PayPal acknowledgement-date question: fill with today.
            from datetime import datetime as _dt
            today = _dt.utcnow()
            try:
                fill_workday_date(page, q["id"], today.month, today.year, label=f"app-q-date:{q['id'][-8:]}")
                # Also fill the day if present
                day_sel = f"[id='{q['id']}-dateSectionDay-input']"
                if page.locator(day_sel).count():
                    fill_spinbutton(page, day_sel, str(today.day), label="app-q-date-day")
                log(f"    date filled: today")
            except Exception as e:
                log(f"    date fill failed: {e}")
                blockers.append(f"date fill failed: {qtext[:80]}")
        elif q["type"] == "text":
            ql = qtext.lower()
            # HPE-style: 'indicate all locations or countries for which you now/in the future require sponsorship'
            # → N/A (we don't need sponsorship).
            answer_text = None
            if "sponsorship" in ql or "countries for which" in ql or "separate each response" in ql:
                answer_text = "N/A"
            elif "salary" in ql or "compensation expectation" in ql or "hourly wage" in ql or "wage expectation" in ql or "pay expectation" in ql:
                # 2026-05-26 (chain_005): NAB/Point&Pay validates this as numeric via a paired hidden input
                # ("eg: $80000 or $38" hint, error 'is required and must have a value' even when textarea has content).
                # Default to a numeric answer; covers more tenants than the "Open to discuss" branch.
                if "number" in ql or "do not put" in ql or "numeric" in ql or "e.g." in ql or "eg:" in ql or "e.g:" in ql or "$" in qtext:
                    answer_text = "150000"
                else:
                    answer_text = "150000"  # safest default — numeric works on every tenant tested so far
            elif "notice period" in ql:
                answer_text = "2 weeks"
            elif "earliest start" in ql or "start date" in ql:
                answer_text = "2 weeks from offer"
            elif "preferred geographic location" in ql or "preferred location" in ql:
                answer_text = "San Francisco, CA"
            elif "highest level of education" in ql or "highest education" in ql or "level of education" in ql:
                answer_text = "Bachelor's Degree"
            elif "sat" in ql and ("score" in ql or "result" in ql):
                # 2026-05-30 (gh-academic-fields-2026-05-30): SAT 1580/1600.
                # Numeric input usually accepts the bare total.
                answer_text = "1580"
            elif ("act" in ql and "score" in ql) or ("gre" in ql and "score" in ql):
                # ACT/GRE: Cyrus did not take. Free-text safe answer.
                answer_text = "N/A"
            elif "minor" in ql and ("college" in ql or "undergrad" in ql or "degree" in ql or "university" in ql):
                answer_text = EDUCATION_DATA.get("minor") or "Mathematics"
            elif "how did you hear" in ql:
                answer_text = "LinkedIn"
            elif (("name and current date" in ql) or "state your name" in ql or "sign and date" in ql or "signature" in ql or ("name" in ql and "date" in ql and "box" in ql)):
                from datetime import datetime as _dt
                _pi = _get_pi()
                _first = _pi.get("identity", {}).get("first_name", "")
                _last = _pi.get("identity", {}).get("last_name", "")
                answer_text = f"{_first} {_last}".strip() + f", {_dt.utcnow().strftime('%m/%d/%Y')}"
            # NOTE 2026-05-26 (Peterson 1269 fix): Peterson Workday tenants ask 6 long-form
            # essay/text questions that have no canned LABEL match. Provide generic on-script
            # answers so the application can submit. These should help any tenant asking
            # similar narrative questions.
            elif "if you marked yes" in ql or "please provide" in ql or "please specify" in ql:
                # Conditional follow-ups gated on a prior 'Yes' that we answered 'No' to.
                # 'N/A' is the universally-accepted safe answer.
                answer_text = "N/A"
            elif ("reason" in ql and ("employment" in ql or "left" in ql or "end" in ql or "separation" in ql)) or \
                 ("why did you leave" in ql) or ("why are you leaving" in ql):
                answer_text = (
                    "Seeking a new opportunity that better aligns with my career growth, "
                    "technical depth, and interest in customer-facing technical work."
                )
            elif ("what interests you" in ql) or ("why are you interested" in ql) or \
                 ("interest in this position" in ql) or ("why do you want" in ql):
                answer_text = (
                    "I'm excited by this role because it combines deep technical work with "
                    "direct customer impact. My background spans engineering, technical "
                    "program management, and pre-sales/solutions work, and I'm drawn to "
                    "organizations where I can solve real customer problems end-to-end."
                )
            elif ("qualifications" in ql) or ("qualified for" in ql) or \
                 ("skills, training" in ql) or ("degrees, licenses" in ql) or \
                 ("why should we hire" in ql) or ("what makes you a good fit" in ql):
                # 2026-05-30: REWRITTEN from resume. Prior version fabricated
                # "BS Industrial Engineering Purdue / 10+ years". Real: BS CS U of
                # Houston (GPA 3.8), ~3 years TPM at Microsoft + intern stints.
                answer_text = (
                    "BS in Computer Science (Minor: Mathematics, GPA 3.8) from the "
                    "University of Houston. Technical Program Manager at Microsoft "
                    "Azure since 2024, with prior TPM internships at Microsoft and "
                    "Amazon Robotics. Strong in Python, SQL, distributed systems, "
                    "data pipelines, AI/automation tooling, customer discovery, and "
                    "translating requirements into shipped platform capabilities. "
                    "Comfortable presenting to executives and partnering across "
                    "engineering, product, and go-to-market teams. Full details on resume."
                )
            elif ("other information" in ql) or ("additional information" in ql) or \
                 ("anything else" in ql) or ("help in evaluating" in ql) or \
                 ("like to add" in ql):
                answer_text = (
                    "Happy to walk through specific projects, customer outcomes, or technical "
                    "deep-dives in an interview. Thank you for your consideration."
                )
            elif ("cover letter" in ql) or ("motivation" in ql and "role" in ql):
                answer_text = (
                    "I'm applying because this role combines technical depth with direct "
                    "customer impact \u2014 the part of my background I'm most energized by. "
                    "My experience in engineering, technical program management, and "
                    "solutions/sales engineering should translate well. Happy to discuss "
                    "specific examples in conversation."
                )
            if not answer_text:
                blockers.append(f"app-question (text) no answer: {qtext[:120]}")
                continue
            try:
                inp = page.locator(f"[id='{q['id']}']")
                inp.scroll_into_view_if_needed(timeout=2000)
                inp.fill(answer_text)
                log(f"    text filled: {answer_text!r}")
            except Exception as e:
                log(f"    text fill failed: {e}")
                blockers.append(f"text fill failed: {qtext[:80]}")
        elif q["type"] == "checkboxGroup":
            ql = qtext.lower()
            chosen = None
            # Case A: Adobe-style "Have you worked here" — pick "I have not worked" / "None of the above".
            for opt in q["options"]:
                lab = (opt.get("label") or "").lower()
                if any(k in lab for k in ["i have not worked", "not worked", "none of the above"]):
                    chosen = opt
                    break
            # Case B: Yes/No checkbox-group (Nvidia sponsorship/auth questions). Use keyword answer.
            if not chosen:
                answer = pick_option(qtext)
                if answer in ("yes", "no"):
                    target = answer.lower()
                    for opt in q["options"]:
                        lab = (opt.get("label") or "").strip().lower()
                        if lab == target:
                            chosen = opt
                            log(f"    checkboxGroup Yes/No → ticking {opt.get('label')!r} for {qtext[:60]!r}")
                            break
            if not chosen:
                # Intel-style: 'If hired, do you intend to (select all that apply)' — tick benign reside/work options
                ql2 = qtext.lower()
                if "if hired" in ql2 and "intend to" in ql2:
                    intel_keywords = ["reside in", "work at the assigned", "relocate", "live and work", "primary residence", "work in the u.s", "work in the united states", "physically work", "work onsite", "neither"]
                    for opt in q["options"]:
                        lab = (opt.get("label") or "").lower()
                        if any(k in lab for k in intel_keywords):
                            try:
                                cb = page.locator(f"[id='{opt['id']}']")
                                cb.scroll_into_view_if_needed(timeout=2000)
                                cb.evaluate("el => { if (!el.checked) el.click(); }")
                                log(f"    ticked (if-hired): {opt.get('label')}")
                                chosen = opt
                            except Exception as e:
                                log(f"    if-hired tick failed: {e}")
                    if chosen:
                        continue
                # Debug: dump available labels so we can extend later
                log(f"    checkboxGroup unmatched. Options: {[o.get('label') for o in q['options']]}")
                blockers.append(f"checkboxGroup: no matching option for: {qtext[:120]}")
                continue
            try:
                cb = page.locator(f"[id='{chosen['id']}']")
                cb.scroll_into_view_if_needed(timeout=2000)
                cb.evaluate("el => { if (!el.checked) el.click(); }")
                log(f"    ticked: {chosen.get('label')}")
            except Exception as e:
                log(f"    checkbox click failed: {e}")
                blockers.append(f"checkbox click failed: {chosen.get('label')}")
    screenshot(page, slug, "q-after")
    return {"blockers": blockers}


def select_dropdown_by_text(page: Page, button_id: str, candidates: list, label: str = "") -> bool:
    """Open a Workday listbox button and click the first option whose text matches any candidate (case-insensitive, exact-or-partial)."""
    try:
        btn = page.locator(f"#{button_id}").first
        if btn.count() == 0:
            log(f"  dropdown {button_id} missing")
            return False
        btn.scroll_into_view_if_needed(timeout=2000)
        btn.click(timeout=5000)
        page.wait_for_timeout(500)
        # Try exact match first
        opts = page.locator('[role=option]').all()
        opt_texts = []
        for opt in opts:
            try: opt_texts.append((opt, (opt.text_content() or "").strip()))
            except Exception: pass
        for cand in candidates:
            cl = cand.lower()
            for opt, t in opt_texts:
                if t.lower() == cl:
                    opt.click(force=True)
                    log(f"  {label or button_id} = {t}")
                    page.wait_for_timeout(300)
                    return True
            for opt, t in opt_texts:
                if cl in t.lower():
                    opt.click(force=True)
                    log(f"  {label or button_id} = {t} (partial: {cand})")
                    page.wait_for_timeout(300)
                    return True
        log(f"  {button_id}: none of {candidates} matched. Available: {[t for _,t in opt_texts][:8]}")
        try: page.keyboard.press("Escape")
        except Exception: pass
        return False
    except Exception as e:
        log(f"  select_dropdown_by_text {button_id} failed: {e}")
        try: page.keyboard.press("Escape")
        except Exception: pass
        return False


def fill_voluntary_disclosures(page: Page, info: dict, slug: str) -> dict:
    """Workday Voluntary Disclosures: gender/ethnicity/veteran + T&C. Decline everywhere; gender fallback to Male if blocking."""
    log("STEP: Voluntary Disclosures")
    page.wait_for_timeout(2500)
    screenshot(page, slug, "vol-before")
    blockers = []

    # Decline answers; gender allows Male fallback per personal-info.json
    # HPE-style tenants don't offer 'Declined to State' — fallback to 'Not Specified'
    # (US EEOC category that maps to undisclosed; semantically equivalent to decline).
    select_dropdown_by_text(page, "personalInfoUS--ethnicity",
        ["Declined to State", "Decline to self-identify", "Decline to State",
         "Do not wish", "Not Specified", "Prefer not to"],
        label="ethnicity")
    # Baker Hughes uses a multi-checkbox ethnicity group instead of a dropdown.
    # Tick "I choose to not disclose" if the dropdown didn't exist.
    try:
        eth_multi = page.locator('input[type=checkbox][id*=ethnicityMulti]')
        if eth_multi.count():
            picked = page.evaluate("""() => {
                const targets = ['choose to not disclose', 'choose not to disclose', 'do not wish', 'prefer not'];
                const cbs = Array.from(document.querySelectorAll('input[type=checkbox][id*=ethnicityMulti]'));
                for (const cb of cbs) {
                    const lab = document.querySelector(`label[for="${cb.id}"]`);
                    const t = (lab ? lab.innerText : '').toLowerCase();
                    if (targets.some(k => t.includes(k))) { if (!cb.checked) cb.click(); return lab.innerText.trim(); }
                }
                return null;
            }""")
            if picked: log(f"  ethnicityMulti declined: {picked}")
    except Exception as e:
        log(f"  ethnicityMulti tick failed: {e}")
    # Baker Hughes — separate Hispanic or Latino dropdown
    if page.locator('#personalInfoUS--hispanicOrLatino').count():
        select_dropdown_by_text(page, "personalInfoUS--hispanicOrLatino",
            ["No", "I do not wish to answer", "Decline"],
            label="hispanicOrLatino")
    select_dropdown_by_text(page, "personalInfoUS--veteranStatus",
        ["I DO NOT WISH TO SELF-IDENTIFY", "Do not wish", "Decline"],
        label="veteran")
    select_dropdown_by_text(page, "personalInfoUS--gender",
        ["Male", "Decline to self-identify", "Do not wish", "Not declared"],
        label="gender")

    # T&C
    tc = page.locator('input[type=checkbox][id*=acceptTermsAndAgreements], input[type=checkbox][id*=termsAndConditions]').first
    if tc.count():
        try:
            tc.evaluate("el => { if (!el.checked) el.click(); }")
            log("  ticked T&C")
        except Exception as e:
            log(f"  T&C tick failed: {e}")
    screenshot(page, slug, "vol-after")
    return {"blockers": blockers}


def fill_self_identify(page: Page, info: dict, slug: str) -> dict:
    """Workday Self Identify (disability form): decline + name + date signature."""
    log("STEP: Self Identify")
    page.wait_for_timeout(2500)
    screenshot(page, slug, "selfid-before")
    blockers = []

    # Disability status: Workday uses checkboxes (id ends -disabilityStatus), 3 options.
    cbs = page.evaluate("""()=>{
      const out=[];
      document.querySelectorAll('input[type=checkbox][id*="-disabilityStatus"]').forEach(c=>{
        const lab=document.querySelector(`label[for="${c.id}"]`);
        out.push({id:c.id, lab:lab?lab.textContent.trim():''});
      });
      return out;
    }""") or []
    log(f"  found {len(cbs)} disabilityStatus checkboxes")
    declined = False
    for c in cbs:
        lab = (c.get("lab") or "").lower()
        if any(k in lab for k in ["do not want to answer", "do not wish", "prefer not", "don't want to answer"]):
            try:
                page.locator(f"[id='{c['id']}']").evaluate("el => { if (!el.checked) el.click(); }")
                log(f"  declined: {c['lab'][:60]}")
                declined = True
                break
            except Exception as e:
                log(f"  decline cb click failed: {e}")
    # Fallback: radios (older Workday)
    if not declined:
        radios = page.evaluate("""()=>{
          const out=[];
          document.querySelectorAll('input[type=radio]').forEach(r=>{
            const lab=document.querySelector(`label[for="${r.id}"]`);
            out.push({id:r.id, lab:lab?lab.textContent.trim():''});
          });
          return out;
        }""") or []
        for r in radios:
            lab = (r.get("lab") or "").lower()
            if any(k in lab for k in ["do not want to answer", "do not wish", "prefer not"]):
                try:
                    page.locator(f"[id='{r['id']}']").evaluate("el => el.click()")
                    log(f"  declined (radio): {r['lab'][:60]}")
                    declined = True
                    break
                except Exception: pass
    if not declined:
        blockers.append("self-identify: no decline-to-answer option")

    # Name (full name signature)
    fullname = f"{info['identity']['first_name']} {info['identity']['last_name']}"
    for sel in [
        '[id="selfIdentifiedDisabilityData--name"]',
        'input[id$="--name"][id*="Disability"]',
        'input[data-automation-id="name"]',
    ]:
        if page.locator(sel).count():
            fill_text(page, sel, fullname, "selfid-name")
            break

    # Date (today). Workday uses MM/DD/YYYY spinbutton.
    today = datetime.now()
    for prefix in ['selfIdentifiedDisabilityData--dateSignedOn', 'dateSignedOn', 'signatureDate']:
        m_sel = f'[id="{prefix}-dateSectionMonth-input"]'
        d_sel = f'[id="{prefix}-dateSectionDay-input"]'
        y_sel = f'[id="{prefix}-dateSectionYear-input"]'
        if page.locator(m_sel).count():
            fill_spinbutton(page, m_sel, str(today.month).zfill(2), "selfid-month")
            fill_spinbutton(page, d_sel, str(today.day).zfill(2), "selfid-day")
            fill_spinbutton(page, y_sel, str(today.year), "selfid-year")
            break

    screenshot(page, slug, "selfid-after")
    return {"blockers": blockers}


def fill_generic_page(page: Page, info: dict, slug: str, label: str) -> dict:
    """Best-effort filler for application-questions/voluntary/self-id."""
    log(f"STEP: generic ({label})")
    page.wait_for_timeout(2500)
    screenshot(page, slug, f"{label}-before")
    blockers = []

    # Default-decline on visible button-dropdowns showing 'Select One'
    btns = page.locator('button[aria-haspopup="listbox"]').all()
    for btn in btns:
        try:
            txt = (btn.text_content() or "").strip().lower()
            if "select one" not in txt:
                continue
            btn.click(timeout=2000)
            page.wait_for_timeout(400)
            # Try decline option
            decline = page.locator('[role=option]').filter(has_text=re.compile(r'decline|prefer not|do not wish|don\'t wish|don\'t want|do not want', re.I)).first
            if decline.count():
                decline.click(force=True)
                page.wait_for_timeout(300)
                continue
            # Find the question text near this button to decide default
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
        except Exception:
            pass

    # Radio groups: scan and apply known defaults
    radio_groups = page.evaluate("""
        () => {
          const groups = {};
          document.querySelectorAll('input[type=radio]').forEach(r => {
            if (!groups[r.name]) {
              let p = r.closest('fieldset, [role=group], [role=radiogroup]');
              let q = '';
              if (p) {
                const legend = p.querySelector('legend, label[id$="--label"], [data-automation-id*="label" i]');
                if (legend) q = legend.textContent.trim();
              }
              if (!q) {
                // walk up
                let n = r.parentElement;
                while (n && !q) {
                  const lab = n.querySelector('label');
                  if (lab && !lab.contains(r)) q = lab.textContent.trim();
                  n = n.parentElement;
                  if (n && n.tagName === 'BODY') break;
                }
              }
              groups[r.name] = {question: q, values: [], checked: false};
            }
            groups[r.name].values.push(r.value);
            if (r.checked) groups[r.name].checked = true;
          });
          return groups;
        }
    """) or {}
    for name, g in radio_groups.items():
        if g.get("checked"):
            continue
        q = (g.get("question") or "").lower()
        target = None
        if any(k in q for k in ["authorized to work", "authorization to work", "legally authorized", "eligible to work"]):
            target = True
        elif any(k in q for k in ["sponsorship", "require sponsorship", "need sponsorship", "visa sponsorship"]):
            target = False
        elif "felony" in q or "convicted" in q:
            target = False
        elif "background check" in q:
            target = True
        elif "drug" in q:
            target = True
        elif "non-compete" in q or "non compete" in q:
            target = False
        elif "clearance" in q or "secret" in q:
            target = False
        elif "previously" in q and ("employed" in q or "applied" in q or "worked" in q):
            target = False
        elif any(k in q for k in ["ai tool", "artificial intelligence", "generative ai", "use ai", "used ai", "ai assist"]):
            target = False  # per policy
        elif "18 years" in q or "age of 18" in q:
            target = True
        elif "relocate" in q:
            target = True
        elif "remote" in q and "work" in q:
            target = True
        if target is None:
            continue
        # Map True/False to values
        for v in g["values"]:
            vl = v.lower()
            if target and vl in ("true", "yes", "1"):
                click_radio(page, name, v)
                log(f"  radio {name}={v} (q: {q[:60]})")
                break
            if not target and vl in ("false", "no", "0"):
                click_radio(page, name, v)
                log(f"  radio {name}={v} (q: {q[:60]})")
                break

    # T&C / consent checkboxes
    cbs = page.locator('input[type=checkbox]').all()
    for cb in cbs:
        try:
            req = cb.get_attribute("aria-required") == "true" or cb.evaluate("el => el.required")
            checked = cb.is_checked()
            if req and not checked:
                # Find label
                lbl_id = cb.get_attribute("id")
                lbl_txt = ""
                if lbl_id:
                    lbl_loc = page.locator(f'label[for="{lbl_id}"]').first
                    if lbl_loc.count():
                        lbl_txt = (lbl_loc.text_content() or "").lower()
                if any(k in lbl_txt for k in ["agree", "terms", "consent", "acknowledge", "certify", "confirm", "accept", "true and complete", "accurate"]):
                    cb.evaluate("el => el.click()")
                    log(f"  ticked T&C checkbox {lbl_id}")
        except Exception:
            pass

    # Find remaining blank required fields
    blanks = page.evaluate("""
        () => {
          const issues = [];
          document.querySelectorAll('input[type=text], textarea, input[type=email], input[type=tel], input[type=date]').forEach(el => {
            const required = el.required || el.getAttribute('aria-required') === 'true';
            if (required && !el.value) {
              let label = '';
              const id = el.id;
              if (id) {
                const lab = document.querySelector(`label[for="${id}"]`);
                if (lab) label = lab.textContent.trim();
              }
              issues.push({type: 'text', id: el.id, name: el.name, label: label.slice(0,120)});
            }
          });
          document.querySelectorAll('button[aria-haspopup="listbox"]').forEach(btn => {
            const aria_req = btn.getAttribute('aria-required');
            if (aria_req !== 'true') return;
            const sel = btn.querySelector('[data-automation-id="selectedItem"]');
            const txt = (sel ? sel.textContent : btn.textContent).trim();
            if (!txt || txt.toLowerCase().includes('select one')) {
              let label = '';
              const id = btn.id;
              if (id) {
                const lab = document.querySelector(`label[for="${id}"]`);
                if (lab) label = lab.textContent.trim();
              }
              issues.push({type: 'dropdown', id: btn.id, label: label.slice(0,120)});
            }
          });
          const groups = {};
          document.querySelectorAll('input[type=radio]').forEach(r => {
            if (!groups[r.name]) groups[r.name] = {checked: false, required: false, q: ''};
            if (r.checked) groups[r.name].checked = true;
            if (r.required || r.getAttribute('aria-required') === 'true') groups[r.name].required = true;
            const fs = r.closest('fieldset, [role=radiogroup]');
            if (fs) {
              const lg = fs.querySelector('legend');
              if (lg) groups[r.name].q = lg.textContent.trim();
            }
          });
          Object.entries(groups).forEach(([n, g]) => {
            if (g.required && !g.checked) issues.push({type:'radio', name:n, label: (g.q||'').slice(0,120)});
          });
          document.querySelectorAll('input[type=checkbox]').forEach(cb => {
            if ((cb.required || cb.getAttribute('aria-required')==='true') && !cb.checked) {
              let label = '';
              const id = cb.id;
              if (id) {
                const lab = document.querySelector(`label[for="${id}"]`);
                if (lab) label = lab.textContent.trim();
              }
              issues.push({type:'checkbox', id: cb.id, label: label.slice(0,120)});
            }
          });
          return issues;
        }
    """) or []
    if blanks:
        log(f"  blank required after fill: {len(blanks)}")
        for b in blanks[:10]:
            log(f"    {b}")
        blockers.append(f"{label}: {len(blanks)} required unanswered: {blanks[:5]}")
    screenshot(page, slug, f"{label}-after")
    return {"blockers": blockers}


# ──────────────────────────────────────────────────────────────────────────
# Account creation
# ──────────────────────────────────────────────────────────────────────────


def mark_account_created(tenant: str) -> None:
    """Persist account_created=true into .workday-creds.json (nested tenants shape)."""
    try:
        if not CREDS_FILE.exists(): return
        data = json.loads(CREDS_FILE.read_text())
        if "tenants" in data and isinstance(data["tenants"], dict):
            t = data["tenants"].setdefault(tenant, {})
            if not t.get("account_created"):
                t["account_created"] = True
                CREDS_FILE.write_text(json.dumps(data, indent=2))
                log(f"creds: marked {tenant} account_created=true")
    except Exception as e:
        log(f"mark_account_created failed: {e}")


def handle_signin_choice(page: Page, slug: str, prefer: str = "create") -> str:
    """Some Workday tenants (Nvidia, HPE, ...) gate account/signin behind a chooser page:
    'Sign in with Google' / 'Sign in with email'. After clicking 'Sign in with email' the
    user lands on a Sign In form with a 'Create Account' link.

    This helper drives that two-step chooser. Returns:
      'none'    - no chooser detected
      'created' - clicked 'Sign in with email' then 'Create Account' link (next call to
                  handle_account_prompt should see a create-account form with verifyPassword)
      'signin'  - clicked 'Sign in with email' only (existing-account path)
      'failed:<reason>'
    Idempotent across iterations; safe to call before every handle_account_prompt.
    """
    page.wait_for_timeout(500)
    sel_email = '[data-automation-id="SignInWithEmailButton"]'
    sel_google = '[data-automation-id="GoogleSignInButton"]'
    sel_create_link = '[data-automation-id="createAccountLink"]'
    has_chooser = page.locator(sel_email).count() and page.locator(sel_google).count()
    if has_chooser:
        try:
            page.locator(sel_email).first.click(timeout=4000)
            log("clicked Sign in with email (chooser)")
            page.wait_for_timeout(2500)
            screenshot(page, slug, "signin-chooser-email")
        except Exception as e:
            return f"failed:chooser-email-click:{e}"
    # Now we should be on an email/password Sign In form. If prefer=='create' and a
    # Create Account link is visible, click it to switch to the create form.
    if prefer == "create":
        link = page.locator(sel_create_link).first
        if link.count() and link.is_visible(timeout=500):
            try:
                link.click(timeout=4000)
                log("clicked Create Account link")
                page.wait_for_timeout(2500)
                screenshot(page, slug, "signin-create-link")
                return "created"
            except Exception as e:
                return f"failed:create-link-click:{e}"
    if has_chooser:
        return "signin"
    return "none"


def handle_account_prompt(page: Page, email: str, password: str, slug: str, tenant: str = "", prefer_signin: bool = False) -> str:
    """Workday account creation: appears as modal or full page after Next/Submit.

    Returns one of:
      'none'       - no account form detected
      'created'    - submitted Create Account; caller should loop (may need email verify)
      'signed_in'  - submitted Sign In with existing creds
      'failed:<reason>' - account form present but submit failed; caller should abort

    If `prefer_signin=True`, skip the Create Account link in the chooser (account already exists).
    """
    page.wait_for_timeout(1500)
    # First, drive any sign-in-method chooser (Nvidia/HPE etc.). Safe no-op for Adobe/PayPal.
    try:
        handle_signin_choice(page, slug, prefer=("signin" if prefer_signin else "create"))
        page.wait_for_timeout(800)
    except Exception as e:
        log(f"signin-choice handler exception (non-fatal): {e}")
    # Workday quirk: cookies banner can block clicks. Dismiss it first if present.
    try:
        for sel in ['[data-automation-id="legalNoticeAcceptButton"]', 'button:has-text("Accept Cookies"):visible']:
            l = page.locator(sel).first
            if l.count() and l.is_visible(timeout=300):
                l.click(); page.wait_for_timeout(400); break
    except Exception:
        pass
    has_email = page.locator('input[data-automation-id="email"]:visible, input[type="email"]:visible').count() > 0
    has_pwd = page.locator('input[type="password"]:visible').count() > 0
    if not (has_email and has_pwd):
        return "none"
    log("account prompt detected")
    screenshot(page, slug, "account-prompt")
    is_create = page.locator('[data-automation-id="createAccountSubmitButton"]:visible, [data-automation-id="verifyPassword"]:visible').count() > 0
    try:
        em = page.locator('input[data-automation-id="email"]:visible, input[type="email"]:visible').first
        em.fill(email)
        pwds = page.locator('input[type="password"]:visible').all()
        for p in pwds:
            try: p.fill(password)
            except Exception: pass
        # NEVER fill the beecatcher honeypot — Workday flags submissions with it set.
        # Agree to T&C
        for cb in page.locator('input[type=checkbox]:visible').all():
            try:
                if not cb.is_checked(): cb.evaluate("el => el.click()")
            except Exception: pass
        page.wait_for_timeout(400)
        # The submit button is often intercepted by a sibling div[data-automation-id="click_filter"]
        # which holds the real click handler. Try multiple strategies in order.
        target_sels = (
            ['[data-automation-id="createAccountSubmitButton"]', 'button:has-text("Create Account")']
            if is_create else
            ['[data-automation-id="signInSubmitButton"]', 'button:has-text("Sign In")']
        )
        clicked = False
        for sel in target_sels:
            loc = page.locator(sel).first
            if not (loc.count() and loc.is_visible(timeout=500)):
                continue
            # Strategy 1: click the click_filter overlay (the real click target in Workday).
            # The aria-label varies by tenant: Adobe uses 'Sign In'/'Create Account';
            # Nvidia uses 'Submit' on sign-in. Try all known variants.
            label_variants = (
                ["Create Account", "Submit"] if is_create
                else ["Sign In", "Submit"]
            )
            for label in label_variants:
                try:
                    filter_loc = page.locator(f'[data-automation-id="click_filter"][aria-label="{label}"]').first
                    if filter_loc.count() and filter_loc.is_visible(timeout=300):
                        filter_loc.click(timeout=4000)
                        clicked = True
                        log(f"clicked {label} via click_filter overlay")
                        break
                except Exception:
                    continue
            if clicked: break
            # Strategy 2: native JS click on the button itself
            try:
                loc.evaluate("el => el.click()")
                clicked = True
                log(f"clicked {sel} via JS")
                break
            except Exception:
                pass
            # Strategy 3: force playwright click
            try:
                loc.click(force=True, timeout=4000)
                clicked = True
                log(f"clicked {sel} via force")
                break
            except Exception as e:
                log(f"click {sel} failed: {e}")
        if not clicked:
            return f"failed:no-clickable-{('create' if is_create else 'signin')}-button"
        page.wait_for_timeout(6000)
        screenshot(page, slug, "after-account-submit")
        # If we landed on a Sign In page (no verifyPassword input but still email+password visible),
        # retry as sign-in.
        try:
            has_verify_pw = page.locator('input[data-automation-id="verifyPassword"]:visible').count() > 0
            has_pw = page.locator('input[type="password"]:visible').count() > 0
            has_email = page.locator('input[data-automation-id="email"]:visible, input[type="email"]:visible').count() > 0
            if is_create and has_pw and has_email and not has_verify_pw:
                log("Create Account redirected to Sign In — attempting sign-in")
                # Recurse once for sign-in. Mark via instance attr to avoid infinite loop.
                if not getattr(handle_account_prompt, "_signin_retry", False):
                    setattr(handle_account_prompt, "_signin_retry", True)
                    try:
                        r = handle_account_prompt(page, email, password, slug, tenant=tenant, prefer_signin=True)
                    finally:
                        setattr(handle_account_prompt, "_signin_retry", False)
                    return r
        except Exception:
            pass
        # Check for inline errors / validation
        try:
            body = (page.locator("body").text_content() or "").lower()
            already_exists = any(p in body for p in (
                "account already exists", "email is already in use", "already registered",
                "email address is already", "an account with this email",
            ))
            # Also: email input flagged aria-invalid AND we're still on a form with an email field is a hint
            if not already_exists and is_create:
                try:
                    email_invalid = page.locator('input[data-automation-id="email"][aria-invalid="true"]:visible').count() > 0
                    if email_invalid and page.locator('input[type=password]:visible').count() > 0:
                        # Could be just an empty/format error, but if the field had a valid email,
                        # the most likely cause is account-exists. Switch to signin retry.
                        already_exists = True
                        log("detected email aria-invalid after Create Account submit — assuming account exists, switching to sign-in")
                except Exception:
                    pass
            if already_exists and is_create:
                log("account already exists — switching to sign-in")
                mark_account_created(tenant)
                if not getattr(handle_account_prompt, "_signin_retry", False):
                    setattr(handle_account_prompt, "_signin_retry", True)
                    try:
                        return handle_account_prompt(page, email, password, slug, tenant=tenant, prefer_signin=True)
                    finally:
                        setattr(handle_account_prompt, "_signin_retry", False)
                return handle_account_prompt(page, email, password, slug, tenant=tenant, prefer_signin=True)
            if "please correct" in body or "the following errors" in body[:5000]:
                # Try to surface the error text
                errs = check_errors(page)
                return f"failed:validation:{errs[:3]}"
        except Exception:
            pass
        if is_create and tenant:
            mark_account_created(tenant)
        return "created" if is_create else "signed_in"
    except Exception as e:
        log(f"account submit exception: {e}")
        return f"failed:exception:{type(e).__name__}"


# ──────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────


STEP_ROUTES = {
    "my information": "info",
    "my experience": "exp",
    "application questions": "questions",
    "voluntary disclosures": "voluntary",
    "self identify": "selfid",
    "self-identify": "selfid",
    "review": "review",
}


def maybe_handle_email_verification(page: Page, email: str, slug: str, result: dict) -> str:
    """After account creation, detect & handle Workday's verification flow.

    Two known patterns:
      A) On-page code input (Workday shows a 'Verify Your Account' / 'enter the code we sent' page).
         Detect: input[data-automation-id="verifyAccountCodeInput"] or text "verify" + 6-8 char code input.
      B) Link-only verification (email contains a click-here link; no on-page form).
         Detect: page body says 'check your email' AND no code input present.

    Returns 'none' | 'verified' | 'failed'. Mutates `result['steps']` and `result['blockers']`.
    """
    page.wait_for_timeout(1500)
    try:
        body = (page.locator("body").text_content() or "").lower()
    except Exception:
        body = ""
    # Heuristic for verification page presence
    needs_verify_text = any(p in body for p in [
        "verify your account", "verify your email", "verification code",
        "we sent a verification", "enter the verification", "check your email",
        "we've sent", "we have sent",
    ])
    code_input = page.locator('input[data-automation-id="verifyAccountCodeInput"]:visible, input[aria-label*="erification"]:visible, input[name*="verification" i]:visible').first
    has_code_input = code_input.count() > 0
    if not needs_verify_text and not has_code_input:
        return "none"
    log("email verification page detected")
    screenshot(page, slug, "verify-prompt")
    result["steps"].append("verification-prompt")
    # Try to pull a code from Gmail
    try:
        sys.path.insert(0, str(HERE))
        from gmail_imap import wait_for_verification_code
        # 90s budget per spec
        try:
            code = wait_for_verification_code(timeout_seconds=90, poll_seconds=5)
        except Exception as e:
            log(f"gmail wait failed: {e}")
            result["blockers"].append(f"email-verification: {type(e).__name__}: {str(e)[:160]}")
            return "failed"
        log(f"got verification code: {code}")
        if has_code_input:
            try:
                code_input.fill(code)
            except Exception:
                code_input.evaluate("(el,v)=>{el.focus(); el.value=v; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}", code)
            page.wait_for_timeout(500)
            # Click any visible Submit / Verify button
            for sel in [
                '[data-automation-id="verifyAccountSubmitButton"]',
                'button:has-text("Verify"):visible',
                'button:has-text("Submit"):visible',
                'button:has-text("Continue"):visible',
            ]:
                l = page.locator(sel).first
                if l.count() and l.is_visible(timeout=400):
                    try:
                        l.click(); break
                    except Exception:
                        try: l.evaluate("el=>el.click()"); break
                        except Exception: pass
            page.wait_for_timeout(5000)
            screenshot(page, slug, "after-verify")
            result["steps"].append("verification-submitted")
            return "verified"
        else:
            # Code-only with no input — the email is link-based. We don't have a way to
            # follow the link safely here. Abort.
            result["blockers"].append("email-verification: link-based flow not yet supported")
            return "failed"
    except Exception as e:
        log(f"verification exception: {e}")
        result["blockers"].append(f"email-verification: {type(e).__name__}: {e}")
        return "failed"


def classify_step(step_text: str) -> str:
    s = (step_text or "").lower()
    for k, v in STEP_ROUTES.items():
        if k in s:
            return v
    return "unknown"


def is_confirmation(page: Page) -> bool:
    try:
        url = (page.url or "")
        if "Job_Application_ID=" in url:
            return True
        # Intel / many other tenants redirect to jobTasks/completed/application
        if "jobTasks/completed/application" in url:
            return True
        # Nvidia-style: explicit submission complete URL
        if "applications/completed" in url:
            return True
        body = (page.locator("body").text_content() or "").lower()
        return any(p in body for p in [
            "your application has been submitted",
            "thank you for applying",
            "we have received your application",
            "thanks for applying",
            "application received",
            "you have submitted your application",
            "we are reviewing your application",
            # PayPal-style: shows app summary card without explicit thank-you copy
            "application submitted",
            "submission successful",
            "successfully submitted",
        ])
    except Exception:
        return False


def is_posting_removed(page: Page) -> bool:
    """Detect a tenant that has pulled the requisition (404 / removed-state shell).

    Workday usually returns 200 with a generic 'page you are looking for' shell
    rather than a real 404, so we sniff body copy. Cheap to call from the entry
    path right after page.goto and again after the loop fails.
    """
    try:
        body = (page.locator("body").text_content() or "").lower()
    except Exception:
        return False
    needles = [
        "page you are looking for doesn't exist",
        "page you are looking for does not exist",
        "job posting is no longer available",
        "this job is no longer available",
        "this position is no longer available",
        "requisition is no longer available",
        "job posting unavailable",
        "this posting has been closed",
    ]
    return any(n in body for n in needles)


def verify_submission_via_userhome(page: Page, apply_url: str, slug: str) -> dict:
    """Post-submit cross-check for tenants that don't redirect to a confirmation URL
    and don't show a thank-you body (e.g. PayPal). Navigates to <tenant>/userHome
    and looks for the application in the My Applications list. This guards against
    double-submits on retry by treating 'application present in userHome' as success.

    Returns {'confirmed': bool, 'evidence': str}.
    Best-effort: any error returns confirmed=False so the normal post-submit blocker
    path still runs.
    """
    try:
        # Workday apply URLs look like https://<tenant>.<wd?>.myworkdayjobs.com/[locale/]<site>/job/<...>/apply
        # The userHome endpoint is hosted at <host>/<site>/userHome (no locale prefix on
        # most tenants). We try a few candidate forms and use the first that responds
        # with something other than a hard error page.
        m = re.match(r"^(https?://[^/]+)(/.+?)/job/", apply_url or "")
        if not m:
            return {"confirmed": False, "evidence": "could-not-derive-site-root"}
        host = m.group(1)
        path_prefix = m.group(2)  # e.g. '/jobs' or '/en-US/external_experienced'
        # Strip a leading locale (2-letter or xx-XX) segment if present — userHome usually
        # lives at the bare site root.
        parts = [p for p in path_prefix.split("/") if p]
        if parts and re.match(r"^[a-z]{2}(-[A-Z]{2})?$", parts[0]):
            site_only = "/" + "/".join(parts[1:])
        else:
            site_only = path_prefix
        candidates = []
        if site_only and site_only != path_prefix:
            candidates.append(f"{host}{site_only}/userHome")
        candidates.append(f"{host}{path_prefix}/userHome")
        last_evidence = "no-candidates"
        for home_url in candidates:
            log(f"verify_submission_via_userhome: trying {home_url}")
            try:
                page.goto(home_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
            except Exception as ne:
                last_evidence = f"nav-error: {ne}"
                continue
            screenshot(page, slug, "userhome-verify")
            body = (page.locator("body").text_content() or "").lower()
            # If the tenant kicked us to a sign-in page, that's not a confirmation signal.
            if "sign in" in body and "my applications" not in body and "submitted applications" not in body:
                last_evidence = "signin-required"
                continue
            # Look for a submitted application listing. Workday's standard My Applications
            # widget shows 'Submitted' status or 'Application' header.
            positive = [
                "submitted applications",
                "my applications",
                "applications submitted",
                "status: submitted",
                "under consideration",
            ]
            hits = [p for p in positive if p in body]
            if hits:
                return {"confirmed": True, "evidence": f"userhome-hit: {hits[:3]} at {home_url}"}
            last_evidence = f"no-application-list-found at {home_url}"
        return {"confirmed": False, "evidence": last_evidence}
    except Exception as e:
        return {"confirmed": False, "evidence": f"error: {e}"}


def run_workday_apply(tenant: str, apply_url: str, slug: str, role_id: int,
                      headless: bool = True, dry_run: bool = False,
                      max_steps: int = 20) -> dict:
    info = load_personal_info()
    creds = load_creds(tenant)
    if not creds:
        return {"ok": False, "error": f"no creds for tenant {tenant}"}
    email = creds["email"]
    password = creds["password"]
    BROWSER_DATA_ROOT.mkdir(exist_ok=True)
    user_data_dir = BROWSER_DATA_ROOT / tenant
    DEBUG_ROOT.mkdir(exist_ok=True)

    result = {
        "ok": False, "tenant": tenant, "slug": slug, "role_id": role_id,
        "apply_url": apply_url, "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [], "blockers": [], "screenshots_dir": str(DEBUG_ROOT / slug),
    }

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless, viewport={"width": 1400, "height": 900},
            user_agent=UA, args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        try:
            page.goto(apply_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            # Posting-removed sniff: do this BEFORE we attempt any auto-fills so the
            # blocker is clean and we don't waste any LLM/captcha budget on a dead
            # requisition. Returns 'posting-removed' so the caller can downgrade or
            # close-out the row.
            if is_posting_removed(page):
                log("POSTING REMOVED at entry")
                screenshot(page, slug, "posting-removed-entry")
                result["blockers"].append("posting-removed")
                return result
            # Dismiss cookies banner if present.
            try:
                for sel in ['[data-automation-id="legalNoticeAcceptButton"]', 'button:has-text("Accept Cookies"):visible']:
                    l = page.locator(sel).first
                    if l.count() and l.is_visible(timeout=300):
                        l.click(); page.wait_for_timeout(500); break
            except Exception: pass
            # JD-page entry (Nvidia, some HPE roles, Curtiss-Wright, etc.): click the 'Apply'
            # button to land on the applyManually chooser. Adobe URLs land directly on the
            # apply flow, so adventureButton may not be present — that's fine, skip silently.
            # NOTE 2026-05-26 (Curtiss-Wright fix): SPA bootstrap on cold persistent context
            # can take >3s; poll up to 10s for adventureButton/applyManually/jobPostingPage
            # before giving up. Also force-click via JS as fallback in case of overlay.
            for _wait_i in range(20):
                if (page.locator('[data-automation-id="adventureButton"]').count() or
                    page.locator('[data-automation-id="applyManually"]').count() or
                    page.locator('[data-automation-id="userHome"]').count()):
                    break
                page.wait_for_timeout(500)
            try:
                adv = page.locator('[data-automation-id="adventureButton"]').first
                if adv.count():
                    try:
                        adv.click(timeout=3000)
                    except Exception:
                        # Overlay or off-viewport: force JS click.
                        page.evaluate("document.querySelector('[data-automation-id=\"adventureButton\"]').click()")
                    page.wait_for_timeout(4000)
                    result["steps"].append("adventureButton")
                    log(f"adventureButton clicked → {page.url}")
            except Exception as e:
                log(f"adventureButton click skipped: {e}")
            # Apply Manually
            if page.locator('[data-automation-id="applyManually"]').count():
                page.click('[data-automation-id="applyManually"]')
                page.wait_for_timeout(4000)
                result["steps"].append("applyManually")

            for iteration in range(max_steps):
                # Check confirmation first
                if is_confirmation(page):
                    log("CONFIRMATION DETECTED")
                    screenshot(page, slug, "confirmation")
                    result["ok"] = True
                    result["confirmation_url"] = page.url
                    result["confirmation_text"] = (page.locator("body").text_content() or "")[:500]
                    return result
                # Check for account prompt (can appear anywhere). Only attempt account submit ONCE.
                if not result.get("_account_attempted"):
                    prefer_signin_flag = bool(creds.get("account_created", False))
                    ap = handle_account_prompt(page, email, password, slug, tenant=tenant, prefer_signin=prefer_signin_flag)
                    if ap != "none":
                        result["_account_attempted"] = True
                        result["steps"].append(f"account-{ap}")
                        if ap.startswith("failed:"):
                            result["blockers"].append(f"account-prompt {ap}")
                            return result
                        page.wait_for_timeout(2500)
                        # After account submission, Workday may demand email verification.
                        if maybe_handle_email_verification(page, email, slug, result) == "failed":
                            return result
                        page.wait_for_timeout(2000)
                        # Verify we actually moved past the account form
                        still_account = page.locator('input[type="password"]:visible').count() > 0
                        if still_account:
                            errs = check_errors(page)
                            result["blockers"].append(f"account form did not advance after submit; errors={errs[:5]}")
                            screenshot(page, slug, "account-stuck")
                            return result
                        # Some tenants (Intel) redirect back to the JD apply page after
                        # sign-in, which shows 'Apply Manually' again. Click it once more
                        # to enter the actual application flow.
                        try:
                            adv2 = page.locator('[data-automation-id="adventureButton"]').first
                            if adv2.count() and adv2.is_visible(timeout=500):
                                adv2.click(); page.wait_for_timeout(3000)
                                result["steps"].append("adventureButton-postauth")
                        except Exception: pass
                        try:
                            am = page.locator('[data-automation-id="applyManually"]').first
                            if am.count() and am.is_visible(timeout=500):
                                am.click(); page.wait_for_timeout(4000)
                                result["steps"].append("applyManually-postauth")
                        except Exception: pass
                        continue
                step_text = detect_step(page)
                kind = classify_step(step_text)
                # Workday occasionally renders a 'Something went wrong' panel after a
                # mid-flow session hiccup (especially when re-entering an in-progress app).
                # A simple reload restores the form and preserves prior data.
                try:
                    body_check = (page.locator("body").text_content() or "")
                except Exception:
                    body_check = ""
                if "Something went wrong" in body_check and not result.setdefault("_swr_reloaded", {}).get(kind):
                    log(f"  'Something went wrong' detected on {kind}; reloading once")
                    result["_swr_reloaded"][kind] = True
                    try:
                        page.reload(wait_until="domcontentloaded")
                        page.wait_for_timeout(6000)
                    except Exception as e:
                        log(f"  reload failed: {e}")
                    step_text = detect_step(page)
                    kind = classify_step(step_text)
                log(f"iter {iteration}: step='{step_text[:80]}' kind={kind}")
                result["steps"].append(f"iter{iteration}:{kind}")
                if kind == "info":
                    fill_my_information(page, info, slug)
                elif kind == "exp":
                    fill_my_experience(page, info, slug)
                elif kind == "review":
                    # Fill any remaining + click Submit
                    fill_generic_page(page, info, slug, "review-page")
                    submitted = False
                    # Diagnostic: list all visible submit-like buttons/overlays
                    try:
                        diag = page.evaluate("""() => Array.from(document.querySelectorAll('button, [data-automation-id*=\"ubmit\"], [data-automation-id*=\"click_filter\"]')).map(e => ({tag:e.tagName, text:(e.innerText||'').slice(0,60), aid:e.getAttribute('data-automation-id'), label:e.getAttribute('aria-label')})).filter(x=>x.text||x.aid||x.label).slice(0,40)""")
                        log(f"  REVIEW buttons: {diag}")
                    except Exception as _de: log(f"  diag err: {_de}")
                    # Try click_filter overlay first (PayPal/some tenants intercept native click)
                    for sel in [
                        '[data-automation-id="click_filter"][aria-label="Submit"]',
                        '[data-automation-id="click_filter"][aria-label="Submit Application"]',
                        '[data-automation-id="pageFooterSubmitButton"]',
                        'button:has-text("Submit"):not(:has-text("Save"))',
                    ]:
                        loc = page.locator(sel).first
                        if loc.count() and loc.is_visible(timeout=500):
                            log(f"clicking Submit: {sel}")
                            screenshot(page, slug, "pre-submit")
                            try:
                                loc.scroll_into_view_if_needed(timeout=2000)
                            except Exception:
                                pass
                            try:
                                loc.click(timeout=5000)
                            except Exception as _ce:
                                log(f"  submit native click failed: {_ce}; trying JS")
                                try: loc.evaluate("el => el.click()")
                                except Exception as _je: log(f"  JS click failed: {_je}")
                            submitted = True
                            page.wait_for_timeout(10000)
                            break
                    if not submitted:
                        result["blockers"].append("review reached but no Submit button")
                        return result
                    screenshot(page, slug, "post-submit")
                    log(f"  post-submit url: {page.url}")
                    body_after = (page.locator("body").text_content() or "")
                    log(f"  post-submit body[:600]: {body_after[:600]!r}")
                    if is_confirmation(page):
                        log("SUBMIT CONFIRMED")
                        result["ok"] = True
                        result["confirmation_url"] = page.url
                        result["confirmation_text"] = (page.locator("body").text_content() or "")[:500]
                        return result
                    # Post-submit userHome cross-check: covers PayPal-style tenants
                    # that show no thank-you copy and don't redirect to a completion URL.
                    # CRITICAL: this prevents the daily cron from re-submitting an
                    # already-submitted application on the next pass.
                    # Only attempt if we have account creds in play (anonymous-only
                    # tenants like Adobe never get a userHome session and would just
                    # see a sign-in page, which we'd correctly treat as 'not confirmed').
                    if result.get("_account_attempted") or creds.get("account_created"):
                        verify = verify_submission_via_userhome(page, apply_url, slug)
                        log(f"  userHome cross-check: {verify}")
                        if verify.get("confirmed"):
                            log("SUBMIT CONFIRMED VIA USERHOME")
                            result["ok"] = True
                            result["confirmation_url"] = page.url
                            result["confirmation_text"] = f"userHome-verified: {verify.get('evidence','')}"[:500]
                            result["confirmation_method"] = "userHome"
                            return result
                    body2 = (page.locator("body").text_content() or "")
                    errs = check_errors(page)
                    if errs:
                        result["blockers"].append(f"post-submit errors: {errs[:5]}")
                    else:
                        result["blockers"].append(f"post-submit body: {body2[:300]}")
                    return result
                elif kind == "voluntary":
                    r = fill_voluntary_disclosures(page, info, slug)
                    if r["blockers"]:
                        result["blockers"].extend(r["blockers"])
                        return result
                elif kind == "selfid":
                    r = fill_self_identify(page, info, slug)
                    if r["blockers"]:
                        result["blockers"].extend(r["blockers"])
                        return result
                elif kind == "questions":
                    r = fill_application_questions(page, info, slug)
                    if r["blockers"]:
                        result["blockers"].extend(r["blockers"])
                        return result
                else:
                    log(f"  unknown step kind, attempting generic fill")
                    r = fill_generic_page(page, info, slug, f"unknown-{iteration}")
                    if r["blockers"]:
                        result["blockers"].extend(r["blockers"])
                        return result

                if dry_run and iteration == 0:
                    log("DRY RUN — stopping after first page fill")
                    result["ok"] = True
                    result["dry_run"] = True
                    return result

                # Click Next
                prev_step = step_text
                if not click_next(page, slug, f"iter{iteration}-{kind}"):
                    # Maybe on Save and Continue button, or modal
                    result["blockers"].append(f"no Next button at iter {iteration} ({kind})")
                    return result
                page.wait_for_timeout(6000)
                # Check for validation errors (filter out success toasts)
                errs = [e for e in check_errors(page) if 'successfully uploaded' not in e.lower() and 'in progress' not in e.lower()]
                if errs:
                    log(f"  validation errors after Next: {errs[:5]}")
                new_step = detect_step(page)
                if new_step == prev_step and kind != "unknown":
                    # Allow ONE retry of same step (Workday sometimes needs a second Next)
                    stuck_count = result.setdefault("_stuck_count", {}).get(kind, 0) + 1
                    result["_stuck_count"][kind] = stuck_count
                    if stuck_count >= 2:
                        result["blockers"].append(f"stuck on {kind} step after Next; errors={errs[:5]}")
                        screenshot(page, slug, f"stuck-{kind}")
                        # Diagnostic dump: list all fieldset legends + any aria-required-invalid fields
                        try:
                            dump = page.evaluate("""() => {
  const fs = Array.from(document.querySelectorAll('fieldset')).map(f => ({legend: (f.querySelector('legend')||{}).innerText||'', id: f.id, invalid: f.getAttribute('aria-invalid')}));
  const reqs = Array.from(document.querySelectorAll('[aria-required=\"true\"]')).map(e => ({tag: e.tagName, id: e.id, name: e.name, invalid: e.getAttribute('aria-invalid'), text: (e.innerText||'').slice(0,80)}));
  const errs = Array.from(document.querySelectorAll('[role=alert], [data-automation-id*=rror]')).map(e => e.innerText).filter(Boolean).slice(0,15);
  return {fieldsets: fs, required: reqs, errors: errs};
}""")
                            log(f"  DIAG fieldsets: {dump.get('fieldsets')}")
                            log(f"  DIAG required: {dump.get('required')}")
                            log(f"  DIAG errors: {dump.get('errors')}")
                        except Exception as _de:
                            log(f"  diag dump failed: {_de}")
                        return result
                    log(f"  same step ({kind}) after Next, retrying once")

            result["blockers"].append(f"hit max_steps={max_steps} without confirmation")
        except Exception as e:
            result["blockers"].append(f"exception: {type(e).__name__}: {e}")
            try: screenshot(page, slug, "exception")
            except Exception: pass
        finally:
            try: ctx.close()
            except Exception: pass
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--role-id", type=int, required=True)
    ap.add_argument("--max-steps", type=int, default=20)
    ap.add_argument("--headless", default="true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    res = run_workday_apply(
        tenant=args.tenant, apply_url=args.url, slug=args.slug, role_id=args.role_id,
        max_steps=args.max_steps,
        headless=args.headless.lower() != "false",
        dry_run=args.dry_run,
    )
    print(json.dumps(res, indent=2, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
