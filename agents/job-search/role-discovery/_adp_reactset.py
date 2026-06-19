import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

def react_currency_text_value():
    return page.evaluate(r"""
    ()=>{
      const el=document.getElementById('question_0')||document.body;
      const k=Object.keys(el).find(x=>x.startsWith('__reactFiber')); let f=el[k];
      for(let i=0;i<16&&f;i++){const m=f.memoizedProps; if(m&&('currencyTextValue'in m)) return {ctv:m.currencyTextValue, ct:m.currencyType, cv:m.currencyValidation, rq:m.requiredQuestionsValidation}; f=f.return;}
      return null;
    }
    """)

print("BEFORE:", react_currency_text_value())

# Use React's native-input-value-setter technique to fire onChange (onDesiredSalaryValue)
r=page.evaluate(r"""
()=>{
  const inp=document.getElementById('desiredSalaryId');
  if(!inp) return 'no-input';
  const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  setter.call(inp,'150000');
  inp.dispatchEvent(new Event('input',{bubbles:true}));
  inp.dispatchEvent(new Event('change',{bubbles:true}));
  inp.dispatchEvent(new Event('blur',{bubbles:true}));
  return 'fired react input on desiredSalaryId';
}
""")
print("salary react-set:", r)
time.sleep(0.8)
print("AFTER salary react-set:", react_currency_text_value())
