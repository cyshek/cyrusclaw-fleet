#!/usr/bin/env python3
"""
captcha_presubmit.py — Runner-side helper that bridges CapSolverClient to
a live Playwright frame/page.

Used by:
    - greenhouse_iframe_runner.py: just before clicking JS_SUBMIT, if the
      page contains a reCAPTCHA v3 loader, solve the token and inject it
      so the spam-gate score passes.
    - (planned) ashby inline runner: same shape — strict-Ashby tenants use
      the well-known sitekey `6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y`.

Gating:
    Hard env gate. `solve_and_inject_recaptcha_v3` is a no-op unless
    `is_enabled()` returns True (i.e. `ENABLE_CAPSOLVER=1` AND
    `CAPSOLVER_API_KEY` is set). When disabled it returns
    `{enabled: False, reason: 'disabled'}` — the caller proceeds as if
    no captcha solver existed, which is exactly the existing behavior.

NO network calls happen at import time, and constructing the helper does
NOT construct a CapSolverClient (which would itself check the env var).
The client is built lazily inside `solve_and_inject_recaptcha_v3`.

Ashby strict sitekey (well-known shared infra, NOT Enterprise):
    `6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y`
    See ashby_filler.py FIX 5 block (line ~805) for full provenance.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from capsolver_client import (
    CapSolverClient,
    CapSolverDisabled,
    CapSolverError,
    is_enabled,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JS payloads
# ---------------------------------------------------------------------------

# Detect a reCAPTCHA v3 loader on the current document.
# Returns: {sitekey, page_url, loader_src, enterprise: bool}
# - enterprise=True if the loader is the enterprise.js variant.
# - sitekey extracted from the `?render=<key>` query string.
JS_DETECT_RECAPTCHA_V3 = r"""
() => {
  const scripts = Array.from(document.scripts);
  let loader = null;
  for (const s of scripts) {
    const src = s.src || '';
    if (/recaptcha\/(api|enterprise)\.js/.test(src) && /[?&]render=[^&]+/.test(src)) {
      loader = src;
      break;
    }
  }
  if (!loader) {
    // Some sites lazy-load — also scan for grecaptcha global + render attr on
    // a .g-recaptcha div with data-sitekey.
    const div = document.querySelector('.g-recaptcha[data-sitekey], [data-sitekey][class*="recaptcha"]');
    if (div) {
      return {
        sitekey: div.getAttribute('data-sitekey'),
        page_url: location.href,
        loader_src: null,
        enterprise: false,
        source: 'div',
      };
    }
    return { sitekey: null, page_url: location.href, loader_src: null, enterprise: false, source: null };
  }
  const m = loader.match(/[?&]render=([^&]+)/);
  return {
    sitekey: m ? decodeURIComponent(m[1]) : null,
    page_url: location.href,
    loader_src: loader,
    enterprise: /enterprise\.js/.test(loader),
    source: 'loader',
  };
}
"""

# Inject a reCAPTCHA v3 token. Ashby uses `g-recaptcha-response` AND
# `g-recaptcha-response-100000` (suffixed). Greenhouse uses
# `g-recaptcha-response`. We try both and create the textarea if missing.
# Returns: {injected_into: [ids], created: [ids], token_len: N}
JS_INJECT_RECAPTCHA_V3 = r"""
(token) => {
  const ids = ['g-recaptcha-response', 'g-recaptcha-response-100000'];
  const setNative = (el, val) => {
    try {
      const proto = Object.getPrototypeOf(el);
      const setter = Object.getOwnPropertyDescriptor(proto, 'value');
      if (setter && setter.set) { setter.set.call(el, val); }
      else { el.value = val; }
    } catch (_e) { el.value = val; }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const injected = [];
  const created = [];
  for (const id of ids) {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement('textarea');
      el.id = id;
      el.name = id;
      el.style.display = 'none';
      document.body.appendChild(el);
      created.push(id);
    }
    setNative(el, token);
    injected.push(id);
  }
  return { injected_into: injected, created, token_len: (token || '').length };
}
"""


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------

def _disabled_result(reason: str) -> dict:
    return {"enabled": False, "reason": reason, "injected": False}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def solve_and_inject_recaptcha_v3(
    frame: Any,
    *,
    page_url: Optional[str] = None,
    fallback_sitekey: Optional[str] = None,
    action: str = "submit",
    min_score: float = 0.7,
    enterprise: Optional[bool] = None,
    client: Optional[CapSolverClient] = None,
) -> dict:
    """End-to-end: detect sitekey on `frame`, solve via CapSolver, inject token.

    Args:
        frame: Playwright `Frame` or `Page` (anything with `.evaluate()`).
        page_url: Override the URL passed to CapSolver. If None, read from
            the detect-JS result (location.href in the frame context).
        fallback_sitekey: Used if detect-JS finds no sitekey. For strict-Ashby
            this should be `6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y`.
        action: pageAction param. Ashby = 'submit', Greenhouse v3 varies.
        min_score: minScore hint passed to CapSolver.
        enterprise: True/False to force Enterprise endpoint. If None, auto-detected
            from the loader URL (enterprise.js → True).
        client: Pre-built CapSolverClient (for tests / shared session).

    Returns a dict with one of these shapes:
        {enabled: False, reason: ..., injected: False}
            — Solver disabled, no work done. Caller proceeds normally.
        {enabled: True, injected: False, reason: ..., detect: {...}}
            — Solver tried but failed (no sitekey, solver error, etc.).
              Caller MUST decide whether to abort or submit-anyway.
        {enabled: True, injected: True, sitekey: ..., token_len: N,
         inject: {...}, enterprise: bool}
            — Token injected successfully. Caller can click submit.

    NEVER raises on solver failures — always returns a dict. Re-raises only
    on programmer errors (e.g. frame is None and detect fails).
    """
    if not is_enabled():
        return _disabled_result(
            "ENABLE_CAPSOLVER!=1 or CAPSOLVER_API_KEY unset"
        )

    # 1. Detect sitekey from the live page.
    detect: dict = {}
    try:
        detect = frame.evaluate(JS_DETECT_RECAPTCHA_V3)
    except Exception as e:
        log.warning("captcha-presubmit detect-JS failed: %s", e)
        detect = {"error": f"{type(e).__name__}: {e}"}

    sitekey = (detect or {}).get("sitekey") or fallback_sitekey
    if not sitekey:
        return {
            "enabled": True,
            "injected": False,
            "reason": "no sitekey detected and no fallback provided",
            "detect": detect,
        }

    page_url_eff = page_url or (detect or {}).get("page_url") or ""
    if not page_url_eff:
        return {
            "enabled": True,
            "injected": False,
            "reason": "no page_url available",
            "detect": detect,
        }

    is_enterprise = (
        enterprise
        if enterprise is not None
        else bool((detect or {}).get("enterprise"))
    )

    # 2. Construct client lazily (raises CapSolverDisabled if env missing,
    #    but is_enabled() already guarded that).
    try:
        client = client or CapSolverClient()
    except CapSolverDisabled as e:
        return {
            "enabled": True,
            "injected": False,
            "reason": f"client construction failed: {e}",
            "detect": detect,
        }

    # 3. Solve.
    try:
        if is_enterprise:
            token = client.recaptcha_v3_enterprise(
                sitekey=sitekey,
                page_url=page_url_eff,
                action=action,
                min_score=min_score,
            )
        else:
            token = client.recaptcha_v3(
                sitekey=sitekey,
                page_url=page_url_eff,
                action=action,
                min_score=min_score,
            )
    except CapSolverError as e:
        log.warning("captcha-presubmit solve failed: %s", e)
        return {
            "enabled": True,
            "injected": False,
            "reason": f"solver error: {type(e).__name__}: {e}",
            "detect": detect,
            "sitekey": sitekey,
            "enterprise": is_enterprise,
        }

    # 4. Inject.
    try:
        inject = frame.evaluate(JS_INJECT_RECAPTCHA_V3, token)
    except Exception as e:
        log.warning("captcha-presubmit inject-JS failed: %s", e)
        return {
            "enabled": True,
            "injected": False,
            "reason": f"inject-JS failed: {type(e).__name__}: {e}",
            "detect": detect,
            "sitekey": sitekey,
            "enterprise": is_enterprise,
            "token_len": len(token),
        }

    return {
        "enabled": True,
        "injected": True,
        "sitekey": sitekey,
        "enterprise": is_enterprise,
        "token_len": len(token),
        "inject": inject,
        "detect": detect,
    }


def solve_and_inject_hcaptcha(
    frame: Any,
    *,
    page_url: Optional[str] = None,
    fallback_sitekey: Optional[str] = None,
    client: Optional[CapSolverClient] = None,
) -> dict:
    """Same shape as `solve_and_inject_recaptcha_v3` but for hCaptcha.

    Uses captcha_inject.JS_DETECT_HCAPTCHA + JS_INJECT_HCAPTCHA from the
    existing module (those payloads have been battle-tested).
    """
    if not is_enabled():
        return _disabled_result(
            "ENABLE_CAPSOLVER!=1 or CAPSOLVER_API_KEY unset"
        )

    # Lazy import — avoids dragging captcha_inject in for the recaptcha path.
    from captcha_inject import JS_DETECT_HCAPTCHA, JS_INJECT_HCAPTCHA

    try:
        detect = frame.evaluate(JS_DETECT_HCAPTCHA)
    except Exception as e:
        log.warning("captcha-presubmit hcaptcha detect-JS failed: %s", e)
        detect = {"error": f"{type(e).__name__}: {e}"}

    sitekey = (detect or {}).get("sitekey") or fallback_sitekey
    if not sitekey:
        return {
            "enabled": True,
            "injected": False,
            "reason": "no hcaptcha sitekey detected and no fallback provided",
            "detect": detect,
        }
    page_url_eff = page_url or (detect or {}).get("page_url") or ""
    if not page_url_eff:
        return {
            "enabled": True,
            "injected": False,
            "reason": "no page_url available",
            "detect": detect,
        }

    try:
        client = client or CapSolverClient()
    except CapSolverDisabled as e:
        return {
            "enabled": True,
            "injected": False,
            "reason": f"client construction failed: {e}",
            "detect": detect,
        }

    try:
        token = client.hcaptcha(sitekey=sitekey, page_url=page_url_eff)
    except CapSolverError as e:
        log.warning("captcha-presubmit hcaptcha solve failed: %s", e)
        return {
            "enabled": True,
            "injected": False,
            "reason": f"solver error: {type(e).__name__}: {e}",
            "detect": detect,
            "sitekey": sitekey,
        }

    try:
        inject = frame.evaluate(JS_INJECT_HCAPTCHA, token)
    except Exception as e:
        log.warning("captcha-presubmit hcaptcha inject-JS failed: %s", e)
        return {
            "enabled": True,
            "injected": False,
            "reason": f"inject-JS failed: {type(e).__name__}: {e}",
            "detect": detect,
            "sitekey": sitekey,
            "token_len": len(token),
        }

    return {
        "enabled": True,
        "injected": True,
        "sitekey": sitekey,
        "token_len": len(token),
        "inject": inject,
        "detect": detect,
    }
