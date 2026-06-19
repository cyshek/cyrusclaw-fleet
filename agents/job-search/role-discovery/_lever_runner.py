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
    if os.environ.get("JOBSEARCH_STEALTH", "0") == "1":
        _mode = os.environ.get("JOBSEARCH_STEALTH_MODE", "light").lower()
        if _mode == "full":
            try:
                from playwright_stealth import stealth_sync
                stealth_sync(page)
                log("playwright-stealth (FULL) applied to page")
            except Exception as _es:
                log(f"stealth(full) apply failed (non-fatal): {_es}")
        else:
            try:
                # Light: hide navigator.webdriver only (Uppy-safe).
                page.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                )
                log("stealth (LIGHT: webdriver-only) applied to page")
            except Exception as _es:
                log(f"stealth(light) apply failed (non-fatal): {_es}")
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
                try:
                    # 2026-06-03: 2Captcha is the PROVEN hCaptcha vendor (CapSolver
                    # discontinued hCaptcha). Try twocaptcha first, then capsolver/nopecha.
                    token = None
                    errs = {}
                    # PASSIVE/invisible hCaptcha (Lever: enclaves>=1 &&
                    # visible_challenge False) needs isInvisible + matching UA
                    # threaded to the solver or the server 400s the token
                    # (FloQast 2026-06-04).
                    _invis = bool(isinstance(det, dict) and det.get('visible_challenge') is False)
                    # hCaptcha ENTERPRISE rqdata (2026-06-05): if the page
                    # carries per-session challenge data, bind the solve to it
                    # via enterprisePayload or the token 400s at apply-POST
                    # (FloQast/PointClickCare shared-sitekey wall). Only
                    # 2Captcha can bind rqdata, so restrict vendors to it.
                    _rqdata = det.get('rqdata') if isinstance(det, dict) else None
                    if _rqdata:
                        log(f"hcaptcha ENTERPRISE rqdata detected (len={len(_rqdata)}) -> enterprisePayload bind")
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
                            log(f"hcaptcha solved via {vend} (token_len={len(token)} invisible={_invis} enterprise={bool(_rqdata)})")
                            break
                        except Exception as ev:
                            errs[vend] = str(ev)
                            log(f"hcaptcha {vend} failed: {ev}")
                    if not token:
                        result['error'] = 'hcaptcha-solve-fail: ' + '; '.join(f'{k}={v}' for k,v in errs.items())
                        result['steps'].append({'i':i,'tool':tool,'err':result['error']})
                        log(f"hcaptcha solve fail (all vendors): {result['error']}"); continue
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
                # SUBMIT: Lever's #btn-submit JS handler validates the hCaptcha
                # widget state and silently no-ops if it thinks it's unsolved
                # (even with a valid token in #hcaptchaResponseInput). Calling
                # form.requestSubmit() fires the NATIVE form POST directly and
                # bypasses that client gate — PROVEN to trigger the real /apply
                # POST (2026-06-03). The server still validates the token, so the
                # token must be solved on the SAME IP the browser egresses from
                # (run via the residential-proxied Chrome, LEVER_CDP=[::1]:18900).
                rsub = page.evaluate("""() => {
                  const f = document.querySelector('#application-form') || document.querySelector('form');
                  if (!f) return {err:'no-form'};
                  try { if (f.requestSubmit) { f.requestSubmit(); return {via:'requestSubmit'}; } f.submit(); return {via:'submit'}; }
                  catch(e){ return {err:String(e)}; }
                }""")
                log(f"resubmit requestSubmit: {rsub}")
                # Lever submits via native form POST -> full-page navigation to a
                # /thanks or confirmation URL. Wait for that navigation.
                try:
                    page.wait_for_url(re.compile(r"/(thanks|confirmation|complete)"), timeout=15000)
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
