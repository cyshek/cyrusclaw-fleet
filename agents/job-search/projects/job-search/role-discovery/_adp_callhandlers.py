import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

res=page.evaluate(r"""
()=>{
  const el=document.getElementById('question_0')||document.body;
  const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
  let mp=null;
  for(let i=0;i<16&&f;i++){const m=f.memoizedProps; if(m&&('onDesiredSalaryValue'in m)){mp=m;break;} f=f.return;}
  if(!mp) return 'no-props-bag';
  const log=[];
  const usd={codeValue:'USD', label:'United States Dollar ( USD )', shortName:'SYS:5:420', value:'USD'};
  try{ mp.setRefferalIndicatorValue(false); log.push('referralIndicator=false'); }catch(e){log.push('refInd-err '+e.message);}
  try{ mp.onDesiredSalaryValue('150000'); log.push('salaryValue=150000'); }catch(e){log.push('salVal-err '+e.message);}
  try{ mp.onDesiredSalaryType({detail:{value:'Annually'}}); log.push('salaryType=Annually'); }catch(e){log.push('salType-err '+e.message);}
  try{ mp.onCurrencyChange({detail: usd}); log.push('currencyChange detail=usd'); }catch(e){log.push('curChg-err '+e.message);}
  try{ mp.onCurrencyValueChange(usd); log.push('currencyValueChange usd'); }catch(e){log.push('curValChg-err '+e.message);}
  return {log};
}
""")
print("handler calls:", json.dumps(res)[:600])
time.sleep(1.2)

chk=page.evaluate(r"""
()=>{
  const el=document.getElementById('question_0')||document.body;
  const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
  for(let i=0;i<16&&f;i++){const m=f.memoizedProps;
    if(m&&('currencyValidation'in m)) return {ctv:m.currencyTextValue, ct:m.currencyType, cv:m.currencyValidation, vs:m.validState, allFilled:m.allRequiredQuestionnaireFilled, refInd:JSON.stringify(m.additionalInformation).slice(0,80)};
    f=f.return;}
  return null;
}
""")
print("AFTER handlers:", json.dumps(chk))
