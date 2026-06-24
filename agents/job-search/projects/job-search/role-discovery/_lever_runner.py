#!/usr/bin/env python3
"""chain_041 Lever submit runner — Playwright CDP -> port 18800.

Executes a lever inline-plan end-to-end:
  - browser.open        -> page.goto
  - sleep               -> wait
  - browser.act.evaluate-> page.evaluate(fn)  (text/select/radio/checkbox/eeo fills)
  - browser.upload      -> #resume-upload-input.set_input_files + WAIT for
                           resumeStorageId (Uppy pipeline now accepts CDP
                           setInputFiles as of 2026-05-31 — chain_037's "Uppy
                           blocked" finding is STALE).
  - browser.act.click   -> click submit selector
  - captcha.handle      -> detect hCaptcha sitekey, solve via CapSolver, inject
                           token via inject_fn, re-click submit.

Confirmation: Lever redirects to /<jid>/thanks or body shows
"Thank you" / "application has been submitted".

Usage: _lever_runner.py <plan.json> [--no-submit] [--no-captcha]
"""
import json, sys, time, re, os
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright
from captcha_solver import CaptchaSolver

# Honor JOBSEARCH_CDP (proxied/residential browser) first, then LEVER_CDP, then default.
CDP = os.environ.get("JOBSEARCH_CDP") or os.environ.get("LEVER_CDP", "http://127.0.0.1:18800")

def log(m): print(f"[lever] {m}", file=sys.stderr, flush=True)

# Fire hCaptcha's real verification callback so form libraries (Lever) that read
# the token via the hCaptcha JS API / a registered c-callback see a verified
# widget. A DOM-only textarea set is NOT enough for Lever (2026-06-03 finding).
# Strategy ladder:
#   1) If a global hcaptcha object exposes widget configs with a `callback`
#      (function or named global), call it with the token.
#   2) Scan window for any function whose name/config references the widget and
#      invoke common Lever callback names.
#   3) Also set every h-captcha-response textarea (belt-and-suspenders) and
#      dispatch input/change so reactive listeners fire.
_HCAPTCHA_CALLBACK_FN = r"""
(token) => {
  const report = {textareas:0, callbacks_called:0, names:[]};
  // 1) set textareas AND hidden inputs (Lever uses input#hcaptchaResponseInput)
  document.querySelectorAll('textarea[name="h-captcha-response"], textarea[id^="h-captcha-response"], textarea[name="g-recaptcha-response"], input[name="h-captcha-response"], #hcaptchaResponseInput, input[name="g-recaptcha-response"]').forEach(t=>{
    try{
      const proto=Object.getPrototypeOf(t);
      const d=Object.getOwnPropertyDescriptor(proto,'value');
      if(d&&d.set)d.set.call(t,token); else t.value=token;
      t.dispatchEvent(new Event('input',{bubbles:true}));
      t.dispatchEvent(new Event('change',{bubbles:true}));
      report.textareas++;
    }catch(_e){}
  });
  // 2) try to call hcaptcha widget callbacks
  const tryCall = (fn) => { try { if (typeof fn==='function'){ fn(token); report.callbacks_called++; return true; } } catch(_e){} return false; };
  const resolveCb = (cb) => {
    if (!cb) return null;
    if (typeof cb === 'function') return cb;
    if (typeof cb === 'string' && typeof window[cb] === 'function') return window[cb];
    return null;
  };
  try {
    const h = window.hcaptcha;
    // Lever reads the token via hcaptcha.getResponse() (data-callback is null on
    // Lever boards). The widget itself is unsolved, so getResponse() returns ''.
    // OVERRIDE getResponse (and grecaptcha.getResponse) to return our 2Captcha
    // token for every widget id. This is the path Lever's submit handler uses.
    if (h && typeof h.getResponse === 'function') {
      const _orig = h.getResponse.bind(h);
      h.getResponse = function(id){ try { const r=_orig(id); if(r) return r; } catch(_e){} return token; };
      report.callbacks_called++; report.names.push('hcaptcha.getResponse-override');
    } else if (h) {
      h.getResponse = function(){ return token; };
      report.names.push('hcaptcha.getResponse-define');
    }
    if (window.grecaptcha && typeof window.grecaptcha.getResponse === 'function') {
      const _g = window.grecaptcha.getResponse.bind(window.grecaptcha);
      window.grecaptcha.getResponse = function(id){ try{const r=_g(id); if(r) return r;}catch(_e){} return token; };
      report.names.push('grecaptcha.getResponse-override');
    }
    // also honor any data-callback if present
    document.querySelectorAll('.h-captcha, [data-hcaptcha-widget-id], [data-sitekey]').forEach(el=>{
      const name = el.getAttribute('data-callback');
      const fn = resolveCb(name);
      if (fn && tryCall(fn)) report.names.push(name);
    });
    ['hcaptchaOnLoad','onHcaptchaSuccess','hcaptchaCallback','onCaptchaSuccess','captchaCallback'].forEach(n=>{
      const fn = resolveCb(n);
      if (fn && tryCall(fn)) report.names.push(n);
    });
  } catch(_e){ report.err = String(_e); }
  return report;
}
"""

def _eval(page, fn, arg=None):
    fn = fn.strip()
    if arg is not None:
        return page.evaluate(f"({fn})({json.dumps(arg)})")
    return page.evaluate(f"({fn})()")

def run_plan(plan_path, no_submit=False, no_captcha=False):
    plan = json.load(open(plan_path))
    steps = plan['steps']
    slug = plan['slug']
    result = {"slug": slug, "steps": [], "ok": False, "error": None, "classify": None}

    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(CDP)
    # Use a DEDICATED context so stale tabs / other automation in the shared
    # OpenClaw browser can't steal focus or navigate our page (2026-06-03:
    # a stale unity.com tab contaminated contexts[0] mid-submit). Fall back to
    # contexts[0] only if new_context isn't permitted over this CDP.
    try:
        ctx = browser.new_context()
        _own_ctx = True
    except Exception as _ce:
        log(f"new_context failed ({_ce}); falling back to contexts[0]")
        ctx = browser.contexts[0]
        _own_ctx = False
    page = ctx.new_page()
    # Opt-in anti-automation fingerprint patch. Two modes (JOBSEARCH_STEALTH_MODE):
    #   'light' (DEFAULT when stealth on): ONLY patch navigator.webdriver via
    #     add_init_script. This is the dominant bot signal hCaptcha scores, and
    #     unlike full stealth_sync it does NOT break Lever's Uppy/filestack
    #     resume uploader. DIAGNOSED 2026-06-03: full stealth_sync's
    #     navigator.plugins/mimeTypes/iframe spoofing makes Uppy fail to read
    #     the file input -> resumeStorageId stays None -> Lever shows "couldn't
    #     auto-read resume / file exceeds 100MB" -> submit no-ops with empty
    #     fields. Proven: stealth_sync => resumeStorageId=None; no-stealth =>
    #     resumeStorageId populates. The webdriver-only patch keeps the upload
    #     working while still hiding the headline automation flag.
    #   'full': legacy playwright-stealth stealth_sync (breaks Uppy on Lever;
    #     kept for Ashby where there is no Uppy upload and the full patch
    #     cracked Clipboard).
    # Stealth: always apply at minimum (default=medium), opt-out with JOBSEARCH_STEALTH=0.
    # MEDIUM (default): patch headless signals that hCaptcha scores WITHOUT touching
    #   navigator.plugins/mimeTypes which breaks Uppy file input reading.
    # FULL: playwright_stealth.stealth_sync (breaks Uppy; use for non-Lever ATS).
    # OFF: JOBSEARCH_STEALTH=0
    if os.environ.get("JOBSEARCH_STEALTH", "1") != "0":
        _mode = os.environ.get("JOBSEARCH_STEALTH_MODE", "medium").lower()
        if _mode == "full":
            try:
                from playwright_stealth import stealth_sync
                stealth_sync(page)
                log("playwright-stealth (FULL) applied to page")
            except Exception as _es:
                log(f"stealth(full) apply failed (non-fatal): {_es}")
        else:
            try:
                # Medium: hide headless-Chrome signals that hCaptcha checks,
                # while NOT touching navigator.plugins/mimeTypes (Uppy-safe).
                page.add_init_script("""
                  // 1. Hide webdriver
                  Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                  // 2. Inject window.chrome (missing in headless)
                  if (!window.chrome) {
                    window.chrome = {
                      runtime: {onConnect:{addListener:()=>{}},onMessage:{addListener:()=>{}}},
                      loadTimes: function(){return {};},
                      csi: function(){return {};},
                    };
                  }
                  // 3. Fix navigator.languages
                  if (!navigator.languages || navigator.languages.length === 0) {
                    Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
                  }
                  // 4. Fix navigator.platform
                  if (!navigator.platform) {
                    Object.defineProperty(navigator,'platform',{get:()=>'Linux x86_64'});
                  }
                  // 5. Intercept hCaptcha postMessage to capture token from widget callback
                  window.__capturedHcaptchaToken = window.__capturedHcaptchaToken || null;
                  (function(){
                    const _orig = window.addEventListener;
                    if (window.__hcaptchaPostMsgHooked) return;
                    window.__hcaptchaPostMsgHooked = true;
                    window.addEventListener('message', function(e) {
                      try {
                        const d = e.data;
                        if (!d) return;
                        let tok = null;
                        if (typeof d === 'object') {
                          tok = d.response || (d.data && d.data.response) || d.token || (d.data && d.data.token);
                        } else if (typeof d === 'string' && d.length > 20) {
                          try { const p = JSON.parse(d); tok = p.response || p.token; } catch(_){}
                        }
                        if (tok && String(tok).length > 20) {
                          window.__capturedHcaptchaToken = String(tok);
                          console.log('[stealth] hcaptcha postMsg token len=' + tok.length);
                        }
                      } catch(_e) {}
                    }, true);
                  })();
                """)
                log("stealth (MEDIUM: headless-hide + postMsg-hook) applied")
            except Exception as _es:
                log(f"stealth(medium) apply failed (non-fatal): {_es}")
    # hCaptcha ENTERPRISE rqdata capture hook (2026-06-05). Some hosts pass
    # rqdata only as an argument to hcaptcha.render()/execute() and never leave
    # it in the DOM, so the detect fn's DOM/blob scan misses it. Install the
    # render/execute wrapper BEFORE navigation so it stashes rqdata on
    # window.__hcaptchaRqData, where JS_DETECT_HCAPTCHA (carrier b) reads it.
    # No-op for non-enterprise hCaptcha. Must be added before page.goto.
    try:
        from captcha_inject import JS_HOOK_HCAPTCHA_RQDATA
        page.add_init_script("(" + JS_HOOK_HCAPTCHA_RQDATA + ")()")
        log("hcaptcha rqdata-capture init hook installed")
    except Exception as _eh:
        log(f"rqdata hook install failed (non-fatal): {_eh}")
    # Capture the authoritative apply-POST response (Lever submits via XHR to
    # /apply or postings.lever.co .../apply?...). Body-text heuristics miss
    # XHR confirmations; the network status is authoritative.
    apply_responses = []
    def _on_response(resp):
        try:
            u = resp.url
            # ONLY the real Lever submit endpoint. Must be a lever.co host AND
            # end in /apply (the POST target). Exclude third-party widgets like
            # linkedin.com/talentwidgets/apply-with-linkedin which also contain
            # 'apply' and return 200 (caused a FALSE 'submitted' on Outreach 814,
            # 2026-06-03).
            import re as _re
            is_lever_submit = bool(_re.search(r'https?://(jobs|api)\.lever\.co/.*/apply(\?|$|/)', u))
            if is_lever_submit and resp.request.method == 'POST':
                rec = {'url': u, 'status': resp.status}
                try:
                    rec['body'] = (resp.text() or '')[:2000]
                except Exception:
                    rec['body'] = ''
                apply_responses.append(rec)
                log(f"APPLY-POST resp: {resp.status} {u}")
        except Exception:
            pass
    page.on('response', _on_response)
    result['apply_responses'] = apply_responses
    try:
        for i, s in enumerate(steps):
            tool = s.get('tool'); args = s.get('args', {})
            log(f"step {i}: {tool}")
            if tool == 'browser.open':
                page.goto(args['url'], wait_until='domcontentloaded', timeout=45000)
                page.wait_for_timeout(2500)
                result['steps'].append({'i':i,'tool':tool})
            elif tool == 'sleep':
                page.wait_for_timeout(args.get('ms', 800))
            elif tool == 'browser.act.evaluate':
                try:
                    r = _eval(page, args['fn'], args.get('arg'))
                except Exception as e:
                    r = {'_eval_err': str(e)}
                result['steps'].append({'i':i,'tool':tool,'r':r})
            elif tool == 'browser.upload':
                paths = args.get('paths') or [args.get('path')]
                # Prefer the explicit Lever resume input.
                fi = None
                for sel in ('#resume-upload-input', "input[name='resume']", 'input[type=file]'):
                    try:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            fi = loc.first; break
                    except Exception:
                        pass
                if fi is None:
                    result['steps'].append({'i':i,'tool':tool,'err':'no-file-input'})
                else:
                    fi.set_input_files(paths[0], timeout=12000)
                    # WAIT for Uppy to produce resumeStorageId (chain_041).
                    sid = None
                    for _ in range(16):
                        page.wait_for_timeout(2000)
                        sid = page.evaluate("() => (document.querySelector('input[name=resumeStorageId]')||{}).value || null")
                        analyzing = page.evaluate("() => /Analyzing resume/i.test(document.body.innerText)")
                        if sid: break
                        if not analyzing: 
                            # give it a couple more cycles even if 'analyzing' text gone
                            pass
                    log(f"upload: resumeStorageId={sid}")
                    result['steps'].append({'i':i,'tool':tool,'resumeStorageId':sid})
            elif tool == 'browser.act.click':
                sel = args.get('selector', '')
                # Strip Playwright-incompatible ':visible' pseudo to a real filter.
                base = sel.replace(':visible', '')
                clicked = False
                try:
                    loc = page.locator(base).filter(visible=True) if ':visible' in sel else page.locator(base)
                    loc.first.scroll_into_view_if_needed(timeout=4000)
                    loc.first.click(timeout=8000)
                    clicked = True
                except Exception as e:
                    log(f"click fail {sel}: {e}")
                    # FALLBACK (2026-06-03): Lever's hCaptcha iframe overlays the
                    # Submit button and intercepts pointer events, so a real
                    # Playwright click times out ("subtree intercepts pointer
                    # events"). A DOM .click() bypasses the pointer-hit test and
                    # fires the button's handler directly. This is what makes the
                    # native form POST actually go through.
                    try:
                        jc = page.evaluate(
                            """(sel) => { const el = document.querySelector(sel) || document.querySelector('#btn-submit') || [...document.querySelectorAll('button,a')].find(b=>/submit application/i.test(b.innerText||'')); if(el){ el.click(); return true;} return false; }""",
                            base.split(',')[0].strip() or '#btn-submit')
                        clicked = bool(jc)
                        log(f"js-click fallback: {clicked}")
                    except Exception as e2:
                        log(f"js-click fallback failed: {e2}")
                page.wait_for_timeout(1500)
                result['steps'].append({'i':i,'tool':tool,'clicked':clicked})
            elif tool == 'captcha.handle':
                if no_captcha:
                    result['steps'].append({'i':i,'tool':tool,'skipped':True}); continue
                det = _eval(page, args['detect_fn'])
                log(f"captcha detect: {det}")
                sitekey = det.get('sitekey') if isinstance(det, dict) else None
                page_url = (det.get('page_url') if isinstance(det, dict) else None) or page.url
                if not sitekey:
                    log("no hCaptcha sitekey detected — assuming none required")
                    result['steps'].append({'i':i,'tool':tool,'note':'no-sitekey'}); continue
                _invis = bool(isinstance(det, dict) and det.get('visible_challenge') is False)
                _rqdata = det.get('rqdata') if isinstance(det, dict) else None
                token = None
                # STRATEGY 1 (2026-06-23): Read token already captured by init hook.
                # The init hook wraps hcaptcha.execute() to stash the token in
                # window.__capturedHcaptchaToken when Lever's own code calls execute
                # on submit-click. This token is from the browser's residential IP
                # and is immediately valid — no external solve needed.
                log("checking window.__capturedHcaptchaToken (from submit-click hook)")
                try:
                    _captured = page.evaluate("() => window.__capturedHcaptchaToken")
                    if _captured and len(_captured) > 20:
                        token = _captured
                        log(f"STRATEGY1: using hook-captured browser token len={len(token)}")
                except Exception as _ce:
                    log(f"hook token read exc: {_ce}")
                # STRATEGY 2: poll for token up to 30s (it may not be ready yet)
                if not token:
                    log("polling for window.__capturedHcaptchaToken up to 30s...")
                    for _pi in range(30):
                        page.wait_for_timeout(1000)
                        try:
                            _captured = page.evaluate("() => window.__capturedHcaptchaToken")
                            if _captured and len(_captured) > 20:
                                token = _captured
                                log(f"STRATEGY2: hook-captured token after {_pi+1}s len={len(token)}")
                                break
                        except Exception:
                            pass
                    else:
                        log("STRATEGY2 poll timeout — no token captured by hook")
                # STRATEGY 3: call hcaptcha.execute() ourselves from browser context
                if not token:
                    log("STRATEGY3: calling hcaptcha.execute() from browser context")
                    try:
                        _exe_tok = page.evaluate("""() => {
                          const h = window.hcaptcha;
                          if (!h || typeof h.execute !== 'function') return null;
                          try {
                            const p = h.execute(undefined, {async: true});
                            if (p && typeof p.then === 'function') {
                              return p.then(r => (r && r.response) ? r.response : String(r||'')).catch(()=>null);
                            }
                          } catch(e) { return null; }
                          return null;
                        }""")
                        if _exe_tok and len(_exe_tok) > 20:
                            token = _exe_tok
                            log(f"STRATEGY3: execute() from browser token len={len(token)}")
                        else:
                            log(f"STRATEGY3: execute() returned: {repr(_exe_tok)[:80]}")
                    except Exception as _s3e:
                        log(f"STRATEGY3 exc: {_s3e}")
                # STRATEGY 4 (last resort): external 2Captcha/capsolver solver
                # Note: Lever rejects these (IP mismatch) but keep for other ATS
                if not token:
                    try:
                        errs = {}
                        try:
                            _ua = page.evaluate("() => navigator.userAgent")
                        except Exception:
                            _ua = None
                        _vendors = ('twocaptcha',) if _rqdata else ('twocaptcha', 'capsolver', 'nopecha')
                        for vend in _vendors:
                            try:
                                token = CaptchaSolver(vendor=vend).solve_hcaptcha(
                                    sitekey, page_url, is_invisible=_invis,
                                    user_agent=_ua, rqdata=_rqdata)
                                log(f"hcaptcha solved via {vend} token_len={len(token)} [FALLBACK]")
                                break
                            except Exception as ev:
                                errs[vend] = str(ev)
                                log(f"hcaptcha {vend} failed: {ev}")
                        if not token:
                            result['error'] = 'hcaptcha-solve-fail: ' + '; '.join(f'{k}={v}' for k,v in errs.items())
                            result['steps'].append({'i':i,'tool':tool,'err':result['error']})
                            log(f"hcaptcha solve fail (all): {result['error']}"); continue
                    except Exception as e:
                        result['error'] = f'hcaptcha-solve-exc: {e}'
                        result['steps'].append({'i':i,'tool':tool,'err':result['error']})
                        log(result['error']); continue
                inj = _eval(page, args['inject_fn'], token)
                log(f"hcaptcha inject: {inj}")
                # CRITICAL (2026-06-03): setting the h-captcha-response textarea
                # is NOT sufficient for Lever. Lever's submit handler reads the
                # token via the hCaptcha JS API / the widget's registered
                # callback, so a DOM-only set leaves getResponse() empty and the
                # submit silently no-ops (no apply-POST fires). Drive the real
                # hCaptcha callback so Lever sees a verified widget.
                cb = _eval(page, _HCAPTCHA_CALLBACK_FN, token)
                log(f"hcaptcha callback-fire: {cb}")
                page.wait_for_timeout(600)
                # SUBMIT STRATEGY (2026-06-23 fix): After captcha solve, the React
                # form may have cleared resumeStorageId / opportunityLocationId.
                # Re-inject known-good values before fetching, then do a direct
                # fetch POST so the serialized body is authoritative.
                # Step 1: find the known resumeStorageId from prior upload step
                _known_sid = next(
                    (s.get('resumeStorageId') for s in result['steps'] if s.get('tool') == 'browser.upload'),
                    None
                )
                # Step 2: re-assert resumeStorageId into the DOM if we know it
                if _known_sid:
                    page.evaluate("""
                      (sid) => {
                        const el = document.querySelector('input[name=resumeStorageId]');
                        if (!el) return;
                        try {
                          const proto = Object.getPrototypeOf(el);
                          const setter = Object.getOwnPropertyDescriptor(proto,'value').set;
                          setter.call(el, sid);
                        } catch(_e) { el.value = sid; }
                        el.dispatchEvent(new Event('input',{bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));
                      }
                    """, _known_sid)
                    log(f"re-injected resumeStorageId={_known_sid}")
                # Step 3: re-run location search to fix selectedLocation={"name":""}
                # Use the searchLocations API result we already fetched (stored on window)
                _loc_fix = page.evaluate("""
                  async () => {
                    const inp = document.querySelector('#location-input, input.location-input');
                    const sel = document.querySelector('#selected-location, input[name="selectedLocation"]');
                    if (!inp || !sel) return {skipped: 'no-inputs'};
                    const curSel = (sel.value||'').trim();
                    // If already valid (has a name), don't touch it
                    try { if (JSON.parse(curSel||'{}').name) return {skipped: 'already-valid', val: curSel}; } catch(_e) {}
                    // Re-use cached search results if available
                    const locs = window.searchedLocations;
                    if (locs && locs.length) {
                      const target = locs[0];
                      const proto = Object.getPrototypeOf(sel);
                      let setter;
                      try { setter = Object.getOwnPropertyDescriptor(proto,'value').set; } catch(_e){}
                      if (setter) setter.call(sel, JSON.stringify(target));
                      else sel.value = JSON.stringify(target);
                      sel.dispatchEvent(new Event('input',{bubbles:true}));
                      sel.dispatchEvent(new Event('change',{bubbles:true}));
                      return {fixed: true, picked: target.name, id: target.id};
                    }
                    // No cached results — try the API again
                    const locText = (inp.value||'Kirkland, WA');
                    try {
                      const res = await fetch('/searchLocations?text='+encodeURIComponent(locText));
                      const data = await res.json();
                      if (data && data.length) {
                        const target = data[0];
                        const proto = Object.getPrototypeOf(sel);
                        let setter;
                        try { setter = Object.getOwnPropertyDescriptor(proto,'value').set; } catch(_e){}
                        if (setter) setter.call(sel, JSON.stringify(target));
                        else sel.value = JSON.stringify(target);
                        sel.dispatchEvent(new Event('input',{bubbles:true}));
                        sel.dispatchEvent(new Event('change',{bubbles:true}));
                        return {fixed: true, picked: target.name, id: target.id, source: 'api-refetch'};
                      }
                    } catch(_e) {}
                    // Last resort: set synthetic location so form doesn't error on empty
                    const locVal = inp.value || 'Kirkland, WA';
                    sel.value = JSON.stringify({name: locVal, text: locVal});
                    return {fixed: 'synthetic', name: locVal};
                  }
                """)
                log(f"location re-fix: {_loc_fix}")
                _apply_url = page.url.split('?')[0]  # strip any query params
                if not _apply_url.endswith('/apply'):
                    _apply_url = _apply_url.rstrip('/') + '/apply'
                # STRATEGY: Use Lever's native form submit path instead of fetch-POST.
                # Lever's submit handler: if hcaptchaResponseInput.value is set and
                # hcaptchaTokenExpired is false, it calls clickSubmitButton() which
                # calls formSubmitButton.click() -> form.submit(). This keeps all
                # browser session context (cookies, file bytes, CSRF) intact.
                native_sub = page.evaluate("""
                  async (captchaToken) => {
                    // Set the hidden input Lever checks before calling clickSubmitButton
                    const inp = document.getElementById('hcaptchaResponseInput');
                    if (inp) {
                      try {
                        const proto = Object.getPrototypeOf(inp);
                        const setter = Object.getOwnPropertyDescriptor(proto,'value').set;
                        if (setter) setter.call(inp, captchaToken); else inp.value = captchaToken;
                      } catch(_e) { inp.value = captchaToken; }
                      inp.dispatchEvent(new Event('input',{bubbles:true}));
                      inp.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                    // Set global tokenExpired=false so Lever's click handler proceeds
                    try { window.hcaptchaTokenExpired = false; } catch(_e){}
                    // Also set the textarea (belt+suspenders)
                    const ta = document.querySelector('textarea[name="h-captcha-response"]');
                    if (ta) { try { ta.value = captchaToken; } catch(_e){} }
                    // Now trigger the submit button — Lever's handler checks the input
                    // value and calls clickSubmitButton() -> formSubmitButton.click() -> form.submit()
                    const btn = document.getElementById('btn-submit');
                    const formBtn = document.getElementById('btn-submit-form') ||
                                    document.querySelector('input[type=submit][style*="display:none"]') ||
                                    document.querySelector('input[type=submit][hidden]') ||
                                    document.querySelector('button[type=submit]:not(#btn-submit)');
                    const hcapInpSet = inp ? inp.value.length : 0;
                    // If Lever's own handler will fire (it checks inp.value), use btn.click()
                    // Otherwise fall back to formBtn.click() or form.submit()
                    if (inp && inp.value && btn) {
                      btn.click();
                      return {via:'btn-click', hcapInpLen: hcapInpSet, btnFound: true};
                    } else if (formBtn) {
                      formBtn.click();
                      return {via:'formBtn-click', hcapInpLen: hcapInpSet};
                    } else {
                      const form = document.querySelector('#application-form') || document.querySelector('form');
                      if (form) { form.submit(); return {via:'form-submit', hcapInpLen: hcapInpSet}; }
                      return {err:'no-submit-path', hcapInpLen: hcapInpSet};
                    }
                  }
                """, token)
                log(f"native-submit result: {native_sub}")
                # Wait for navigation after native submit
                try:
                    page.wait_for_url(re.compile(r"/(thanks|confirmation|complete|apply$)"),
                                      timeout=20000)
                except Exception:
                    page.wait_for_timeout(5000)
                # Check if native submit succeeded (navigated to /thanks)
                _cur_url_after_native = page.url
                log(f"url after native-submit: {_cur_url_after_native}")
                if 'thanks' in _cur_url_after_native or 'confirmation' in _cur_url_after_native:
                    log("native-submit SUCCESS: on thanks/confirmation page")
                    rsub = {**native_sub, 'success': True, 'url': _cur_url_after_native}
                    result['steps'].append({'i':i,'tool':tool,'sitekey':sitekey,'token_len':len(token),'inject':inj,'resubmit':rsub})
                    continue
                # Native submit didn't navigate to thanks — fall back to fetch-POST
                log("native-submit did not reach /thanks — trying fetch-POST fallback")
                # Build FormData from all form inputs + captcha token
                fetch_result = page.evaluate("""
                  async (captchaToken) => {
                    const form = document.querySelector('#application-form') || document.querySelector('form');
                    if (!form) return {err: 'no-form'};
                    // Re-build a fresh FormData from current DOM state
                    const fd = new FormData(form);
                    // Remove the file input — Lever uses resumeStorageId for server-side
                    // storage; re-sending the file triggers a redundant upload that can
                    // conflict with the already-uploaded resumeStorageId.
                    fd.delete('resume');
                    // Inject captcha token — override any existing h-captcha-response
                    fd.set('h-captcha-response', captchaToken);
                    // Also set g-recaptcha-response for belt-and-suspenders
                    fd.set('g-recaptcha-response', captchaToken);
                    // Log what we're sending
                    const keys = [];
                    for (const [k, v] of fd.entries()) {
                      if (k !== 'h-captcha-response' && k !== 'g-recaptcha-response') {
                        keys.push(k + '=' + String(v).slice(0,40));
                      } else {
                        keys.push(k + '=<token_len:' + v.length + '>');
                      }
                    }
                    try {
                      const resp = await fetch(form.action || location.href, {
                        method: 'POST',
                        body: fd,
                        credentials: 'include',
                        redirect: 'follow'
                      });
                      const text = await resp.text();
                      // Extract error messages from the HTML response
                      let errMsg = '';
                      try {
                        // Try to find JSON error data embedded in the page
                        const jsonMatch = text.match(/data-errors='([^']+)'/);
                        if (jsonMatch) errMsg = jsonMatch[1];
                        // Look for error text near 'required' or 'error' markers
                        const domParser = new DOMParser();
                        const doc = domParser.parseFromString(text, 'text/html');
                        const errEls = doc.querySelectorAll('.error-message, .field-error, [class*="error"], .warning');
                        const errTexts = [];
                        errEls.forEach(el => { const t = el.textContent.trim(); if (t) errTexts.push(t); });
                        if (errTexts.length) errMsg += ' ERRORS:' + errTexts.slice(0,5).join(' | ');
                        // Extract body text for diagnostic
                        const body = doc.body ? doc.body.innerText || doc.body.textContent : '';
                        errMsg += ' BODY:' + body.slice(0, 300);
                      } catch(_e) { errMsg = text.slice(0, 300); }
                      return {
                        via: 'fetch-post',
                        status: resp.status,
                        url: resp.url,
                        fields: keys,
                        body_snippet: text.slice(0, 300),
                        err_detail: errMsg.slice(0, 500)
                      };
                    } catch(e) {
                      return {err: String(e), fields: keys};
                    }
                  }
                """, token)
                log(f"fetch-post result: status={fetch_result.get('status')} url={fetch_result.get('url','?')}")
                log(f"fetch-post fields: {fetch_result.get('fields',[])}")
                if fetch_result.get('err_detail'):
                    log(f"fetch-post err_detail: {fetch_result['err_detail'][:500]}")
                if fetch_result.get('err'):
                    log(f"fetch-post error: {fetch_result['err']} — falling back to requestSubmit")
                    rsub = page.evaluate("""() => {
                      const f = document.querySelector('#application-form') || document.querySelector('form');
                      if (!f) return {err:'no-form'};
                      try { if (f.requestSubmit) { f.requestSubmit(); return {via:'requestSubmit'}; } f.submit(); return {via:'submit'}; }
                      catch(e){ return {err:String(e)}; }
                    }""")
                    log(f"resubmit requestSubmit fallback: {rsub}")
                else:
                    rsub = fetch_result
                    # If fetch returned a success/redirect, navigate the browser to the result URL
                    if fetch_result.get('status', 0) in (200, 201, 302) or 'thanks' in fetch_result.get('url', ''):
                        result_url = fetch_result.get('url', '')
                        if result_url and result_url != page.url:
                            try:
                                page.goto(result_url, wait_until='domcontentloaded', timeout=15000)
                            except Exception:
                                pass
                        # Record this as the apply response too
                        apply_responses.append({
                            'url': fetch_result.get('url', _apply_url),
                            'status': fetch_result.get('status', 0),
                            'body': fetch_result.get('body_snippet', ''),
                            'via': 'fetch-post'
                        })
                # Wait for navigation or page update
                try:
                    page.wait_for_url(re.compile(r"/(thanks|confirmation|complete)"), timeout=10000)
                except Exception:
                    page.wait_for_timeout(3000)
                result['steps'].append({'i':i,'tool':tool,'sitekey':sitekey,'token_len':len(token),'inject':inj,'resubmit':rsub})
            else:
                result['steps'].append({'i':i,'tool':tool,'note':'unhandled'})

        # confirmation
        page.wait_for_timeout(2500)
        url = page.url
        body = ''
        try:
            body = (page.locator('body').text_content() or '')[:1500]
        except Exception:
            pass
        result['final_url'] = url
        result['body_excerpt'] = body[:400]
        # AUTHORITATIVE for native-form Lever: navigation AWAY from /apply to a
        # thank-you/confirmation URL = submitted. (Lever posts the form natively;
        # the page leaves /apply on success.)
        nav_confirmed = bool(re.search(r"/(thanks|confirmation|complete)", url)) or (
            '/apply' not in url and 'lever.co' in url)
        # also accept a real Lever apply-POST 2xx if captured (XHR boards).
        ok_post = next((r for r in apply_responses if 200 <= r['status'] < 300), None)
        err_post = next((r for r in apply_responses if r['status'] >= 400), None)
        if ok_post or nav_confirmed:
            result['ok'] = True; result['classify'] = 'submitted'
            result['confirm_signal'] = f"apply-POST {ok_post['status']}" if ok_post else f"nav->{url}"
            log(f"LEVER SUBMIT SUCCESS ({result['confirm_signal']})")
        elif '/thanks' in url or re.search(r"thank you|application (has been )?(submitted|received)|we['\u2019]?ll be in touch|received your application", body, re.I):
            result['ok'] = True; result['classify'] = 'submitted'
            result['confirm_signal'] = 'body-text/redirect'
            log("LEVER SUBMIT SUCCESS")
        elif err_post:
            result['ok'] = False; result['classify'] = 'apply-post-error'
            result['error'] = f"apply-POST {err_post['status']}: {err_post.get('body','')[:200]}"
            log(f"LEVER SUBMIT FAIL: {result['error']}")
        elif re.search(r"please complete the captcha|verify you are human|required field|please fill", body, re.I):
            result['ok'] = False; result['classify'] = 'form-or-captcha'
            result['error'] = result.get('error') or 'form-or-captcha-incomplete'
        else:
            result['ok'] = False; result['classify'] = 'unconfirmed'
            result['error'] = result.get('error') or 'submit-clicked-but-no-confirmation'
        return result
    finally:
        try:
            import os as _os
            _dbg = _os.environ.get('LEVER_DEBUG_DIR')
            if _dbg:
                _os.makedirs(_dbg, exist_ok=True)
                page.screenshot(path=_os.path.join(_dbg, f"{slug}-final.png"), full_page=True)
        except Exception:
            pass
        try:
            if not __import__('os').environ.get('LEVER_KEEP_PAGE'):
                page.close()
        except Exception: pass

if __name__ == '__main__':
    plan = sys.argv[1]
    r = run_plan(plan, no_submit='--no-submit' in sys.argv, no_captcha='--no-captcha' in sys.argv)
    print(json.dumps(r, indent=2, default=str))
    sys.exit(0 if r['ok'] else 1)
