import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[-60:])

d=page.evaluate(r"""
()=>{
  const c=document.querySelector('input[name="self_att_agree_chk"]');
  const sub=[...document.querySelectorAll('button')].find(b=>/Submit/i.test(b.innerText)&&b.offsetWidth>0);
  const errs=[...document.querySelectorAll('[role=alert],.vdl-validation-error,.error-color')].map(e=>e.innerText.trim()).filter(t=>t&&t.length>2&&!/certify|Afghan|I understand/i.test(t)).slice(0,6);
  // check React state of attestation via fiber
  let attReact=null;
  if(c){const k=Object.keys(c).find(x=>x.startsWith('__reactFiber')); let f=c[k]; for(let i=0;i<12&&f;i++){const m=f.memoizedProps; if(m&&('checked'in m||'selfAttestAgree'in m||'isChecked'in m)){attReact={checked:m.checked,isChecked:m.isChecked};break;} f=f.return;}}
  return {
    attChecked:c?c.checked:'NA',
    attReact,
    submitDisabled:sub?sub.disabled:'no-btn',
    submitAria:sub?sub.getAttribute('aria-disabled'):null,
    errs
  };
}
""")
print("DIAG:", json.dumps(d, indent=1)[:900])

# The label-click may have toggled DOM but React's onChange didn't fire -> Submit sees unchecked in React.
# Re-check via the label's REAL playwright click (trusted gesture) so React onChange fires.
c=page.locator('input[name="self_att_agree_chk"]')
cid=c.first.get_attribute("id")
print("checkbox id:", cid)
# uncheck-recheck through a trusted label click
lbl=page.locator('label[for="%s"]'%cid)
print("label count:", lbl.count())
if lbl.count()>0:
    # toggle off (DOM is on) then on, via trusted clicks, to drive React
    lbl.first.click(timeout=3000); time.sleep(0.4)
    print("after click1 checked=", c.first.is_checked())
    if not c.first.is_checked():
        lbl.first.click(timeout=3000); time.sleep(0.4)
        print("after click2 checked=", c.first.is_checked())
