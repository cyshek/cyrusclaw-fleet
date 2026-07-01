from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    # Find the Check Your Email page for cyshekari@gmail.com (not +keysight alias)
    check_pg = None
    for ctx in b.contexts:
        for pg in ctx.pages:
            url = pg.url or ""
            if "reset-password/request/hs-13178" in url:
                try:
                    txt = pg.frames[0].evaluate("()=>document.body.innerText.slice(0,200)")
                    if "cyshekari@gmail.com" in txt and "keysight" not in txt and "Check Your Email" in txt:
                        check_pg = pg
                        print("Found check-email page:", url[:60])
                        print("Text:", txt[:200])
                        break
                except:
                    pass
        if check_pg:
            break
    
    if check_pg:
        # Find and click Resend email
        resend = check_pg.frames[0].evaluate("""()=>{
            const btns = [...document.querySelectorAll('button,a')];
            const rb = btns.find(b => /resend/i.test(b.textContent||b.innerText||b.href||b.id||b.name||''));
            if (rb) { rb.click(); return {text: rb.textContent.trim(), clicked: true}; }
            return {clicked: false, available: btns.map(b=>(b.textContent||b.innerText||'').trim().slice(0,30)).filter(t=>t)};
        }""")
        print("Resend result:", resend)
        time.sleep(3)
        txt2 = check_pg.frames[0].evaluate("()=>document.body.innerText.slice(0,200)")
        print("After resend:", txt2[:150])
    else:
        print("No check-email page found for main email")
