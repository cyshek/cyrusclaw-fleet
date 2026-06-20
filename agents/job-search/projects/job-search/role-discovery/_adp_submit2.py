import time, json
from playwright.sync_api import sync_playwright
CDP="http://127.0.0.1:18800"
pw=sync_playwright().start(); br=pw.chromium.connect_over_cdp(CDP); ctx=br.contexts[0]
page=[p for p in ctx.pages if "workforcenow.adp.com" in p.url][0]
print("url:", page.url[-40:])

# capture console + responses
msgs=[]
page.on("console", lambda m: msgs.append(("console", m.type, m.text[:120])))
resps=[]
def on_resp(r):
    try:
        u=r.url
        if "recruitment" in u or "applicant" in u or "apply" in u or "submit" in u.lower():
            resps.append((r.status, u[-70:]))
    except Exception: pass
page.on("response", on_resp)

def att_checked():
    return page.evaluate("()=>{const c=document.querySelector('input[name=\"self_att_agree_chk\"]');return c?c.checked:'NA';}")

# Re-check attestation via trusted mouse click on label
coords=page.evaluate(r"""()=>{const d=document.getElementById('self_att_agree_chk'); const lbl=d?d.querySelector('label'):null; if(!lbl)return null; lbl.scrollIntoView({block:'center'}); const r=lbl.getBoundingClientRect(); return {x:r.x+8, y:r.y+r.height/2};}""")
if att_checked()!=True and coords:
    page.mouse.click(coords["x"], coords["y"]); time.sleep(0.6)
print("att checked pre-submit:", att_checked())

# Inspect Submit button: tag, disabled, onclick presence, react props
sb=page.evaluate(r"""
()=>{const b=[...document.querySelectorAll('button')].find(x=>/^Submit$/i.test(x.innerText.trim())&&x.offsetWidth>0); if(!b)return 'no-submit'; const r=b.getBoundingClientRect(); return {disabled:b.disabled, aria:b.getAttribute('aria-disabled'), x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2), tag:b.tagName, cls:(b.className||'').slice(0,40)};}
""")
print("submit btn:", json.dumps(sb))

before_url=page.url
# Trusted mouse click on submit coords
if isinstance(sb, dict):
    page.mouse.click(sb["x"], sb["y"])
    print("mouse-clicked Submit at", sb["x"], sb["y"])
time.sleep(3)
# also try locator click as backup
still=page.evaluate("()=>/Self Attestation is required/i.test(document.body.innerText)")
print("still attest after mouse:", still)
if still:
    try:
        page.locator("button:has-text('Submit')").filter(visible=True).first.click(timeout=5000)
        print("locator-clicked Submit")
    except Exception as e:
        print("locator submit exc:", str(e)[:80])

for i in range(8):
    time.sleep(2)
    d=page.evaluate(r"""()=>{const body=document.body.innerText; return {url:location.href, submitted:/submitted|thank you for applying|successfully|received your application|confirmation/i.test(body), stillAttest:/Self Attestation is required/i.test(body), title:(document.querySelector('h1,h2,h3')||{}).innerText||''};}""")
    if d["submitted"] or d["url"]!=before_url or not d["stillAttest"]:
        print("RESULT @%ds:"%((i+1)*2), json.dumps(d)[:500]); break
    if i==7: print("RESULT no-change:", json.dumps(d)[:400])

print("--- console (last 6) ---")
for m in msgs[-6:]: print(m)
print("--- responses (last 8) ---")
for r in resps[-8:]: print(r)
