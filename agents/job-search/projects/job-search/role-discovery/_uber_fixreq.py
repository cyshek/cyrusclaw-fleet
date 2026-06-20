import sys, time
from playwright.sync_api import sync_playwright
job=sys.argv[1]
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp('http://127.0.0.1:18800')
page=None
for ctx in br.contexts:
    for p in ctx.pages:
        if f'/careers/apply/form/{job}' in p.url: page=p; break
    if page: break
if not page:
    print("NO PAGE"); sys.exit(2)

# 1) zipCode -> 98033
z=page.locator('input[name="zipCode"]').first
if z.count():
    z.fill("98033"); print("zip filled:", z.input_value())
else:
    print("NO ZIP FIELD")

# 2) disabilityAccomodation radio -> No
r=page.evaluate("""()=>{
  const norm=s=>(s||'').replace(/\s+/g,' ').trim().toLowerCase();
  const rs=[...document.querySelectorAll('input[name="disabilityAccomodation"]')];
  if(!rs.length) return 'NO_RADIOS';
  let t=rs.find(x=>norm(x.value)==='no')||rs.find(x=>norm(x.value).startsWith('no'));
  if(!t) return 'NO_OPT:'+rs.map(x=>x.value).join('|');
  t.scrollIntoView({block:'center'});
  const lbl=t.closest('label')||(t.id?document.querySelector('label[for="'+t.id+'"]'):null);
  (lbl||t).click(); if(!t.checked) t.click();
  return t.checked?'OK':'CLICKED_UNVERIFIED';
}""")
print("disabilityAccomodation ->", r)
time.sleep(0.5)
# verify both
chk=page.evaluate("""()=>{
  const z=document.querySelector('input[name="zipCode"]');
  const da=[...document.querySelectorAll('input[name="disabilityAccomodation"]')].find(x=>x.checked);
  const inv=[...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name||e.id||e.tagName);
  return JSON.stringify({zip:z?z.value:null, zipInvalid:z?z.getAttribute('aria-invalid'):null, disabAccom:da?da.value:null, stillInvalid:inv});
}""")
print("CHECK:", chk)
