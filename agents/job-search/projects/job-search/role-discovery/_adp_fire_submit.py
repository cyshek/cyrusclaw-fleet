import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[-40:])

resps=[]
page.on("response", lambda r: resps.append((r.status, r.request.method, r.url[-75:])) if any(k in r.url.lower() for k in ["submit","apply","recruitment","applicant","mdf"]) else None)
errs=[]
page.on("console", lambda m: errs.append((m.type, m.text[:140])) if m.type in ("error","warning") else None)

# ensure attest checked
ac=page.evaluate("()=>{const c=document.querySelector('input[name=\"self_att_agree_chk\"]');return c&&c.checked;}")
print("att checked:", ac)

# Invoke the Submit button's React onClick directly via fiber
r=page.evaluate(r"""
()=>{
  const b=[...document.querySelectorAll('button')].find(x=>/^Submit$/i.test(x.innerText.trim())&&x.offsetWidth>0);
  if(!b) return 'no-submit';
  const pk=Object.keys(b).find(k=>k.startsWith('__reactProps'));
  if(!pk) return 'no-props';
  try{ b[pk].onClick({preventDefault(){},stopPropagation(){},target:b,currentTarget:b}); return 'invoked onClick'; }
  catch(e){ return 'onClick err: '+e.message; }
}
""")
print("invoke submit:", r)

before_url=page.url
for i in range(12):
    time.sleep(2)
    d=page.evaluate(r"""()=>{
      const body=document.body.innerText;
      // search whole doc incl modals
      const allText=document.documentElement.innerText;
      return {url:location.href,
        submitted:/application (has been )?submitted|thank you for applying|successfully submitted|received your application|application complete|confirmation number|you have successfully applied|application was submitted/i.test(allText),
        stillAttest:/Self Attestation is required/i.test(body),
        modal:[...document.querySelectorAll('[role=dialog],.modal,.vdl-modal')].map(m=>m.innerText.trim().slice(0,80)).filter(Boolean).slice(0,2),
        title:(document.querySelector('h1,h2,h3')||{}).innerText||'',
        sample:allText.replace(/\s+/g,' ').slice(0,300)};
    }""")
    if d["submitted"] or d["url"]!=before_url or not d["stillAttest"] or d["modal"].__len__()>0:
        print("RESULT @%ds:"%((i+1)*2), json.dumps(d)[:700]); break
    if i==11: print("RESULT no-change:", json.dumps(d)[:500])

print("--- responses ---")
for x in resps[-10:]: print(x)
print("--- console err/warn ---")
for x in errs[-6:]: print(x)
