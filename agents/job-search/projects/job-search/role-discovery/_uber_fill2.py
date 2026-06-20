#!/usr/bin/env python3
"""Complete the OPEN Uber apply form: month dropdowns (by section), Current checkbox,
year fields, screening radios, subsidiary select, demographics, arbitration.
Operates on the already-open signed-in page via CDP. Idempotent-ish (re-running re-picks).
Usage: _uber_fill2.py <job_id>
"""
import sys, time
from playwright.sync_api import sync_playwright

CDP="http://127.0.0.1:18800"
job_id=sys.argv[1]
pw=sync_playwright().start()
br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if f"/careers/apply/form/{job_id}" in p.url:
            page=p; break
    if page: break
if not page:
    print("NO FORM PAGE", job_id); sys.exit(2)
print("page:", page.url)

def pick_month(section_root_name, combo_id, month_code):
    """Click the combobox with id=combo_id located within the same section as the input
    named section_root_name, then click the option whose text == month_code (e.g. '03')."""
    r = page.evaluate("""([rootName, comboId, mc]) => {
      const anchor=document.querySelector(`input[name="${rootName}"]`);
      if(!anchor) return 'NO_ANCHOR';
      // find nearest ancestor that contains a combobox with comboId
      let cur=anchor, combo=null;
      for(let up=0; up<8 && cur; up++){ cur=cur.parentElement; if(!cur) break;
        const c=cur.querySelector(`[role=combobox]#${comboId}`); if(c){ combo=c; break; } }
      if(!combo){ // fallback: any combobox with that id
        const all=[...document.querySelectorAll(`[role=combobox]#${comboId}`)];
        combo=all[0]||null; }
      if(!combo) return 'NO_COMBO';
      combo.scrollIntoView({block:'center'}); combo.click();
      return 'OPENED';
    }""", [section_root_name, combo_id, month_code])
    if r!='OPENED':
        print("  pick_month", section_root_name, combo_id, "->", r); return False
    time.sleep(0.6)
    r2 = page.evaluate("""(mc) => {
      const opts=[...document.querySelectorAll('[role=option]')];
      const o=opts.find(x=>(x.innerText||'').trim()===mc);
      if(o){ o.scrollIntoView({block:'center'}); o.click(); return 'PICKED'; }
      return 'NO_OPT';
    }""", month_code)
    print("  pick_month", section_root_name, combo_id, month_code, "->", r2)
    time.sleep(0.5)
    return r2=='PICKED'

def fill(name, val):
    loc=page.locator(f'input[name="{name}"], textarea[name="{name}"]').first
    if loc.count():
        try:
            loc.fill(val); print("filled", name, "=", val[:25]); return True
        except Exception as e:
            print("fill-fail", name, str(e)[:60]); return False
    print("MISS", name); return False

def click_current(section_root_name):
    """Check the 'Current' checkbox in the section containing section_root_name."""
    r=page.evaluate("""(rootName) => {
      const anchor=document.querySelector(`input[name="${rootName}"]`);
      if(!anchor) return 'NO_ANCHOR';
      let cur=anchor, box=null;
      for(let up=0; up<8 && cur; up++){ cur=cur.parentElement; if(!cur) break;
        // a checkbox input or a label/element whose text includes 'Current'
        const cb=cur.querySelector('input[type=checkbox]');
        if(cb){ box=cb; break; }
        const lbls=[...cur.querySelectorAll('label,[role=checkbox]')].filter(x=>/current/i.test(x.innerText||''));
        if(lbls.length){ box=lbls[0]; break; }
      }
      if(!box) return 'NO_BOX';
      const checked = box.getAttribute('aria-checked')==='true' || box.checked===true;
      if(!checked){ box.scrollIntoView({block:'center'}); box.click(); return 'CLICKED'; }
      return 'ALREADY';
    }""", section_root_name)
    print("current", section_root_name, "->", r)
    return r in ('CLICKED','ALREADY')

def pick_radio(qsub, opt):
    r=page.evaluate("""([qsub, opt]) => {
      const norm=s=>(s||'').replace(/\\s+/g,' ').trim().toLowerCase();
      const groups=[...document.querySelectorAll('[role=radiogroup]')];
      for(const g of groups){
        let ctx='', cur=g;
        for(let up=0; up<7 && cur; up++){ cur=cur.parentElement; if(!cur) break; const t=norm(cur.innerText); if(t.includes(norm(qsub))){ ctx=t; break; } }
        if(!ctx) continue;
        const cands=[...g.querySelectorAll('label,[role=radio],button,input[type=radio]')];
        for(const c of cands){ const n=norm(c.innerText)||norm(c.getAttribute('aria-label'))||norm(c.value); if(n && n.startsWith(norm(opt))){ c.scrollIntoView({block:'center'}); c.click(); return 'OK:'+n.slice(0,20); } }
        // looser includes
        for(const c of cands){ const n=norm(c.innerText)||norm(c.getAttribute('aria-label'))||norm(c.value); if(n && n.includes(norm(opt))){ c.scrollIntoView({block:'center'}); c.click(); return 'OK2:'+n.slice(0,20); } }
      }
      return 'MISS';
    }""", [qsub, opt])
    print("radio", qsub[:34], "=>", opt, "->", r)
    return str(r).startswith('OK')

def pick_select(combo_id, option_text):
    """Open a custom combobox by id and pick an option by text (for subsidiaryQuestion)."""
    r=page.evaluate("""(cid)=>{ const c=document.querySelector(`[role=combobox]#${cid}`); if(!c) return 'NO_COMBO'; c.scrollIntoView({block:'center'}); c.click(); return 'OPEN'; }""", combo_id)
    if r!='OPEN':
        print("select", combo_id, "->", r); return False
    time.sleep(0.6)
    r2=page.evaluate("""(opt)=>{ const norm=s=>(s||'').replace(/\\s+/g,' ').trim().toLowerCase(); const opts=[...document.querySelectorAll('[role=option]')]; const o=opts.find(x=>norm(x.innerText)===norm(opt))||opts.find(x=>norm(x.innerText).includes(norm(opt))); if(o){o.scrollIntoView({block:'center'}); o.click(); return 'PICKED:'+(o.innerText||'').trim().slice(0,15);} return 'NO_OPT:'+opts.map(x=>(x.innerText||'').trim()).slice(0,8).join('|'); }""", option_text)
    print("select", combo_id, option_text, "->", r2)
    return str(r2).startswith('PICKED')

# ---- EXPERIENCE: Microsoft, start March 2024, Current ----
click_current("experiences.0.companyName")              # so end date not required
pick_month("experiences.0.startDate.year","start-date-month","03")
fill("experiences.0.startDate.year","2024")

# ---- EDUCATION: UH, Aug 2021 - Dec 2024 ----
pick_month("educations.0.startDate.year","start-date-month","08")
fill("educations.0.startDate.year","2021")
pick_month("educations.0.endDate.year","end-date-month","12")
fill("educations.0.endDate.year","2024")

# ---- SCREENING radios (truthful) ----
pick_radio("Driver", "No")                               # ever a Driver/Eats/Freight -> No
pick_radio("open to being considered for other roles", "Yes")
pick_radio("reside in the United States", "Yes")
pick_select("subsidiaryQuestion", "No")                  # employed by Uber subsidiary -> No
pick_radio("legal right to work", "Yes")
pick_radio("require our sponsorship", "No")

# ---- DEMOGRAPHICS (voluntary) -> Prefer not to say ----
pick_radio("gender with which you most identify", "Prefer not to say")
pick_radio("Hispanic or Latino", "Prefer not to say")
pick_radio("disability", "Prefer not to say")
pick_radio("Protected Veteran", "I prefer not to say")
pick_radio("sexual orientation", "Prefer not to say")

# ---- ARBITRATION (required to proceed) -> agree ----
pick_radio("Arbitration Agreement", "Yes, I agree")

time.sleep(1)
# Report enabled-state of year fields + any visible validation
state=page.evaluate("""()=>{
  const v=n=>{const e=document.querySelector(`input[name="${n}"]`); return e?{val:e.value, disabled:e.disabled}:null;};
  return JSON.stringify({
    expStartYear:v('experiences.0.startDate.year'),
    eduStartYear:v('educations.0.startDate.year'),
    eduEndYear:v('educations.0.endDate.year'),
    firstName:v('firstName'), phone:v('mobileNumber')
  });
}""")
print("STATE:", state)
print("FILL2_DONE")
