#!/usr/bin/env python3
"""PHASE 6 (final recipe): all-JS focus (NO Playwright .click -> no viewport timeouts).
Test on the empty regenerated block:
  KB  : JS-focus month input, page.keyboard.type('08'), JS-focus year input,
        page.keyboard.type('2022'). Read back EXACT mon/yr. (runner-style but per-section
        JS focus + readback)
  KBA : JS-focus month, page.keyboard.type('08') then ArrowRight/Tab handled by widget,
        continue typing '2022' (auto-advance). Read back.
  PICK: all-JS calendar monthPicker: click dateIcon (JS), navigate year arrows (JS clicks),
        click month cell (JS). Read back.
Whichever yields mon=08 & yr=2022 with no error = the recipe. NEVER submits."""
import sys, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from playwright.sync_api import sync_playwright
import _workday_runner as W

TENANT = "exfo"
URL = "https://exfo.wd10.myworkdayjobs.com/en-US/EXFO_Careers/job/Solutions-Engineer_R-100191"
STATUS = HERE / "STATUS.md"
OUT = HERE / "_probe6_results.json"
TMM, TYYYY = "08", "2022"


def status(msg):
    ts = time.strftime("%H:%M:%S")
    print("[p6]", msg, flush=True)
    try:
        with open(STATUS, "a") as f:
            f.write("[" + ts + "] P6 " + str(msg) + chr(10))
    except Exception:
        pass


def resume_path():
    c = HERE.parent / "resume" / "Cyrus_Shekari_Resume_master.docx"
    return str(c) if c.exists() else None


READ_JS = r"""
(base)=>{
  const out={base};
  const g=(suf)=>document.getElementById(base+suf);
  const mon=g('-dateSectionMonth-input'), yr=g('-dateSectionYear-input');
  out.exists=!!mon; out.monVal=mon?(mon.value||''):null; out.yrVal=yr?(yr.value||''):null;
  out.monVT=mon?mon.getAttribute('aria-valuetext'):null; out.yrVT=yr?yr.getAttribute('aria-valuetext'):null;
  let wrap=mon||yr; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date/.test(wrap.getAttribute('data-automation-id')||''))break;}
  const errs=[]; if(wrap){for(const e of wrap.querySelectorAll('[role=alert],[data-automation-id*=error],[id$=-error]')){const t=(e.textContent||'').trim(); if(t)errs.push(t.slice(0,100));}}
  out.errors=errs; return out;
}
"""


def read_date(page, base):
    try: return page.evaluate(READ_JS, base)
    except Exception as e:
        return {"err": str(e)[:120], "base": base}


def we_indices(page):
    return page.evaluate(r"""()=>{const s=new Set();for(const x of document.querySelectorAll('input')){const m=(x.id||'').match(/workExperience-(\d+)--/);if(m)s.add(+m[1]);}return [...s].sort((a,b)=>a-b);}""")


def js_focus(page, iid):
    return page.evaluate("(id)=>{const el=document.getElementById(id);if(!el)return false;el.scrollIntoView({block:'center'});el.focus();return document.activeElement===el;}", iid)


def js_clear(page, iid):
    page.evaluate(r"""(id)=>{const el=document.getElementById(id);if(!el)return;el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,'');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}""", iid)
    page.wait_for_timeout(100)


def fill_text_min(page, ix):
    W._kbd_fill_we_block_by_idx(page, str(ix), {
        "title": "Probe Role", "company": "ProbeCo", "location": "Seattle, WA",
        "current": False, "start": ("01", "2020"), "end": ("01", "2021"), "desc": "probe do-not-submit",
    })
    page.wait_for_timeout(400)
    for which in ("startDate", "endDate"):
        for sec in ("dateSectionMonth-input", "dateSectionYear-input"):
            iid = "workExperience-" + str(ix) + "--" + which + "-" + sec
            if page.evaluate("(id)=>!!document.getElementById(id)", iid):
                js_clear(page, iid)


def recipe_KB(page, base):
    """JS-focus month -> keyboard.type('08'); JS-focus year -> keyboard.type('2022')."""
    mid = base + "-dateSectionMonth-input"; yid = base + "-dateSectionYear-input"
    js_clear(page, mid); js_clear(page, yid)
    js_focus(page, mid); page.wait_for_timeout(120)
    page.keyboard.type(TMM, delay=80); page.wait_for_timeout(250)
    js_focus(page, yid); page.wait_for_timeout(120)
    page.keyboard.type(TYYYY, delay=80); page.wait_for_timeout(250)
    page.keyboard.press("Tab"); page.wait_for_timeout(300)
    return read_date(page, base)


def recipe_KBA(page, base):
    """JS-focus month -> keyboard.type('082022') letting the segment mask auto-advance."""
    mid = base + "-dateSectionMonth-input"; yid = base + "-dateSectionYear-input"
    js_clear(page, mid); js_clear(page, yid)
    js_focus(page, mid); page.wait_for_timeout(120)
    page.keyboard.type(TMM + TYYYY, delay=80); page.wait_for_timeout(300)
    page.keyboard.press("Tab"); page.wait_for_timeout(300)
    return read_date(page, base)


def recipe_PICK(page, base):
    """All-JS calendar monthPicker: open dateIcon, navigate year arrows, click month cell."""
    mid = base + "-dateSectionMonth-input"
    js_clear(page, mid); js_clear(page, base + "-dateSectionYear-input")
    opened = page.evaluate(r"""(base)=>{
      const mon=document.getElementById(base+'-dateSectionMonth-input');
      let wrap=mon; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date/.test(wrap.getAttribute('data-automation-id')||''))break;}
      if(!wrap)return 'no-wrap';
      const ic=wrap.querySelector('[data-automation-id=dateIcon]'); if(!ic)return 'no-icon';
      ic.scrollIntoView({block:'center'}); ic.click(); return 'clicked';
    }""", base)
    page.wait_for_timeout(800)
    struct = page.evaluate(r"""()=>{
      const mp=document.querySelector('[data-automation-id*=monthPicker]'); if(!mp)return {none:true};
      const btns=[...mp.querySelectorAll('button,[role=button]')].map(b=>({da:b.getAttribute('data-automation-id')||'',al:b.getAttribute('aria-label')||'',txt:(b.textContent||'').trim().slice(0,14)})).slice(0,24);
      const yr=[...mp.querySelectorAll('*')].map(e=>(e.textContent||'').trim()).find(t=>/^\d{4}$/.test(t));
      return {year:yr, btns};
    }""")
    nav = page.evaluate(r"""([targetYear,targetMonAbbr])=>{
      const mp=document.querySelector('[data-automation-id*=monthPicker]'); if(!mp)return 'no-mp';
      function curYear(){const t=[...mp.querySelectorAll('*')].map(e=>(e.textContent||'').trim()).find(s=>/^\d{4}$/.test(s)); return t?parseInt(t):null;}
      const allb=[...mp.querySelectorAll('button,[role=button]')];
      const prev=allb.find(b=>/prev|back|left/i.test((b.getAttribute('aria-label')||'')+(b.getAttribute('data-automation-id')||'')));
      const next=allb.find(b=>/next|forward|right/i.test((b.getAttribute('aria-label')||'')+(b.getAttribute('data-automation-id')||'')));
      let guard=0, cy=curYear(); const path=[];
      while(cy!==null && cy!==targetYear && guard<60){
        if(cy>targetYear){ if(!prev){path.push('no-prev');break;} prev.click(); } else { if(!next){path.push('no-next');break;} next.click(); }
        guard++; cy=curYear();
      }
      const mcell=[...mp.querySelectorAll('button,[role=button],div,td,abbr,span')].find(b=>(b.textContent||'').trim()===targetMonAbbr);
      if(mcell){ mcell.click(); return 'clicked-'+targetMonAbbr+'@year'+cy+' guard'+guard; }
      return 'no-month-cell@'+cy+' guard'+guard;
    }""", [int(TYYYY), "Aug"])
    page.wait_for_timeout(600)
    return {"opened": opened, "struct": struct, "nav": nav, "readback": read_date(page, base)}


def navigate(page):
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    for cb in ["[data-automation-id=legalNoticeAcceptButton]", "button:has-text('Accept Cookies')"]:
        if page.locator(cb).count():
            try: page.locator(cb).first.click(timeout=3000)
            except Exception: pass
            break
    for _ in range(6):
        if (page.locator("[data-automation-id=email]").count()
                or page.locator("[data-automation-id=pageFooterNextButton]").count()
                or page.locator("input#name--legalName--firstName").count()):
            break
        for sel in ["[data-automation-id=applyManually]", "[data-automation-id=continueButton]", "[data-automation-id=adventureButton]"]:
            if page.locator(sel).count():
                W.safe_click(page, sel); page.wait_for_timeout(3000); break
        else:
            page.wait_for_timeout(1500)
    if not W.ensure_signed_in(page, TENANT, base_url=URL):
        return False
    for i in range(8):
        page.wait_for_timeout(1500)
        body = page.locator("body").text_content() or ""
        cur = W.current_step_name(page, body)
        status("nav step " + str(i) + ": " + cur)
        if "My Experience" in cur:
            return True
        if "My Information" in cur:
            W.fill_my_information(page, W.SOURCE_DEFAULT)
        if not W.click_next(page):
            page.wait_for_timeout(1000)
    return "My Experience" in W.current_step_name(page, page.locator("body").text_content() or "")


def ev(rb):
    mon = (rb.get("monVal") or "").strip(); yr = (rb.get("yrVal") or "").strip()
    mon_ok = mon in (TMM, str(int(TMM))); yr_ok = yr == TYYYY
    err_clear = not any(("required" in (e or "").lower()) or ("must" in (e or "").lower()) or ("invalid" in (e or "").lower()) for e in (rb.get("errors") or []))
    return {"mon": mon, "yr": yr, "mon_ok": mon_ok, "yr_ok": yr_ok, "both_ok": mon_ok and yr_ok, "err_clear": err_clear, "errors": rb.get("errors")}


def find_empty(page, idxs):
    for ix in idxs:
        if not (page.evaluate("(ix)=>{const e=document.getElementById('workExperience-'+ix+'--jobTitle');return e?(e.value||''):'';}", ix) or "").strip():
            return ix
    return None


def add_block(page, before):
    W._wd_section_add(page, "Work Experience")
    page.wait_for_timeout(1500)
    after = we_indices(page)
    new = [i for i in after if i not in before]
    return (new[0] if new else None)


def main():
    W.EMAIL, W.PW, W._ACCOUNT_MODE = W.resolve_account_for_tenant(TENANT, force_fresh=None)
    W._FRESH_VERIFY_PW = W.PW if W._ACCOUNT_MODE in ("create_fresh", "signin_fresh") else None
    status("account " + W.EMAIL)
    out = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(HERE.parent / ".workday-browser-data" / TENANT),
            headless=True, viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            accept_downloads=True,
        )
        page = ctx.new_page(); page.set_default_timeout(20000)
        try:
            if not navigate(page):
                status("FAILED reach My Experience"); ctx.close(); return
            status("ON My Experience -> handle_experience")
            try: W.handle_experience(page, resume_path())
            except Exception as e:
                status("handle_experience err: " + str(e)[:120])
            page.wait_for_timeout(2000)
            idxs = we_indices(page); status("idxs " + json.dumps(idxs))

            recipes = {}

            # KB on the empty block
            ix = find_empty(page, idxs)
            status("KB on empty block " + str(ix))
            if ix is not None:
                fill_text_min(page, ix)
                rb = recipe_KB(page, "workExperience-" + str(ix) + "--startDate")
                recipes["KB_focus_type_persection"] = {"ix": ix, "rb": rb, "eval": ev(rb)}
                status("KB -> " + json.dumps(ev(rb)) + " raw mon=" + repr(rb.get("monVal")) + " yr=" + repr(rb.get("yrVal")) + " VT=" + repr(rb.get("monVT")) + "/" + repr(rb.get("yrVT")))

            # KBA on a fresh block
            nix = add_block(page, we_indices(page)); status("KBA block " + str(nix))
            if nix is not None:
                fill_text_min(page, nix)
                rb = recipe_KBA(page, "workExperience-" + str(nix) + "--startDate")
                recipes["KBA_focus_type_combined"] = {"ix": nix, "rb": rb, "eval": ev(rb)}
                status("KBA -> " + json.dumps(ev(rb)) + " raw mon=" + repr(rb.get("monVal")) + " yr=" + repr(rb.get("yrVal")) + " VT=" + repr(rb.get("monVT")) + "/" + repr(rb.get("yrVT")))

            # PICK on a fresh block
            aix = add_block(page, we_indices(page)); status("PICK block " + str(aix))
            if aix is not None:
                fill_text_min(page, aix)
                res = recipe_PICK(page, "workExperience-" + str(aix) + "--startDate")
                recipes["PICK_calendar"] = {"ix": aix, "result": res, "eval": ev(res.get("readback", {}))}
                status("PICK struct: " + json.dumps(res.get("struct"))[:280])
                status("PICK nav=" + str(res.get("nav")) + " -> " + json.dumps(ev(res.get("readback", {}))) + " raw mon=" + repr(res.get("readback", {}).get("monVal")) + " yr=" + repr(res.get("readback", {}).get("yrVal")))

            out["recipes"] = recipes
            winner = None
            for lab in ["KB_focus_type_persection", "KBA_focus_type_combined", "PICK_calendar"]:
                if recipes.get(lab, {}).get("eval", {}).get("both_ok"):
                    winner = lab; break
            out["winner"] = winner
            status("WINNER = " + str(winner))
            OUT.write_text(json.dumps(out, indent=2))
            status("WROTE _probe6_results.json. DONE (no submit).")
        finally:
            try: ctx.close()
            except Exception: pass


if __name__ == "__main__":
    main()
