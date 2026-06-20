#!/usr/bin/env python3
"""THROWAWAY SPIKE: find a date-commit mechanism that PERSISTS into Workday's MM/YYYY
date-section spinbutton on the live EXFO fresh account. Reuses _workday_runner nav helpers
to park on My Experience, then probes mechanisms A-E reading value back + red error.
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
RESUME = None


def status(msg):
    ts = time.strftime("%H:%M:%S")
    print("[probe]", msg, flush=True)
    try:
        with open(STATUS, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def find_resume():
    cands = [
        HERE.parent / "resume" / "Cyrus_Shekari_Resume_master.docx",
        HERE.parent / "resume" / "Cyrus_Shekari_Resume_master.pdf",
    ]
    for c in cands:
        if c.exists():
            return str(c)
    rd = HERE.parent / "resume"
    if rd.exists():
        for ext in ("*.pdf", "*.docx"):
            g = list(rd.glob(ext))
            if g:
                return str(g[0])
    return None


DATE_DOM_JS = r"""
(base)=>{
  const out = {base};
  const all=[...document.querySelectorAll('input,div,span,button,[data-automation-id]')];
  const byEnd=(suf)=>all.find(e=>(e.id||'').endsWith(suf)||(e.getAttribute('data-automation-id')||'').endsWith(suf));
  const mon=byEnd(base+'-dateSectionMonth-input');
  const yr =byEnd(base+'-dateSectionYear-input');
  const disp=byEnd(base+'-display');
  out.monId = mon?mon.id:null;
  out.yrId  = yr?yr.id:null;
  out.monVal= mon?(mon.value||''):null;
  out.yrVal = yr?(yr.value||''):null;
  out.dispText = disp?(disp.textContent||'').trim():null;
  let wrap = mon||yr||disp;
  for(let i=0;i<10&&wrap;i++){ wrap=wrap.parentElement; if(wrap && (wrap.getAttribute('data-automation-id')||'').toLowerCase().includes('date')) break; }
  out.wrapAutomationId = wrap?(wrap.getAttribute('data-automation-id')||''):null;
  const scope = wrap||document;
  const btns=[...scope.querySelectorAll('button,[role=button],svg,[data-automation-id]')];
  out.pickerBtns = btns.filter(b=>{const da=(b.getAttribute('data-automation-id')||'').toLowerCase(); const al=(b.getAttribute('aria-label')||'').toLowerCase(); return /datepicker|calendar|monthpicker|datesection.*button|date.*icon/.test(da)||/calendar|date|month/.test(al);}).slice(0,8).map(b=>({tag:b.tagName, da:b.getAttribute('data-automation-id')||'', al:b.getAttribute('aria-label')||'', txt:(b.textContent||'').trim().slice(0,20)}));
  const errs=[];
  if(wrap){ for(const e of wrap.querySelectorAll('[data-automation-id*=error],[role=alert],.css-error,[id$=-error]')){const t=(e.textContent||'').trim(); if(t)errs.push(t.slice(0,120));} }
  out.errors = errs;
  if(mon){ out.monAria={required:mon.getAttribute('aria-required'), invalid:mon.getAttribute('aria-invalid'), role:mon.getAttribute('role'), valuenow:mon.getAttribute('aria-valuenow'), label:mon.getAttribute('aria-label')}; }
  return out;
}
"""


def read_date(page, base):
    try:
        return page.evaluate(DATE_DOM_JS, base)
    except Exception as e:
        return {"err": str(e)[:120]}


def date_committed(page, base):
    d = read_date(page, base)
    return d.get("monVal"), d.get("yrVal"), d.get("errors"), d


def mech_B_native_setter(page, input_id, val):
    return page.evaluate(r"""([id,val])=>{
      const el=document.getElementById(id); if(!el)return 'no-el';
      el.scrollIntoView({block:'center'}); el.focus();
      const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');
      d.set.call(el,val);
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.dispatchEvent(new Event('change',{bubbles:true}));
      el.blur();
      return el.value;
    }""", [input_id, str(val)])


def mech_C_react_fiber(page, input_id, val):
    return page.evaluate(r"""([id,val])=>{
      const el=document.getElementById(id); if(!el)return 'no-el';
      const k=Object.keys(el).find(k=>k.startsWith('__reactProps$'));
      if(!k) return 'no-reactprops';
      const props=el[k];
      const fns=Object.keys(props).filter(p=>typeof props[p]==='function');
      let called=[];
      try{ if(typeof props.onChange==='function'){ props.onChange({target:{value:val, name:el.name}, currentTarget:{value:val}}); called.push('onChange'); } }catch(e){called.push('onChange-err:'+e.message.slice(0,40));}
      try{ if(typeof props.onInput==='function'){ props.onInput({target:{value:val}}); called.push('onInput'); } }catch(e){}
      return JSON.stringify({fns, called, val:el.value});
    }""", [input_id, str(val)])


def mech_D_fill_tab(page, input_id, val):
    try:
        loc = page.locator(f"#{input_id}").first
        page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", input_id)
        loc.fill(str(val), timeout=4000)
        page.keyboard.press("Tab")
        page.wait_for_timeout(300)
        return "filled+tab"
    except Exception as e:
        return "err:" + str(e)[:80]


def mech_E_press_seq(page, input_id, val):
    try:
        loc = page.locator(f"#{input_id}").first
        page.evaluate("(id)=>{const e=document.getElementById(id);if(e)e.scrollIntoView({block:'center'});}", input_id)
        loc.click(timeout=4000)
        page.wait_for_timeout(150)
        for ch in str(val):
            page.keyboard.press(f"Digit{ch}")
            page.wait_for_timeout(120)
        page.keyboard.press("Tab")
        page.wait_for_timeout(300)
        return "pressed+tab"
    except Exception as e:
        return "err:" + str(e)[:80]


def mech_A_picker(page, base, mm, yyyy):
    d = read_date(page, base)
    pbtns = d.get("pickerBtns") or []
    if not pbtns:
        return f"no-picker-btn (wrap={d.get('wrapAutomationId')})"
    clicked = page.evaluate(r"""(base)=>{
      const all=[...document.querySelectorAll('input,div,span,button,[data-automation-id]')];
      const byEnd=(suf)=>all.find(e=>(e.id||'').endsWith(suf)||(e.getAttribute('data-automation-id')||'').endsWith(suf));
      let wrap=byEnd(base+'-dateSectionMonth-input')||byEnd(base+'-display');
      for(let i=0;i<10&&wrap;i++){wrap=wrap.parentElement; if(wrap&&(wrap.getAttribute('data-automation-id')||'').toLowerCase().includes('date'))break;}
      if(!wrap)return 'no-wrap';
      const b=[...wrap.querySelectorAll('button,[role=button]')].find(x=>{const da=(x.getAttribute('data-automation-id')||'').toLowerCase();const al=(x.getAttribute('aria-label')||'').toLowerCase();return /datepicker|calendar|monthpicker|date.*icon/.test(da)||/calendar|date|month/.test(al);});
      if(!b)return 'no-clickable';
      b.scrollIntoView({block:'center'}); b.click(); return 'clicked:'+(b.getAttribute('data-automation-id')||b.getAttribute('aria-label')||'?');
    }""", base)
    page.wait_for_timeout(800)
    return f"picker {clicked}"


def navigate_to_my_experience(page):
    status("goto apply url")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    for cb in ["[data-automation-id=legalNoticeAcceptButton]", "button:has-text('Accept Cookies')"]:
        if page.locator(cb).count():
            try:
                page.locator(cb).first.click(timeout=3000)
            except Exception:
                pass
            break
    for _nav in range(6):
        if (page.locator("[data-automation-id=email]").count()
                or page.locator("[data-automation-id=SignInWithEmailButton]").count()
                or page.locator("[data-automation-id=pageFooterNextButton]").count()
                or page.locator("input#name--legalName--firstName").count()):
            break
        if page.locator("[data-automation-id=applyManually]").count():
            W.safe_click(page, "[data-automation-id=applyManually]"); page.wait_for_timeout(3500); continue
        if page.locator("[data-automation-id=continueButton]").count():
            W.safe_click(page, "[data-automation-id=continueButton]"); page.wait_for_timeout(3500); continue
        if page.locator("[data-automation-id=adventureButton]").count():
            W.safe_click(page, "[data-automation-id=adventureButton]"); page.wait_for_timeout(3000); continue
        page.wait_for_timeout(1500)
    status("ensure_signed_in")
    ok = W.ensure_signed_in(page, TENANT, base_url=URL)
    status(f"signed_in={ok}")
    if not ok:
        return False
    for i in range(8):
        page.wait_for_timeout(1500)
        body = page.locator("body").text_content() or ""
        cur = W.current_step_name(page, body)
        status(f"step iter {i}: '{cur}'")
        if "My Experience" in cur:
            return True
        if "My Information" in cur:
            W.fill_my_information(page, W.SOURCE_DEFAULT)
        if not W.click_next(page):
            status("no next button while walking to My Experience")
            page.wait_for_timeout(1000)
    body = page.locator("body").text_content() or ""
    return "My Experience" in W.current_step_name(page, body)


def main():
    global RESUME
    RESUME = find_resume()
    try:
        STATUS.write_text("# PROBE STATUS - workday-date-commit-spike\n")
    except Exception:
        pass
    status(f"resume={RESUME}")
    W.EMAIL, W.PW, W._ACCOUNT_MODE = W.resolve_account_for_tenant(TENANT, force_fresh=None)
    W._FRESH_VERIFY_PW = W.PW if W._ACCOUNT_MODE in ("create_fresh", "signin_fresh") else None
    status(f"account: email={W.EMAIL} mode={W._ACCOUNT_MODE} pw_len={len(W.PW)}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(HERE.parent / ".workday-browser-data" / TENANT),
            headless=True, viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            accept_downloads=True,
        )
        page = ctx.new_page()
        page.set_default_timeout(20000)
        try:
            if not navigate_to_my_experience(page):
                status("FAILED to reach My Experience - dumping body head")
                body = (page.locator("body").text_content() or "")[:300]
                status("body head: " + body.replace("\n", " "))
                ctx.close(); return
            status("ON My Experience OK")
            status("running handle_experience (upload + populate) to get blocks")
            try:
                W.handle_experience(page, RESUME)
            except Exception as e:
                status("handle_experience err: " + str(e)[:120])
            page.wait_for_timeout(2000)
            base = page.evaluate(r"""()=>{
              const inp=[...document.querySelectorAll('input')].find(x=>/workExperience-\d+--dateSectionMonth-input/.test(x.id||''));
              if(!inp)return null;
              const m=(inp.id||'').match(/(workExperience-\d+--startDate)/);
              return m?m[1]:null;
            }""")
            status(f"discovered startDate base = {base}")
            if not base:
                dump = page.evaluate(r"""()=>{const ids=[...document.querySelectorAll('input')].map(x=>x.id||'').filter(s=>/workExperience-\d+/.test(s)).slice(0,40);return ids;}""")
                status("NO date section. workExp input ids: " + json.dumps(dump))
                ddump = page.evaluate(r"""()=>{const ids=[...document.querySelectorAll('input,div[role=spinbutton],[data-automation-id]')].map(x=>x.id||x.getAttribute('data-automation-id')||'').filter(s=>/date/i.test(s)).slice(0,40);return ids;}""")
                status("any 'date' ids: " + json.dumps(ddump))
                ctx.close(); return

            mon0, yr0, err0, d0 = date_committed(page, base)
            status(f"BASELINE: monVal={mon0!r} yrVal={yr0!r} errors={err0} wrap={d0.get('wrapAutomationId')} pickerBtns={d0.get('pickerBtns')}")
            status(f"BASELINE monAria={d0.get('monAria')} monId={d0.get('monId')} yrId={d0.get('yrId')}")

            mon_id = d0.get("monId")
            yr_id = d0.get("yrId")
            TARGET_MM, TARGET_YYYY = "08", "2022"

            results = {}

            def probe(label, fn):
                status(f"--- MECH {label} ---")
                try:
                    ret = fn()
                except Exception as e:
                    ret = "EXC:" + str(e)[:100]
                page.wait_for_timeout(600)
                mon, yr, errs, dd = date_committed(page, base)
                ok_mon = (mon or "").strip() in (TARGET_MM, str(int(TARGET_MM)))
                cleared = not any("required" in (e or "").lower() or "must have" in (e or "").lower() for e in (errs or []))
                r = {"ret": ret, "monVal": mon, "yrVal": yr, "errors": errs, "month_set": ok_mon, "err_cleared": cleared}
                results[label] = r
                status(f"MECH {label} -> month_set={ok_mon} monVal={mon!r} err_cleared={cleared} errors={errs} ret={str(ret)[:80]}")
                return r

            if mon_id:
                probe("B_native_setter", lambda: mech_B_native_setter(page, mon_id, TARGET_MM))
                probe("C_react_fiber", lambda: mech_C_react_fiber(page, mon_id, TARGET_MM))
                probe("D_fill_tab", lambda: mech_D_fill_tab(page, mon_id, TARGET_MM))
                probe("E_press_seq", lambda: mech_E_press_seq(page, mon_id, TARGET_MM))
            probe("A_picker", lambda: mech_A_picker(page, base, TARGET_MM, TARGET_YYYY))

            winner = None
            for lab in ["E_press_seq", "D_fill_tab", "B_native_setter", "C_react_fiber", "A_picker"]:
                if (results.get(lab) or {}).get("month_set"):
                    winner = lab; break
            status(f"MONTH WINNER (value persisted) = {winner}")

            if winner and yr_id:
                status(f"--- applying winner {winner} to YEAR ---")
                if winner == "E_press_seq":
                    mech_E_press_seq(page, yr_id, TARGET_YYYY)
                elif winner == "D_fill_tab":
                    mech_D_fill_tab(page, yr_id, TARGET_YYYY)
                elif winner == "B_native_setter":
                    mech_B_native_setter(page, yr_id, TARGET_YYYY)
                elif winner == "C_react_fiber":
                    mech_C_react_fiber(page, yr_id, TARGET_YYYY)
                page.wait_for_timeout(800)
                mon, yr, errs, dd = date_committed(page, base)
                status(f"AFTER YEAR via {winner}: monVal={mon!r} yrVal={yr!r} errors={errs}")

            block_diag = page.evaluate(r"""(base)=>{
              const m=base.match(/workExperience-(\d+)--/); if(!m)return null;
              const idx=m[1];
              const out={idx, reqEmpty:[], errors:[]};
              for(const el of document.querySelectorAll('input[aria-required=true],textarea[aria-required=true]')){
                if((el.id||'').includes('workExperience-'+idx+'--') && !(el.value||'').trim()) out.reqEmpty.push(el.id);
              }
              for(const e of document.querySelectorAll('[role=alert],[data-automation-id*=error]')){const t=(e.textContent||'').trim(); if(t&&t.length<120 && /date|required|from|to/i.test(t))out.errors.push(t);}
              return out;
            }""", base)
            status("BLOCK DIAG after date fill: " + json.dumps(block_diag))

            (HERE / "_probe_results.json").write_text(json.dumps({
                "base": base,
                "baseline": {"monVal": mon0, "yrVal": yr0, "errors": err0, "wrap": d0.get("wrapAutomationId"),
                             "pickerBtns": d0.get("pickerBtns"), "monAria": d0.get("monAria")},
                "results": results, "month_winner": winner, "block_diag": block_diag,
            }, indent=2))
            status("WROTE _probe_results.json")
            status("PROBE PHASE 1 COMPLETE")
        finally:
            try:
                ctx.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
