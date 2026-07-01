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
EMAIL = os.environ.get("ICIMS_EMAIL_OVERRIDE", "").strip() or _PI["contact"]["email"]
# Auth0 email: allow override so fresh aliases bypass locked accounts (use ICIMS_AUTH0_EMAIL_OVERRIDE)
CANONICAL_EMAIL = os.environ.get("ICIMS_AUTH0_EMAIL_OVERRIDE", "").strip() or _PI["contact"]["email"]
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
    ' '+(el.placeholder||'')).toLowerCase();
  // NOTE: we deliberately EXCLUDE autocomplete attr from OTP detection — postal-code
  // contains 'code' and triggers false positives on zip/postal inputs.
  const codeRe=/otp|one[-_ ]?time|onetime|verification|verif(y|ication)?code|\bcode\b|passcode|\bpin\b|securitycode|mfa|2fa/;
  // Fields that look like OTP but are definitely NOT (address/zip/profile fields).
  const antiRe=/postal|zip|address|phone|profile|birthdate|dob|gender|race|veteran|disability|salary|company|employer|start.?date|end.?date/;
  // 1. A single explicit code field.
  for(const el of all){
    if(!vis(el)) continue;
    const t=txt(el);
    // Also check name/id directly for address-like patterns
    const nameId=((el.name||'')+' '+(el.id||'')).toLowerCase();
    if(antiRe.test(nameId)) continue;
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
# iCIMS account password — used for Auth0 Universal Login password step.
# AMD/Keysight/SiriusXM account created 2026-06-30 with this password (reset via
# clicks.icims.com link in Gmail, proved working for AMD 3970 submission).
# ---------------------------------------------------------------------------
ICIMS_PASSWORD_DEFAULT = "JobSearch2026!amd"


def _load_icims_password():
    """Load iCIMS candidate password from env or default."""
    return os.environ.get("ICIMS_PASSWORD", "").strip() or ICIMS_PASSWORD_DEFAULT


# ---------------------------------------------------------------------------
# Auth0 Universal Login handler (iCIMS Apr-2025+ hCaptcha wall on Auth0 page).
# Proven 2026-06-30 on AMD iCIMS (sitekey ccfa5854-...). After the email gate
# + OTP, some iCIMS tenants redirect to an Auth0 page that ALSO has an hCaptcha.
# We solve it, inject h-captcha-response + g-recaptcha-response, submit the form,
# then fill the password field that appears.
# ---------------------------------------------------------------------------
_AUTH0_URL_RE = re.compile(
    r"auth0\.com|icims\.auth0\.com|login\.icims\.com", re.IGNORECASE)

_AUTH0_BODY_DETECT_JS = (
    "()=>{" +
    "const forms=!!document.querySelector('form#identifier-form,form#kc-form-login');" +
    "const userInp=!!document.querySelector('input#username,input[name=\"username\"]');" +
    "const pwdInp=!!document.querySelector('input[type=\"password\"]');" +
    "return {forms, userInp, pwdInp," +
    " urlMatch:/(auth0|icims\\.auth0|login\\.icims)/i.test(location.href)};" +
    "}"
)

_AUTH0_HCAP_DETECT_JS = (
    "()=>{" +
    "const iframe=document.querySelector('iframe[src*=\"hcaptcha\"]');" +
    "const sk=document.querySelector('[data-sitekey]');" +
    "const resp=document.querySelector('textarea[name=\"h-captcha-response\"]," +
    "textarea[name=\"g-recaptcha-response\"],textarea[id^=\"h-captcha-response\"]');" +
    "var sk2=null;if(iframe){var m2=iframe.src.match(/sitekey=([0-9a-f-]{30,})/i);if(m2)sk2=m2[1];}" +
    "return {present:!!(iframe||sk||resp)," +
    " sitekey:(sk?sk.getAttribute('data-sitekey'):null)||sk2," +
    " iframeUrl:iframe?iframe.src.slice(0,200):null," +
    " hasResp:!!resp};" +
    "}"
)

# Inject hCaptcha token into Auth0 form (sets both h-captcha-response AND
# g-recaptcha-response textareas, then submits the form directly).
_AUTH0_INJECT_AND_SUBMIT_JS = r"""(token)=>{
  let count=0;
  // Set textareas (h-captcha-response, g-recaptcha-response)
  const sels=[
    'textarea[name="h-captcha-response"]',
    'textarea[name="g-recaptcha-response"]',
    'textarea[id^="h-captcha-response"]',
    'textarea[id^="g-recaptcha-response"]'
  ];
  for(const sel of sels){
    for(const el of document.querySelectorAll(sel)){
      try{
        const d=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value');
        d.set.call(el,token);
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
        count++;
      }catch(e){}
    }
  }
  // Also inject into hidden 'captcha' input (Auth0 reads this field)
  const captchaHidden = document.querySelector('input[name="captcha"]');
  if(captchaHidden){
    const dh=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
    dh.set.call(captchaHidden,token);
    captchaHidden.dispatchEvent(new Event('input',{bubbles:true}));
    captchaHidden.dispatchEvent(new Event('change',{bubbles:true}));
    count++;
  }
  // Also call hcaptcha.callback() if available (notifies Auth0's hCaptcha widget)
  try{
    if(window.hcaptcha && typeof window.hcaptcha.execute === 'function'){
      // Try internal callback dispatch
      const allWidgets = document.querySelectorAll('[data-hcaptcha-widget-id]');
      allWidgets.forEach(w => {
        const wid = w.getAttribute('data-hcaptcha-widget-id');
        try{ window.hcaptcha.setData(wid, {response: token}); }catch(e){}
      });
    }
  }catch(e){}
  // Do NOT submit the form — instead return so the caller can click Continue
  // (form.submit() bypasses Auth0 SPA routing and causes page to stay on identifier)
  return {injected:count, submitted:false};
}"""

_AUTH0_FILL_EMAIL_JS = r"""(email)=>{
  const inp=document.querySelector('input#username,input[name="username"],input[type="email"]');
  if(!inp)return 'MISSING';
  const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
  inp.scrollIntoView({block:'center'});inp.focus();d.set.call(inp,email);
  inp.dispatchEvent(new Event('input',{bubbles:true}));
  inp.dispatchEvent(new Event('change',{bubbles:true}));
  inp.blur();return 'ok:'+inp.value.slice(0,20);
}"""

_AUTH0_CLICK_CONTINUE_JS = r"""()=>{
  const btn=document.querySelector('button[type=submit],button[name=action],input[type=submit]');
  if(btn){btn.scrollIntoView({block:'center'});btn.click();return 'clicked:'+(btn.textContent||btn.value||'').trim().slice(0,30);}
  return null;
}"""

_AUTH0_FILL_PASSWORD_JS = r"""(pwd)=>{
  const inp=[...document.querySelectorAll('input[type=password]')].find(el=>{
    const r=el.getBoundingClientRect();const s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';
  });
  if(!inp)return 'MISSING';
  const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
  inp.scrollIntoView({block:'center'});inp.focus();d.set.call(inp,pwd);
  inp.dispatchEvent(new Event('input',{bubbles:true}));
  inp.dispatchEvent(new Event('change',{bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true}));
  inp.blur();return 'ok:'+inp.value.length;
}"""


def _is_auth0_page(page):
    """Return True if the current page or any frame looks like Auth0 Universal Login."""
    try:
        if _AUTH0_URL_RE.search(page.url or ""):
            return True
    except Exception:
        pass
    for fr in page.frames:
        try:
            url = fr.url or ""
            if _AUTH0_URL_RE.search(url):
                return True
            det = fr.evaluate(_AUTH0_BODY_DETECT_JS)
            if det and (det.get("urlMatch") or det.get("forms") or det.get("userInp")):
                return True
        except Exception:
            pass
    return False


def _find_auth0_frame(page):
    """Return the frame that IS the Auth0 page (or None if not on Auth0)."""
    for fr in page.frames:
        try:
            url = fr.url or ""
            if _AUTH0_URL_RE.search(url):
                return fr
            det = fr.evaluate(_AUTH0_BODY_DETECT_JS)
            if det and (det.get("urlMatch") or det.get("forms") or det.get("userInp")):
                return fr
        except Exception:
            pass
    # Fallback to main frame if top-level URL matched.
    try:
        if _AUTH0_URL_RE.search(page.url or ""):
            return page.frames[0] if page.frames else None
    except Exception:
        pass
    return None


def handle_auth0_login(page, email, password, debug=None):
    """Handle the Auth0 Universal Login flow that iCIMS tenants redirect to.

    Proved 2026-06-30 on AMD iCIMS (3970): after email gate + OTP the page
    navigates to Auth0 which also has an hCaptcha. Inject token into both
    h-captcha-response + g-recaptcha-response textareas + form.submit().
    Then fill the visible password input and click submit.

    Returns:
      'done'            - Auth0 flow completed, now on iCIMS portal
      'no-auth0'        - Not on Auth0; caller should proceed normally
      'blocked-captcha' - hCaptcha present but could not solve
      'failed'          - Other failure (no identifier/password field found)
    """
    if not _is_auth0_page(page):
        log("Auth0: not detected (URL=%s)", (page.url or "")[:80])
        return "no-auth0"

    log("Auth0 Universal Login detected:", (page.url or "")[:80])
    shot(page, debug, "AUTH0-00-detected")

    auth0_fr = _find_auth0_frame(page)
    if auth0_fr is None:
        auth0_fr = page.frames[0] if page.frames else None
    log("Auth0 frame:", (auth0_fr.url if auth0_fr else "(none)")[:80])

    # ---- hCaptcha on the Auth0 identifier page --------------------------------
    hcap = {}
    if auth0_fr:
        try:
            hcap = auth0_fr.evaluate(_AUTH0_HCAP_DETECT_JS)
        except Exception as exc:
            log("Auth0 hCaptcha detect error:", exc)

    log("Auth0 hCaptcha: present=%s sitekey=%s",
        hcap.get("present"), hcap.get("sitekey"))

    if hcap.get("present") or hcap.get("sitekey"):
        sitekey = hcap.get("sitekey")
        if not sitekey:
            # Try to pull sitekey from the iframe URL.
            iframe_url = hcap.get("iframeUrl") or ""
            m = re.search(r"sitekey=([0-9a-f\-]+)", iframe_url, re.IGNORECASE)
            if m:
                sitekey = m.group(1)
        if not sitekey:
            # Fallback: AMD Auth0 sitekey (all careers-amd tenants share it).
            sitekey = "ccfa5854-6c50-47f8-92e6-4a4dfbe474c3"
            log("Auth0 hCaptcha: sitekey not in DOM, using AMD fallback:", sitekey)

        log("Auth0 hCaptcha: solving sitekey=%s url=%s",
            sitekey, (page.url or "")[:60])
        token, reason = None, None
        for _hcap_try in range(3):
            token, reason = try_solve_hcaptcha(sitekey, page.url)
            if token:
                break
            log("Auth0 hCaptcha attempt %d/3 FAILED: %s", _hcap_try + 1, reason)
            if "UNSOLVABLE" not in str(reason):
                break  # Non-transient error, don't retry
            page.wait_for_timeout(3000)
        if not token:
            log("Auth0 hCaptcha all retries FAILED:", reason)
            shot(page, debug, "AUTH0-ERR-hcaptcha")
            return "blocked-captcha"

        log("Auth0 hCaptcha solved (%s), injecting...", reason)
        if auth0_fr:
            try:
                res = auth0_fr.evaluate(_AUTH0_INJECT_AND_SUBMIT_JS, token)
                log("Auth0 hCaptcha inject result:", res)
            except Exception as exc:
                log("Auth0 hCaptcha inject error:", exc)
        # After token injection, wait for the hCaptcha widget to verify + click Continue
        page.wait_for_timeout(2000)
        shot(page, debug, "AUTH0-01-captcha-injected")
        # Click the Continue / Submit button to proceed past the identifier+hCaptcha
        if auth0_fr:
            try:
                click_res = auth0_fr.evaluate(_AUTH0_CLICK_CONTINUE_JS)
                log("Auth0 identifier Continue click after hCaptcha:", click_res)
            except Exception as exc:
                log("Auth0 identifier Continue click error:", exc)
        page.wait_for_timeout(5000)
        shot(page, debug, "AUTH0-02-post-captcha")
        log("After Auth0 captcha submit, URL:", (page.url or "")[:80])
    else:
        log("Auth0: no hCaptcha on identifier page")

    # ---- Identifier / email step ---------------------------------------------
    # Re-detect Auth0 frame (page may have navigated after captcha form.submit()).
    for _attempt in range(3):
        auth0_fr = _find_auth0_frame(page)
        if auth0_fr:
            break
        # If we already left Auth0, skip identifier step.
        if not _is_auth0_page(page):
            log("Auth0: already navigated away after captcha (to %s)",
                (page.url or "")[:60])
            auth0_fr = None
            break
        page.wait_for_timeout(2000)

    if auth0_fr:
        try:
            fill_res = auth0_fr.evaluate(_AUTH0_FILL_EMAIL_JS, email)
            log("Auth0 email fill:", fill_res)
        except Exception as exc:
            log("Auth0 email fill error:", exc)
        page.wait_for_timeout(500)
        try:
            click_res = auth0_fr.evaluate(_AUTH0_CLICK_CONTINUE_JS)
            log("Auth0 continue click:", click_res)
        except Exception as exc:
            log("Auth0 continue click error:", exc)
        page.wait_for_timeout(3000)
        shot(page, debug, "AUTH0-03-after-identifier")

    # ---- Password step -------------------------------------------------------
    pwd_filled = False
    for attempt in range(5):
        for fr in page.frames:
            try:
                has_pwd = fr.evaluate(
                    "()=>{const e=[...document.querySelectorAll('input[type=password]')]"
                    ".find(el=>{const r=el.getBoundingClientRect();"
                    "return r.width>0&&r.height>0;});return !!e;}"
                )
                if has_pwd:
                    # Use ONLY Playwright native fill for Auth0 password (React state)
                    try:
                        pw_locator = fr.locator('input[type=password]').first
                        pw_locator.clear(timeout=3000)
                        pw_locator.fill(password, timeout=5000)
                        # Verify value was set
                        actual_val = pw_locator.input_value(timeout=2000)
                        log("Auth0 password Playwright fill: len=%d", len(actual_val))
                        if len(actual_val) > 0:
                            page.wait_for_timeout(600)  # let React state settle
                            # Use Playwright click for the submit button
                            btn_locator = fr.locator('button[type=submit],button[name=action],input[type=submit]').first
                            btn_locator.click(timeout=5000)
                            log("Auth0 password submit (Playwright click): ok")
                            pwd_filled = True
                            break
                        else:
                            log("Auth0 password fill returned empty - trying JS fallback")
                    except Exception as pf_exc:
                        log("Auth0 password Playwright fill error: %s", pf_exc)
                    # JS fallback if Playwright fill failed
                    fill_res = fr.evaluate(_AUTH0_FILL_PASSWORD_JS, password)
                    log("Auth0 password JS fill (frame=%s): %s",
                        (fr.url or "")[:40], fill_res)
                    if fill_res and "ok" in str(fill_res):
                        page.wait_for_timeout(600)
                        click_res = fr.evaluate(_AUTH0_CLICK_CONTINUE_JS)
                        log("Auth0 password JS submit click:", click_res)
                        pwd_filled = True
                        break
            except Exception as exc:
                log("Auth0 pwd attempt %d error: %s", attempt, exc)
        if pwd_filled:
            break
        page.wait_for_timeout(2000)

    shot(page, debug, "AUTH0-04-after-password")
    if not pwd_filled:
        log("Auth0: could not fill password input (not found after 5 attempts)")
        return "failed"

    # Wait for navigation back to iCIMS portal.
    page.wait_for_timeout(6000)
    shot(page, debug, "AUTH0-05-post-login")
    final_url = page.url or ""
    log("Auth0 login complete. Final URL:", final_url[:80])
    # Detect failed login: if we're still on the login.icims.com password page,
    # the password was rejected (wrong password, or account not recognized).
    if "login.icims.com/u/login/password" in final_url:
        # Capture error message for diagnosis
        for fr in page.frames:
            try:
                err_msg = fr.evaluate("() => { const e = document.querySelector('.cf-alert-block,.error-message,.alert-danger,[class*=error],[class*=alert]'); return e ? e.innerText.slice(0,120) : null; }")
                if err_msg:
                    log("Auth0 error message:", err_msg)
                    break
            except Exception:
                pass
        log("Auth0: still on password page after submit — login FAILED (wrong password?)")
        return "failed"
    return "done"


# ---------------------------------------------------------------------------
# hCaptcha solve attempt via shared CaptchaSolver. Returns (token|None, reason).
# ---------------------------------------------------------------------------


def try_solve_hcaptcha(sitekey, page_url, is_invisible=False):
    """Solve hCaptcha via 2Captcha PROXYLESS.

    AMD iCIMS email gate (sitekey 94fee806-...) is INVISIBLE hCaptcha Enterprise:
    - Fails with ERROR_CAPTCHA_UNSOLVABLE when PROXY_2CAPTCHA is set (proxied task)
    - Succeeds proxyless but takes ~170s (proved 2026-07-01)
    - timeout_s=300 gives 130s of margin beyond the observed 170s worst-case

    Auth0 identifier hCaptcha (ccfa5854-...): pass is_invisible=False (visible hCaptcha
    on the Auth0 Universal Login page -- shown as a human-verification challenge).

    Do NOT use CaptchaSolver wrapper here -- it caches TwoCaptchaClient which
    picks up PROXY_2CAPTCHA env on init and the proxy causes UNSOLVABLE.
    """
    try:
        import twocaptcha_client as _tc
    except Exception as e:
        log("twocaptcha_client import fail:", e)
        return None, "icims-hcaptcha-no-vendor"
    try:
        # proxy="" overrides PROXY_2CAPTCHA env to force proxyless mode.
        # timeout_s=300 accommodates AMD's slow (~170s) solve time.
        client = _tc.TwoCaptchaClient(proxy="", timeout_s=300)  # AMD hCaptcha ~170s avg, max 300s
        token = client.hcaptcha(sitekey, page_url, is_invisible=is_invisible)
        if token:
            log("hCaptcha solved via 2Captcha proxyless (invisible=%s), token=%s...",
                is_invisible, token[:20])
            return token, "solved-via-twocaptcha-proxyless"
    except _tc.TwoCaptchaTimeout as e:
        log("hCaptcha 2Captcha timeout:", e)
        return None, "icims-hcaptcha-timeout"
    except _tc.TwoCaptchaError as e:
        log("hCaptcha 2Captcha error:", e)
        return None, f"icims-hcaptcha-twocaptcha-error:{e}"
    except Exception as e:
        log("hCaptcha unexpected:", e)
        return None, "icims-hcaptcha-no-vendor"
    return None, "icims-hcaptcha-no-vendor"
# JS to inject solved hCaptcha token + submit the AMD iCIMS invisible-hCaptcha email gate.
# AMD iCIMS intercepts form submit and calls hcaptcha.execute(); we bypass by creating the
# hidden input that AMD's own callback creates, then submitting via HTMLFormElement.prototype.submit.
_ICIMS_EMAIL_GATE_INJECT_JS = r"""
(token) => {
  var form = document.getElementById('enterEmailForm')
    || document.querySelector('form[action*="step=email"], form[action*="/login"]');
  if (!form) return {ok: false, reason: 'no_form'};
  // Tick all unchecked checkboxes (GDPR accept, etc).
  form.querySelectorAll('input[type=checkbox]').forEach(function(c) { if (!c.checked) c.click(); });
  // Remove any stale h-captcha-response hidden inputs.
  form.querySelectorAll('input[name="h-captcha-response"]').forEach(function(e) { e.remove(); });
  form.querySelectorAll('input[name="behavior-type"]').forEach(function(e) { e.remove(); });
  // Create the hidden token input (replicates AMD hCaptcha callback behavior).
  var captchaInput = document.createElement('input');
  captchaInput.type = 'hidden';
  captchaInput.name = 'h-captcha-response';
  captchaInput.value = token;
  form.appendChild(captchaInput);
  // behavior-type field (AMD requires this alongside the token).
  var behaviorInput = document.createElement('input');
  behaviorInput.type = 'hidden';
  behaviorInput.name = 'behavior-type';
  behaviorInput.value = 'other';
  form.appendChild(behaviorInput);
  // Also set any visible textareas (non-AMD tenants with visible hCaptcha).
  form.querySelectorAll('textarea[name="h-captcha-response"], textarea[id^="h-captcha-response"]').forEach(function(t) {
    t.value = token;
  });
  // Submit via native HTMLFormElement.prototype.submit to bypass the event listener
  // (AMD's listener calls hcaptcha.execute() which triggers a NEW challenge).
  try {
    HTMLFormElement.prototype.submit.call(form);
    return {ok: true, reason: 'native_submit'};
  } catch(e) {
    var btn = form.querySelector('#enterEmailSubmitButton, input[type=submit], button[type=submit]');
    if (btn) { btn.click(); return {ok: true, reason: 'click_fallback'}; }
    return {ok: false, reason: 'no_submit_btn'};
  }
}
"""


def inject_hcaptcha(page, token):
    """Inject hCaptcha token + submit the iCIMS email gate form.

    AMD iCIMS uses INVISIBLE hCaptcha (data-size=invisible) where:
    - Form submit event is intercepted -> calls hcaptcha.execute()
    - hCaptcha callback creates hidden <input name=h-captcha-response> and calls
      HTMLFormElement.prototype.submit.call(form) directly

    Standard textarea injection fails: server reads only the hidden input created by
    the callback (or our replication of it). This function replicates the callback.

    For non-AMD tenants that use visible hCaptcha textareas, the fallback textarea
    set + click_fallback path handles submission.

    Returns True if the injection + submit was attempted.
    """
    # Find the iframe frame containing the email gate form.
    gate_fr = None
    for fr in page.frames:
        try:
            has_form = fr.evaluate(
                "()=>!!document.getElementById('enterEmailForm') || !!document.querySelector('form[action*=\"step=email\"],[action*=\"/login\"]')")
            if has_form:
                gate_fr = fr
                break
        except Exception:
            pass
    # Fallback: frame with email input
    if not gate_fr:
        for fr in page.frames:
            try:
                if fr.evaluate("()=>!!document.querySelector('#email,input[type=email]')"):
                    gate_fr = fr
                    break
            except Exception:
                pass
    if not gate_fr:
        log("inject_hcaptcha: no email gate frame found")
        return False
    try:
        res = gate_fr.evaluate(_ICIMS_EMAIL_GATE_INJECT_JS, token)
        log("inject_hcaptcha result:", res)
        return bool(res and res.get("ok"))
    except Exception as e:
        log("inject_hcaptcha error:", e)
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
    # Tick any unchecked checkbox in the email gate frame (e.g. AMD "I accept" GDPR checkbox).
    frame_eval(fr, r"""()=>{
      document.querySelectorAll('input[type=checkbox]').forEach(chk=>{
        if(!chk.checked){chk.click();}
      });return true;}""")
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
            # Use the iframe URL (where hCaptcha is rendered) for better token binding.
            # AMD email gate uses INVISIBLE hCaptcha (data-size=invisible).
            hcap_page_url = eg.get("frame") or page.url
            token, reason = try_solve_hcaptcha(eg.get("sitekey"), hcap_page_url, is_invisible=True)
            result["hcaptcha_solve"] = reason
            if not token:
                result.update(status="blocked", block_reason="icims-hcaptcha-no-vendor")
                result["detail"] = ("iCIMS email gate is hCaptcha-protected and no working "
                                    "hCaptcha vendor is configured (CapSolver discontinued "
                                    "hCaptcha; no nopecha key). Same class as Palantir Lever.")
                shot(page, args.debug, "WALL-hcaptcha")
                print(json.dumps(result)); _close(page, args); return result
            inject_hcaptcha(page, token)
            # inject_hcaptcha now handles checkbox + form.submit() for AMD invisible hCaptcha.
            # Wait for navigation: the iframe should navigate away from /login on success.
            # TargetClosedError means the iCIMS outer page fully navigated (e.g. to Auth0).
            _page_closed_after_inject = False
            try:
                page.wait_for_timeout(6000)
            except Exception as _wte:
                log("wait_for_timeout after hcaptcha inject (page navigated to Auth0?): %s", _wte)
                _page_closed_after_inject = True
            if not _page_closed_after_inject:
                shot(page, args.debug, "02-post-email-hcap")
            # Check if we're still on the email gate (= token was rejected by server).
            still_on_gate = False
            if not _page_closed_after_inject:
                for _fr in page.frames:
                    try:
                        if _fr.evaluate("()=>!!document.getElementById('enterEmailForm') || !!document.getElementById('enterEmailSubmitButton')"):
                            still_on_gate = True
                            break
                    except Exception:
                        pass
            if still_on_gate:
                log("hCaptcha token rejected by server (still on email gate); blocking")
                result.update(status="blocked", block_reason="icims-hcaptcha-token-rejected")
                shot(page, args.debug, "WALL-hcaptcha-rejected")
                print(json.dumps(result)); _close(page, args); return result
            log("Email gate passed (navigated away from gate)")
            # If page navigated entirely (top-level nav to Auth0), find the new page.
            if _page_closed_after_inject:
                import time as _time
                _time.sleep(3)
                try:
                    _all_pages = [_p for _ctx in page.context.browser.contexts for _p in _ctx.pages]
                except Exception:
                    _all_pages = []
                # Find a page that is on Auth0
                for _ap in _all_pages:
                    try:
                        if _AUTH0_URL_RE.search(_ap.url or ""):
                            log("Found Auth0 page after top-level nav: %s", (_ap.url or "")[:80])
                            page = _ap
                            break
                    except Exception:
                        pass

        if eg.get("status") == "no-email-frame":
            result.update(status="blocked", block_reason="icims-no-email-gate")
            result["detail"] = "Could not locate the iCIMS email-entry form (gate structure changed or page not reached)."
            shot(page, args.debug, "ERR-no-email-frame")
            print(json.dumps(result)); _close(page, args); return result

        # Submit email (no-hCaptcha path) -> account/register/form.
        if not eg.get("hcaptcha"):
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

        # --- Auth0 Universal Login (iCIMS tenants that redirect to Auth0 after OTP) ---
        # AMD/Keysight/SiriusXM tenants redirect to auth0 after email+OTP.
        # Proved 2026-06-30: Auth0 page has its own hCaptcha (sitekey ccfa5854-...);
        # inject token + form.submit() -> password page -> fill password -> back to iCIMS.
        icims_password = _load_icims_password()
        # Use CANONICAL_EMAIL for Auth0 (the real account), not the gate alias.
        auth0_email = CANONICAL_EMAIL
        auth0_result = handle_auth0_login(
            page, auth0_email, icims_password, debug=args.debug)
        result["auth0"] = auth0_result
        log("Auth0 login result:", auth0_result)
        if auth0_result == "blocked-captcha":
            result.update(status="blocked",
                          block_reason="icims-auth0-hcaptcha-no-vendor")
            shot(page, args.debug, "AUTH0-WALL")
            print(json.dumps(result)); _close(page, args); return result
        if auth0_result == "failed":
            # Failed to fill password or identifier - log but don't abort;
            # the form may still be reachable (rare case where Auth0 auto-completed).
            log("Auth0 login FAILED - continuing to check form availability")
        if auth0_result in ("done", "failed"):
            page.wait_for_timeout(3000)
            shot(page, args.debug, "03-post-auth0")

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
