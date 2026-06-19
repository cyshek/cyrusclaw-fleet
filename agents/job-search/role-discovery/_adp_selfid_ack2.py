import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Check both required/decline checkboxes via React-aware click on the associated label/wrapper.
# These are custom checkboxes (input visually hidden) -> click the rendered label element.
res=page.evaluate(r"""
()=>{
  const log=[];
  ['disabilityStatusCheck','enthinicityAndRaceId'].forEach(nm=>{
    const c=document.querySelector('input[name="'+nm+'"]');
    if(!c){log.push(nm+':notfound');return;}
    if(c.checked){log.push(nm+':already');return;}
    // find the clickable rendered control: the label[for=id], or a styled sibling/ancestor
    let target=document.querySelector('label[for="'+c.id+'"]');
    if(!target){ // wrapping label
      target=c.closest('label');
    }
    if(!target){ // sibling span/div acting as checkbox UI
      target=c.parentElement&&c.parentElement.querySelector('span,.vdl-checkbox__box,.checkbox-label');
    }
    if(target){ target.click(); log.push(nm+':clicked-label checked='+c.checked); }
    else { c.click(); log.push(nm+':clicked-input checked='+c.checked); }
  });
  return log;
}
""")
print("check attempt:", json.dumps(res))
time.sleep(0.8)
final=page.evaluate("()=>['disabilityStatusCheck','enthinicityAndRaceId'].map(n=>{const c=document.querySelector('input[name=\"'+n+'\"]');return n+'='+(c?c.checked:'NA');})")
print("final checked:", final)

if not ("disabilityStatusCheck=True" in final):
    # force via native setter + events
    page.evaluate(r"""
    ()=>{const c=document.querySelector('input[name="disabilityStatusCheck"]'); if(c&&!c.checked){c.click(); if(!c.checked){const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'checked').set; s.call(c,true); c.dispatchEvent(new Event('click',{bubbles:true})); c.dispatchEvent(new Event('change',{bubbles:true}));}}}
    """)
    time.sleep(0.5)
    print("after force:", page.evaluate("()=>document.querySelector('input[name=\"disabilityStatusCheck\"]').checked"))

loc=page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next"); time.sleep(6)
after=page.evaluate(r"""
()=>{
  const body=document.body.innerText;
  const stillSelfId=/Gender\s*--Select One--/i.test(body);
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,5);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,5);
  return {stillSelfId,headings:h,errs,sample:body.replace(/\s+/g,' ').slice(0,500)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1200])
