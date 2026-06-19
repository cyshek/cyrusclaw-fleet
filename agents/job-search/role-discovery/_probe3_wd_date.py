#!/usr/bin/env python3
"""PHASE 3 SPIKE: run handle_experience to add+fill blocks, then in the SAME live page
(a) read back EACH block's start/end date to see if the runner's _fill_wd_date committed,
(b) probe mechanisms A-E on the empty regenerated block's start-date month, reading value
+ red error each time, (c) test whether a committed date stops the regen on Next.
NEVER submits (stays on My Experience)."""
import sys, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from playwright.sync_api import sync_playwright
import _workday_runner as W

TENANT = "exfo"
URL = "https://exfo.wd10.myworkdayjobs.com/en-US/EXFO_Careers/job/Solutions-Engineer_R-100191"
STATUS = HERE / "STATUS.md"
OUT = HERE / "_probe3_results.json"


def status(msg):
    ts = time.strftime("%H:%M:%S")
    print("[p3]", msg, flush=True)
    try:
        with open(STATUS, "a") as f:
            f.write("[" + ts + "] P3 " + str(msg) + chr(10))
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
  out.monVal = mon?(mon.value||''):null;
  out.yrVal  = yr?(yr.value||''):null;
  out.monAria = mon?{required:mon.getAttribute('aria-required'),invalid:mon.getAttribute('aria-invalid'),valuetext:mon.getAttribute('aria-valuetext')}:null;
  let wrap=mon||yr; for(let i=0;i<12&&wrap;i++){wrap=wrap.parentElement; if(wrap&&/formField-(start|end)Date/.test(wrap.getAttribute('data-automation-id')||''))break;}
  const errs=[];
  if(wrap){for(const e of wrap.querySelectorAll('[role=alert],[data-automation-id*=error],[id$=-error]')){const t=(e.textContent||'').trim(); if(t)errs.push(t.slice(0,100));}}
  out.errors=errs;
  if(wrap){const ic=wrap.querySelector('[data-automation-id=dateIcon]');out.hasIcon=!!ic;}
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


# mechanisms
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


def clear_input(page, iid):
    try:
        page.evaluate(r"""(id)=>{const el=document.getElementById(id);if(!el)return;el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,'');el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.blur();}""", iid)
        page.wait_for_timeout(200)
    except Exception:
        pass


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
            status("ON My Experience -> running handle_experience (adds+fills via runner)")
            try:
                W.handle_experience(page, resume_path())
            except Exception as e:
                status("handle_experience err: " + str(e)[:120])
            page.wait_for_timeout(2000)

            idxs = we_indices(page)
            status("WE indices after fill: " + json.dumps(idxs))
            out["indices"] = idxs

            # (A) read back EACH block start/end date -> did runner's _fill_wd_date commit?
            rb = {}
            for ix in idxs:
                jt = jobtitle(page, ix)
                sd = read_date(page, "workExperience-" + str(ix) + "--startDate")
                ed = read_date(page, "workExperience-" + str(ix) + "--endDate")
                rb[ix] = {"jobTitle": jt, "start": sd, "end": ed}
                status("RB ix=" + str(ix) + " jt=" + repr(jt)
                       + " | startMon=" + repr(sd.get("monVal")) + " startYr=" + repr(sd.get("yrVal")) + " startErr=" + json.dumps(sd.get("errors"))
                       + " | endMon=" + repr(ed.get("monVal")) + " endYr=" + repr(ed.get("yrVal")))
            out["readback"] = rb

            # (B) pick the EMPTY block (jobTitle blank) for mechanism probing
            empty_ix = None
            for ix in idxs:
                if not (jobtitle(page, ix) or "").strip():
                    empty_ix = ix; break
            status("EMPTY block for mech probe = " + str(empty_ix))
            out["empty_idx"] = empty_ix
            if empty_ix is None and idxs:
                # if no empty, add one so we can probe a virgin date widget
                status("no empty block; clicking Work Experience Add to get a virgin block")
                try:
                    W._wd_section_add(page, "Work Experience")
                    page.wait_for_timeout(1500)
                    idxs2 = we_indices(page)
                    new = [i for i in idxs2 if i not in idxs]
                    empty_ix = new[0] if new else None
                    status("added block -> empty_ix=" + str(empty_ix) + " idxs2=" + json.dumps(idxs2))
                except Exception as e:
                    status("add err " + str(e)[:80])

            if empty_ix is not None:
                base = "workExperience-" + str(empty_ix) + "--startDate"
                mon_id = base + "-dateSectionMonth-input"
                yr_id = base + "-dateSectionYear-input"
                TMM, TYYYY = "08", "2022"
                results = {}

                def probe(label, fn):
                    status("--- MECH " + label + " ---")
                    clear_input(page, mon_id)
                    try:
                        ret = fn()
                    except Exception as e:
                        ret = "EXC:" + str(e)[:90]
                    page.wait_for_timeout(600)
                    d = read_date(page, base)
                    mon = d.get("monVal"); errs = d.get("errors") or []
                    month_set = (mon or "").strip() in (TMM, str(int(TMM)))
                    err_cleared = not any(("required" in (e or "").lower()) or ("must have" in (e or "").lower()) for e in errs)
                    results[label] = {"ret": ret, "monVal": mon, "errors": errs, "month_set": month_set, "err_cleared": err_cleared, "aria": d.get("monAria")}
                    status("MECH " + label + " -> month_set=" + str(month_set) + " monVal=" + repr(mon) + " err_cleared=" + str(err_cleared) + " errors=" + json.dumps(errs) + " aria=" + json.dumps(d.get("monAria")) + " ret=" + str(ret)[:60])

                probe("B_native_setter", lambda: mB(page, mon_id, TMM))
                probe("C_react_fiber", lambda: mC(page, mon_id, TMM))
                probe("D_fill_tab", lambda: mD(page, mon_id, TMM))
                probe("E_press_seq", lambda: mE(page, mon_id, TMM))

                winner = None
                for lab in ["E_press_seq", "D_fill_tab", "B_native_setter", "C_react_fiber"]:
                    if results.get(lab, {}).get("month_set"):
                        winner = lab; break
                status("MONTH WINNER = " + str(winner))
                out["mech_results"] = results
                out["winner"] = winner

                # (C) If a winner, fully fill this block (incl year + end-date) via winner,
                #     verify error clears, then click Next and observe regen behaviour.
                if winner:
                    fn = {"E_press_seq": mE, "D_fill_tab": mD, "B_native_setter": mB, "C_react_fiber": mC}[winner]
                    status("--- winner " + winner + ": fill block fully + Next/regen test ---")
                    # fill text fields via runner kbd helper (commits), but DATES via winner
                    W._kbd_fill_we_block_by_idx(page, str(empty_ix), {
                        "title": "Solutions Engineer Probe", "company": "ProbeCo", "location": "Seattle, WA",
                        "current": False, "start": ("08", "2022"), "end": ("06", "2023"),
                        "desc": "probe do-not-submit",
                    })
                    page.wait_for_timeout(500)
                    # reassert start month/year via the winning mechanism (the keystone)
                    clear_input(page, mon_id); fn(page, mon_id, TMM); page.wait_for_timeout(300)
                    clear_input(page, yr_id); fn(page, yr_id, TYYYY); page.wait_for_timeout(400)
                    sd = read_date(page, base)
                    # also handle END date via winner
                    ebase = "workExperience-" + str(empty_ix) + "--endDate"
                    emon = ebase + "-dateSectionMonth-input"; eyr = ebase + "-dateSectionYear-input"
                    end_present = page.evaluate("(id)=>!!document.getElementById(id)", emon)
                    if end_present:
                        clear_input(page, emon); fn(page, emon, "06"); page.wait_for_timeout(300)
                        clear_input(page, eyr); fn(page, eyr, "2023"); page.wait_for_timeout(400)
                    ed = read_date(page, ebase)
                    status("post-winner START mon=" + repr(sd.get("monVal")) + " yr=" + repr(sd.get("yrVal")) + " err=" + json.dumps(sd.get("errors")))
                    status("post-winner END   mon=" + repr(ed.get("monVal")) + " yr=" + repr(ed.get("yrVal")) + " err=" + json.dumps(ed.get("errors")) + " end_present=" + str(end_present))
                    out["post_winner"] = {"start": sd, "end": ed, "end_present": end_present}

                    idx_before = we_indices(page)
                    advanced = W.click_next(page)
                    page.wait_for_timeout(2500)
                    body = page.locator("body").text_content() or ""
                    cur = W.current_step_name(page, body)
                    idx_after = we_indices(page)
                    perrs = page.evaluate(r"""()=>{const o=[];for(const e of document.querySelectorAll('[role=alert],[data-automation-id=errorMessage],[data-automation-id*=error]')){const t=(e.textContent||'').trim();if(t&&t.length<120)o.push(t);}return [...new Set(o)].slice(0,12);}""")
                    status("AFTER NEXT: step=" + cur + " advanced=" + str(advanced)
                           + " idx_before=" + json.dumps(idx_before) + " idx_after=" + json.dumps(idx_after)
                           + " new_block=" + str(len(idx_after) > len(idx_before)) + " left_MyExp=" + str("My Experience" not in cur))
                    status("page errors after Next: " + json.dumps(perrs))
                    out["regen_test"] = {"step_after": cur, "advanced": advanced, "idx_before": idx_before,
                                         "idx_after": idx_after, "new_block": len(idx_after) > len(idx_before),
                                         "left_my_experience": "My Experience" not in cur, "page_errors": perrs}

            OUT.write_text(json.dumps(out, indent=2))
            status("WROTE _probe3_results.json. DONE.")
        finally:
            try: ctx.close()
            except Exception: pass


if __name__ == "__main__":
    main()
