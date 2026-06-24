#!/usr/bin/env python3
"""
captcha_inject.py — Helpers for injecting solved captcha tokens into a live
browser page.

The actual `evaluate` call must be performed by the caller (the inline-submit
runner uses the openclaw `browser` tool, while raw Playwright callers use
`page.evaluate(...)`). This module just exposes the JS payloads as strings,
plus a tiny convenience wrapper if a Playwright `page` is passed in.

Why two layers? `lever_filler.py` emits a *plan* of browser actions consumed
by another agent. So the JS strings here are appended to that plan. We do not
import Playwright unless someone calls `inject_hcaptcha_token(page, token)`
directly with a real `page` object.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# JS payloads (executed via browser.act.evaluate or page.evaluate)
# ---------------------------------------------------------------------------

# hCaptcha — sets every <textarea name="h-captcha-response"> AND
# <textarea name="g-recaptcha-response"> (some hCaptcha embeddings re-use the
# Google name for backward compat) using the native React-friendly setter so
# React/Vue forms see the change. Returns {found: N, set: N}.
JS_INJECT_HCAPTCHA = r"""
(token) => {
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
  const selectors = [
    'textarea[name="h-captcha-response"]',
    'textarea[name="g-recaptcha-response"]',
    'textarea[id^="h-captcha-response"]',
    'textarea[id^="g-recaptcha-response"]',
    'input[name="h-captcha-response"]',
    'input[name="g-recaptcha-response"]',
  ];
  const seen = new Set();
  let found = 0;
  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      if (seen.has(el)) continue;
      seen.add(el);
      found++;
      // Make hidden/zero-size textareas writable for React form libs that read
      // `.value` directly. We don't need them visible.
      if (el.style) {
        el.style.display = el.style.display === 'none' ? '' : el.style.display;
      }
      setNative(el, token);
    }
  }
  // Fire a global hCaptcha "verified" callback if present (some boards
  // register `window.hcaptcha._onVerify` or check `hcaptcha.getResponse()`).
  // We can't easily call internal callbacks, but setting the textarea is
  // sufficient for boards that read it on submit (Lever, Greenhouse, Ashby).
  return { found, set: found, token_len: (token || '').length };
}
"""

# reCAPTCHA v2 — same idea, target g-recaptcha-response only.
JS_INJECT_RECAPTCHA_V2 = r"""
(token) => {
  const setNative = (el, val) => {
    try {
      const proto = Object.getPrototypeOf(el);
      const setter = Object.getOwnPropertyDescriptor(proto, 'value');
      if (setter && setter.set) { setter.set.call(el, val); } else { el.value = val; }
    } catch (_e) { el.value = val; }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  let found = 0;
  for (const el of document.querySelectorAll('textarea[name="g-recaptcha-response"], textarea[id^="g-recaptcha-response"]')) {
    found++;
    if (el.style) el.style.display = '';
    setNative(el, token);
  }
  return { found, set: found, token_len: (token || '').length };
}
"""

# Cloudflare Turnstile — input[name="cf-turnstile-response"]
JS_INJECT_TURNSTILE = r"""
(token) => {
  const setNative = (el, val) => {
    try {
      const proto = Object.getPrototypeOf(el);
      const setter = Object.getOwnPropertyDescriptor(proto, 'value');
      if (setter && setter.set) { setter.set.call(el, val); } else { el.value = val; }
    } catch (_e) { el.value = val; }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  let found = 0;
  for (const el of document.querySelectorAll('input[name="cf-turnstile-response"], textarea[name="cf-turnstile-response"]')) {
    found++; setNative(el, token);
  }
  return { found, set: found, token_len: (token || '').length };
}
"""

# Detect hCaptcha sitekey on the page. Returns {sitekey, page_url, found_iframes}.
# Useful for the runner: read this once, hand the sitekey to the solver, then
# inject the returned token.
JS_DETECT_HCAPTCHA = r"""
() => {
  // Common patterns:
  //   <div class="h-captcha" data-sitekey="...">
  //   <div data-hcaptcha-widget-id ... data-sitekey="...">
  //   <iframe src="https://newassets.hcaptcha.com/captcha/v1/.../hcaptcha.html#frame=challenge&id=...&sitekey=...">
  let sitekey = null;
  for (const el of document.querySelectorAll('[data-sitekey]')) {
    const candidate = el.getAttribute('data-sitekey');
    if (candidate && /^[0-9a-f-]{8,}$/i.test(candidate)) { sitekey = candidate; break; }
  }
  if (!sitekey) {
    for (const f of document.querySelectorAll('iframe[src*="hcaptcha.com"]')) {
      const m = (f.src || '').match(/[?&#]sitekey=([0-9a-f-]+)/i);
      if (m) { sitekey = m[1]; break; }
    }
  }
  const enclaves = document.querySelectorAll('iframe[src*="hcaptcha-enclave"]').length;
  const challenge = document.querySelectorAll('iframe[src*="hcaptcha.html"]').length;

  // hCaptcha ENTERPRISE rqdata extraction (2026-06-05). Enterprise/invisible
  // widgets generate per-session challenge data (`rqdata`) that MUST be passed
  // to the solver as enterprisePayload.rqdata, or the solved token is
  // valid-but-unbound and the apply-POST 400s (reproduced on FloQast +
  // PointClickCare, shared sitekey e33f87f8-...). Try several known carriers,
  // most-reliable first:
  let rqdata = null;
  try {
    // (a) data attribute on the widget container/iframe.
    for (const el of document.querySelectorAll('[data-hcaptcha-rqdata],[data-rqdata]')) {
      const v = el.getAttribute('data-hcaptcha-rqdata') || el.getAttribute('data-rqdata');
      if (v) { rqdata = v; break; }
    }
    // (b) captured render/execute config (set by the page-init hook below, if
    //     it ran before render: window.__hcaptchaRqData).
    if (!rqdata && window.__hcaptchaRqData) rqdata = window.__hcaptchaRqData;
    // (c) hCaptcha internal config blob: window.hcaptcha may expose the last
    //     render params; also scan a global config object some hosts set.
    if (!rqdata) {
      const blobs = [];
      try { if (window.hcaptcha && window.hcaptcha.getRespKey) blobs.push(window.hcaptcha); } catch(e){}
      for (const k of ['__hcaptchaConfig','hcaptchaConfig','rqdata']) {
        try { if (window[k]) blobs.push(window[k]); } catch(e){}
      }
      for (const b of blobs) {
        try {
          const s = JSON.stringify(b);
          const m = s && s.match(/"rqdata"\s*:\s*"([^"]+)"/);
          if (m) { rqdata = m[1]; break; }
        } catch(e){}
      }
    }
    // (d) last resort: scan inline <script> text for an rqdata string literal.
    if (!rqdata) {
      for (const sc of document.querySelectorAll('script:not([src])')) {
        const m = (sc.textContent || '').match(/["']rqdata["']\s*:\s*["']([^"']{16,})["']/);
        if (m) { rqdata = m[1]; break; }
      }
    }
  } catch (e) {}

  return {
    sitekey,
    page_url: location.href,
    enclaves,
    challenge_iframes: challenge,
    visible_challenge: challenge > 0,
    rqdata: rqdata || null,
    is_enterprise: !!rqdata,
  };
}
"""


# Page-init hook to CAPTURE hCaptcha Enterprise rqdata at render time. Some
# hosts pass rqdata only as an argument to hcaptcha.render()/execute() and never
# leave it in the DOM, so JS_DETECT_HCAPTCHA's DOM/blob scan misses it. Install
# this via page.add_init_script(...) BEFORE the page loads: it wraps render and
# execute to stash any `rqdata` they receive on window.__hcaptchaRqData, where
# the detect fn (carrier b) then reads it. No-op if hCaptcha isn't enterprise.
JS_HOOK_HCAPTCHA_RQDATA = r"""
() => {
  try {
    window.__capturedHcaptchaToken = null;
    const stash = (cfg) => {
      try {
        if (cfg && typeof cfg === 'object' && cfg.rqdata) {
          window.__hcaptchaRqData = cfg.rqdata;
        }
      } catch (e) {}
    };
    const captureToken = (result) => {
      try {
        let tok = null;
        if (result && typeof result === 'object' && result.response) tok = result.response;
        else if (typeof result === 'string' && result.length > 20) tok = result;
        if (tok) {
          window.__capturedHcaptchaToken = tok;
          console.log('[hcaptcha-hook] captured token len=' + tok.length);
        }
      } catch(e) {}
    };
    let _h = window.hcaptcha;
    const wrap = (h) => {
      if (!h || h.__rqWrapped) return h;
      try {
        const _render = h.render;
        if (typeof _render === 'function') {
          h.render = function (el, cfg) { stash(cfg); return _render.apply(this, arguments); };
        }
        const _execute = h.execute;
        if (typeof _execute === 'function') {
          h.execute = function (idOrCfg, cfg) {
            stash(cfg); stash(idOrCfg);
            let result;
            try { result = _execute.apply(this, arguments); } catch(e) { throw e; }
            // Capture token from sync or promise result
            if (result && typeof result.then === 'function') {
              result.then(captureToken).catch(()=>{});
            } else {
              captureToken(result);
            }
            return result;
          };
        }
        // Also hook getResponse to capture any token the widget already has
        const _gr = h.getResponse;
        if (typeof _gr === 'function' && !h.__grHooked) {
          h.getResponse = function(wid) {
            const r = _gr.apply(this, arguments);
            if (r && r.length > 20) captureToken(r);
            return r;
          };
          h.__grHooked = true;
        }
        h.__rqWrapped = true;
      } catch (e) {}
      return h;
    };
    if (_h) { wrap(_h); }
    // hCaptcha loads async: trap the assignment so we wrap it when it appears.
    Object.defineProperty(window, 'hcaptcha', {
      configurable: true,
      get() { return _h; },
      set(v) { _h = wrap(v); },
    });
  } catch (e) {}
}
"""


# ---------------------------------------------------------------------------
# Optional Playwright convenience wrapper
# ---------------------------------------------------------------------------

def inject_hcaptcha_token(page_or_target: Any, token: str) -> bool:
    """
    Inject an hCaptcha token into the given page. Accepts a Playwright `Page`
    (anything with an `evaluate` method) or an openclaw browser target dict
    (we just return False in that case — the caller must dispatch the JS via
    the browser tool).

    Returns True if at least one textarea was found and set.
    """
    if hasattr(page_or_target, "evaluate"):
        try:
            result = page_or_target.evaluate(JS_INJECT_HCAPTCHA, token)
        except Exception:
            return False
        # Sync vs async page: result may be a coroutine in async mode. We
        # don't await here on purpose — async callers should call this
        # function's coroutine equivalent themselves. For now, only sync
        # Playwright `Page.evaluate` is supported via this convenience path.
        if isinstance(result, dict):
            return int(result.get("set", 0)) > 0
        return False
    return False


def emit_hcaptcha_inject_step(label: str, token: str, comment: str | None = None) -> dict:
    """Build a single browser.act.evaluate step for the openclaw runner."""
    return {
        "tool": "browser.act.evaluate",
        "args": {
            "label": label,
            "fn": JS_INJECT_HCAPTCHA,
            "arg": token,
            "comment": comment or "Inject solved hCaptcha token into h-captcha-response textarea(s).",
        },
    }


def emit_hcaptcha_detect_step(label: str, comment: str | None = None) -> dict:
    return {
        "tool": "browser.act.evaluate",
        "args": {
            "label": label,
            "fn": JS_DETECT_HCAPTCHA,
            "comment": comment or "Detect hCaptcha sitekey + page_url for solver dispatch.",
        },
    }
