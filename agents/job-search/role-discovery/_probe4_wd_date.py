#!/usr/bin/env python3
"""PHASE 4 CONFIRM: fill EVERY work-exp block's start (+end) date via mechanism D
(.fill + Tab) and via mechanism C (react onChange) CLEANLY, read back EXACT values,
verify red error gone, then click Next to confirm (a) no new block regen, (b) step
advances past My Experience. Also probe the calendar PICKER (A) DOM for completeness.
NEVER submits: if it would leave My Experience, we STOP (do not proceed to Review)."""
import sys, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from playwright.sync_api import sync_playwright
import _workday_runner as W

TENANT = "exfo"
URL = "https://exfo.wd10.myworkdayjobs.com/en-US/EXFO_Careers/job/Solutions-Engineer_R-100191"
STATUS = HERE / "STATUS.md"
OUT = HERE / "_probe4_results.json"


def status(msg):
    ts = time.strftime("%H:%M:%S")
    print("[p4]", msg, flush=True)
    try:
        with open(STATUS, "a") as f:
            f.write("[" + ts + "] P4 " + str(msg) + chr(10))
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
  out.exists = !!mon;
  out.monVal = mon?(mon.value||''):null;
  out.yrVal  = yr?(yr.value||''):null;
  out.monVT = mon?mon.getAttribute('aria-valuetext'):null;
  out.yrVT  = yr?yr.getAttribute('aria-valuetext'):null;
  out.monInvalid = mon?mon.getAttribute('aria-invalid'):null;
  let wrap=mon||yr; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date/.test(wrap.getAttribute('data-automation-id')||''))break;}
  const errs=[]; if(wrap){for(const e of wrap.querySelectorAll('[role=alert],[data-automation-id*=error],[id$=-error]')){const t=(e.textContent||'').trim(); if(t)errs.push(t.slice(0,100));}}
  out.errors=errs;
  return out;
}
"""


def read_date(page, base):
    try:
        return page.evaluate(READ_JS, base)
    except Exception as e:
        return {"err": str(e)[:120], "base": base}


def we_indices(page):
    return page.evaluate(r"""()=>{const s=new Set();for(const x of document.querySelectorAll('input')){const m=(x.id||'').match(/workExperience-(\d+)--/);if(m)s.add(+m[1]);}return [...s].sort((a,b)=>a-b);}""")


def jobtitle(page, ix):
    return page.evaluate("(ix)=>{const e=document.getElementById('workExperience-'+ix+'--jobTitle');return e?(e.value||''):null;}", ix)


def clear_input(page, iid):
    page.evaluate(r"""(id)=>{const el=document.getElementById(id);if(!el)return;el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,'');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}""", iid)
    page.wait_for_timeout(120)


def fillD(page, iid, val):
    """Mechanism D: scroll, focus via JS, clear, Playwright .fill(), then Tab."""
    page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", iid)
    clear_input(page, iid)
    page.locator("#" + iid).first.fill(str(val), timeout=4000)
    page.keyboard.press("Tab")
    page.wait_for_timeout(250)


def fillC(page, iid, val):
    """Mechanism C: react onChange direct-invoke off the fiber props."""
    page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", iid)
    clear_input(page, iid)
    page.evaluate(r"""([id,val])=>{const el=document.getElementById(id);if(!el)return 'no-el';const k=Object.keys(el).find(k=>k.startsWith('__reactProps$'));if(!k)return 'no-rp';const props=el[k];try{if(props.onChange)props.onChange({target:{value:val,name:el.name},currentTarget:{value:val}});}catch(e){return 'err:'+e.message.slice(0,40);}return 'ok';}""", [iid, str(val)])
    page.wait_for_timeout(250)


def fill_block_dates(page, ix, start_mm, start_yyyy, current, end_mm, end_yyyy, mech):
    """Fill one block's start (+end if not current) dates via mech, return readback."""
    fn = fillD if mech == "D" else fillC
    sb = "workExperience-" + str(ix) + "--startDate"
    fn(page, sb + "-dateSectionMonth-input", start_mm)
    fn(page, sb + "-dateSectionYear-input", start_yyyy)
    sd = read_date(page, sb)
    ed = None
    if not current:
        eb = "workExperience-" + str(ix) + "--endDate"
        if page.evaluate("(id)=>!!document.getElementById(id)", eb + "-dateSectionMonth-input"):
            fn(page, eb + "-dateSectionMonth-input", end_mm)
            fn(page, eb + "-dateSectionYear-input", end_yyyy)
            ed = read_date(page, eb)
    return sd, ed


def probe_picker(page, base):
    """Open calendar picker (dateIcon) and snapshot its DOM, then Escape (no commit needed)."""
    info = page.evaluate(r"""(base)=>{
      const mon=document.getElementById(base+'-dateSectionMonth-input');
      let wrap=mon; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date/.test(wrap.getAttribute('data-automation-id')||''))break;}
      if(!wrap)return {err:'no-wrap'};
      const ic=wrap.querySelector('[data-automation-id=dateIcon]');
      if(!ic)return {err:'no-icon'};
      ic.scrollIntoView({block:'center'}); ic.click();
      return {clicked:true};
    }""", base)
    page.wait_for_timeout(900)
    pop = page.evaluate(r"""()=>{
      const sels=['[data-automation-id*=datePicker]','[data-automation-id*=DatePicker]','[data-automation-id*=monthPicker]','[data-automation-id*=calendar]','[role=dialog]','[role=grid]'];
      for(const s of sels){const el=document.querySelector(s); if(el)return {sel:s, da:el.getAttribute('data-automation-id')||el.getAttribute('role'), txt:(el.textContent||'').trim().slice(0,120)};}
      return {none:true};
    }""")
    try: page.keyboard.press("Escape")
    except Exception: pass
    page.wait_for_timeout(300)
    return {"open": info, "popup": pop}


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


# real history dates keyed by company substring
HIST = {
    "microsoft": {"start": ("03", "2024"), "current": True, "end": (None, None)},
    "amazon": {"start": ("08", "2023"), "current": False, "end": ("12", "2023")},
    "pro painters": {"start": ("05", "2021"), "current": False, "end": ("05", "2022")},
}


def company_of(page, ix):
    return (page.evaluate("(ix)=>{const e=document.getElementById('workExperience-'+ix+'--companyName');return e?(e.value||''):'';}", ix) or "").lower()


def main():
    mech = sys.argv[1] if len(sys.argv) > 1 else "D"
    W.EMAIL, W.PW, W._ACCOUNT_MODE = W.resolve_account_for_tenant(TENANT, force_fresh=None)
    W._FRESH_VERIFY_PW = W.PW if W._ACCOUNT_MODE in ("create_fresh", "signin_fresh") else None
    status("account " + W.EMAIL + " mech=" + mech)
    out = {"mech": mech}
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
            status("ON My Experience -> handle_experience to add+fill text fields")
            try:
                W.handle_experience(page, resume_path())
            except Exception as e:
                status("handle_experience err: " + str(e)[:120])
            page.wait_for_timeout(2000)
            idxs = we_indices(page)
            status("indices: " + json.dumps(idxs))
            out["indices"] = idxs

            # PICKER probe on first block (informational)
            if idxs:
                out["picker"] = probe_picker(page, "workExperience-" + str(idxs[0]) + "--startDate")
                status("PICKER probe: " + json.dumps(out["picker"])[:240])

            # Fill EVERY block's dates via mech, matching company -> history.
            fills = {}
            for ix in idxs:
                jt = (jobtitle(page, ix) or "").strip()
                comp = company_of(page, ix)
                h = None
                for key, v in HIST.items():
                    if key in comp:
                        h = v; break
                if h is None:
                    # empty/unknown block (e.g. regenerated 95): give it a deterministic non-current date
                    if not jt:
                        # fill its text fields first so it's a valid block, else Workday keeps it empty/required
                        W._kbd_fill_we_block_by_idx(page, str(ix), {
                            "title": "Solutions Engineer Probe", "company": "ProbeCo", "location": "Seattle, WA",
                            "current": False, "start": ("08", "2022"), "end": ("06", "2023"), "desc": "probe do-not-submit",
                        })
                        page.wait_for_timeout(400)
                    h = {"start": ("08", "2022"), "current": False, "end": ("06", "2023")}
                sd, ed = fill_block_dates(page, ix, h["start"][0], h["start"][1], h["current"], h["end"][0], h["end"][1], mech)
                fills[ix] = {"company": comp, "current": h["current"], "start": sd, "end": ed}
                status("FILLED ix=" + str(ix) + " comp=" + repr(comp) + " cur=" + str(h["current"])
                       + " -> startMon=" + repr(sd.get("monVal")) + " startYr=" + repr(sd.get("yrVal")) + " startVT=" + repr(sd.get("monVT")) + "/" + repr(sd.get("yrVT")) + " startErr=" + json.dumps(sd.get("errors"))
                       + (" | endMon=" + repr(ed.get("monVal")) + " endYr=" + repr(ed.get("yrVal")) + " endErr=" + json.dumps(ed.get("errors")) if ed else " | (current/no-end)"))
            out["fills"] = fills

            # Re-read ALL dates fresh to confirm persistence after the whole sweep
            final = {}
            allgood = True
            for ix in idxs:
                sd = read_date(page, "workExperience-" + str(ix) + "--startDate")
                jt = (jobtitle(page, ix) or "").strip()
                cur = page.evaluate("(ix)=>{const c=[...document.querySelectorAll('input[type=checkbox]')].find(e=>(e.id||'').includes('workExperience-'+ix+'--currentlyWorkHere'));return !!(c&&c.checked);}", ix)
                ed = read_date(page, "workExperience-" + str(ix) + "--endDate") if not cur else None
                start_ok = bool((sd.get("monVal") or "").strip()) and bool((sd.get("yrVal") or "").strip())
                end_ok = True if cur else (bool((ed or {}).get("monVal")) and bool((ed or {}).get("yrVal")))
                if not (start_ok and end_ok):
                    allgood = False
                final[ix] = {"jobTitle": jt, "current": cur, "startMon": sd.get("monVal"), "startYr": sd.get("yrVal"),
                             "endMon": (ed or {}).get("monVal"), "endYr": (ed or {}).get("yrVal"),
                             "startErr": sd.get("errors"), "endErr": (ed or {}).get("errors"), "start_ok": start_ok, "end_ok": end_ok}
            out["final_readback"] = final
            out["all_dates_committed"] = allgood
            status("FINAL all_dates_committed=" + str(allgood) + " -> " + json.dumps(final))

            # Now click Next ONCE and see if (a) regen, (b) advance past My Experience.
            idx_before = we_indices(page)
            advanced = W.click_next(page)
            page.wait_for_timeout(2800)
            body = page.locator("body").text_content() or ""
            cur_step = W.current_step_name(page, body)
            idx_after = we_indices(page)
            perrs = page.evaluate(r"""()=>{const o=[];for(const e of document.querySelectorAll('[role=alert],[data-automation-id=errorMessage],[data-automation-id*=error]')){const t=(e.textContent||'').trim();if(t&&t.length<120&&!/successfully uploaded/i.test(t))o.push(t);}return [...new Set(o)].slice(0,12);}""")
            out["next_test"] = {"step_after": cur_step, "advanced_click": advanced,
                                "idx_before": idx_before, "idx_after": idx_after,
                                "new_block_spawned": len(idx_after) > len(idx_before),
                                "left_my_experience": "My Experience" not in cur_step,
                                "page_errors": perrs}
            status("NEXT: step=" + cur_step + " advanced=" + str(advanced)
                   + " idx_before=" + json.dumps(idx_before) + " idx_after=" + json.dumps(idx_after)
                   + " new_block=" + str(len(idx_after) > len(idx_before)) + " left_MyExp=" + str("My Experience" not in cur_step))
            status("NEXT page errors: " + json.dumps(perrs))
            status("STOPPING HERE — will NOT proceed toward Review/Submit (probe contract).")

            OUT.write_text(json.dumps(out, indent=2))
            status("WROTE _probe4_results.json. DONE.")
        finally:
            try: ctx.close()
            except Exception: pass


if __name__ == "__main__":
    main()
