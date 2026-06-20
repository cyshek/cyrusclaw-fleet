import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[:90])

# Check the attestation box (custom checkbox -> click label)
res=page.evaluate(r"""
()=>{
  const c=document.querySelector('input[name="self_att_agree_chk"]');
  if(!c) return 'notfound';
  if(c.checked) return 'already';
  let t=document.querySelector('label[for="'+c.id+'"]')||c.closest('label');
  if(t){t.click();}
  if(!c.checked){const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'checked').set; s.call(c,true); c.dispatchEvent(new Event('click',{bubbles:true})); c.dispatchEvent(new Event('change',{bubbles:true}));}
  return 'checked='+c.checked;
}
""")
print("attest:", res)
time.sleep(0.6)
print("attest verified:", page.evaluate("()=>document.querySelector('input[name=\"self_att_agree_chk\"]').checked"))

# capture URL before submit
before_url=page.url

sub=page.locator("button:has-text('Submit')").filter(visible=True).first
sub.scroll_into_view_if_needed(timeout=2000); sub.click(timeout=8000); print("clicked Submit")
# wait for confirmation / navigation
for i in range(10):
    time.sleep(2)
    d=page.evaluate(r"""
    ()=>{
      const body=document.body.innerText;
      return {
        url:location.href,
        submitted:/application (has been )?submitted|thank you for applying|successfully submitted|we(.|')ve received your application|application complete/i.test(body),
        title:(document.querySelector('h1,h2,h3')||{}).innerText||'',
        sample:body.replace(/\s+/g,' ').slice(0,400)
      };
    }
    """)
    if d["submitted"] or d["url"]!=before_url:
        print("POST-SUBMIT @%ds:"%((i+1)*2), json.dumps(d)[:700]); break
    if i==9:
        print("POST-SUBMIT (no change) :", json.dumps(d)[:700])
