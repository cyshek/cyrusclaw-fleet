import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# 1) fill desired salary
ds=page.locator("#desiredSalaryId"); ds.scroll_into_view_if_needed(timeout=2000); ds.click(timeout=2500)
ds.press("Control+a"); ds.press("Delete"); page.keyboard.type("150000", delay=50); page.keyboard.press("Tab"); time.sleep(0.6)
print("desiredSalary:", page.evaluate("()=>document.getElementById('desiredSalaryId').value"))

# 2) set add_info_select_box currency via component property API (match q3 value shape) + openPicker fallback
res=page.evaluate(r"""
() => {
  const el=document.getElementById('add_info_select_box');
  if(!el) return 'no-el';
  const usd={codeValue:'USD', label:'United States Dollar ( USD )', shortName:'SYS:5:420', value:'USD'};
  const log=[];
  try {
    // set via property; SDF setter usually triggers internal state + emits sdfChange
    el.value = {value:'USD', label:'United States Dollar ( USD )'};
    log.push('set value obj');
  } catch(e){ log.push('value-set-err '+e.message); }
  try {
    const idx=(el.items||[]).findIndex(it=>it.value==='USD' || it.codeValue==='USD');
    if(idx>=0){ el.selectedIndex=idx; log.push('selectedIndex='+idx); }
  } catch(e){ log.push('idx-err '+e.message); }
  try { el.selectedValue='USD'; log.push('selectedValue=USD'); } catch(e){ log.push('selval-err '+e.message); }
  // fire events SDF/React listen for
  ['sdfChange','sdfInput','change','input'].forEach(ev=>{
    try{ el.dispatchEvent(new CustomEvent(ev,{bubbles:true, composed:true, detail:{value:'USD', label:'United States Dollar ( USD )'}})); }catch(e){}
  });
  // read back
  let sel=''; if(el.shadowRoot){const s=el.shadowRoot.querySelector('#selected-label,.selected-label,[part=selected-value]'); sel=s?s.innerText.trim():'';}
  return {log, valueAfter:JSON.stringify(el.value), selectedLabel:sel, selectedValue:JSON.stringify(el.selectedValue)};
}
""")
print("set currency result:", json.dumps(res)[:600])
time.sleep(1)

# Next
loc=page.locator("button:has-text('Next')").filter(visible=True).first
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next"); time.sleep(5)
after=page.evaluate(r"""
() => {
  const body=document.body.innerText;
  const stuck=/Please answer the following questions/i.test(body)&&/Correct the information/i.test(body);
  const onSelfId=/Self-?Identification|Voluntary Self|veteran|disability|gender|race|ethnicity/i.test(body)&&!/Please answer the following questions/i.test(body);
  const onReview=/Review Your Application/i.test(body)&&!/Please answer the following questions/i.test(body);
  const h=[...document.querySelectorAll('h1,h2,h3,h4')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<70).slice(0,6);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,6);
  return {stuck, onSelfId, onReview, headings:h, errs, sample:body.replace(/\s+/g,' ').slice(0,400)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1200])
