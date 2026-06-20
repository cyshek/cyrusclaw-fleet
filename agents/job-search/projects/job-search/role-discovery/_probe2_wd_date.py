#!/usr/bin/env python3
"""PHASE 2 SPIKE: read-back existing filled blocks' dates (did runner's _fill_wd_date
commit?) + test mechanisms A-E on the EMPTY block's start-date. NEVER submits."""
import sys, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from playwright.sync_api import sync_playwright
import _workday_runner as W

TENANT = "exfo"
URL = "https://exfo.wd10.myworkdayjobs.com/en-US/EXFO_Careers/job/Solutions-Engineer_R-100191"
STATUS = HERE / "STATUS.md"
OUT = HERE / "_probe2_results.json"


def status(msg):
    ts = time.strftime("%H:%M:%S")
    print("[p2]", msg, flush=True)
    try:
        with open(STATUS, "a") as f:
            f.write("[" + ts + "] P2 " + str(msg) + chr(10))
    except Exception:
        pass


def find_resume():
    c = HERE.parent / "resume" / "Cyrus_Shekari_Resume_master.docx"
    return str(c) if c.exists() else None


# Read a date widget by full base (e.g. 'workExperience-8--startDate').
READ_JS = r"""
(base)=>{
  const out={base};
  const g=(suf)=>document.getElementById(base+suf);
  const mon=g('-dateSectionMonth-input'), yr=g('-dateSectionYear-input');
  const monD=g('-dateSectionMonth-display'), yrD=g('-dateSectionYear-display');
  out.monVal = mon?(mon.value||''):null;
  out.yrVal  = yr?(yr.value||''):null;
  out.monDisp= monD?(monD.textContent||'').trim():null;
  out.yrDisp = yrD?(yrD.textContent||'').trim():null;
  out.monAria = mon?{required:mon.getAttribute('aria-required'),invalid:mon.getAttribute('aria-invalid'),valuenow:mon.getAttribute('aria-valuenow'),valuetext:mon.getAttribute('aria-valuetext')}:null;
  // wrap container -> error text
  let wrap=mon; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&(wrap.getAttribute('data-automation-id')||'')==='formField-startDate')break; if(wrap&&(wrap.getAttribute('data-automation-id')||'')==='formField-endDate')break;}
  const errs=[];
  if(wrap){for(const e of wrap.querySelectorAll('[role=alert],[data-automation-id*=error],[id$=-error]')){const t=(e.textContent||'').trim(); if(t)errs.push(t.slice(0,100));}}
  out.errors=errs;
  // picker icon present?
  if(wrap){const ic=wrap.querySelector('[data-automation-id=dateIcon],[data-automation-id*=DatePicker],button');out.iconDa=ic?(ic.getAttribute('data-automation-id')||ic.tagName):null;}
  return out;
}
"""


def read_date(page, base):
    try:
        return page.evaluate(READ_JS, base)
    except Exception as e:
        return {"err": str(e)[:120], "base": base}


def all_we_indices(page):
    return page.evaluate(r"""()=>{const s=new Set();for(const x of document.querySelectorAll('input')){const m=(x.id||'').match(/workExperience-(\d+)--/);if(m)s.add(+m[1]);}return [...s].sort((a,b)=>a-b);}""")


# ---- mechanisms (operate on a section input id) ----
def mB(page, iid, val):
    return page.evaluate(r"""([id,val])=>{const el=document.getElementById(id);if(!el)return 'no-el';el.scrollIntoView({block:'center'});el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,val);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.blur();return el.value;}""", [iid, str(val)])


def mC(page, iid, val):
    return page.evaluate(r"""([id,val])=>{const el=document.getElementById(id);if(!el)return 'no-el';const k=Object.keys(el).find(k=>k.startsWith('__reactProps$'));if(!k)return 'no-reactprops';const props=el[k];const fns=Object.keys(props).filter(p=>typeof props[p]==='function');let called=[];try{if(props.onChange){props.onChange({target:{value:val,name:el.name},currentTarget:{value:val}});called.push('onChange');}}catch(e){called.push('oc-err:'+e.message.slice(0,30));}return JSON.stringify({fns,called,val:el.value});}""", [iid, str(val)])


def mD(page, iid, val):
    try:
        page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", iid)
        page.locator("#" + iid).first.fill(str(val), timeout=4000)
        page.keyboard.press("Tab"); page.wait_for_timeout(300)
        return "filled+tab"
    except Exception as e:
        return "err:" + str(e)[:70]


def mE(page, iid, val):
    try:
        page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", iid)
        page.locator("#" + iid).first.click(timeout=4000); page.wait_for_timeout(150)
        for ch in str(val):
            page.keyboard.press("Digit" + ch); page.wait_for_timeout(110)
        page.keyboard.press("Tab"); page.wait_for_timeout(300)
        return "press+tab"
    except Exception as e:
        return "err:" + str(e)[:70]


def mA_picker(page, base):
    """Open the dateIcon picker for this base, return what the picker DOM looks like."""
    opened = page.evaluate(r"""(base)=>{
      const mon=document.getElementById(base+'-dateSectionMonth-input');
      let wrap=mon; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date/.test(wrap.getAttribute('data-automation-id')||''))break;}
      if(!wrap)return 'no-wrap';
      const ic=wrap.querySelector('[data-automation-id=dateIcon]')||wrap.querySelector('button');
      if(!ic)return 'no-icon';
      ic.scrollIntoView({block:'center'}); ic.click(); return 'clicked-'+(ic.getAttribute('data-automation-id')||ic.tagName);
    }""", base)
    page.wait_for_timeout(900)
    # snapshot any picker popup
    pop = page.evaluate(r"""()=>{
      const pops=[...document.querySelectorAll('[data-automation-id*=datePicker],[data-automation-id*=DatePicker],[role=dialog],[data-automation-id*=monthPicker],[data-automation-id*=calendar]')];
      return pops.slice(0,3).map(p=>({da:p.getAttribute('data-automation-id')||p.getAttribute('role'),txt:(p.textContent||'').trim().slice(0,80)}));
    }""")
    return {"opened": opened, "popup": pop}


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
        status("step " + str(i) + ": " + cur)
        if "My Experience" in cur:
            return True
        if "My Information" in cur:
            W.fill_my_information(page, W.SOURCE_DEFAULT)
        if not W.click_next(page):
            page.wait_for_timeout(1000)
    return "My Experience" in W.current_step_name(page, page.locator("body").text_content() or "")


def main():
    W.EMAIL, W.PW, W._ACCOUNT_MODE = W.resolve_account_for_tenant(TENANT, force_fresh=None)
    W._FRESH_VERIFY_PW = W.PW if W._ACCOUNT_MODE in ("create_fresh", "signin_fresh") else None
    status("account " + W.EMAIL + " mode=" + W._ACCOUNT_MODE)
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
            status("ON My Experience")
            page.wait_for_timeout(1500)
            idxs = all_we_indices(page)
            status("WE block indices: " + json.dumps(idxs))
            out["indices"] = idxs

            # 1) Read-back EXISTING filled blocks' start dates (did runner commit?)
            existing = {}
            for ix in idxs:
                base = "workExperience-" + str(ix) + "--startDate"
                d = read_date(page, base)
                jt = page.evaluate("(ix)=>{const e=document.getElementById('workExperience-'+ix+'--jobTitle');return e?(e.value||''):null;}", ix)
                d["jobTitle"] = jt
                existing[ix] = d
                status("READBACK ix=" + str(ix) + " jt=" + repr(jt) + " monVal=" + repr(d.get("monVal")) + " yrVal=" + repr(d.get("yrVal")) + " monDisp=" + repr(d.get("monDisp")) + " errors=" + json.dumps(d.get("errors")))
            out["existing_readback"] = existing

            # 2) Find the EMPTY block (jobTitle blank) to probe mechanisms on.
            empty_ix = None
            for ix in idxs:
                jt = (existing.get(ix, {}).get("jobTitle") or "").strip()
                if not jt:
                    empty_ix = ix; break
            status("EMPTY block idx = " + str(empty_ix))
            out["empty_idx"] = empty_ix

            if empty_ix is None:
                status("No empty block to probe mechanisms on; using last filled block's start date for mechanism test (will overwrite)")
                empty_ix = idxs[-1] if idxs else None

            if empty_ix is None:
                status("no blocks at all"); ctx.close(); return

            base = "workExperience-" + str(empty_ix) + "--startDate"
            mon_id = base + "-dateSectionMonth-input"
            yr_id = base + "-dateSectionYear-input"
            TARGET_MM, TARGET_YYYY = "08", "2022"

            results = {}

            def probe(label, fn, target_id_for_clear=None):
                status("--- MECH " + label + " on " + base + " ---")
                # clear month first so each mech starts from blank (native clear)
                if target_id_for_clear:
                    try:
                        page.evaluate(r"""(id)=>{const el=document.getElementById(id);if(!el)return;el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,'');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.blur();}""", target_id_for_clear)
                        page.wait_for_timeout(200)
                    except Exception:
                        pass
                try:
                    ret = fn()
                except Exception as e:
                    ret = "EXC:" + str(e)[:90]
                page.wait_for_timeout(600)
                d = read_date(page, base)
                mon = d.get("monVal"); errs = d.get("errors") or []
                month_set = (mon or "").strip() in (TARGET_MM, str(int(TARGET_MM)))
                err_cleared = not any(("required" in (e or "").lower()) or ("must have" in (e or "").lower()) for e in errs)
                results[label] = {"ret": ret, "monVal": mon, "monDisp": d.get("monDisp"), "errors": errs, "month_set": month_set, "err_cleared": err_cleared}
                status("MECH " + label + " -> month_set=" + str(month_set) + " monVal=" + repr(mon) + " monDisp=" + repr(d.get("monDisp")) + " err_cleared=" + str(err_cleared) + " errors=" + json.dumps(errs) + " ret=" + str(ret)[:70])

            # Run B, C, D, E on MONTH (each clears month first). A last.
            probe("B_native_setter", lambda: mB(page, mon_id, TARGET_MM), target_id_for_clear=mon_id)
            probe("C_react_fiber", lambda: mC(page, mon_id, TARGET_MM), target_id_for_clear=mon_id)
            probe("D_fill_tab", lambda: mD(page, mon_id, TARGET_MM), target_id_for_clear=mon_id)
            probe("E_press_seq", lambda: mE(page, mon_id, TARGET_MM), target_id_for_clear=mon_id)
            # A: picker — open + dump popup (don't clear; just inspect)
            a = mA_picker(page, base)
            results["A_picker_open"] = a
            status("MECH A_picker -> " + json.dumps(a)[:200])
            # close any popup with Escape
            try: page.keyboard.press("Escape")
            except Exception: pass

            winner = None
            for lab in ["E_press_seq", "D_fill_tab", "B_native_setter", "C_react_fiber"]:
                if results.get(lab, {}).get("month_set"):
                    winner = lab; break
            status("MONTH WINNER = " + str(winner))
            out["month_winner"] = winner
            out["results"] = results

            # 3) If a winner, fill BOTH month+year via winner, then check FULL block error clear,
            #    then click Next/Continue and see if it advances or spawns a NEW empty block.
            if winner:
                status("--- applying winner " + winner + " to MONTH+YEAR + checking regen ---")
                fn = {"E_press_seq": mE, "D_fill_tab": mD, "B_native_setter": mB, "C_react_fiber": mC}[winner]
                # also fill the rest of the empty block so Next isn't blocked by OTHER fields
                W._kbd_fill_we_block_by_idx(page, str(empty_ix), {
                    "title": "Solutions Engineer Test", "company": "ProbeCo", "location": "Seattle, WA",
                    "current": False, "start": ("08", "2022"), "end": ("06", "2023"),
                    "desc": "probe block do-not-submit",
                })
                page.wait_for_timeout(500)
                # now explicitly (re)assert the start month+year via the winner
                fn(page, mon_id, TARGET_MM); page.wait_for_timeout(300)
                fn(page, yr_id, TARGET_YYYY); page.wait_for_timeout(400)
                d = read_date(page, base)
                status("post-winner start date: monVal=" + repr(d.get("monVal")) + " yrVal=" + repr(d.get("yrVal")) + " errors=" + json.dumps(d.get("errors")))
                out["post_winner_startdate"] = d

                idx_before = all_we_indices(page)
                status("indices BEFORE Next: " + json.dumps(idx_before))
                advanced = W.click_next(page)
                page.wait_for_timeout(2500)
                body = page.locator("body").text_content() or ""
                cur = W.current_step_name(page, body)
                idx_after = all_we_indices(page)
                status("after Next: step=" + cur + " advanced_click=" + str(advanced) + " indices=" + json.dumps(idx_after))
                out["regen_test"] = {"step_after": cur, "indices_before": idx_before, "indices_after": idx_after,
                                     "advanced": advanced, "new_block_spawned": len(idx_after) > len(idx_before),
                                     "left_my_experience": "My Experience" not in cur}
                # capture any errors on page
                errs = page.evaluate(r"""()=>{const o=[];for(const e of document.querySelectorAll('[role=alert],[data-automation-id=errorMessage],[data-automation-id*=error]')){const t=(e.textContent||'').trim();if(t&&t.length<120)o.push(t);}return [...new Set(o)].slice(0,12);}""")
                status("page errors after Next: " + json.dumps(errs))
                out["regen_test"]["page_errors"] = errs

            OUT.write_text(json.dumps(out, indent=2))
            status("WROTE _probe2_results.json. DONE.")
        finally:
            try: ctx.close()
            except Exception: pass


if __name__ == "__main__":
    main()
