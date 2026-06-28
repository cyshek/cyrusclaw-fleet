#!/usr/bin/env python3
"""
_icims_runner.py — iCIMS ATS apply runner (multi-tenant *.icims.com).

iCIMS career portals live at `careers-<company>.icims.com/jobs/<reqId>/<slug>/job`.
The JD page embeds the apply UI in an iframe (`?in_iframe=1`). Clicking "Apply for
this job online" routes to `/jobs/<reqId>/<slug>/login`, an **email-entry gate** —
you enter your email and the portal either recognizes an existing candidate account
(-> password) or starts a register-in-flow. From there it's a multi-section form:
personal info, resume upload (standard <input type=file>, set via CDP
set_input_files), EEO, and screening/knockout questions.

THIS RUNNER (like _tesla_runner) connects over CDP to the already-running OpenClaw
browser rather than launching its own — iCIMS tenants sit behind bot defenses and
the persistent profile carries candidate cookies for re-login. It drives the
JD -> Apply -> login/register -> form -> submit flow for the queued tenants.

=== EMAIL-OTP VERIFICATION (shipped 2026-06-20) ===
Effective Apr-2025 iCIMS Universal Login (Auth0) and the candidate career-portal
apply gate verify the candidate email with a **6-digit one-time code** emailed from
an icims.com host (`no-reply@icims.com` / `*@hire.icims.com` / `*@talent.icims.com`,
or Auth0-on-behalf-of-iCIMS). After the email-entry step the portal renders a
"Verification Code" input and mails the code. This runner now clears that gate
automatically via `handle_otp_gate()`:
  1. detect the OTP input (name/id/aria with otp|code|verification|pin, or a 6-cell
     segmented input, or body text "verification code" / "enter the code"),
  2. read the freshest 6-digit iCIMS code from Gmail (gmail_imap.wait_for_icims_otp,
     90s budget, app password at projects/job-search/.gmail-app-password),
  3. type it (segmented inputs filled per-cell) + click Verify/Continue/Submit,
  4. confirm the gate cleared. If no code arrives in the window -> EXIT 10.

=== KNOWN HARD WALL (verified live 2026-06-03, Joby careers-jobyaviation) ===
The iCIMS email-entry gate (`/login`, the FIRST step) is on some tenants ALSO
protected by an hCaptcha "Verify you are human" checkbox that PRECEDES the OTP.
Where that checkbox is a hard hCaptcha challenge (sitekey e.g.
`94fee806-5cac-4582-9738-384a0f4ea6f8`, a real `newassets.hcaptcha.com` frame),
submitting the email without a valid `h-captcha-response` token does nothing — the
page re-renders on `/login`. CapSolver discontinued hCaptcha (confirmed live: ERROR_INVALID_TASK_DATA)
but 2Captcha supports it and is configured (TWOCAPTCHA_API_KEY, $9+ balance). `try_solve_hcaptcha`
now tries twocaptcha first. The OTP handling runs the moment human-verification is passed
(a no-captcha tenant, a warmed/recognized profile where the checkbox auto-passes, or
once a vendor is provisioned) — NO further code change needed.

Other queued tenants are walled for DIFFERENT precise reasons (set per-row):
  - AMD (internal-amd.icims.com) / SiriusXM (employees-siriusxmradio.icims.com):
    INTERNAL employee SSO portals, no public req -> `icims-internal-sso-portal`.
  - Rivian: public apply = careers.rivian.com (custom/Phenom), the icims URL is the
    employee-internal one -> not a public iCIMS job (`not-public-icims`).
  - Paramount+: SmartRecruiters-class, not iCIMS (`not-icims-smartrecruiters`).

Usage:
  python3 _icims_runner.py --url <jobUrl> [--dryrun] [--debug DIR] [--cdp ...]
  --dryrun : drive the flow, fill what's reachable, stop before final Submit.

EXIT codes (consumed by inline_submit dispatch):
  0  = submitted / dryrun-ready
  2  = login/auth block (incl. hCaptcha-no-vendor, no-email-gate)
  3  = submitted but no confirmation observed
  4  = could not click submit (no submit button)
  5  = loop / time cap
  6  = requisition closed / removed
  7  = already applied
  10 = OTP timeout (gate detected, no 6-digit iCIMS code arrived within budget)
"""
import sys, os, time, json, argparse, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CDP_DEFAULT = "http://127.0.0.1:18800"
RESUME = os.path.abspath(os.path.join(HERE, "..", "resume", "Cyrus_Shekari_Resume.pdf"))

# ---- Identity (loaded from personal-info.json) ----------------------------
_PI_PATH = os.path.join(HERE, "..", "personal-info.json")
with open(_PI_PATH) as _f:
    _PI = json.load(_f)
FIRST = _PI["identity"]["first_name"]
LAST = _PI["identity"]["last_name"]
EMAIL = _PI["contact"]["email"]
PHONE = _PI["contact"]["phone"].replace("-", "")  # 10-digit no-dash
PHONE_FMT = _PI["contact"]["phone"]
ADDR_STREET = _PI["address"]["street"]
ADDR_CITY = _PI["address"]["city"]
ADDR_STATE = _PI["address"]["state"]
ADDR_ZIP = _PI["address"]["zip"]
ADDR_COUNTRY = _PI["address"].get("country", "United States")
LINKEDIN = _PI["contact"].get("linkedin", "https://linkedin.com/in/cyshekari")

# ---- Knockout / screening answer heuristics (TRUTHFUL only) ----------------
# Cyrus: US citizen, authorized to work in US, NO sponsorship now or future, no
# security clearance, open to relocate, travel 100%. Mirrors TOOLS.md Workday/
# Tesla heuristics. NEVER fabricate a biographical/knockout fact.
KNOCKOUT_ANSWERS = {
    "authorized_to_work_us": "yes",
    "require_sponsorship_now": "no",
    "require_sponsorship_future": "no",
    "us_citizen": "yes",
    "security_clearance": "no",
    "willing_to_relocate": "yes",
    "willing_to_travel": "yes",   # travel=100%
    "former_employee": "no",
    "18_or_older": "yes",
    "agree_terms": "yes",
}
EEO_DECLINE = "decline"  # privacy-respecting standard (matches Tesla runner)


def log(*a):
    print("[icims]", *a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Truthful knockout resolver. Given a question's visible text, return the answer
# token ('yes'/'no'/'decline') or None if unrecognized. Specific patterns first.
# ---------------------------------------------------------------------------
def resolve_knockout(question_text: str):
    q = (question_text or "").lower()
    if any(k in q for k in ("gender", "race", "ethnicity", "veteran", "disability",
                            "self-identify", "self identify")):
        return EEO_DECLINE
    if "sponsor" in q:                       # sponsorship now/future -> NO
        return "no"
    if ("authorized" in q or "authorization" in q or "legally" in q) and "work" in q:
        return "yes"
    if "eligible to work" in q or "right to work" in q:
        return "yes"
    if "citizen" in q:                       # US citizen -> YES
        return "yes"
    if "clearance" in q:                     # security clearance -> NO
        return "no"
    if "relocat" in q:
        return "yes"
    if "travel" in q:                        # travel 100% -> YES
        return "yes"
    if "former" in q and ("employee" in q or "employ" in q):
        return "no"
    if "previously" in q and ("employ" in q or "work" in q):
        return "no"
    if "18 years" in q or "at least 18" in q or "age of 18" in q:
        return "yes"
    if any(k in q for k in ("agree", "acknowledge", "consent", "i certify", "i confirm")):
        return "yes"
    return None


# ---- React-aware field setters (run in a frame) ---------------------------
JS_SET = r"""([sel,val])=>{
  const el=document.querySelector(sel);
  if(!el) return sel+':MISSING';
  const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype
              : el.tagName==='SELECT'?HTMLSelectElement.prototype
              : HTMLInputElement.prototype;
  const d=Object.getOwnPropertyDescriptor(proto,'value');
  el.scrollIntoView({block:'center'}); el.focus(); d.set.call(el,val);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.blur(); return sel+':ok';
}"""

JS_PICK = r"""([sel,val])=>{
  const el=document.querySelector(sel);
  if(!el) return sel+':MISSING';
  const want=String(val).toLowerCase();
  const opt=[...el.options].find(o=>o.value.toLowerCase()===want)
        || [...el.options].find(o=>o.textContent.trim().toLowerCase()===want)
        || [...el.options].find(o=>o.textContent.trim().toLowerCase().includes(want));
  if(!opt) return sel+':NOOPT:'+[...el.options].map(o=>o.textContent.trim()).slice(0,8).join('|');
  el.scrollIntoView({block:'center'});
  const d=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value');
  el.focus(); d.set.call(el,opt.value);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.blur(); return sel+'='+opt.value;
}"""

JS_RADIO_BY_LABEL = r"""([groupText,want])=>{
  const wantRe = want==='yes' ? /^\s*yes\s*$/i : want==='no' ? /^\s*no\s*$/i
              : new RegExp(want,'i');
  const radios=[...document.querySelectorAll('input[type=radio]')];
  for(const r of radios){
    let lbl = r.id ? document.querySelector('label[for="'+r.id+'"]') : null;
    if(!lbl){let p=r.parentElement;for(let i=0;i<3&&p&&!lbl;i++){lbl=p.tagName==='LABEL'?p:p.querySelector('label');p=p.parentElement;}}
    const txt=(lbl&&lbl.textContent||r.value||'').trim();
    if(wantRe.test(txt)){ r.scrollIntoView({block:'center'}); r.click(); return 'radio:'+txt+':'+r.checked; }
  }
  return 'radio:NOMATCH';
}"""

JS_CHECK = r"""(sel)=>{
  const el=document.querySelector(sel);
  if(!el) return sel+':NOCHK';
  if(el.checked) return sel+':already';
  el.scrollIntoView({block:'center'}); el.click();
  if(el.checked) return sel+':ok';
  let lbl=el.id?document.querySelector('label[for="'+el.id+'"]'):null;
  if(!lbl){let p=el.parentElement;for(let i=0;i<4&&p&&!lbl;i++){if(p.tagName==='LABEL'){lbl=p;break;}lbl=p.querySelector('label');p=p.parentElement;}}
  if(lbl) lbl.click();
  return sel+':'+el.checked;
}"""


def frame_eval(fr, fn, arg=None):
    try:
        return fr.evaluate(fn, arg) if arg is not None else fr.evaluate(fn)
    except Exception as e:
        return f"EVALERR:{e}"


def find_form_frame(page, selector):
    """Return the first frame containing `selector`, else None."""
    for fr in page.frames:
        try:
            if fr.evaluate("(s)=>!!document.querySelector(s)", selector):
                return fr
        except Exception:
            pass
    return None


def shot(page, debug_dir, name):
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    try:
        page.screenshot(path=os.path.join(debug_dir, name + ".png"), full_page=True)
    except Exception as e:
        log("shot fail", name, e)


# ---------------------------------------------------------------------------
# Terminal-state detection (already-applied / closed req)
# ---------------------------------------------------------------------------
def detect_terminal(page):
    txt = ""
    for fr in page.frames:
        try:
            txt += "\n" + fr.evaluate("()=>document.body.innerText")
        except Exception:
            pass
    low = txt.lower()
    if re.search(r"already (applied|submitted)|you have applied|previously applied", low):
        return "already_applied"
    if re.search(r"no longer (available|accepting)|position (has been )?(filled|closed)|"
                 r"requisition .{0,10}closed|this (job|position) is no longer|"
                 r"page (you are looking for )?(does not|doesn.t) exist|page not found", low):
        return "closed"
    return None


def detect_hcaptcha(page):
    """Return (present, sitekey) if an hCaptcha challenge gates the form."""
    for fr in page.frames:
        try:
            res = fr.evaluate(r"""()=>{
              const hcFrame=!!document.querySelector('iframe[src*="hcaptcha"]');
              const skEl=document.querySelector('[data-sitekey]');
              const respEl=document.querySelector('[name="h-captcha-response"],textarea[id^="h-captcha-response"]');
              return {hcFrame, sitekey: skEl?skEl.getAttribute('data-sitekey'):null,
                      hasResp:!!respEl, respFilled: respEl?!!respEl.value:false};
            }""")
            if res.get("hcFrame") or res.get("hasResp") or res.get("sitekey"):
                return True, res.get("sitekey")
        except Exception:
            pass
    return False, None


def detect_confirmation(page):
    for fr in page.frames:
        try:
            res = fr.evaluate(r"""()=>{
              const t=document.body.innerText;
              const conf=/thank you for (applying|your (interest|application))|application (has been|was|is) (received|submitted|complete)|we.{0,4}ve received your application|your application (has been|was) (submitted|received|sent)|successfully submitted|submission (complete|successful)|application complete/i.test(t);
              return {conf, head:t.slice(0,300), url:location.href};
            }""")
            if res.get("conf"):
                return res
        except Exception:
            pass
    return {"conf": False}


# ---------------------------------------------------------------------------
# Email-OTP verification gate (iCIMS Universal Login / Auth0, Apr-2025+).
# After the email-entry step iCIMS mails a 6-digit code and renders a code input.
# We detect it, read the code from Gmail, type it, and continue. EXIT 10 on no-code.
# ---------------------------------------------------------------------------
_OTP_DETECT_JS = r"""()=>{
  const all=[...document.querySelectorAll('input')];
  const vis=el=>{const r=el.getBoundingClientRect();const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
  const txt=el=>((el.name||'')+' '+(el.id||'')+' '+(el.getAttribute('aria-label')||'')+
    ' '+(el.placeholder||'')+' '+(el.getAttribute('autocomplete')||'')).toLowerCase();
  const codeRe=/otp|one[-_ ]?time|onetime|verification|verif(y|ication)?code|\bcode\b|passcode|pin|securitycode|mfa|2fa/;
  // 1. A single explicit code field.
  for(const el of all){
    if(!vis(el)) continue;
    const t=txt(el);
    if((el.type==='text'||el.type==='tel'||el.type==='number'||el.type==='')&&codeRe.test(t)){
      return {present:true, segmented:false, n:1, sel: el.id?('#'+CSS.escape(el.id)):
              (el.name?('input[name="'+el.name+'"]'):null), why:'named:'+t.trim().slice(0,40)};
    }
  }
  // 2. A segmented code input: 4-8 visible single-char text/number inputs in a row.
  const singles=all.filter(el=>vis(el)&&(el.type==='text'||el.type==='tel'||el.type==='number')&&
    (el.maxLength===1|| (el.getAttribute('maxlength')==='1')) );
  if(singles.length>=4 && singles.length<=8){
    return {present:true, segmented:true, n:singles.length, sel:null, why:'segmented:'+singles.length};
  }
  // 3. Body text indicates a code step (and we are NOT on the bare email-only step).
  const bt=(document.body.innerText||'').toLowerCase();
  const emailStep=/enter your email|email address/.test(bt) && !/verification|enter the code|we (sent|emailed)|6-digit|six-digit/.test(bt);
  const codeStep=/verification code|enter the code|we (sent|emailed|just sent)|6-digit code|six-digit code|one-time (code|passcode|password)|check your email for/.test(bt);
  if(codeStep && !emailStep){
    return {present:true, segmented:false, n:1, sel:null, why:'bodytext'};
  }
  return {present:false};
}"""

_OTP_FILL_SINGLE_JS = r"""([sel,val])=>{
  const el = sel ? document.querySelector(sel)
    : [...document.querySelectorAll('input')].find(e=>{
        const r=e.getBoundingClientRect();
        const t=((e.name||'')+' '+(e.id||'')+' '+(e.getAttribute('aria-label')||'')+' '+(e.placeholder||'')).toLowerCase();
        return r.width>0&&r.height>0&&/otp|code|verif|passcode|pin/.test(t);
      });
  if(!el) return 'OTP_INPUT_MISSING';
  const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
  el.scrollIntoView({block:'center'}); el.focus(); d.set.call(el,val);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.blur(); return 'ok:'+el.value;
}"""

_OTP_FILL_SEGMENTED_JS = r"""([digits])=>{
  const all=[...document.querySelectorAll('input')].filter(el=>{
    const r=el.getBoundingClientRect();const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&
      (el.type==='text'||el.type==='tel'||el.type==='number')&&
      (el.maxLength===1||el.getAttribute('maxlength')==='1');
  });
  if(all.length<digits.length) return 'SEG_TOO_FEW:'+all.length;
  const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
  for(let i=0;i<digits.length;i++){
    const el=all[i]; el.focus(); d.set.call(el,digits[i]);
    el.dispatchEvent(new Event('input',{bubbles:true}));
    el.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true,key:digits[i]}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
  }
  all[Math.min(digits.length,all.length)-1].blur();
  return 'seg_ok:'+digits.length;
}"""

_OTP_CONTINUE_JS = r"""()=>{
  const b=[...document.querySelectorAll('button,input[type=submit],input[type=button],a')]
    .find(x=>/^(verify|continue|submit|next|confirm|log ?in|sign ?in|verify code|verify email)$/i
      .test((x.value||x.textContent||'').trim()));
  if(b){b.scrollIntoView({block:'center'}); b.click(); return (b.value||b.textContent||'').trim();}
  return null;
}"""


def detect_otp_gate(page):
    """Scan all frames for an iCIMS email-OTP input. Returns
    {present, frame(_url), segmented, n, sel, why} (present False if none)."""
    for fr in page.frames:
        try:
            res = fr.evaluate(_OTP_DETECT_JS)
        except Exception:
            continue
        if res and res.get("present"):
            res["frame"] = fr.url
            res["_frame_obj"] = fr
            return res
    return {"present": False}


def fill_otp(fr, code, segmented=False, n=1):
    """Type the OTP code into a frame's code input(s). Single field or segmented
    per-cell. Returns the JS result string."""
    code = re.sub(r"\D", "", str(code or ""))
    if segmented:
        return frame_eval(fr, _OTP_FILL_SEGMENTED_JS, [list(code)])
    return frame_eval(fr, _OTP_FILL_SINGLE_JS, [None, code])


def click_otp_continue(page):
    """Click the Verify/Continue/Submit button on the OTP step (any frame)."""
    for fr in page.frames:
        r = frame_eval(fr, _OTP_CONTINUE_JS)
        if r and not str(r).startswith("EVALERR") and r != "null" and r is not None:
            return r
    return None


def _read_icims_otp(gmail_mod, timeout, since_epoch):
    """Indirection so tests can inject a fake gmail module. Returns code or raises
    TimeoutError."""
    if gmail_mod is None:
        import gmail_imap as gmail_mod  # noqa: WPS433
    return gmail_mod.wait_for_icims_otp(timeout_seconds=timeout, since_epoch=since_epoch)


def handle_otp_gate(page, debug=None, gmail_mod=None, timeout=90, since_epoch=None):
    """Detect + clear the iCIMS email-OTP gate.

    Returns a dict with `status` in:
      - 'absent'  : no OTP gate present (nothing to do; caller proceeds)
      - 'passed'  : code entered and the gate cleared
      - 'timeout' : gate present but no 6-digit iCIMS code arrived (-> EXIT 10)
      - 'entered_unconfirmed' : code typed + continue clicked, gate still showing
      - 'no_input': gate text seen but no fillable input found
    """
    det = detect_otp_gate(page)
    if not det.get("present"):
        return {"status": "absent"}
    log("OTP gate detected:", det.get("why"), "segmented=", det.get("segmented"))
    shot(page, debug, "OTP-00-detected")
    # Request window starts slightly before now (email was just triggered).
    if since_epoch is None:
        since_epoch = time.time() - 60
    try:
        code = _read_icims_otp(gmail_mod, timeout, since_epoch)
    except TimeoutError as e:
        log("OTP timeout:", e)
        shot(page, debug, "OTP-timeout")
        return {"status": "timeout", "detail": str(e), "detect": det.get("why")}
    if not code:
        shot(page, debug, "OTP-timeout")
        return {"status": "timeout", "detail": "empty-code", "detect": det.get("why")}
    log("OTP code received (masked):", str(code)[:2] + "****")
    fr = det.get("_frame_obj") or find_form_frame(page, "input")
    fill_res = fill_otp(fr, code, det.get("segmented", False), det.get("n", 1))
    log("OTP fill:", fill_res)
    if isinstance(fill_res, str) and ("MISSING" in fill_res or "TOO_FEW" in fill_res):
        shot(page, debug, "OTP-no-input")
        return {"status": "no_input", "fill": fill_res, "code_len": len(str(code))}
    page.wait_for_timeout(800)
    btn = click_otp_continue(page)
    log("OTP continue click:", btn)
    # Poll for the gate to clear (code field gone or advanced past it).
    for _ in range(8):
        page.wait_for_timeout(1500)
        if not detect_otp_gate(page).get("present"):
            shot(page, debug, "OTP-01-passed")
            return {"status": "passed", "code_len": len(str(code)), "btn": btn}
    shot(page, debug, "OTP-unconfirmed")
    return {"status": "entered_unconfirmed", "code_len": len(str(code)), "btn": btn}


# ---------------------------------------------------------------------------
# hCaptcha solve attempt via shared CaptchaSolver. Returns (token|None, reason).
# ---------------------------------------------------------------------------
def try_solve_hcaptcha(sitekey, page_url):
    try:
        from captcha_solver import CaptchaSolver, SolverNotConfigured, SolverError
    except Exception as e:
        return None, f"captcha-solver-import-fail:{e}"
    for vendor in ("twocaptcha", "nopecha"):  # capsolver dropped hCaptcha; 2Captcha works
        try:
            solver = CaptchaSolver(vendor=vendor)
        except (SolverNotConfigured, SolverError):
            continue
        try:
            token = solver.solve_hcaptcha(sitekey, page_url)
            if token:
                return token, f"solved-via-{vendor}"
        except Exception as e:
            log(f"hcaptcha solve via {vendor} failed:", e)
            continue
    return None, "icims-hcaptcha-no-vendor"


def inject_hcaptcha(page, token):
    try:
        from captcha_inject import inject_hcaptcha_token
    except Exception as e:
        log("inject import fail:", e)
        return False
    for fr in page.frames:
        try:
            if fr.evaluate("()=>!!document.querySelector('[name=\"h-captcha-response\"],textarea[id^=\"h-captcha-response\"]')"):
                return inject_hcaptcha_token(fr, token)
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# Flow steps
# ---------------------------------------------------------------------------
def open_apply(ctx, job_url, debug):
    """Open JD, click Apply, land on the iCIMS /login (email-entry) gate."""
    pg = ctx.new_page()
    pg.goto(job_url, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    log("JD url:", pg.url, "| title:", pg.title())
    shot(pg, debug, "00-jd")
    term = detect_terminal(pg)
    if term:
        return pg, term
    if "/login" in pg.url:
        return pg, None
    clicked = None
    for fr in pg.frames:
        try:
            r = fr.evaluate(r"""()=>{
              const a=[...document.querySelectorAll('a,button,input[type=submit]')]
                .find(x=>/apply for this job|apply now|apply online|^apply$/i.test((x.value||x.textContent||'').trim()));
              if(a){a.scrollIntoView({block:'center'});a.click();return (a.value||a.textContent||'').trim();}
              return null;}""")
            if r:
                clicked = r
                break
        except Exception:
            pass
    log("apply click:", clicked)
    if not clicked:
        m = re.match(r"(https://[^?#]+?/jobs/\d+/[^/]+)/job", job_url)
        if m:
            pg.goto(m.group(1) + "/login", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    return pg, detect_terminal(pg)


def email_gate(page, debug):
    """Fill the iCIMS email-entry gate. Returns dict with hcaptcha/result info."""
    sel = "#email, input[name='css_loginName'], input[type=email]"
    fr = find_form_frame(page, sel)
    if not fr:
        return {"stage": "email", "status": "no-email-frame"}
    frame_eval(fr, JS_SET, [sel, EMAIL])
    page.wait_for_timeout(800)
    shot(page, debug, "01-email-filled")
    present, sitekey = detect_hcaptcha(page)
    return {"stage": "email", "status": "filled", "hcaptcha": present,
            "sitekey": sitekey, "frame": fr.url}


def submit_email(page):
    fr = find_form_frame(page, "#enterEmailSubmitButton, input[type=submit]")
    if not fr:
        return False
    frame_eval(fr, r"""()=>{const b=document.querySelector('#enterEmailSubmitButton')||
      [...document.querySelectorAll('input[type=submit],button[type=submit],button')].find(x=>/next|continue|submit/i.test((x.value||x.textContent||'').trim()));
      if(b){b.scrollIntoView({block:'center'});b.click();return true;}return false;}""")
    return True


def fill_screening(page, debug):
    """Best-effort fill of reachable screening/knockout radio questions using the
    truthful resolver. Returns a list of {q, ans, res}."""
    applied = []
    for fr in page.frames:
        try:
            questions = fr.evaluate(r"""()=>{
              const out=[]; const seen=new Set();
              document.querySelectorAll('input[type=radio]').forEach(r=>{
                if(seen.has(r.name))return; seen.add(r.name);
                let p=r.closest('fieldset,.iCIMS_TableRow,tr,div'); let q='';
                for(let i=0;i<4&&p;i++){const t=(p.innerText||'').trim();if(t.length>10){q=t;break;}p=p.parentElement;}
                out.push({name:r.name,q:q.slice(0,200)});
              });
              return out;
            }""")
        except Exception:
            continue
        for item in (questions or []):
            ans = resolve_knockout(item["q"])
            if ans in ("yes", "no"):
                res = frame_eval(fr, JS_RADIO_BY_LABEL, [item["q"][:40], ans])
                applied.append({"q": item["q"][:80], "ans": ans, "res": res})
    if applied:
        shot(page, debug, "03-screening")
    return applied


def upload_resume_anyframe(page):
    for fr in page.frames:
        try:
            inp = fr.query_selector("input[type=file]")
            if inp:
                if not os.path.exists(RESUME):
                    return "resume-missing:" + RESUME
                inp.set_input_files(RESUME)
                page.wait_for_timeout(1500)
                n = fr.evaluate("()=>{const f=document.querySelector('input[type=file]');return f?f.files.length:-1;}")
                return f"files={n}@{fr.url[:50]}"
        except Exception:
            pass
    return "no-file-input"


# ---------------------------------------------------------------------------
def run(args):
    from playwright.sync_api import sync_playwright
    deadline = time.time() + (args.max_seconds or 600)
    result = {"url": args.url, "status": "unknown", "dryrun": args.dryrun,
              "block_reason": None}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page, term = open_apply(ctx, args.url, args.debug)
        page.set_default_timeout(20000)
        if term == "already_applied":
            result.update(status="already_applied", block_reason="already-applied")
            shot(page, args.debug, "TERM-already-applied")
            print(json.dumps(result)); _close(page, args); return result
        if term == "closed":
            result.update(status="closed", block_reason="closed-req")
            shot(page, args.debug, "TERM-closed")
            print(json.dumps(result)); _close(page, args); return result

        eg = email_gate(page, args.debug)
        result["email_gate"] = eg
        log("email gate:", eg)

        # hCaptcha wall?
        if eg.get("hcaptcha"):
            log("hCaptcha gate detected; attempting solve")
            token, reason = try_solve_hcaptcha(eg.get("sitekey"), page.url)
            result["hcaptcha_solve"] = reason
            if not token:
                result.update(status="blocked", block_reason="icims-hcaptcha-no-vendor")
                result["detail"] = ("iCIMS email gate is hCaptcha-protected and no working "
                                    "hCaptcha vendor is configured (CapSolver discontinued "
                                    "hCaptcha; no nopecha key). Same class as Palantir Lever.")
                shot(page, args.debug, "WALL-hcaptcha")
                print(json.dumps(result)); _close(page, args); return result
            inject_hcaptcha(page, token)
            page.wait_for_timeout(800)

        if eg.get("status") == "no-email-frame":
            result.update(status="blocked", block_reason="icims-no-email-gate")
            result["detail"] = "Could not locate the iCIMS email-entry form (gate structure changed or page not reached)."
            shot(page, args.debug, "ERR-no-email-frame")
            print(json.dumps(result)); _close(page, args); return result

        # Submit email -> account/register/form. (Only reached if no hCaptcha wall.)
        submit_email(page)
        page.wait_for_timeout(5000)
        shot(page, args.debug, "02-post-email")

        # --- Email-OTP verification gate (iCIMS Universal Login / Auth0, Apr-2025+) ---
        # After the email step iCIMS mails a 6-digit code and renders a code input.
        # Clear it automatically by reading the code from Gmail. A detected-but-
        # unfulfilled gate is terminal: EXIT 10 (otp-timeout).
        otp = handle_otp_gate(page, debug=args.debug,
                              timeout=getattr(args, "otp_timeout", 90))
        result["otp"] = otp
        if otp.get("status") == "timeout":
            result.update(status="otp_timeout",
                          block_reason="icims-otp-timeout:" + str(otp.get("detail", "")))
            print(json.dumps(result)); _close(page, args); return result
        if otp.get("status") == "no_input":
            result.update(status="blocked",
                          block_reason="icims-otp-no-input")
            print(json.dumps(result)); _close(page, args); return result
        if otp.get("status") != "absent":
            page.wait_for_timeout(3000)

        term = detect_terminal(page)
        if term == "already_applied":
            result.update(status="already_applied", block_reason="already-applied")
            shot(page, args.debug, "TERM-already-applied")
            print(json.dumps(result)); _close(page, args); return result

        # Resume upload + screening fill across whatever sections render.
        result["resume"] = upload_resume_anyframe(page)
        result["screening"] = fill_screening(page, args.debug)

        if time.time() > deadline:
            result.update(status="blocked", block_reason="icims-time-cap")
            print(json.dumps(result)); _close(page, args); return result

        if args.dryrun:
            result.update(status="dryrun-ready",
                          note="Reached form past email gate; filled reachable fields; STOPPED before Submit.")
            shot(page, args.debug, "04-dryrun-final")
            print(json.dumps(result, indent=1)); _close(page, args); return result

        # REAL SUBMIT: click the final submit button (iCIMS varies; match by text).
        submitted = False
        for fr in page.frames:
            r = frame_eval(fr, r"""()=>{const b=[...document.querySelectorAll('input[type=submit],button[type=submit],button,a')]
              .find(x=>/^(submit|submit application|finish|complete application|apply)$/i.test((x.value||x.textContent||'').trim()));
              if(b){b.scrollIntoView({block:'center'});b.click();return (b.value||b.textContent||'').trim();}return null;}""")
            if r and not str(r).startswith("EVALERR"):
                submitted = True
                result["submit_btn"] = r
                break
        if not submitted:
            result.update(status="blocked", block_reason="icims-no-submit-button")
            shot(page, args.debug, "ERR-no-submit")
            print(json.dumps(result)); _close(page, args); return result

        # Poll for on-page confirmation (authoritative proof-of-submit).
        final = {"conf": False}
        for _ in range(12):
            page.wait_for_timeout(2000)
            final = detect_confirmation(page)
            if final.get("conf"):
                break
        result["final"] = final
        if final.get("conf"):
            result.update(status="applied", block_reason=None)
            shot(page, args.debug, "05-confirmation")
        else:
            result.update(status="uncertain", block_reason="icims-submit-unconfirmed")
            shot(page, args.debug, "05-uncertain")
        print(json.dumps(result, indent=1)); _close(page, args); return result


def _close(page, args):
    if not getattr(args, "keep_open", False):
        try:
            page.close()
        except Exception:
            pass


# Map a run() result status -> process EXIT code (see module docstring).
_STATUS_EXIT = {
    "applied": 0,
    "dryrun-ready": 0,
    "already_applied": 7,
    "closed": 6,
    "otp_timeout": 10,
    "uncertain": 3,            # submitted but unconfirmed
}


def exit_code_for(result: dict) -> int:
    """Translate a run() result dict into the documented EXIT code. Defaults:
    a generic blocked/auth state -> 2; an explicit no-submit-button -> 4; a
    time/loop cap -> 5."""
    status = (result or {}).get("status")
    if status in _STATUS_EXIT:
        return _STATUS_EXIT[status]
    reason = str((result or {}).get("block_reason") or "")
    if "no-submit-button" in reason:
        return 4
    if "time-cap" in reason or "loop" in reason:
        return 5
    if "otp-timeout" in reason:
        return 10
    if "closed" in reason or "already-applied" in reason:
        return 7 if "already" in reason else 6
    return 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--dryrun", action="store_true")
    ap.add_argument("--apply", action="store_true", help="alias: real submit (default unless --dryrun)")
    ap.add_argument("--debug", default=None, help="screenshot dir")
    ap.add_argument("--cdp", default=CDP_DEFAULT)
    ap.add_argument("--max-seconds", type=int, default=600)
    ap.add_argument("--otp-timeout", type=int, default=90,
                    help="seconds to wait for the iCIMS email OTP (EXIT 10 on miss)")
    ap.add_argument("--keep-open", action="store_true")
    args = ap.parse_args()
    r = run(args)
    code = exit_code_for(r)
    ok = code == 0
    try:
        from debug_shots import prune_step_shots_on_success
        if args.debug:
            prune_step_shots_on_success(args.debug, None, code, success_codes=(0,))
    except Exception as e:
        print(f"[icims] debug-shot prune skipped: {e}")
    sys.exit(code)


if __name__ == "__main__":
    main()