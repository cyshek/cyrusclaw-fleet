#!/usr/bin/env python3
"""PHASE 5: nail the EXACT date-commit recipe. The combined MM/YYYY widget garbles digits
when month+year are typed sequentially with Tab. Test two robust recipes on a fresh block:
  K1: .fill() month section, then .fill() year section as SEPARATE explicit actions
      (no Tab between; click/focus each section by id first).
  K2: type into the COMBINED display via the month input: focus month, type 'MMYYYY'
      letting the segment-mask auto-advance (Workday auto-advances month->year).
  A : calendar monthPicker: click dateIcon -> monthPicker popup -> navigate year arrows
      -> click month cell (Aug). Read back EXACT mon+yr.
Run all three on DISTINCT fresh blocks (Add a block per recipe) so they don't interfere.
NEVER submits."""
import sys, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from playwright.sync_api import sync_playwright
import _workday_runner as W

TENANT = "exfo"
URL = "https://exfo.wd10.myworkdayjobs.com/en-US/EXFO_Careers/job/Solutions-Engineer_R-100191"
STATUS = HERE / "STATUS.md"
OUT = HERE / "_probe5_results.json"
TMM, TYYYY = "08", "2022"


def status(msg):
    ts = time.strftime("%H:%M:%S")
    print("[p5]", msg, flush=True)
    try:
        with open(STATUS, "a") as f:
            f.write("[" + ts + "] P5 " + str(msg) + chr(10))
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
  out.monInvalid=mon?mon.getAttribute('aria-invalid'):null; out.yrInvalid=yr?yr.getAttribute('aria-invalid'):null;
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


def clear_input(page, iid):
    page.evaluate(r"""(id)=>{const el=document.getElementById(id);if(!el)return;el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,'');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}""", iid)
    page.wait_for_timeout(120)


def add_block(page, before):
    """Click Work Experience Add, return the new index (not in `before`)."""
    W._wd_section_add(page, "Work Experience")
    page.wait_for_timeout(1500)
    after = we_indices(page)
    new = [i for i in after if i not in before]
    return (new[0] if new else None), after


def fill_text_min(page, ix):
    """Give a block minimal valid text so it isn't required-empty (keeps it stable)."""
    W._kbd_fill_we_block_by_idx(page, str(ix), {
        "title": "Probe Role", "company": "ProbeCo", "location": "Seattle, WA",
        "current": False, "start": ("01", "2020"), "end": ("01", "2021"), "desc": "probe do-not-submit",
    })
    page.wait_for_timeout(400)
    # clear the dates kbd-fill set, so each recipe starts from blank
    for which in ("startDate", "endDate"):
        for sec in ("dateSectionMonth-input", "dateSectionYear-input"):
            iid = "workExperience-" + str(ix) + "--" + which + "-" + sec
            if page.evaluate("(id)=>!!document.getElementById(id)", iid):
                clear_input(page, iid)


def recipe_K1(page, ix):
    """Separate .fill() on each section input, click/focus each first, NO Tab between."""
    sb = "workExperience-" + str(ix) + "--startDate"
    mid = sb + "-dateSectionMonth-input"; yid = sb + "-dateSectionYear-input"
    page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", mid)
    clear_input(page, mid); clear_input(page, yid)
    page.locator("#" + mid).first.click(timeout=4000); page.wait_for_timeout(120)
    page.locator("#" + mid).first.fill(TMM, timeout=4000); page.wait_for_timeout(250)
    page.locator("#" + yid).first.click(timeout=4000); page.wait_for_timeout(120)
    page.locator("#" + yid).first.fill(TYYYY, timeout=4000); page.wait_for_timeout(250)
    page.keyboard.press("Tab"); page.wait_for_timeout(300)
    return read_date(page, sb)


def recipe_K2(page, ix):
    """Focus month, type the full MMYYYY string letting the mask auto-advance month->year."""
    sb = "workExperience-" + str(ix) + "--startDate"
    mid = sb + "-dateSectionMonth-input"; yid = sb + "-dateSectionYear-input"
    page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", mid)
    clear_input(page, mid); clear_input(page, yid)
    page.locator("#" + mid).first.click(timeout=4000); page.wait_for_timeout(150)
    # type month then year digits with small delays; Workday auto-advances to year section
    page.keyboard.type(TMM + TYYYY, delay=90)
    page.keyboard.press("Tab"); page.wait_for_timeout(300)
    return read_date(page, sb)


def recipe_A(page, ix):
    """Calendar monthPicker: open dateIcon -> navigate year arrows -> click month cell."""
    sb = "workExperience-" + str(ix) + "--startDate"
    mid = sb + "-dateSectionMonth-input"
    clear_input(page, mid); clear_input(page, sb + "-dateSectionYear-input")
    opened = page.evaluate(r"""(base)=>{
      const mon=document.getElementById(base+'-dateSectionMonth-input');
      let wrap=mon; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date/.test(wrap.getAttribute('data-automation-id')||''))break;}
      if(!wrap)return 'no-wrap';
      const ic=wrap.querySelector('[data-automation-id=dateIcon]'); if(!ic)return 'no-icon';
      ic.scrollIntoView({block:'center'}); ic.click(); return 'clicked';
    }""", sb)
    page.wait_for_timeout(800)
    # Inspect monthPicker structure: year label + prev/next buttons + month cells
    struct = page.evaluate(r"""()=>{
      const mp=document.querySelector('[data-automation-id*=monthPicker]');
      if(!mp)return {none:true};
      const btns=[...mp.querySelectorAll('button,[role=button]')].map(b=>({da:b.getAttribute('data-automation-id')||'',al:b.getAttribute('aria-label')||'',txt:(b.textContent||'').trim().slice(0,12)})).slice(0,30);
      // year display
      const yr=[...mp.querySelectorAll('*')].map(e=>(e.textContent||'').trim()).find(t=>/^\d{4}$/.test(t));
      return {year:yr, btns, html:(mp.innerText||'').slice(0,120)};
    }""")
    out = {"opened": opened, "struct": struct}
    # Navigate year: click prev/next year arrow until target year shown, then click month.
    nav = page.evaluate(r"""([targetYear,targetMonAbbr])=>{
      const mp=document.querySelector('[data-automation-id*=monthPicker]'); if(!mp)return 'no-mp';
      function curYear(){const t=[...mp.querySelectorAll('*')].map(e=>(e.textContent||'').trim()).find(s=>/^\d{4}$/.test(s)); return t?parseInt(t):null;}
      // find prev/next year buttons (aria-label often 'Previous'/'Next' or contains 'year')
      const allb=[...mp.querySelectorAll('button,[role=button]')];
      const prev=allb.find(b=>/prev/i.test((b.getAttribute('aria-label')||'')+(b.getAttribute('data-automation-id')||'')));
      const next=allb.find(b=>/next/i.test((b.getAttribute('aria-label')||'')+(b.getAttribute('data-automation-id')||'')));
      let guard=0, cy=curYear();
      while(cy!==null && cy!==targetYear && guard<40){
        if(cy>targetYear){ if(!prev)break; prev.click(); } else { if(!next)break; next.click(); }
        guard++; cy=curYear();
      }
      // click the month cell matching abbr
      const mcell=[...mp.querySelectorAll('button,[role=button],div,td')].find(b=>(b.textContent||'').trim()===targetMonAbbr);
      if(mcell){ mcell.click(); return 'clicked-'+targetMonAbbr+'@'+cy; }
      return 'no-month-cell@'+cy;
    }""", [int(TYYYY), "Aug"])
    out["nav"] = nav
    page.wait_for_timeout(600)
    out["readback"] = read_date(page, sb)
    return out


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


def evaluate_rb(rb):
    mon = (rb.get("monVal") or "").strip(); yr = (rb.get("yrVal") or "").strip()
    mon_ok = mon in (TMM, str(int(TMM)))
    yr_ok = yr == TYYYY
    err_clear = not any(("required" in (e or "").lower()) or ("must have" in (e or "").lower()) or ("invalid" in (e or "").lower()) for e in (rb.get("errors") or []))
    return {"mon": mon, "yr": yr, "mon_ok": mon_ok, "yr_ok": yr_ok, "both_ok": mon_ok and yr_ok, "err_clear": err_clear, "errors": rb.get("errors")}


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
            status("ON My Experience -> handle_experience (creates blocks)")
            try: W.handle_experience(page, resume_path())
            except Exception as e:
                status("handle_experience err: " + str(e)[:120])
            page.wait_for_timeout(2000)
            base_idxs = we_indices(page)
            status("base indices: " + json.dumps(base_idxs))

            # Use the empty regenerated block for recipe K1; Add fresh blocks for K2 and A.
            empty_ix = None
            for ix in base_idxs:
                if not (page.evaluate("(ix)=>{const e=document.getElementById('workExperience-'+ix+'--jobTitle');return e?(e.value||''):'';}", ix) or "").strip():
                    empty_ix = ix; break

            recipes = {}

            # --- K1 on empty block (give it min text first) ---
            if empty_ix is not None:
                status("K1 target empty block " + str(empty_ix))
                fill_text_min(page, empty_ix)
                rb = recipe_K1(page, empty_ix)
                recipes["K1_separate_fill"] = {"ix": empty_ix, "rb": rb, "eval": evaluate_rb(rb)}
                status("K1 -> " + json.dumps(recipes["K1_separate_fill"]["eval"]) + " rawMon=" + repr(rb.get("monVal")) + " rawYr=" + repr(rb.get("yrVal")))

            # --- K2 on a fresh Add block ---
            cur_idxs = we_indices(page)
            nix, after = add_block(page, cur_idxs)
            status("K2 added block " + str(nix))
            if nix is not None:
                fill_text_min(page, nix)
                rb = recipe_K2(page, nix)
                recipes["K2_type_combined"] = {"ix": nix, "rb": rb, "eval": evaluate_rb(rb)}
                status("K2 -> " + json.dumps(recipes["K2_type_combined"]["eval"]) + " rawMon=" + repr(rb.get("monVal")) + " rawYr=" + repr(rb.get("yrVal")))

            # --- A on a fresh Add block ---
            cur_idxs = we_indices(page)
            aix, after = add_block(page, cur_idxs)
            status("A added block " + str(aix))
            if aix is not None:
                fill_text_min(page, aix)
                rb_full = recipe_A(page, aix)
                recipes["A_calendar_picker"] = {"ix": aix, "result": rb_full, "eval": evaluate_rb(rb_full.get("readback", {}))}
                status("A struct: " + json.dumps(rb_full.get("struct"))[:300])
                status("A nav: " + str(rb_full.get("nav")) + " -> " + json.dumps(recipes["A_calendar_picker"]["eval"]) + " rawMon=" + repr(rb_full.get("readback", {}).get("monVal")) + " rawYr=" + repr(rb_full.get("readback", {}).get("yrVal")))

            out["recipes"] = recipes
            # Winner = first recipe with both_ok
            winner = None
            for lab in ["A_calendar_picker", "K2_type_combined", "K1_separate_fill"]:
                if recipes.get(lab, {}).get("eval", {}).get("both_ok"):
                    winner = lab; break
            out["winner"] = winner
            status("RECIPE WINNER (both mon+yr correct) = " + str(winner))

            OUT.write_text(json.dumps(out, indent=2))
            status("WROTE _probe5_results.json. DONE. (no submit)")
        finally:
            try: ctx.close()
            except Exception: pass


if __name__ == "__main__":
    main()
