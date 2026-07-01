from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    # Find any identifier page
    id_pg = None
    for ctx in b.contexts:
        for pg in ctx.pages:
            if "login.icims.com/u/login/identifier" in (pg.url or ""):
                id_pg = pg; break
        if id_pg: break
    
    if not id_pg:
        print("No identifier page")
    else:
        fr = id_pg.frames[0]
        # Enter fresh alias email
        new_email = "cyshekari+ks2026b@gmail.com"
        fill = fr.evaluate("""(em)=>{
            const inp = document.querySelector('input#username,input[name=username]');
            if (!inp) return 'no-inp';
            const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
            d.set.call(inp, em); inp.dispatchEvent(new Event('input',{bubbles:true}));
            return 'ok:'+inp.value;
        }""", new_email)
        print("Fill:", fill)
        # Click Continue without solving hCaptcha
        cont = fr.evaluate("""()=>{
            const btn = document.querySelector('button[type=submit],button[name=action]');
            if (btn) { btn.click(); return 'clicked:'+btn.textContent.trim().slice(0,20); }
            return 'no-btn';
        }""")
        print("Continue:", cont)
        time.sleep(6)
        print("URL:", id_pg.url[:80])
        id_pg.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug/alias-test.png")
        txt = fr.evaluate("()=>document.body.innerText.slice(0,300)")
        print("Body:", txt[:200])
