import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

def q0_state():
    return page.evaluate(r"""
    ()=>{
      const el=document.getElementById('question_0');
      const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
      for(let i=0;i<18&&f;i++){const m=(f.alternate&&f.alternate.memoizedProps&&('additionalInformation'in f.alternate.memoizedProps))?f.alternate.memoizedProps:f.memoizedProps;
        if(m&&('additionalInformation'in m)){const ai=m.additionalInformation; return {inv:el.getAttribute('aria-invalid'), refInd:ai.applicantReferralIndicator, given:ai.applicantReferredBy&&ai.applicantReferredBy.personName?ai.applicantReferredBy.personName.givenName:'?', allFilled:m.allRequiredQuestionnaireFilled, validState:m.validState};}
        f=f.return;}
      return null;
    }
    """)

for val in ["Hiring Team", "John Smith", "Not Applicable"]:
    q0=page.locator("#question_0"); q0.click(timeout=2500); q0.press("Control+a"); q0.press("Delete")
    page.keyboard.type(val, delay=40); page.keyboard.press("Tab"); time.sleep(0.9)
    print("Q0=%r ->"%val, json.dumps(q0_state()))
