from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:18800")
    for ctx in b.contexts:
        for pg in ctx.pages:
            url = pg.url or ""
            if "login.icims.com/u/login/identifier" in url:
                fr = pg.frames[0]
                txt = fr.evaluate("()=>document.body.innerText")
                print("URL:", url[:70])
                print("TEXT:", txt[:600])
                links = fr.evaluate("()=>[...document.querySelectorAll(chr(39)+chr(97)+chr(39))].map(el=>el.href)")
                for h in links: print("  HREF:", h[:80])
                break
