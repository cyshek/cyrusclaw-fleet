import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Clear question_0 entirely (referral name should be empty when not referred)
q0=page.locator("#question_0"); q0.scroll_into_view_if_needed(timeout=2000); q0.click(timeout=2500)
q0.press("Control+a"); q0.press("Delete")
page.evaluate("()=>{const e=document.getElementById('question_0'); e.value=''; e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); e.dispatchEvent(new Event('blur',{bubbles:true}));}")
page.keyboard.press("Tab"); time.sleep(0.7)
s0=page.evaluate("()=>({v:document.getElementById('question_0').value, inv:document.getElementById('question_0').getAttribute('aria-invalid'), req:document.getElementById('question_0').getAttribute('aria-required')})")
print("Q0 after clear:", s0)

# Click Next, see if Q0 empty is accepted (maybe it's only required if referred)
loc=page.locator("button:has-text('Next')").filter(visible=True).first
loc.click(timeout=6000); print("clicked Next #1"); time.sleep(4)
mid=page.evaluate(r"""
()=>{
  const inv=[...document.querySelectorAll('[aria-invalid=true]')].filter(e=>e.offsetWidth>0).map(e=>({id:e.id,val:(e.value||'').slice(0,16)}));
  const eb=[...document.querySelectorAll('.qMainDiv .vdl-validation-error')].filter(e=>e.offsetWidth>0&&e.innerText.trim()).map(e=>{const l=(e.closest('.qMainDiv')||{}).querySelector?(e.closest('.qMainDiv').querySelector('label.qLabel')||{}).innerText:''; return {q:(l||'').slice(0,45),err:e.innerText.trim().slice(0,40)};});
  const stuck=/Correct the information/i.test(document.body.innerText)&&/following questions/i.test(document.body.innerText);
  const h=[...document.querySelectorAll('h2,h3')].map(x=>x.innerText.trim()).filter(t=>t&&t.length<60).slice(0,4);
  return {invalidNow:inv, fieldErrors:eb, stuck, headings:h};
}
""")
print("AFTER NEXT:", json.dumps(mid, indent=1)[:1100])
