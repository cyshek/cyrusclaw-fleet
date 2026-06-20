#!/usr/bin/env python3
"""
_phenom_runner.py — Phenom People (phenom*/phenompeople) guest-apply runner.

Phenom career sites (e.g. careers.starktech.com, careers.nordstrom.com) expose a
multi-step guest "Quick Apply" form at `<base>/<locale>/apply?jobSeqNo=<id>`.
Fields use STABLE `id` attributes (NO `name` attr), so select via getElementById
and set the value via the native value-setter + input/change (React/Angular
controlled). The resume upload is a SINGLE hidden `input[type=file]` whose custom
"Upload Resume" button rejects browser-tool upload — but CDP `set_input_files`
on the hidden input works (proven 2026-06-03 on Stark Tech: server parses the PDF
and auto-fills firstName). Resume is MANDATORY (Next -> "Resume Import is
mandatory" alert otherwise).

Flow:
  step=1 personalInformation : resume upload + name/email/phone/address/country/
          state/city/zip/applicantSource -> Next
  subsequent steps           : voluntary EEO / questions / review -> Next/Submit
  Confirmation = on-page "application has been submitted/received" text or a
  /apply...&step=...confirmation URL.

Connects over CDP to the running OpenClaw browser (passes any anti-bot the site
applies and reuses session). Mirrors _tesla_runner.py architecture.

Usage:
  python3 _phenom_runner.py --url <applyOrJobUrl> [--dryrun] [--debug DIR] [--cdp http://127.0.0.1:18800]
"""
import sys, os, time, json, argparse, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FIRST = "Cyrus"
LAST = "Shekari"
PREFERRED = "Cyrus"
EMAIL = "cyshekari@gmail.com"
PHONE = "3468040227"
ADDRESS = "12420 NE 120th St #1437"
CITY = "Kirkland"
STATE = "Washington"  # select label; falls back to WA value-match
STATE_CODE = "WA"
ZIP = "98034"
COUNTRY = "United States"  # falls back to USA/US
SOURCE = "LinkedIn"

RESUME = os.path.abspath(os.path.join(HERE, "..", "resume", "Cyrus_Shekari_Resume.pdf"))
CDP_DEFAULT = "http://127.0.0.1:18800"


def log(*a):
    print("[phenom]", *a, file=sys.stderr, flush=True)


# Set an input/textarea by id via native setter (React/Angular-safe).
JS_SET_ID = r"""([id,val])=>{
  const el=document.getElementById(id);
  if(!el) return id+':MISSING';
  const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
  const d=Object.getOwnPropertyDescriptor(proto,'value');
  el.focus(); d.set.call(el,val);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.dispatchEvent(new Event('keyup',{bubbles:true}));
  el.blur(); return id+':ok';
}"""

# Pick a <select> option by id, matching value OR visible text (case-insensitive),
# trying a list of candidate values.
JS_PICK_SELECT_ID = r"""([id,cands])=>{
  const el=document.getElementById(id);
  if(!el) return id+':MISSING';
  let opt=null;
  for(const c of cands){
    opt=[...el.options].find(o=>o.value.toLowerCase()===String(c).toLowerCase()) ||
        [...el.options].find(o=>o.textContent.trim().toLowerCase()===String(c).toLowerCase());
    if(opt) break;
  }
  if(!opt) for(const c of cands){
    opt=[...el.options].find(o=>o.textContent.trim().toLowerCase().includes(String(c).toLowerCase()));
    if(opt) break;
  }
  if(!opt) return id+':NOOPT:'+[...el.options].map(o=>o.value).slice(0,12).join('|');
  const d=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value');
  el.focus(); d.set.call(el,opt.value);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.blur(); return id+'='+opt.value;
}"""


def set_id(page, _id, val):
    return page.evaluate(JS_SET_ID, [_id, val])


def pick_select(page, _id, cands):
    """Try Playwright select_option first (commits to React state properly),
    fall back to JS native-setter if the element is not found."""
    for c in cands:
        try:
            page.select_option(f'#{_id}', label=str(c), timeout=3000)
            return f'{_id}=label:{c}'
        except Exception:
            pass
        try:
            page.select_option(f'#{_id}', value=str(c), timeout=3000)
            return f'{_id}=value:{c}'
        except Exception:
            pass
    # Fallback to JS native-setter
    return page.evaluate(JS_PICK_SELECT_ID, [_id, cands])


def shot(page, debug_dir, name):
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    try:
        page.screenshot(path=os.path.join(debug_dir, name + ".png"), full_page=True)
    except Exception as e:
        log("shot fail", name, e)


def apply_url_from(job_url):
    """Normalize a Phenom JD or apply URL into the apply form URL."""
    if "/apply" in job_url:
        return job_url
    # JD form: <base>/<locale>/job/<SEQNO>/<slug>  -> <base>/<locale>/apply?jobSeqNo=<SEQNO>
    m = re.search(r"^(https?://[^/]+/[a-z]{2}/[a-z]{2})/job/([^/]+)", job_url)
    if m:
        return f"{m.group(1)}/apply?jobSeqNo={m.group(2)}"
    return job_url


def upload_resume(page):
    inp = page.query_selector('input[type=file]')
    if not inp:
        return "no-file-input"
    if not os.path.exists(RESUME):
        return "resume-missing:" + RESUME
    inp.set_input_files(RESUME)
    # server parses async; poll for the resumeName/parse signal
    for _ in range(15):
        page.wait_for_timeout(1000)
        info = page.evaluate("""()=>{const f=document.querySelector('input[type=file]');
          return JSON.stringify({files:f?f.files.length:-1,
            resumeName:(document.getElementById('resumeName')||{}).value||'',
            bucket:(document.getElementById('resumeBucketId')||{}).value||'',
            isResume:(document.getElementById('isResume')||{}).value||''});}""")
        d = json.loads(info)
        if d.get("resumeName") and d.get("bucket"):
            return "ok:" + info
    return "uncommitted:" + info


def fill_personal(page, debug):
    res = {"resume": upload_resume(page)}
    log("resume:", res["resume"])
    page.wait_for_timeout(1500)
    # Resume parse may overwrite name/email; re-set authoritative values.
    res["firstName"] = set_id(page, "firstName", FIRST)
    res["lastName"] = set_id(page, "lastName", LAST)
    res["preferredName"] = set_id(page, "preferredName", PREFERRED)
    res["email"] = set_id(page, "email", EMAIL)
    res["phone"] = set_id(page, "phone", PHONE)
    res["candidateAddress"] = set_id(page, "candidateAddress", ADDRESS)
    res["city"] = set_id(page, "city", CITY)
    res["zipCode"] = set_id(page, "zipCode", ZIP)
    res["country"] = pick_select(page, "country", [COUNTRY, "USA", "US", "United States of America"])
    page.wait_for_timeout(800)  # state options often depend on country
    res["state"] = pick_select(page, "state", [STATE, STATE_CODE, "Washington"])
    res["applicantSource"] = pick_select(page, "applicantSource", [SOURCE, "LinkedIn", "Other", "Job Board"])
    shot(page, debug, "01-personal-filled")
    return res


def click_next(page):
    """Click the Next/Submit navigation button. Prefers 'Next' (exact) then 'Submit',
    using Playwright trusted click (commits to React) rather than JS .click().
    Falls back to JS click if Playwright locator fails."""
    for label in ['Next', 'Submit', 'Continue', 'Finish']:
        try:
            btn = page.locator(f'button:text-is("{label}")').last
            if btn.count() > 0:
                btn.scroll_into_view_if_needed(timeout=3000)
                btn.click(timeout=5000)
                return label
        except Exception:
            pass
    # Fallback: JS click on any next-ish button (avoid nav breadcrumbs by preferring
    # buttons NOT inside the step-nav header)
    return page.evaluate(r"""()=>{
      const btns=[...document.querySelectorAll('main button,main input[type=submit]')];
      const next=btns.find(b=>/^(next|submit|continue|finish)$/i.test((b.textContent||b.value||'').trim()));
      if(next){ next.scrollIntoView({block:'center'}); next.click(); return (next.textContent||next.value||'').trim(); }
      return null;
    }""")


def detect_alert(page):
    """Phenom validation surfaces as an alert() (caught by page.on dialog) OR an
    inline error region; return inline error text if present."""
    return page.evaluate(r"""()=>{
      const errs=[...document.querySelectorAll('[class*=error],[class*=Error],[role=alert],.au-target')]
        .map(e=>(e.textContent||'').trim()).filter(t=>t && t.length<200 &&
          /mandatory|required|invalid|please/i.test(t));
      return errs.slice(0,4).join(' | ');
    }""")


def detect_confirmation(page):
    return page.evaluate(r"""()=>{
      const t=document.body.innerText; const url=location.href;
      const conf=/thank you for (applying|your application|your interest)|application (has been|was) (submitted|received|completed)|we.{0,3}ve received your application|successfully (submitted|applied)|application complete|your application is (complete|submitted)|you have successfully applied/i.test(t)
                 || /confirmation/i.test(url)
                 || /applythankyou.*status=success/i.test(url);
      return JSON.stringify({confirmed:conf, url, head:t.slice(0,260)});
    }""")


def current_step(page):
    return page.evaluate(r"""()=>{
      const m=location.href.match(/stepname=([a-zA-Z]+)/);
      const sn=m?m[1]:'';
      const n=(document.getElementById('stepNum')||{}).value||'';
      return JSON.stringify({stepname:sn, stepNum:n, url:location.href});
    }""")


def run(args):
    from playwright.sync_api import sync_playwright
    result = {"url": args.url, "status": "unknown", "dryrun": args.dryrun}
    apply_url = apply_url_from(args.url)
    result["apply_url"] = apply_url
    alerts = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page.on("dialog", lambda d: (alerts.append(d.message), d.accept()))
        page.set_default_timeout(25000)
        page.goto(apply_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        shot(page, args.debug, "00-landing")
        # Confirm we're on a personal-info step with the expected fields.
        has_form = page.evaluate("()=>!!document.getElementById('firstName') && !!document.querySelector('input[type=file]')")
        if not has_form:
            result["status"] = "blocked-no-form"
            result["page_head"] = page.evaluate("()=>document.body.innerText.slice(0,400)")
            result["step"] = current_step(page)
            print(json.dumps(result)); return result

        result["step1"] = fill_personal(page, args.debug)
        # Clear any benign dialogs from the personal-info step (e.g. resume-upload
        # success alert) so they don't trigger a false blocked-alert in the loop below.
        alerts.clear()
        # Suppress any future window.alert() calls so they don't block click evaluation.
        page.evaluate("() => { window.alert = function() {}; }")

        if args.dryrun:
            result["status"] = "dryrun-ready"
            result["note"] = "Personal step filled (resume uploaded); STOPPED before Next/Submit."
            shot(page, args.debug, "02-dryrun-final")
            print(json.dumps(result, indent=1)); return result

        # Advance through steps until confirmation, no form, or a stuck alert.
        for i in range(8):
            clicked = click_next(page)
            log("next click:", clicked, "iter", i)
            page.wait_for_timeout(3500)
            conf = json.loads(detect_confirmation(page))
            if conf["confirmed"]:
                result["status"] = "applied"; result["final"] = conf
                shot(page, args.debug, "05-confirmation")
                print(json.dumps(result, indent=1)); return result
            inline = detect_alert(page)
            if alerts:
                result["status"] = "blocked-alert"
                result["alerts"] = alerts
                result["inline"] = inline
                result["step"] = current_step(page)
                shot(page, args.debug, "ERR-alert")
                print(json.dumps(result, indent=1)); return result
            stp = json.loads(current_step(page))
            log("now at", stp)
            # If a new step has required selects/checkboxes (EEO etc.), best-effort
            # decline-to-answer + agree-to-required, then continue.
            page.evaluate(r"""()=>{
              // tick any required consent checkboxes
              [...document.querySelectorAll('input[type=checkbox]')].forEach(c=>{
                const lbl=(c.closest('label')||{}).textContent||document.querySelector('label[for="'+c.id+'"]')?.textContent||'';
                if(/agree|consent|acknowledg|certif|terms|privacy/i.test(lbl) && !c.checked){ c.click(); }
              });
              // set EEO selects to a decline option where present
              [...document.querySelectorAll('select')].forEach(s=>{
                if(s.value) return;
                const dec=[...s.options].find(o=>/decline|not.*(wish|disclose|identify)|prefer not/i.test(o.textContent));
                if(dec){ const d=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value'); d.set.call(s,dec.value); s.dispatchEvent(new Event('change',{bubbles:true})); }
              });
            }""")
            page.wait_for_timeout(800)
            if clicked is None and i > 0:
                break

        # Final confirmation poll
        for _ in range(6):
            page.wait_for_timeout(2000)
            conf = json.loads(detect_confirmation(page))
            if conf["confirmed"]:
                result["status"] = "applied"; result["final"] = conf
                shot(page, args.debug, "05-confirmation")
                print(json.dumps(result, indent=1)); return result
        result["status"] = "uncertain"
        result["final"] = json.loads(detect_confirmation(page))
        result["alerts"] = alerts
        result["step"] = current_step(page)
        shot(page, args.debug, "05-uncertain")
        print(json.dumps(result, indent=1)); return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--dryrun", action="store_true")
    ap.add_argument("--debug", default=None)
    ap.add_argument("--cdp", default=CDP_DEFAULT)
    args = ap.parse_args()
    r = run(args)
    ok = r.get("status") in ("applied", "dryrun-ready")
    try:
        from debug_shots import prune_step_shots_on_success
        if args.debug:
            prune_step_shots_on_success(args.debug, None, 0 if ok else 2, success_codes=(0,))
    except Exception as e:
        print(f"[phenom] debug-shot prune skipped: {e}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
