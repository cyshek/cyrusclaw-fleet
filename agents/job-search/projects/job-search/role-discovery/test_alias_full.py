from playwright.sync_api import sync_playwright
import time, sys
sys.path.insert(0, "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
import twocaptcha_client as tc

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
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
        new_email = "cyshekari+ks2026c@gmail.com"
        fill = fr.evaluate("""(em)=>{
            const inp = document.querySelector('input#username,input[name=username]');
            if (!inp) return 'no-inp';
            const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
            d.set.call(inp, em); inp.dispatchEvent(new Event('input',{bubbles:true}));
            return 'ok:'+inp.value;
        }""", new_email)
        print("Fill:", fill)
        
        # Solve hCaptcha
        client = tc.TwoCaptchaClient(proxy="", timeout_s=300)
        print("Solving hCaptcha...")
        token = client.hcaptcha("ccfa5854-6bd6-4dd4-8d86-709a062e61ee", id_pg.url, is_invisible=False)
        if token:
            print(f"Token: {token[:30]}...")
            # Inject
            inject = fr.evaluate("""(tok)=>{
                let count=0;
                for (const sel of ['textarea[name=h-captcha-response]','textarea[name=g-recaptcha-response]','textarea[id^=h-captcha-response]']) {
                    for (const el of document.querySelectorAll(sel)) {
                        const d=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value');
                        d.set.call(el,tok); el.dispatchEvent(new Event('change',{bubbles:true})); count++;
                    }
                }
                const hid=document.querySelector('input[name=captcha]');
                if(hid) { const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value'); d.set.call(hid,tok); hid.dispatchEvent(new Event('change',{bubbles:true})); count++; }
                return {count};
            }""", token)
            print("Inject:", inject)
            # Click Continue
            cont = fr.evaluate("""()=>{
                const btn = document.querySelector('button[type=submit],button[name=action]');
                if (btn) { btn.click(); return 'clicked:'+btn.textContent.trim().slice(0,20); }
                return 'no-btn';
            }""")
            print("Continue:", cont)
            time.sleep(6)
            print("URL:", id_pg.url[:80])
            id_pg.screenshot(path="/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.icims-debug/alias-auth0-test.png")
            txt = fr.evaluate("()=>document.body.innerText.slice(0,300)")
            print("Body:", txt[:250])
        else:
            print("hCaptcha solve failed")
