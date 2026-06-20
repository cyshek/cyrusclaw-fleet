import sys
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
JS=r"""
() => {
  const v=n=>{const e=document.querySelector('input[name="'+n+'"]')||document.querySelector('textarea[name="'+n+'"]'); return e?e.value:null;};
  const checked=nm=>{const t=[...document.querySelectorAll('input[name="'+nm+'"]')].find(x=>x.checked); return t?t.value:null;};
  const sub=document.querySelector('[role=combobox]#subsidiaryQuestion');
  const resumeOk=/successfully uploaded/i.test(document.body.innerText)|| /_v2/i.test(document.body.innerText);
  const sb=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.innerText));
  const errs=[...document.querySelectorAll('[role=alert]')].map(e=>(e.innerText||'').trim()).filter(Boolean);
  return JSON.stringify({
    firstName:v('firstName'),lastName:v('lastName'),phone:v('mobileNumber'),
    resumeUploaded:resumeOk,
    driver:checked('driverPartnerQuestion'),openRoles:checked('openRolesQuestion'),inUSA:checked('inUSA'),
    subsidiary:sub?sub.getAttribute('aria-label'):null,
    legalWork:checked('legalRightToWork'),sponsorship:checked('requireVisaSponsorship'),
    gender:checked('gender'),race:checked('race'),disability:checked('disability'),veteran:checked('veteran'),orient:checked('sexualOrientation'),
    arbitration:checked('arbitrationAgreement'),
    eduSchool:v('educations.0.schoolName'),eduDeg:v('educations.0.degree'),eduMajor:v('educations.0.fieldOfStudy'),
    eduSY:v('educations.0.startDate.year'),eduEY:v('educations.0.endDate.year'),
    submitDisabled:sb?sb.disabled:null, alerts:errs
  }, null, 1);
}
"""
print(page.evaluate(JS))
