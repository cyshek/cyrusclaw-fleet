import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url before:", page.url[:90])

# Click Previous to go back to Resume, then Next to re-enter Questions fresh
prev=page.locator("button:has-text('Previous')").filter(visible=True).first
if prev.count()>0:
    prev.click(timeout=5000); print("clicked Previous"); time.sleep(4)
    print("now headings:", page.evaluate("()=>[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,4)"))
    nxt=page.locator("button:has-text('Next')").filter(visible=True).first
    nxt.click(timeout=5000); print("clicked Next back to Questions"); time.sleep(4)

# Inspect PRISTINE desired-salary block React state (untouched)
chk=page.evaluate(r"""
()=>{
  const ds=document.getElementById('desiredSalaryId');
  const ai=document.getElementById('add_info_select_box');
  let cv=null,vs=null,allFilled=null,reqOk=null;
  // find the container fiber with these props
  const root=document.querySelector('.qMainDiv')||document.body;
  const fk=Object.keys(root).find(k=>k.startsWith('__reactFiber'));
  // search whole tree from body for the props bag
  function findProps(){
    const el=document.getElementById('question_0')||document.body;
    const k=Object.keys(el).find(x=>x.startsWith('__reactFiber'));
    if(!k) return null; let f=el[k];
    for(let i=0;i<16&&f;i++){const mp=f.memoizedProps; if(mp&&('currencyValidation'in mp)){return mp;} f=f.return;}
    return null;
  }
  const mp=findProps();
  if(mp){cv=mp.currencyValidation; vs=mp.validState; allFilled=mp.allRequiredQuestionnaireFilled; reqOk=mp.requiredQuestionsValidation;}
  let aiSel=''; if(ai&&ai.shadowRoot){const s=ai.shadowRoot.querySelector('#selected-label,.selected-label'); aiSel=s?s.innerText.trim():'';}
  return {desiredSalaryVal:ds?ds.value:'NO-DS', aiSelected:aiSel, aiValue:ai?JSON.stringify(ai.value):'NO-AI', currencyValidation:cv, validState:vs, allFilled, reqOk};
}
""")
print("PRISTINE desired-salary state:", json.dumps(chk))
