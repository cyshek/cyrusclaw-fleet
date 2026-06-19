import json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])
# read FRESH props by re-querying fiber (avoid stale memoizedProps: read from the CURRENT alternate)
st=page.evaluate(r"""
()=>{
  const el=document.getElementById('question_0')||document.body;
  const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
  // find the bag in BOTH fiber and its alternate (current committed tree)
  function findBag(node){
    let f=node;
    for(let i=0;i<18&&f;i++){const m=f.memoizedProps; if(m&&('currencyValidation'in m)) return m; f=f.return;}
    return null;
  }
  let mp=findBag(f);
  // prefer the alternate (current) if present
  let alt = el[k] && el[k].alternate ? findBag(el[k].alternate) : null;
  const pick = alt || mp;
  if(!pick) return null;
  return {
    currencyValidation:pick.currencyValidation, validState:pick.validState,
    requiredQuestionsValidation:pick.requiredQuestionsValidation,
    allRequiredQuestionnaireFilled:pick.allRequiredQuestionnaireFilled,
    currencyTextValue:pick.currencyTextValue, currencyType:pick.currencyType,
    additionalInformation:JSON.stringify(pick.additionalInformation),
    countAns:pick.countOfRequiredQuestionsAnswered, totalReq:pick.totalNumberOfRequiredQuestions,
    inValidQuestionAnswers:JSON.stringify(pick.inValidQuestionAnswers),
    questionAnswers:JSON.stringify(pick.questionAnswers).slice(0,260)
  };
}
""")
print(json.dumps(st, indent=2)[:1800] if st else "no bag")
# which field shows the error block
err=page.evaluate(r"""
()=>[...document.querySelectorAll('.qMainDiv .vdl-validation-error')].filter(e=>e.offsetWidth>0&&e.innerText.trim()).map(e=>{const b=e.closest('.qMainDiv'); const l=b?b.querySelector('label.qLabel,.qLabel,#desiredSalaryLabel'):null; return {q:(l?l.innerText:'').slice(0,50), err:e.innerText.trim().slice(0,40)};})
""")
print("FIELD ERRORS:", json.dumps(err))
