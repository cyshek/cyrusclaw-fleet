#!/usr/bin/env python3
"""Fill missing companies + dates for parser-populated experiences 1-4 (truthful, from
Cyrus's resume), and re-commit subsidiaryQuestion=No. Operates on open page via CDP.
Each experience block has its own start-date-month/end-date-month combobox (dup ids) so
we target by the block's companyName anchor.
Usage: _uber_fill_exp.py <job_id>
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

def fill(name, val):
    loc=page.locator(f'input[name="{name}"], textarea[name="{name}"]').first
    if loc.count():
        try: loc.fill(val); print("filled", name, "=", val[:22]); return True
        except Exception as e: print("fill-fail", name, str(e)[:50]); return False
    print("MISS", name); return False

def pick_month_in_block(block_idx, which, month_code):
    """which: 'start-date-month' or 'end-date-month'. Find combo with that id inside the
    experiences.<block_idx> block (anchored on its companyName input)."""
    combo_id=which
    r=page.evaluate("""([bi, comboId])=>{
      const anchor=document.querySelector(`input[name=\"experiences.${bi}.companyName\"]`); if(!anchor) return 'NO_ANCHOR';
      let cur=anchor, combo=null;
      for(let up=0; up<10 && cur; up++){ cur=cur.parentElement; if(!cur) break;
        // ensure this ancestor still scopes to THIS experience block (contains the companyName)
        if(!cur.querySelector(`input[name=\"experiences.${bi}.companyName\"]`)) break;
        const c=cur.querySelector(`[role=combobox]#${comboId}`); if(c){combo=c;break;} }
      if(!combo) return 'NO_COMBO';
      combo.scrollIntoView({block:'center'}); combo.click(); return 'OPENED';
    }""", [block_idx, combo_id])
    if r!='OPENED': print(f"  exp{block_idx} {which} ->", r); return False
    time.sleep(0.5)
    r2=page.evaluate("""(mc)=>{const o=[...document.querySelectorAll('[role=option]')].find(x=>(x.innerText||'').trim()===mc); if(o){o.scrollIntoView({block:'center'});o.click();return 'PICKED';} return 'NO_OPT';}""", month_code)
    print(f"  exp{block_idx} {which} {month_code} ->", r2); time.sleep(0.4)
    return r2=='PICKED'

# Resume-truthful data for parser blocks
# exp0 Microsoft TPM (already done). exp1 Amazon, exp2/3 Microsoft interns, exp4 Pro Painters.
plan=[
  (1, "Amazon Robotics", "08","2023","12","2023"),   # Aug 2023 - Dec 2023
  (2, "Microsoft",       "05","2023","08","2023"),   # May 2023 - Aug 2023 (blank co -> Microsoft)
  (3, "Microsoft",       "05","2022","08","2022"),   # May 2022 - Aug 2022 (blank co -> Microsoft)
  (4, "Pro Painters",    "05","2021","05","2022"),   # May 2021 - May 2022
]
for bi, co, sm, sy, em, ey in plan:
    # fill company if blank
    cur=page.locator(f'input[name="experiences.{bi}.companyName"]').first
    curval=cur.input_value() if cur.count() else ""
    if not curval.strip():
        fill(f"experiences.{bi}.companyName", co)
    pick_month_in_block(bi, "start-date-month", sm)
    fill(f"experiences.{bi}.startDate.year", sy)
    pick_month_in_block(bi, "end-date-month", em)
    fill(f"experiences.{bi}.endDate.year", ey)

# Re-commit subsidiaryQuestion = No (more robust: open, wait, pick exact)
def pick_subsidiary():
    r=page.evaluate("""()=>{const c=document.querySelector('[role=combobox]#subsidiaryQuestion'); if(!c) return 'NO'; c.scrollIntoView({block:'center'}); c.click(); return 'OPEN';}""")
    if r!='OPEN': print("subsidiary open ->", r); return False
    time.sleep(0.7)
    r2=page.evaluate("""()=>{const opts=[...document.querySelectorAll('[role=option]')]; const o=opts.find(x=>(x.innerText||'').trim().toLowerCase()==='no'); if(o){o.scrollIntoView({block:'center'});o.click();return 'PICKED';} return 'OPTS:'+opts.map(x=>(x.innerText||'').trim()).slice(0,6).join('|');}""")
    print("subsidiary pick ->", r2)
    return r2=='PICKED'
pick_subsidiary()
time.sleep(0.6)
subtxt=page.evaluate("""()=>{const c=document.querySelector('[role=combobox]#subsidiaryQuestion'); return c?(c.innerText||'').trim():null;}""")
print("subsidiary now:", repr(subtxt))

# Final experiences dump
out=page.evaluate("""()=>{return JSON.stringify([0,1,2,3,4].map(i=>({co:(document.querySelector(`input[name=\"experiences.${i}.companyName\"]`)||{}).value, t:(document.querySelector(`input[name=\"experiences.${i}.title\"]`)||{}).value, sy:(document.querySelector(`input[name=\"experiences.${i}.startDate.year\"]`)||{}).value, ey:(document.querySelector(`input[name=\"experiences.${i}.endDate.year\"]`)||{}).value, cur:(document.querySelector(`input[name=\"experiences.${i}.isCurrent\"]`)||{}).checked})));}""")
print("EXPS:", out)
print("FILLEXP_DONE")
