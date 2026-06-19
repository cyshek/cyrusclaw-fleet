import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Inspect the two checkbox labels (full text via associated label/sibling)
labels=page.evaluate(r"""
()=>{
  const out={};
  ['enthinicityAndRaceId','disabilityStatusCheck'].forEach(nm=>{
    const c=document.querySelector('input[name="'+nm+'"]');
    if(!c){out[nm]='not found';return;}
    let t=(c.closest('label')||{}).innerText||'';
    if(!t){const l=document.querySelector('label[for="'+c.id+'"]'); t=l?l.innerText:'';}
    if(!t){const p=c.parentElement; t=p?p.innerText:'';}
    out[nm]=(t||'').trim().slice(0,70);
  });
  return out;
}
""")
print("checkbox labels:", json.dumps(labels))

# Try Next with nothing selected (Self-ID is voluntary)
loc=page.locator("button:has-text('Next')").filter(visible=True).first
print("Next button present:", loc.count()>0)
loc.scroll_into_view_if_needed(timeout=2000); loc.click(timeout=6000); print("clicked Next"); time.sleep(6)
after=page.evaluate(r"""
()=>{
  const body=document.body.innerText;
  const stillSelfId=/Voluntary Self-?ID/i.test(body)&&/(--Select One--|decline to identify)/i.test(body)&&/Gender/i.test(body)&&!(/Review Your Application/i.test(body)&&/Self-Attest/i.test(body)&&/Edit/i.test(body));
  const onReview=/Review Your Application/i.test(body);
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,5);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/Afghan/i.test(t)).slice(0,5);
  return {stillSelfId,onReview,headings:h,errs,sample:body.replace(/\s+/g,' ').slice(0,450)};
}
""")
print("AFTER NEXT:", json.dumps(after, indent=1)[:1200])
