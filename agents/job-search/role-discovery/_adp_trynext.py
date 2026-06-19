import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Q0 clean value
q0=page.locator("#question_0"); q0.click(timeout=2500); q0.press("Control+a"); q0.press("Delete")
page.keyboard.type("Not Applicable", delay=40); page.keyboard.press("Tab"); time.sleep(0.8)

# verify validState before clicking
vs=page.evaluate(r"""
()=>{const el=document.getElementById('question_0'); const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
for(let i=0;i<18&&f;i++){const m=f.memoizedProps; if(m&&('validState'in m)) return {validState:m.validState, allFilled:m.allRequiredQuestionnaireFilled}; f=f.return;} return null;}
""")
print("pre-Next validState:", json.dumps(vs))

loc=page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next"); time.sleep=5
time.sleep(6)
after=page.evaluate(r"""
()=>{
  const body=document.body.innerText;
  const stuck=/following questions/i.test(body)&&/Correct the information/i.test(body);
  const onSelfId=/Self-?Identification|Voluntary Self|veteran|disability status|gender|race\/ethnicity|ethnicity/i.test(body)&&!/following questions/i.test(body);
  const onReview=/Review Your Application/i.test(body)&&!/following questions/i.test(body);
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,5);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,5);
  return {stuck,onSelfId,onReview,headings:h,errs,sample:body.replace(/\s+/g,' ').slice(0,350)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1100])
