#!/usr/bin/env python3
"""
_workable_runner.py — Workable ATS (apply.workable.com) public apply runner.

Workable public apply forms live at:
  https://apply.workable.com/<company>/j/<JOBID>/        (JD page, OVERVIEW tab)
  https://apply.workable.com/<company>/j/<JOBID>/apply/  (the actual form)

No auth wall, no employee SSO for public postings. This runner connects over
CDP to the already-running OpenClaw browser (shared, one submit at a time) and
drives the single-page apply form.

Form anatomy (mapped live 2026-06-02 on unusual-machines/AA281C63AF TPM):
  Core fields (stable `name` attrs): firstname, lastname, email, phone (tel),
    address (required, has a geo-autocomplete widget), city, postcode, country,
    headline (optional), summary/cover_letter (optional textareas).
  Resume: a HIDDEN <input type=file> rendered with a RANDOM id
    (input_files_input_<rand>) and NO name attr. Forms often render TWO file
    inputs — an optional one and a REQUIRED one (the resume). We target the
    file input(s) by `input[type=file]` and set_input_files on the required one
    (set on ALL of them is harmless but we prefer the required). The browser
    TOOL upload times out (custom dropzone, no native chooser) — Playwright
    set_input_files on the hidden input works.
  Screening questions: custom fields with names like `CA_<digits>` (textarea /
    text / select / radio / checkbox). Required ones are marked. We answer text
    questions with a tailored interest blurb; selects/radios via heuristics
    (SPON=No, AUTH=Yes, AFFIRM willingness=Yes); EEO/voluntary -> decline.
  Consent/GDPR: SOME Workable tenants render a required consent checkbox before
    Submit. We check ALL unchecked required checkboxes that look like consent.
  Submit: button text "Submit application". Confirmation = redirect to a
    /thank-you-ish URL or on-page "Application submitted" / "Thank you for
    applying" text.

All inputs are React-controlled -> set via native value-setter + input/change
dispatch (plain .value= reverts). Custom checkboxes need a label-click fallback.

Answer heuristics (Cyrus: US citizen, NO sponsorship, authorized to work,
open to relocate/onsite/hybrid, available to start, 18+, not former employee).
EEO/voluntary self-id -> prefer not to disclose / decline.

Usage:
  python3 _workable_runner.py --url <jobUrl> [--dryrun] [--debug DIR] [--cdp http://127.0.0.1:18800]
  --dryrun : fill EVERYTHING incl. resume + screening answers, print the answers
             it WOULD submit, STOP before clicking final Submit (Workable can't
             edit after submit — always audit the printed answer lines first).
"""
import sys, os, time, json, argparse, re

EMAIL = "cyshekari@gmail.com"
FIRST = "Cyrus"
LAST = "Shekari"
PHONE = "3468040227"
LINKEDIN = "https://www.linkedin.com/in/cyrus-shekari"
HEADLINE = "Technical Program Manager | Microsoft Azure, Amazon Robotics"
# Address — a real US address keeps the geo-autocomplete + required-field happy.
# Cyrus's real location (prefill.json source of truth): Kirkland, WA.
ADDRESS = "Kirkland, Washington, United States"
CITY = "Kirkland"
COUNTRY = "United States"
POSTCODE = "98033"
# Fallback role-agnostic interest blurb (used ONLY if per-question tailoring
# fails). Company-neutral so it never name-drops the wrong employer.
INTEREST = ("I'm drawn to building structure in fast-growth, ambiguous environments — "
            "exactly where I've delivered. At Microsoft Azure I led a 0-to-1 Resilience "
            "Automation Platform driving $14M+ in business impact, and at Amazon Robotics "
            "I ran a zero-downtime 2,000+ unit OS migration. Coordinating engineering, "
            "product, manufacturing and supply-chain teams from concept through launch is "
            "the work I do best, and this role is one I'd be proud to drive.")

RESUME_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "resume", "Cyrus_Shekari_Resume.pdf")
RESUME = os.path.abspath(RESUME_SRC)
CDP_DEFAULT = "http://127.0.0.1:18800"

# ---- Screening-answer heuristics (single source of truth; tested) -----------
# Cyrus: US citizen, NO sponsorship, authorized, open to relocate/onsite, 18+.
# Mirrors TOOLS.md Workday heuristics: SPON=No, AUTH=Yes, AFFIRM willingness=Yes,
# NEGATIVE/former-employer=No, EEO/voluntary -> decline.
SPON_RE = re.compile(r"sponsor|visa|h-?1b|work permit|immigration|require.*authoriz|green card", re.I)
AUTH_RE = re.compile(r"authoriz|eligible to work|legally (able|allowed|entitled) to work|right to work", re.I)
NEG_RE = re.compile(r"former (employee|intern|contractor)|previously (employed|worked)|non-?compete|related to (anyone|an employee)|currently employed (by|at) (us|the company)", re.I)
AFFIRM_RE = re.compile(r"relocat|onsite|on-site|in[- ]office|hybrid|willing|able to|available to start|commute|at least 18|18 years|come into|comfortable", re.I)
EEO_RE = re.compile(r"gender|race|ethnic|veteran|disab|hispanic|latino|sexual orientation|pronoun|voluntary self|self-?identif", re.I)
DECLINE_OPTS = re.compile(r"prefer not|decline|don.?t wish|not to disclose|not to answer|i do not wish", re.I)


def classify_question(label):
    """Return 'no' | 'yes' | 'decline' | 'text' for a screening question label.
    Order matters: EEO first (decline), then SPON (No), NEG (No), AUTH (Yes),
    AFFIRM (Yes), else default Yes for unknown willing/able questions."""
    if EEO_RE.search(label):
        return "decline"
    if SPON_RE.search(label):
        return "no"
    if NEG_RE.search(label):
        return "no"
    if AUTH_RE.search(label):
        return "yes"
    if AFFIRM_RE.search(label):
        return "yes"
    return "yes"  # unknown "are you willing/able" -> Yes is safer for a wanted job


def pick_option(opts, decision):
    """Given a list of option label strings and a yes/no/decline decision,
    return the best-matching option label (or None)."""
    if not opts:
        return None
    low = [(o, o.strip().lower()) for o in opts if o and o.strip()]
    if decision == "decline":
        for o, l in low:
            if DECLINE_OPTS.search(l):
                return o
        # fall through to "no"-ish if no explicit decline
        decision = "no"
    want_yes = ["yes", "i am", "i do", "true"]
    want_no = ["no", "i am not", "i do not", "false"]
    wants = want_yes if decision == "yes" else want_no
    for o, l in low:
        if l in wants:
            return o
    for o, l in low:
        if any(l.startswith(w) for w in wants):
            return o
    # avoid accidentally picking the opposite literal
    for o, l in low:
        if decision == "yes" and l.startswith("yes"):
            return o
        if decision == "no" and l.startswith("no"):
            return o
    return None


def log(*a):
    print("[workable]", *a, file=sys.stderr, flush=True)


# ---- React-aware field setters (run in-page) -------------------------------
JS_SET_INPUT = r"""([sel,val])=>{
  const el=document.querySelector(sel);
  if(!el) return sel+':MISSING';
  const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype
              : el.tagName==='SELECT'?HTMLSelectElement.prototype
              : HTMLInputElement.prototype;
  const d=Object.getOwnPropertyDescriptor(proto,'value');
  el.focus(); d.set.call(el,val);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.dispatchEvent(new Event('blur',{bubbles:true}));
  return sel+':ok';
}"""

JS_PICK_SELECT = r"""([name,val])=>{
  const el=document.querySelector('select[name="'+name+'"]')||document.querySelector('#'+CSS.escape(name));
  if(!el) return name+':MISSING';
  const opt=[...el.options].find(o=>o.value===val) ||
            [...el.options].find(o=>o.textContent.trim().toLowerCase()===String(val).toLowerCase());
  if(!opt) return name+':NOOPT:'+[...el.options].map(o=>o.textContent.trim()).join('|');
  const d=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value');
  el.focus(); d.set.call(el,opt.value);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  return name+'='+opt.textContent.trim();
}"""

JS_RADIO_BY_LABEL = r"""([name,wantLabel])=>{
  const rs=[...document.querySelectorAll('input[type=radio][name="'+name+'"]')];
  if(!rs.length) return name+':NORADIO';
  function lbl(el){let t='';if(el.id){const l=document.querySelector('label[for="'+CSS.escape(el.id)+'"]');if(l)t=l.textContent.trim();}if(!t){let p=el.closest('label,div,li');if(p){const l=p.querySelector('label');if(l)t=l.textContent.trim();else t=p.textContent.trim();}}return t.toLowerCase();}
  let el=rs.find(r=>lbl(r)===wantLabel.toLowerCase())||rs.find(r=>lbl(r).startsWith(wantLabel.toLowerCase()))||rs.find(r=>r.value.toLowerCase()===wantLabel.toLowerCase());
  if(!el) return name+':NOOPT:'+rs.map(r=>lbl(r)).join('|');
  el.click();
  if(!el.checked){const l=el.id?document.querySelector('label[for="'+CSS.escape(el.id)+'"]'):null;if(l)l.click();}
  return name+'='+wantLabel+':'+el.checked;
}"""

JS_CHECK = r"""(idOrName)=>{
  let el=document.querySelector('input[type=checkbox][name="'+idOrName+'"]')||document.getElementById(idOrName);
  if(!el) return idOrName+':NOCHK';
  if(el.checked) return idOrName+':'+el.checked;
  el.click();
  if(el.checked) return idOrName+':'+el.checked;
  let lbl = el.id ? document.querySelector('label[for="'+CSS.escape(el.id)+'"]') : null;
  if(!lbl){ let p=el.parentElement; for(let i=0;i<4&&p&&!lbl;i++){ if(p.tagName==='LABEL'){lbl=p;break;} lbl=p.querySelector('label'); p=p.parentElement; } }
  if(lbl){ lbl.click(); }
  if(el.checked) return idOrName+':'+el.checked;
  const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'checked');
  d.set.call(el,true);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.dispatchEvent(new Event('click',{bubbles:true}));
  return idOrName+':'+el.checked;
}"""


def set_input(page, sel, val):
    return page.evaluate(JS_SET_INPUT, [sel, val])

def pick_select(page, name, val):
    return page.evaluate(JS_PICK_SELECT, [name, val])

def set_radio(page, name, want_label):
    return page.evaluate(JS_RADIO_BY_LABEL, [name, want_label])

def set_check(page, id_or_name):
    return page.evaluate(JS_CHECK, id_or_name)


def shot(page, debug_dir, name):
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    try:
        page.screenshot(path=os.path.join(debug_dir, name + ".png"), full_page=True)
    except Exception as e:
        log("shot fail", name, e)


def apply_url_from(job_url):
    u = job_url.rstrip("/")
    if u.endswith("/apply"):
        return u + "/"
    return u + "/apply/"


def open_apply_page(ctx, job_url, debug):
    ap = ctx.new_page()
    # Hook turnstile.render to capture the sitekey when the widget mounts.
    try:
        ap.add_init_script(TURNSTILE_HOOK)
    except Exception:
        pass
    target = apply_url_from(job_url)
    ap.goto(target, wait_until="domcontentloaded", timeout=60000)
    ap.wait_for_timeout(3500)
    # Dismiss cookie banner if present (it can overlay the submit button).
    try:
        ap.evaluate(r"""()=>{const b=[...document.querySelectorAll('button')].find(x=>/accept all|accept cookies/i.test(x.textContent||''));if(b)b.click();}""")
    except Exception:
        pass
    ap.wait_for_timeout(800)
    shot(ap, debug, "00-apply-loaded")
    return ap


def upload_resume(page):
    """Set the REQUIRED hidden file input. Workable renders file inputs with
    random ids and no name; pick the required one, fall back to the last file
    input (resume is typically last/required)."""
    inputs = page.query_selector_all('input[type=file]')
    if not inputs:
        return "no-input"
    if not os.path.exists(RESUME):
        return "resume-missing:" + RESUME
    # Prefer required input; else the last one.
    target = None
    for el in inputs:
        try:
            if el.get_attribute("required") is not None:
                target = el
                break
        except Exception:
            pass
    if target is None:
        target = inputs[-1]
    target.set_input_files(RESUME)
    page.wait_for_timeout(2500)
    # Workable shows the uploaded filename / parses the resume; verify a file is set.
    n = 0
    for el in page.query_selector_all('input[type=file]'):
        try:
            cnt = el.evaluate("e=>e.files?e.files.length:0")
            n += cnt
        except Exception:
            pass
    parsed = page.evaluate(r"""()=>/Cyrus_Shekari_Resume|\.pdf|uploaded|remove file|delete/i.test(document.body.innerText)""")
    return f"files={n} parsedText={parsed}"


def map_screening_questions(page):
    """Discover custom screening fields (name starts with CA_ or similar) plus
    any required radios/checkboxes/selects/textareas not in the core set."""
    return page.evaluate(r"""()=>{
      const CORE=new Set(['firstname','lastname','email','headline','phone','address','city','postcode','country','summary','cover_letter','resume']);
      function labelFor(el){
        let t='';
        if(el.id){const l=document.querySelector('label[for="'+CSS.escape(el.id)+'"]');if(l)t=l.textContent.trim();}
        if(!t){let p=el.closest('div,fieldset,li');for(let i=0;i<4&&p&&!t;i++){const l=p.querySelector('label,legend');if(l)t=l.textContent.trim();p=p.parentElement;}}
        return t.replace(/SVGs not supported.*/,'').replace(/^\*/,'').trim().slice(0,160);
      }
      const out=[]; const seenRadio=new Set();
      document.querySelectorAll('input,select,textarea').forEach(e=>{
        const nm=e.name||e.id||'';
        if(e.type==='hidden'||e.type==='file'||e.type==='submit'||e.type==='button') return;
        if(CORE.has(nm)) return;
        if(e.type==='radio'){
          if(seenRadio.has(e.name)) return; seenRadio.add(e.name);
          const rs=[...document.querySelectorAll('input[type=radio][name="'+e.name+'"]')];
          out.push({kind:'radio',name:e.name,req:rs.some(r=>r.required),label:labelFor(e),opts:rs.map(r=>{let t='';if(r.id){const l=document.querySelector('label[for="'+CSS.escape(r.id)+'"]');if(l)t=l.textContent.trim();}if(!t){const p=r.closest('label,li,div');if(p)t=p.textContent.trim();}return t.slice(0,60)||r.value;})});
          return;
        }
        if(e.type==='checkbox'){ out.push({kind:'checkbox',name:e.name,id:e.id,req:e.required,label:labelFor(e)}); return; }
        if(e.tagName==='SELECT'){ out.push({kind:'select',name:e.name||e.id,req:e.required,label:labelFor(e),opts:[...e.options].map(o=>o.textContent.trim()).filter(Boolean)}); return; }
        // text / textarea / email-ish custom
        out.push({kind:(e.tagName==='TEXTAREA'?'textarea':'text'),name:e.name||e.id,req:e.required,label:labelFor(e)});
      });
      return out;
    }""")


# ---- Per-question tailored free-text answers (genuine, not canned) ----------
ID_FIELD_RE = re.compile(r"\b(job\s*id|requisition|req\s*(id|#|number)?|posting\s*id|reference\s*(id|number|code)?|vacancy\s*(id|code))\b", re.I)

# Cyrus's real, truthful experience facts — the ONLY material the model may draw
# on for behavioral/opinion answers. No fabricated employers/titles/metrics.
CYRUS_FACTS = (
    "Cyrus Shekari — Technical Program Manager. Real experience: Microsoft Azure "
    "(TPM since 2024): led a 0-to-1 Resilience Automation Platform, ~$14M+ business "
    "impact, coordinating engineering, product and partner teams under ambiguity. "
    "Amazon Robotics: ran a zero-downtime OS migration across 2,000+ units, aligning "
    "hardware, ops, and supply-chain stakeholders to a hard deadline. Strengths: "
    "driving clarity in ambiguous fast-growth environments, cross-functional "
    "coordination concept->launch, stakeholder/expectation management, adapting "
    "plans under shifting priorities. US citizen, ~2-3 yrs FT experience."
)


def build_tailored_answers(questions, company, role, jd_text, job_code=None):
    """Generate a DISTINCT, truthful, role-tailored answer for each required
    free-text question. ID/code fields get the job code, not prose. Returns
    {name: answer_text}. Falls back to {} on any model failure (caller then
    uses the generic INTEREST blurb so a required field is never left blank)."""
    free = [q for q in questions if q["kind"] in ("text", "textarea") and q.get("req")]
    if not free:
        return {}
    out = {}
    ask = []
    for q in free:
        lbl = (q.get("label") or "").strip()
        if ID_FIELD_RE.search(lbl) and job_code:
            out[q["name"]] = str(job_code)
        else:
            ask.append(q)
    if not ask:
        return out
    try:
        from cover_answer_generator import call_model
    except Exception:
        return out
    qlist = "\n".join(f'{i+1}. {q.get("label")}' for i, q in enumerate(ask))
    prompt = (
        f"You are answering job-application screening questions AS the candidate "
        f"(first person). Role: {role or 'Product/Program Manager'} at "
        f"{company or 'the company'}.\n\nCandidate facts (use ONLY these; do NOT "
        f"invent employers, titles, dates, projects, or metrics):\n{CYRUS_FACTS}\n\n"
        f"Job context (optional):\n{(jd_text or '')[:1200]}\n\n"
        f"Answer each question below in 2-4 concrete sentences. Each answer must "
        f"be DISTINCT, specific, and reference a real example from the candidate "
        f"facts where relevant. No generic filler, no repeating the same story "
        f"verbatim across answers. Do NOT mention being an AI or that this is "
        f"auto-generated.\n\nQuestions:\n{qlist}\n\n"
        f'Return ONLY a JSON array of strings, one answer per question in order, '
        f'e.g. ["answer1","answer2"]. No prose outside the JSON.'
    )
    try:
        raw = call_model(prompt, timeout=240)
        s = raw.strip()
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z]*\n", "", s); s = re.sub(r"\n```\s*$", "", s)
        start, end = s.find("["), s.rfind("]")
        arr = json.loads(s[start:end+1]) if start >= 0 and end > start else []
    except Exception as e:
        log("tailored-answer model failed:", str(e)[:200])
        return out
    for q, ans in zip(ask, arr):
        if isinstance(ans, str) and ans.strip():
            out[q["name"]] = ans.strip()
    return out


# ---- Cloudflare Turnstile handling (token-accepting captcha) ----------------
def detect_turnstile(page, wait_ms=12000):
    """After the form is filled, Workable lazily mounts a Cloudflare Turnstile
    widget. The most reliable source is the hooked turnstile.render params
    (TURNSTILE_HOOK), which capture sitekey + action even when response-field
    is false (no DOM input). Retries up to wait_ms for the widget to mount.
    Returns (sitekey, action) or (None, None)."""
    deadline = time.time() + wait_ms / 1000.0
    while time.time() < deadline:
        # (a) hooked render params — primary, carries action + sitekey
        try:
            params = page.evaluate("()=>window.__cfParams||[]")
            for pr in params:
                if pr.get("sitekey"):
                    return pr["sitekey"], pr.get("action")
        except Exception:
            pass
        # (b) DOM data-sitekey
        sk = page.evaluate(r"""()=>{
          let s=null;
          document.querySelectorAll('[data-sitekey]').forEach(e=>{const k=e.getAttribute('data-sitekey');if(k)s=k;});
          return s;
        }""")
        if sk:
            return sk, None
        # (c) iframe URL param k=
        for fr in page.frames:
            u = fr.url or ""
            if "challenges.cloudflare.com" in u or "turnstile" in u:
                m = re.search(r"[?&/]k=([0-9A-Za-z_-]+)", u)
                if m:
                    return m.group(1), None
        # nudge the widget to mount: scroll it into view
        try:
            page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
        except Exception:
            pass
        page.wait_for_timeout(800)
    return None, None


TURNSTILE_HOOK = r"""
  window.__cfParams=[];
  const __iv=setInterval(()=>{
    if(window.turnstile&&!window.__cfHooked){
      window.__cfHooked=true;
      const orig=window.turnstile.render;
      window.turnstile.render=function(el,opts){try{window.__cfParams.push(opts||{});}catch(e){}return orig.apply(this,arguments);};
    }
  },50);
"""


def inject_turnstile_token(page, token):
    """Inject a solved Turnstile token so Workable's form reads it. Workable
    renders the widget with response-field:false (NO hidden input), reading the
    token via the render callback / turnstile.getResponse(). So we: (1) set any
    cf-turnstile-response input if present, (2) override turnstile.getResponse,
    and (3) invoke the captured render callback with the token."""
    return page.evaluate(r"""(token)=>{
      const rep={inputs:0,override:false,callback:false};
      document.querySelectorAll('input[name="cf-turnstile-response"],input[name="g-recaptcha-response"],textarea[name="cf-turnstile-response"],textarea[name="g-recaptcha-response"]').forEach(i=>{
        const set=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value')||Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');
        try{set.set.call(i,token);}catch(e){i.value=token;}
        i.dispatchEvent(new Event('input',{bubbles:true}));
        i.dispatchEvent(new Event('change',{bubbles:true}));
        rep.inputs++;
      });
      if(window.turnstile&&typeof window.turnstile.getResponse==='function'){
        const _o=window.turnstile.getResponse.bind(window.turnstile);
        window.turnstile.getResponse=function(id){try{const r=_o(id);if(r)return r;}catch(e){}return token;};
        rep.override=true;
      }
      // Fire the captured render callback(s) so the React form receives the token.
      try{
        (window.__cfParams||[]).forEach(pr=>{
          if(pr&&typeof pr.callback==='function'){pr.callback(token);rep.callback=true;}
        });
      }catch(e){}
      return rep;
    }""", token)


def solve_turnstile_if_present(page, debug=None):
    """Detect+solve a Turnstile widget. Returns dict with status. Token-accepting
    captcha (NOT score-gated) -> 2Captcha clears it."""
    sk, action = detect_turnstile(page)
    if not sk:
        return {"present": False}
    log("turnstile sitekey:", sk, "action:", action)
    try:
        from captcha_solver import CaptchaSolver
        page_url = page.url
        last_err = None
        for vendor in ("twocaptcha", "capsolver"):
            try:
                tok = CaptchaSolver(vendor=vendor).solve_turnstile(sk, page_url, action=action)
                if tok:
                    rep = inject_turnstile_token(page, tok)
                    log("turnstile solved via", vendor, "token_len", len(tok), "inject", rep)
                    return {"present": True, "solved": True, "vendor": vendor,
                            "action": action, "token_len": len(tok), "inject": rep}
            except Exception as e:
                last_err = f"{vendor}: {str(e)[:160]}"
                continue
        log("turnstile solve failed:", last_err)
        return {"present": True, "solved": False, "error": last_err}
    except Exception as e:
        return {"present": True, "solved": False, "error": str(e)[:200]}


def answer_screening(page, questions, debug, tailored=None):
    """Fill discovered screening questions per heuristics. Returns audit list."""
    audit = []
    for q in questions:
        kind, name, label, req = q["kind"], q["name"], q.get("label", ""), q.get("req")
        decision = classify_question(label)
        if kind in ("text", "textarea"):
            # Free-text required question -> tailored per-question answer if we
            # generated one; else the generic interest blurb. Optional -> skip.
            if req:
                ans = (tailored or {}).get(name) or INTEREST
                tag = "TAILORED" if (tailored or {}).get(name) else "INTEREST_BLURB"
                r = page.evaluate(JS_SET_INPUT, [f'[name="{name}"]', ans])
                if r.endswith("MISSING"):
                    r = page.evaluate(JS_SET_INPUT, ['#' + name, ans])
                audit.append({"q": label, "kind": kind, "answer": tag, "text": ans[:120], "r": r})
            else:
                audit.append({"q": label, "kind": kind, "answer": "(skipped optional)"})
        elif kind == "select":
            opt = pick_option(q.get("opts", []), decision)
            if opt is None and req:
                opt = (q.get("opts") or [None])[-1]  # last resort: last option
            r = pick_select(page, name, opt) if opt is not None else f"{name}:no-pick"
            audit.append({"q": label, "kind": kind, "decision": decision, "answer": opt, "r": r})
        elif kind == "radio":
            opt = pick_option(q.get("opts", []), decision)
            r = set_radio(page, name, opt) if opt else f"{name}:no-opt"
            audit.append({"q": label, "kind": kind, "decision": decision, "answer": opt, "r": r})
        elif kind == "checkbox":
            # Consent/agree/privacy -> check. Otherwise check only if required.
            is_consent = re.search(r"consent|agree|privacy|terms|gdpr|acknowledg|i confirm|policy", label, re.I)
            if is_consent or req:
                r = set_check(page, name or q.get("id"))
                audit.append({"q": label, "kind": kind, "answer": "checked", "r": r})
            else:
                audit.append({"q": label, "kind": kind, "answer": "(left unchecked)"})
    return audit


def fill_core(page, debug):
    log("fill core fields")
    out = {}
    out["firstname"] = set_input(page, 'input[name="firstname"]', FIRST)
    out["lastname"] = set_input(page, 'input[name="lastname"]', LAST)
    out["email"] = set_input(page, 'input[name="email"]', EMAIL)
    out["phone"] = set_input(page, 'input[name="phone"]', PHONE)
    out["headline"] = set_input(page, 'input[name="headline"]', HEADLINE)
    # address has a geo-autocomplete; set value + also fill city/postcode/country
    out["address"] = set_input(page, 'input[name="address"]', ADDRESS)
    page.wait_for_timeout(800)
    # try to commit any autocomplete suggestion (press Escape to keep typed value)
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    out["city"] = set_input(page, 'input[name="city"]', CITY)
    out["postcode"] = set_input(page, 'input[name="postcode"]', POSTCODE)
    out["country"] = set_input(page, 'input[name="country"]', COUNTRY)
    out["resume"] = upload_resume(page)
    log("resume:", out["resume"])
    shot(page, debug, "01-core-filled")
    return out


def detect_confirmation(page):
    return page.evaluate(r"""()=>{
      const t=document.body.innerText;
      const url=location.href;
      const conf=/application (submitted|received|was sent)|thank you for applying|thank you for your (application|interest)|we.{0,3}ve received your application|your application has been (submitted|received|sent)|successfully (submitted|applied)|application complete/i.test(t);
      return JSON.stringify({confirmed:conf, url, head:t.slice(0,400)});
    }""")


def detect_validation_errors(page):
    return page.evaluate(r"""()=>{
      const errs=[...document.querySelectorAll('[class*="error"],[role=alert],[aria-invalid=true]')].map(e=>(e.textContent||'').trim()).filter(Boolean);
      return [...new Set(errs)].slice(0,12);
    }""")


def click_submit(page):
    return page.evaluate(r"""()=>{
      let b=[...document.querySelectorAll('button[type=submit],button')].find(x=>/submit application|^submit$|^apply$/i.test((x.textContent||'').trim()));
      if(!b) b=document.querySelector('button[type=submit]');
      if(b){ b.scrollIntoView({block:'center'}); b.click(); return (b.textContent||'').trim()||'clicked'; }
      return null;
    }""")


def run(args):
    from playwright.sync_api import sync_playwright
    result = {"url": args.url, "status": "unknown", "dryrun": args.dryrun}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = open_apply_page(ctx, args.url, args.debug)
        page.set_default_timeout(20000)

        # Verify we're on a real apply form.
        has_form = page.evaluate("""()=>!!document.querySelector('input[name="firstname"]') && !!document.querySelector('input[name="email"]')""")
        if not has_form:
            result["status"] = "blocked-no-form"
            result["page_head"] = page.evaluate("()=>document.body.innerText.slice(0,400)")
            shot(page, args.debug, "ERR-no-form")
            print(json.dumps(result, indent=1))
            if not args.keep_open:
                page.close()
            return result

        core = fill_core(page, args.debug)
        result["core"] = core

        questions = map_screening_questions(page)
        result["screening_discovered"] = questions
        # Generate genuine, distinct per-question answers (not a canned blurb).
        job_code = None
        m = re.search(r"/j/([A-Za-z0-9]+)", args.url)
        if m:
            job_code = m.group(1)
        jd_text = ""
        if getattr(args, "jd", None) and os.path.exists(args.jd):
            try:
                jd_text = open(args.jd, encoding="utf-8", errors="ignore").read()
            except Exception:
                pass
        if not jd_text:
            try:
                jd_text = page.evaluate("()=>document.body.innerText.slice(0,2000)")
            except Exception:
                pass
        tailored = build_tailored_answers(questions, getattr(args, "company", None),
                                          getattr(args, "role", None), jd_text, job_code)
        result["tailored_count"] = len(tailored)
        audit = answer_screening(page, questions, args.debug, tailored=tailored)
        result["screening_answers"] = audit
        shot(page, args.debug, "02-screening-filled")

        # Print audit lines so a human can review before any real submit.
        log("---- SCREENING / ANSWER AUDIT ----")
        for a in audit:
            log(f"  Q: {a.get('q','')}  ->  {a.get('answer')}  ({a.get('kind')}, decision={a.get('decision','-')})  [{a.get('r','')}]")
        log("  resume:", core.get("resume"))
        log("----------------------------------")

        if args.dryrun:
            result["status"] = "dryrun-ready"
            result["note"] = "Form + screening + resume filled; STOPPED before final Submit."
            shot(page, args.debug, "03-dryrun-final")
            print(json.dumps(result, indent=1))
            if not args.keep_open:
                page.close()
            return result

        # REAL SUBMIT
        # Authoritative confirmation: listen for the apply POST -> 201.
        apply_posts = []
        def _on_resp(r):
            try:
                if (r.request.method == "POST"
                        and re.search(r"apply\.workable\.com/api/v\d+/jobs/[^/]+/apply", r.url)):
                    apply_posts.append({"status": r.status, "url": r.url})
            except Exception:
                pass
        page.on("response", _on_resp)

        # Scroll so the lazy/interaction-only Turnstile mounts and our hook
        # captures its render params (__cfParams). Do NOT pre-click Submit:
        # a tokenless submit returns HTTP 412 and POISONS the attempt (the
        # token is single-use). Solve+inject FIRST so the form auto-submits
        # on the render callback with a valid token (proven on LCM + Unusual
        # Machines, 2026-06-03).
        try:
            page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
        except Exception:
            pass
        page.wait_for_timeout(2000)

        ts = solve_turnstile_if_present(page, args.debug)
        result["turnstile"] = ts
        if not ts.get("present"):
            # Widget is interaction-only and hasn't rendered yet. One click
            # mounts it (a tokenless 412 here is harmless — Workable accepts a
            # fresh tokenized retry). Then solve+inject for real.
            log("turnstile not yet mounted; clicking submit once to trigger render")
            click_submit(page)
            page.wait_for_timeout(2500)
            ts = solve_turnstile_if_present(page, args.debug)
            result["turnstile"] = ts
        if ts.get("present") and not ts.get("solved"):
            result["status"] = "blocked-turnstile-unsolved"
            shot(page, args.debug, "03b-turnstile-unsolved")
            print(json.dumps(result, indent=1))
            if not args.keep_open:
                page.close()
            return result
        if ts.get("solved"):
            shot(page, args.debug, "03c-turnstile-solved")
            page.wait_for_timeout(1500)
        # If the callback didn't auto-submit, click Submit ONCE (now tokenized).
        if not apply_posts:
            clicked = click_submit(page)
            log("submit click (tokenized):", clicked)
            result["submit_btn"] = clicked
        page.wait_for_timeout(2500)

        # Poll for confirmation: authoritative = apply POST 201; backstop = text.
        final = None
        for _ in range(12):
            if any(pp["status"] in (200, 201) for pp in apply_posts):
                break
            page.wait_for_timeout(2000)
            final = json.loads(detect_confirmation(page))
            if final["confirmed"]:
                break
        result["final"] = final
        result["apply_posts"] = apply_posts
        post_ok = any(pp["status"] in (200, 201) for pp in apply_posts)
        if post_ok or (final and final["confirmed"]):
            result["status"] = "applied"
            result["confirm_via"] = "apply-post" if post_ok else "text"
            shot(page, args.debug, "04-confirmation")
        else:
            result["status"] = "uncertain"
            result["validation_errors"] = detect_validation_errors(page)
            shot(page, args.debug, "04-uncertain")
        print(json.dumps(result, indent=1))
        if not args.keep_open:
            page.close()
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--dryrun", action="store_true")
    ap.add_argument("--debug", default=None, help="screenshot dir")
    ap.add_argument("--cdp", default=CDP_DEFAULT)
    ap.add_argument("--keep-open", action="store_true", help="don't close the apply tab on exit")
    ap.add_argument("--company", default=None, help="company name for tailored answers")
    ap.add_argument("--role", default=None, help="role title for tailored answers")
    ap.add_argument("--jd", default=None, help="path to JD text file for tailoring")
    args = ap.parse_args()
    r = run(args)
    sys.exit(0 if r.get("status") in ("applied", "dryrun-ready") else 2)


if __name__ == "__main__":
    main()