#!/usr/bin/env python3
"""Post-resume-upload fill for Uber form: re-fill screening radios + subsidiary + demographics,
education, and correct experience.0 (Microsoft). Inspect Remove-experience buttons to drop
junk parser blocks. Operates on open page via CDP.
Usage: _uber_fill3.py <job_id>
"""
import sys, time
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"; job_id=sys.argv[1]
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP)
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if f"/careers/apply/form/{job_id}" in p.url: page=p; break
    if page: break
if not page: print("NO PAGE"); sys.exit(2)
print("page:", page.url)

def fill(name, val, clear_first=True):
    loc=page.locator(f'input[name="{name}"], textarea[name="{name}"]').first
    if loc.count():
        try:
            loc.fill(val); print("filled", name, "=", val[:25]); return True
        except Exception as e:
            print("fill-fail", name, str(e)[:50]); return False
    print("MISS", name); return False

def pick_radio_by_name(name, value):
    """Directly click the radio input[name][value=...] (exact names known)."""
    r=page.evaluate("""([nm,val])=>{
      const norm=s=>(s||'').replace(/\\s+/g,' ').trim().toLowerCase();
      const rs=[...document.querySelectorAll(`input[name=\"${nm}\"]`)];
      // match by value startswith
      let t=rs.find(x=>norm(x.value).startsWith(norm(val)))||rs.find(x=>norm(x.value).includes(norm(val)));
      if(!t) return 'NO_OPT:'+rs.map(x=>x.value).slice(0,6).join('|');
      // click the input or its label wrapper
      t.scrollIntoView({block:'center'});
      const lbl=t.closest('label')|| (t.id?document.querySelector(`label[for=\"${t.id}\"]`):null);
      (lbl||t).click();
      if(!t.checked){ t.click(); }
      return t.checked?'OK':'CLICKED_UNVERIFIED';
    }""", [name, value])
    print("radio", name, "=", value, "->", r)
    return str(r).startswith('OK') or r=='CLICKED_UNVERIFIED'

def pick_month(section_root_name, combo_id, month_code):
    r=page.evaluate("""([rootName, comboId])=>{
      const anchor=document.querySelector(`input[name=\"${rootName}\"]`); if(!anchor) return 'NO_ANCHOR';
      let cur=anchor, combo=null;
      for(let up=0; up<8 && cur; up++){ cur=cur.parentElement; if(!cur) break; const c=cur.querySelector(`[role=combobox]#${comboId}`); if(c){combo=c;break;} }
      if(!combo) return 'NO_COMBO';
      combo.scrollIntoView({block:'center'}); combo.click(); return 'OPENED';
    }""", [section_root_name, combo_id])
    if r!='OPENED': print("month", section_root_name, "->", r); return False
    time.sleep(0.5)
    r2=page.evaluate("""(mc)=>{const o=[...document.querySelectorAll('[role=option]')].find(x=>(x.innerText||'').trim()===mc); if(o){o.scrollIntoView({block:'center'});o.click();return 'PICKED';} return 'NO_OPT';}""", month_code)
    print("month", section_root_name, combo_id, month_code, "->", r2); time.sleep(0.4)
    return r2=='PICKED'

def check_current(section_root_name):
    r=page.evaluate("""(rootName)=>{
      const anchor=document.querySelector(`input[name=\"${rootName}\"]`); if(!anchor) return 'NO_ANCHOR';
      let cur=anchor, box=null;
      for(let up=0; up<8 && cur; up++){ cur=cur.parentElement; if(!cur) break; const cb=cur.querySelector('input[type=checkbox]'); if(cb){box=cb;break;} }
      if(!box) return 'NO_BOX';
      if(!(box.checked||box.getAttribute('aria-checked')==='true')){ box.scrollIntoView({block:'center'}); (box.closest('label')||box).click(); if(!box.checked) box.click(); return 'CLICKED'; }
      return 'ALREADY';
    }""", section_root_name)
    print("current", section_root_name, "->", r); return r in ('CLICKED','ALREADY')

def pick_select(combo_id, option_text):
    r=page.evaluate("""(cid)=>{const c=document.querySelector(`[role=combobox]#${cid}`); if(!c) return 'NO_COMBO'; c.scrollIntoView({block:'center'}); c.click(); return 'OPEN';}""", combo_id)
    if r!='OPEN': print("select", combo_id, "->", r); return False
    time.sleep(0.5)
    r2=page.evaluate("""(opt)=>{const norm=s=>(s||'').replace(/\\s+/g,' ').trim().toLowerCase(); const opts=[...document.querySelectorAll('[role=option]')]; const o=opts.find(x=>norm(x.innerText)===norm(opt))||opts.find(x=>norm(x.innerText).includes(norm(opt))); if(o){o.scrollIntoView({block:'center'});o.click(); return 'PICKED:'+(o.innerText||'').trim();} return 'NO_OPT:'+opts.map(x=>(x.innerText||'').trim()).slice(0,6).join('|');}""", option_text)
    print("select", combo_id, option_text, "->", r2); return str(r2).startswith('PICKED')

# Count experiences + remove buttons
info=page.evaluate("""()=>{
  const exps=[...document.querySelectorAll('input[name^=\"experiences.\"][name$=\".companyName\"]')].map(e=>({n:e.name, co:e.value}));
  const removeBtns=[...document.querySelectorAll('button')].filter(b=>/remove experience/i.test(b.innerText)).length;
  return JSON.stringify({exps, removeBtns});
}""")
print("EXP_INFO:", info)

# ---- correct experience.0 (Microsoft TPM) ----
fill("experiences.0.title","Technical Program Manager")
check_current("experiences.0.companyName")
pick_month("experiences.0.startDate.year","start-date-month","03")
fill("experiences.0.startDate.year","2024")

# ---- EDUCATION (parser cleared it) ----
fill("educations.0.schoolName","University of Houston")
fill("educations.0.degree","Bachelor of Science")
fill("educations.0.fieldOfStudy","Computer Science")
pick_month("educations.0.startDate.year","start-date-month","08")
fill("educations.0.startDate.year","2021")
pick_month("educations.0.endDate.year","end-date-month","12")
fill("educations.0.endDate.year","2024")

# ---- SCREENING (re-fill all; parser cleared most) ----
pick_radio_by_name("driverPartnerQuestion","No")
pick_radio_by_name("openRolesQuestion","Yes")
pick_radio_by_name("inUSA","Yes")
pick_select("subsidiaryQuestion","No")
pick_radio_by_name("legalRightToWork","Yes")
pick_radio_by_name("requireVisaSponsorship","No")
# ---- DEMOGRAPHICS ----
pick_radio_by_name("gender","Prefer not to say")
pick_radio_by_name("race","Prefer not to say")
pick_radio_by_name("disability","Prefer not to say")
pick_radio_by_name("veteran","I prefer not to say")
pick_radio_by_name("sexualOrientation","Prefer not to say")
# ---- ARBITRATION ----
pick_radio_by_name("arbitrationAgreement","Yes, I agree")

time.sleep(1)
# final checked state
chk=page.evaluate("""()=>{const r={}; ['driverPartnerQuestion','openRolesQuestion','inUSA','legalRightToWork','requireVisaSponsorship','gender','race','disability','veteran','sexualOrientation','arbitrationAgreement'].forEach(nm=>{const t=[...document.querySelectorAll(`input[name=\"${nm}\"]`)].find(x=>x.checked); r[nm]=t?t.value.slice(0,22):null;}); const sub=document.querySelector('[role=combobox]#subsidiaryQuestion'); r._subsidiary=sub?(sub.innerText||'').trim():''; const v=n=>{const e=document.querySelector(`input[name=\"${n}\"]`);return e?e.value:null;}; r._eduSchool=v('educations.0.schoolName'); r._expYr=v('experiences.0.startDate.year'); r._eduStartYr=v('educations.0.startDate.year'); r._eduEndYr=v('educations.0.endDate.year'); return JSON.stringify(r);}""")
print("FINAL_CHECK:", chk)
print("FILL3_DONE")
