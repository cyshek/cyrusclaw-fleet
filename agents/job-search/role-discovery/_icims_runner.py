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

=== KNOWN HARD WALL (verified live 2026-06-03, Joby careers-jobyaviation) ===
The iCIMS email-entry gate (`/login`, the FIRST step) is protected by **hCaptcha**
(sitekey e.g. `94fee806-5cac-4582-9738-384a0f4ea6f8`, a real
`newassets.hcaptcha.com` challenge frame). Submitting the email WITHOUT a valid
`h-captcha-response` token does nothing — the page re-renders on `/login`. Per
TOOLS.md, **CapSolver has discontinued all hCaptcha solving** and no nopecha key is
configured, so the gate is a HARD BLOCK in the same class as the Palantir Lever
hCaptcha wall. The runner ATTEMPTS a solve via the shared CaptchaSolver; on
SolverNotConfigured / vendor-reject it returns block_reason
`icims-hcaptcha-no-vendor` so the moment Cyrus provisions a working hCaptcha vendor
(nopecha, or a capsolver plan that supports hCaptcha) this runner completes with NO
code change.

Other queued tenants are walled for DIFFERENT precise reasons (set per-row):
  - AMD (internal-amd.icims.com) / SiriusXM (employees-siriusxmradio.icims.com):
    INTERNAL employee SSO portals, no public req -> `icims-internal-sso-portal`.
  - Rivian: public apply = careers.rivian.com (custom/Phenom), the icims URL is the
    employee-internal one -> not a public iCIMS job (`not-public-icims`).
  - Paramount+: SmartRecruiters-class, not iCIMS (`not-icims-smartrecruiters`).

Usage:
  python3 _icims_runner.py --url <jobUrl> [--dryrun] [--debug DIR] [--cdp ...]
  --dryrun : drive the flow, fill what's reachable, stop before final Submit.
"""
import sys, os, time, json, argparse, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CDP_DEFAULT = "http://127.0.0.1:18800"

# ---- Personal info loader (reads agents/job-search/personal-info.json) -----
_INFO_PATH = os.path.join(HERE, "..", "personal-info.json")
def _info():
    with open(_INFO_PATH) as _f:\n        return json.load(_f)\n\ndef _phone_digits(p):
    """Strip non-digits from phone string."""
    return re.sub(r'[^0-9]', '', p or '')

def _phone_fmt(p):
    """Format phone as NXX-NXX-XXXX (no country code)."""
    d = _phone_digits(p).lstrip('1')
    if len(d) == 10:
        return f"{d[0:3]}-{d[3:6]}-{d[6:]}"
    return p

def _FIRST():         return _info()["identity"]["first_name"]
def _LAST():          return _info()["identity"]["last_name"]
def _EMAIL():         return _info()["identity"]["email"]
def _PHONE():         return _phone_digits(_info()["identity"]["phone"])
def _PHONE_FMT():     return _phone_fmt(_info()["identity"]["phone"])
def _LINKEDIN():      return _info()["identity"]["linkedin_url"]
def _ADDR_STREET():   return _info()["address"]["street"]
def _ADDR_CITY():     return _info()["address"]["city"]
def _ADDR_STATE():    return _info()["address"]["state"]
def _ADDR_ZIP():      return _info()["address"]["zip"]
def _ADDR_COUNTRY():  return _info()["address"].get("country", "United States")

RESUME = os.path.abspath(os.path.join(HERE, "..", "resume", "Cyrus_Shekari_Resume.pdf"))

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
# hCaptcha solve attempt via shared CaptchaSolver. Returns (token|None, reason).
# ---------------------------------------------------------------------------
def try_solve_hcaptcha(sitekey, page_url):
    try:
        from captcha_solver import CaptchaSolver, SolverNotConfigured, SolverError
    except Exception as e:
        return None, f"captcha-solver-import-fail:{e}"
    for vendor in ("nopecha", "capsolver"):
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
    frame_eval(fr, JS_SET, [sel, _EMAIL()])
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--dryrun", action="store_true")
    ap.add_argument("--apply", action="store_true", help="alias: real submit (default unless --dryrun)")
    ap.add_argument("--debug", default=None, help="screenshot dir")
    ap.add_argument("--cdp", default=CDP_DEFAULT)
    ap.add_argument("--max-seconds", type=int, default=600)
    ap.add_argument("--keep-open", action="store_true")
    args = ap.parse_args()
    r = run(args)
    ok = r.get("status") in ("applied", "dryrun-ready")
    try:
        from debug_shots import prune_step_shots_on_success
        if args.debug:
            prune_step_shots_on_success(args.debug, None, 0 if ok else 2, success_codes=(0,))
    except Exception as e:
        print(f"[icims] debug-shot prune skipped: {e}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()