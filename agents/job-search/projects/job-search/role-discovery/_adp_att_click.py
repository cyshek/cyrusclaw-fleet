import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[-45:])

def att_checked():
    return page.evaluate("()=>{const c=document.querySelector('input[name=\"self_att_agree_chk\"]');return c?c.checked:'NA';}")

print("before:", att_checked())
# Get fresh label coords and click via trusted mouse gesture
coords=page.evaluate(r"""
()=>{const d=document.getElementById('self_att_agree_chk'); const lbl=d?d.querySelector('label'):null; if(!lbl)return null; lbl.scrollIntoView({block:'center'}); const r=lbl.getBoundingClientRect(); return {x:r.x+8, y:r.y+r.height/2};}
""")
print("label coords:", coords)
if coords:
    page.mouse.click(coords["x"], coords["y"])
    time.sleep(0.7)
print("after mouse click:", att_checked())

# If still false, click the label text via Playwright locator with force (trusted)
if att_checked()!=True:
    lbl=page.locator('#self_att_agree_chk label').first
    try:
        lbl.click(timeout=3000, force=True); time.sleep(0.6)
    except Exception as e:
        print("force click exc:", str(e)[:60])
    print("after force label:", att_checked())

if att_checked()==True:
    before_url=page.url
    sub=page.locator("button:has-text('Submit')").filter(visible=True).first
    sub.scroll_into_view_if_needed(timeout=2000); sub.click(timeout=8000); print("clicked Submit")
    for i in range(12):
        time.sleep(2)
        d=page.evaluate(r"""
        ()=>{const body=document.body.innerText; return {url:location.href, submitted:/application (has been )?submitted|thank you for applying|successfully submitted|received your application|application complete|confirmation number|successfully applied/i.test(body), stillAttest:/Self Attestation is required/i.test(body), title:(document.querySelector('h1,h2,h3')||{}).innerText||'', sample:body.replace(/\s+/g,' ').slice(0,350)};}
        """)
        if d["submitted"] or d["url"]!=before_url or not d["stillAttest"]:
            print("POST-SUBMIT @%ds:"%((i+1)*2), json.dumps(d)[:750]); break
        if i==11: print("POST-SUBMIT no-change:", json.dumps(d)[:600])
else:
    print("ATTESTATION STILL NOT CHECKED — cannot submit")
