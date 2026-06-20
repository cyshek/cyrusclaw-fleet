import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

def esc():
    try: page.keyboard.press("Escape")
    except Exception: pass
    time.sleep(0.3)

def select_sdf(qid, want):
    el=page.locator("#%s"%qid); el.scroll_into_view_if_needed(timeout=2000); el.click(timeout=3000); time.sleep(0.9)
    opts=page.evaluate("()=>[...document.querySelectorAll('[role=option]')].filter(x=>x.offsetWidth>0).map(x=>x.innerText.trim())")
    target=None
    for w in want:
        for o in opts:
            if o.lower()==w.lower(): target=o; break
        if target: break
    if target:
        page.locator("[role=option]").filter(has_text=target).first.click(timeout=3000)
        print("  %s -> %r"%(qid,target)); time.sleep(0.5); return True
    print("  %s NO MATCH opts=%s"%(qid,opts)); esc(); return False

# Re-answer Q1 (how heard) + Q3 (VISA) via UI (these open & commit reliably)
select_sdf("question_1", ["LinkedIn"]); esc()
select_sdf("question_3", ["No"]); esc()

# Q2 Total Compensation text + currency react-select (this one's a MDFSelectBox that worked before)
page.locator("#question_2").fill("150000", timeout=3000); print("Q2=150000")
try:
    cur=page.locator("#question_currency_type_2"); cur.click(timeout=2500); time.sleep(0.7)
    opt=page.locator(".MDFSelectBox__option").filter(has_text="United States Dollar").first
    if opt.count()>0: opt.click(timeout=3000); print("Q2 currency -> USD")
    esc()
except Exception as e:
    print("Q2 currency exc", str(e)[:80])

# Now drive desired-salary + referral via React handlers (the proven workaround)
res=page.evaluate(r"""
()=>{
  const el=document.getElementById('question_0')||document.body;
  const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
  let mp=null;
  for(let i=0;i<16&&f;i++){const m=f.memoizedProps; if(m&&('onDesiredSalaryValue'in m)){mp=m;break;} f=f.return;}
  if(!mp) return 'no-bag';
  const usd={codeValue:'USD', label:'United States Dollar ( USD )', shortName:'SYS:5:420', value:'USD'};
  const log=[];
  try{ mp.setRefferalIndicatorValue(false); log.push('refInd=false'); }catch(e){log.push('e1 '+e.message);}
  try{ mp.onRefferedEmplChange(false); log.push('refEmpl=false'); }catch(e){log.push('e1b '+e.message);}
  try{ mp.onDesiredSalaryValue('150000'); log.push('salary=150000'); }catch(e){log.push('e2 '+e.message);}
  try{ mp.onDesiredSalaryType({detail:{value:'Annually'}}); log.push('type=Annually'); }catch(e){log.push('e3 '+e.message);}
  try{ mp.onCurrencyChange({detail: usd}); log.push('curChange'); }catch(e){log.push('e4 '+e.message);}
  try{ mp.onCurrencyValueChange(usd); log.push('curValChange'); }catch(e){log.push('e5 '+e.message);}
  return {log};
}
""")
print("React handlers:", json.dumps(res)[:500])
time.sleep(1.5)

# Click Next
loc=page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next"); time.sleep(5)
after=page.evaluate(r"""
()=>{
  const body=document.body.innerText;
  const stuck=/following questions/i.test(body)&&/Correct the information/i.test(body);
  const onSelfId=/Self-?Identification|Voluntary Self|veteran|disability|gender|race|ethnicity/i.test(body)&&!/following questions/i.test(body);
  const onReview=/Review Your Application/i.test(body)&&!/following questions/i.test(body);
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,5);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,5);
  return {stuck,onSelfId,onReview,headings:h,errs,sample:body.replace(/\s+/g,' ').slice(0,300)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1100])
